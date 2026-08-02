"""M6 — results, school → class → subject, across cycles (DASH3 §4.6).

`AssessmentCycle` already carries every type a school runs — `chapter_test`,
`class_test`, `slip_test`, `objective`, `band_test`, plus term exams — so "weekly
CET" versus "main exam" is a **filter, not a schema change**. `ExamService.feed`
and `AssessmentService.class_analysis` do this per class; this is the batched
org-wide version, in three grouped queries regardless of how many exams the year
holds.

Three honesty rules:

  * **Participation is shown next to every average.** An 88% average from 9 of 42
    students is not an 88% class, and a roll-up that hides the denominator would
    let a half-marked exam quietly lift the school figure.
  * **Nothing is pooled across `scale`** (V1-8, `S-114`/`Q-50`). Until V1-8 this
    module summed `tot_s / tot_x` over every cycle in scope, so *"Maths is at
    61%"* was the arithmetic mean of an April diagnostic, twelve slip tests and
    one final — a fact about nothing. Now **trajectory is drawn from `minor`**
    (frequent tests are what show movement) and **standing is read from
    `major`**, the two are returned separately, and every row-level `avg_pct` is
    computed within one bucket. `core/exams.py` owns what the words mean.
  * **Bands never appear** (P4). `band_test` cycles are included in the results
    roll-up as tests — they are real marks — but no tier, suggestion or band label
    is returned anywhere in this module.
"""

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exams import (
    MAJOR,
    MINOR,
    SCALE_LABELS,
    SCALE_PURPOSE,
    SCALES,
    normalise_scale,
    type_label,
)
from app.models import (
    AcademicYear,
    AssessmentCycle,
    AssessmentScore,
    ExamType,
    SchoolClass,
    Student,
    Subject,
)
from app.schemas.insights import (
    ExamBand,
    ExamRollup,
    ExamsBoard,
    ExamScopeRow,
    ExamTrend,
    ExamTrendPoint,
    ScaleFigure,
)
from app.services.school_clock import today_in


def _scale_acc() -> dict:
    """One accumulator per scope row: separate totals per scale, plus the id.
    `[score, max, exams, scored]` for each bucket."""
    acc: dict = {s: [0.0, 0.0, 0, 0] for s in SCALES}
    acc["id"] = None
    return acc


def _accumulate(acc: dict, scale: str, score: float, max_score: float,
                scored: int, row_id: object) -> None:
    acc[scale][0] += score
    acc[scale][1] += max_score
    acc[scale][2] += 1
    acc[scale][3] += scored
    acc["id"] = row_id


def _figure(scale: str, totals: list) -> ScaleFigure:
    return ScaleFigure(
        scale=scale, label=SCALE_LABELS[scale], purpose=SCALE_PURPOSE[scale],
        exams=totals[2], scored=totals[3],
        avg_pct=round(totals[0] / totals[1] * 100, 1) if totals[1] else None)

MAX_RECENT = 30
MAX_TREND_POINTS = 12
# Distribution buckets, low → high. Deliberately five and named, so the chart is
# readable without a legend of numbers.
BANDS = ((0, 35, "Below 35%"), (35, 50, "35–50%"), (50, 65, "50–65%"),
         (65, 80, "65–80%"), (80, 101, "80%+"))


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


def _headline(out: ExamsBoard) -> str:
    """§7 rule 3 — *"6-B Maths is the one class-subject worth a conversation."*

    Two rules this sentence has to survive:

    * **`S-114` never pool.** The figure quoted here comes from ONE bucket and
      the sentence names which — a number blended across a 5-mark slip test and
      an 80-mark final is a fact about nothing, and the headline is exactly
      where that blend would be most persuasive and least visible.
    * **`S-118` carry the denominator.** An 88% average over 9 of 42 students is
      not an 88% class, so participation rides along.

    "Worth a conversation" needs something to compare against: with one class
    there is no weakest, only the only. It says so rather than inventing a rank.
    """
    basis = out.standing if out.scale_basis == "major" else out.trajectory
    label = (basis.label if basis else out.scale_basis).lower()
    if basis is None or not basis.exams:
        return (f"{out.exams} {'exam' if out.exams == 1 else 'exams'} recorded, "
                "none scored yet.")

    lead = (f"{basis.avg_pct}% across {basis.exams} "
            f"{'test' if basis.exams == 1 else 'tests'} ({label})."
            if basis.avg_pct is not None else
            f"{basis.exams} {label} recorded, none scored yet.")

    # The weakest class-subject, but only when there is a field to be weakest in.
    rated = [r for r in out.by_class if r.avg_pct is not None and r.scored]
    if len(rated) > 1:
        worst = min(rated, key=lambda r: r.avg_pct)
        lead += (f" {worst.label} is the one worth a conversation — "
                 f"{worst.avg_pct}% across {worst.scored} scored.")
    elif len(rated) == 1:
        only = rated[0]
        lead += f" Only {only.label} has scored results so far ({only.avg_pct}%)."
    return lead


class ExamInsights:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return today_in(m.org.timezone)

    def _year(self, m: CurrentMember, year_id: uuid.UUID | None) -> AcademicYear | None:
        if year_id is not None:
            return self.db.scalar(select(AcademicYear).where(
                AcademicYear.id == year_id, AcademicYear.org_id == m.org_id))
        return self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == m.org_id, AcademicYear.is_active.is_(True)))

    def board(self, m: CurrentMember, year_id: uuid.UUID | None = None,
              type_filter: str | None = None,
              scale_filter: str | None = None) -> ExamsBoard:
        today = self._today(m)
        year = self._year(m, year_id)
        out = ExamsBoard(as_of=today, academic_year_id=year.id if year else None,
                         type_filter=type_filter, scale_filter=scale_filter)

        q = select(AssessmentCycle).where(AssessmentCycle.org_id == m.org_id)
        if year is not None:
            q = q.where(AssessmentCycle.date >= year.start_date,
                        AssessmentCycle.date <= year.end_date)
        cycles = list(self.db.scalars(q.order_by(AssessmentCycle.date.desc())))
        # The school's own words are what the filter offers and what every row
        # displays (`D-55`) — grouping by the system kind is what it replaced.
        type_names = dict(self.db.execute(
            select(ExamType.id, ExamType.name).where(ExamType.org_id == m.org_id)).all())
        out.types = sorted({type_names.get(c.exam_type_id) or type_label(c.type)
                            for c in cycles})
        if type_filter:
            cycles = [c for c in cycles
                      if (type_names.get(c.exam_type_id) or type_label(c.type)) == type_filter
                      or c.type == type_filter]
        if scale_filter in SCALES:
            cycles = [c for c in cycles if normalise_scale(c.scale, c.type) == scale_filter]
        if not cycles:
            out.headline = "No exams have been recorded for this year yet."
            return out

        cids = [c.id for c in cycles]
        agg = {
            cid: (int(n), float(s or 0), float(x or 0))
            for cid, n, s, x in self.db.execute(
                select(AssessmentScore.cycle_id,
                       func.count(func.distinct(AssessmentScore.student_id)),
                       func.sum(AssessmentScore.score),
                       func.sum(AssessmentScore.max_score))
                .where(AssessmentScore.cycle_id.in_(cids))
                .group_by(AssessmentScore.cycle_id)).all()
        }
        class_ids = {c.class_id for c in cycles if c.class_id}
        classes = {
            cid: _label(name, section) for cid, name, section in self.db.execute(
                select(SchoolClass.id, SchoolClass.name, SchoolClass.section)
                .where(SchoolClass.id.in_(class_ids))).all()
        } if class_ids else {}
        rosters = {
            cid: int(n) for cid, n in self.db.execute(
                select(Student.class_id, func.count(Student.id))
                .where(Student.org_id == m.org_id, Student.status == "active",
                       Student.class_id.in_(class_ids))
                .group_by(Student.class_id)).all()
        } if class_ids else {}
        subjects = {
            sid: name for sid, name in self.db.execute(
                select(Subject.id, Subject.name)
                .where(Subject.org_id == m.org_id)).all()
        }

        # Every accumulator is keyed by scale — there is no bucket in this
        # method that both a slip test and a term exam can land in (`S-114`).
        by_class: dict[str, dict] = defaultdict(_scale_acc)
        by_subject: dict[str, dict] = defaultdict(_scale_acc)
        trends: dict[str, dict[str, list[ExamTrendPoint]]] = defaultdict(
            lambda: {s: [] for s in SCALES})
        totals = {s: [0.0, 0.0, 0, 0] for s in SCALES}   # score, max, exams, scored
        cids_by_scale: dict[str, list] = {s: [] for s in SCALES}

        for c in cycles:
            scale = normalise_scale(c.scale, c.type)
            scored, s, x = agg.get(c.id, (0, 0.0, 0.0))
            avg = round(s / x * 100, 1) if x else None
            roster = (len(c.student_ids) if c.student_ids
                      else rosters.get(c.class_id, scored) if c.class_id else scored)
            out.exams += 1
            out.scored += scored
            totals[scale][0] += s
            totals[scale][1] += x
            totals[scale][2] += 1
            totals[scale][3] += scored
            cids_by_scale[scale].append(c.id)
            if len(out.recent) < MAX_RECENT:
                out.recent.append(ExamRollup(
                    cycle_id=c.id, name=c.name, type=c.type,
                    type_label=type_names.get(c.exam_type_id) or type_label(c.type),
                    scale=scale, locked=c.locked_at is not None, date=c.date,
                    class_id=c.class_id, class_label=classes.get(c.class_id),
                    subject_id=c.subject_id, subject_name=subjects.get(c.subject_id),
                    avg_pct=avg, scored=scored, roster=roster,
                    participation=round(scored / roster, 3) if roster else None))
            if avg is None:
                continue
            if c.class_id:
                _accumulate(by_class[classes.get(c.class_id, "?")], scale, s, x,
                            scored, c.class_id)
            if c.subject_id:
                name = subjects.get(c.subject_id, "?")
                _accumulate(by_subject[name], scale, s, x, scored, c.subject_id)
                trends[name][scale].append(
                    ExamTrendPoint(label=c.name, date=c.date, avg_pct=avg))

        out.standing = _figure(MAJOR, totals[MAJOR])
        out.trajectory = _figure(MINOR, totals[MINOR])
        # The basis: what the caller asked for, else major if the window holds
        # any major exams (that is what "how are they doing" means once a term
        # exam exists), else minor. It is **named** on the board, so a screen
        # can say which — a silent switch would be the defect this fixes.
        basis = (scale_filter if scale_filter in SCALES
                 else MAJOR if totals[MAJOR][2] else MINOR)
        out.scale_basis = basis
        out.avg_pct = (round(totals[basis][0] / totals[basis][1] * 100, 1)
                       if totals[basis][1] else None)
        out.by_class = self._scope(by_class, basis)
        out.by_subject = self._scope(by_subject, basis)
        # Trajectories come from minor tests — that is what frequent tests are
        # for. A school that runs only major exams still gets its line, from
        # major, and the board says so rather than drawing nothing.
        trend_scale = MINOR if any(v[MINOR] for v in trends.values()) else MAJOR
        out.trend_scale = trend_scale
        out.trends = [
            ExamTrend(key=name, label=name,
                      points=sorted(buckets[trend_scale], key=lambda p: p.date)[-MAX_TREND_POINTS:])
            for name, buckets in sorted(trends.items())
            if len(buckets[trend_scale]) > 1  # a single point is not a trajectory
        ]
        out.distribution = self._distribution(m, cids_by_scale[basis])
        out.headline = _headline(out)
        return out

    @staticmethod
    def _scope(bucket: dict, basis: str) -> list[ExamScopeRow]:
        rows = []
        for key, acc in bucket.items():
            per = {s: (round(acc[s][0] / acc[s][1] * 100, 1) if acc[s][1] else None)
                   for s in SCALES}
            rows.append(ExamScopeRow(
                key=key, id=acc["id"], label=key,
                exams=acc[basis][2], scored=acc[basis][3],
                avg_pct=per[basis],
                minor_pct=per[MINOR], minor_exams=acc[MINOR][2],
                major_pct=per[MAJOR], major_exams=acc[MAJOR][2]))
        rows.sort(key=lambda r: (-(r.avg_pct if r.avg_pct is not None else -1), r.label))
        return rows

    def _distribution(self, m: CurrentMember, cycle_ids: list[uuid.UUID]) -> list[ExamBand]:
        """Every mark in scope, bucketed — **in Postgres**.

        The CASE runs server-side and one row per bucket comes back, rather than
        every score in the year crossing a remote connection to be counted in
        Python. For a school with 40 exams that is the difference between five
        rows and forty thousand.
        """
        pct = AssessmentScore.score / AssessmentScore.max_score * 100
        bucket = case(
            *[(pct < hi, name) for _lo, hi, name in BANDS[:-1]],
            else_=BANDS[-1][2])
        rows = self.db.execute(
            select(bucket.label("bucket"), func.count(AssessmentScore.id))
            .where(AssessmentScore.org_id == m.org_id,
                   AssessmentScore.cycle_id.in_(cycle_ids),
                   AssessmentScore.max_score > 0)
            .group_by(bucket)).all()
        counts = {name: int(n) for name, n in rows}
        return [ExamBand(label=name, count=counts.get(name, 0)) for _lo, _hi, name in BANDS]
