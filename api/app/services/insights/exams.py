"""M6 — results, school → class → subject, across cycles (DASH3 §4.6).

`AssessmentCycle` already carries every type a school runs — `chapter_test`,
`class_test`, `slip_test`, `objective`, `band_test`, plus term exams — so "weekly
CET" versus "main exam" is a **filter, not a schema change**. `ExamService.feed`
and `AssessmentService.class_analysis` do this per class; this is the batched
org-wide version, in three grouped queries regardless of how many exams the year
holds.

Two honesty rules:

  * **Participation is shown next to every average.** An 88% average from 9 of 42
    students is not an 88% class, and a roll-up that hides the denominator would
    let a half-marked exam quietly lift the school figure.
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
from app.models import (
    AcademicYear,
    AssessmentCycle,
    AssessmentScore,
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
)
from app.services.school_clock import today_in

MAX_RECENT = 30
MAX_TREND_POINTS = 12
# Distribution buckets, low → high. Deliberately five and named, so the chart is
# readable without a legend of numbers.
BANDS = ((0, 35, "Below 35%"), (35, 50, "35–50%"), (50, 65, "50–65%"),
         (65, 80, "65–80%"), (80, 101, "80%+"))


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


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
              type_filter: str | None = None) -> ExamsBoard:
        today = self._today(m)
        year = self._year(m, year_id)
        out = ExamsBoard(as_of=today, academic_year_id=year.id if year else None,
                         type_filter=type_filter)

        q = select(AssessmentCycle).where(AssessmentCycle.org_id == m.org_id)
        if year is not None:
            q = q.where(AssessmentCycle.date >= year.start_date,
                        AssessmentCycle.date <= year.end_date)
        cycles = list(self.db.scalars(q.order_by(AssessmentCycle.date.desc())))
        out.types = sorted({c.type for c in cycles})
        if type_filter:
            cycles = [c for c in cycles if c.type == type_filter]
        if not cycles:
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

        by_class: dict[str, list] = defaultdict(lambda: [0, 0, 0.0, 0.0, None])
        by_subject: dict[str, list] = defaultdict(lambda: [0, 0, 0.0, 0.0, None])
        trends: dict[str, list[ExamTrendPoint]] = defaultdict(list)
        tot_s = tot_x = 0.0
        scored_total = 0

        for c in cycles:
            scored, s, x = agg.get(c.id, (0, 0.0, 0.0))
            avg = round(s / x * 100, 1) if x else None
            roster = (len(c.student_ids) if c.student_ids
                      else rosters.get(c.class_id, scored) if c.class_id else scored)
            out.exams += 1
            scored_total += scored
            tot_s += s
            tot_x += x
            if len(out.recent) < MAX_RECENT:
                out.recent.append(ExamRollup(
                    cycle_id=c.id, name=c.name, type=c.type, date=c.date,
                    class_id=c.class_id, class_label=classes.get(c.class_id),
                    subject_id=c.subject_id, subject_name=subjects.get(c.subject_id),
                    avg_pct=avg, scored=scored, roster=roster,
                    participation=round(scored / roster, 3) if roster else None))
            if avg is None:
                continue
            if c.class_id:
                acc = by_class[classes.get(c.class_id, "?")]
                acc[0] += 1
                acc[1] += scored
                acc[2] += s
                acc[3] += x
                acc[4] = c.class_id
            if c.subject_id:
                name = subjects.get(c.subject_id, "?")
                acc = by_subject[name]
                acc[0] += 1
                acc[1] += scored
                acc[2] += s
                acc[3] += x
                acc[4] = c.subject_id
                trends[name].append(ExamTrendPoint(label=c.name, date=c.date, avg_pct=avg))

        out.scored = scored_total
        out.avg_pct = round(tot_s / tot_x * 100, 1) if tot_x else None
        out.by_class = self._scope(by_class)
        out.by_subject = self._scope(by_subject)
        out.trends = [
            ExamTrend(key=name, label=name,
                      points=sorted(points, key=lambda p: p.date)[-MAX_TREND_POINTS:])
            for name, points in sorted(trends.items())
            if len(points) > 1  # a single point is not a trajectory
        ]
        out.distribution = self._distribution(m, cids)
        return out

    @staticmethod
    def _scope(bucket: dict) -> list[ExamScopeRow]:
        rows = [
            ExamScopeRow(key=key, id=v[4], label=key, exams=v[0], scored=v[1],
                         avg_pct=round(v[2] / v[3] * 100, 1) if v[3] else None)
            for key, v in bucket.items()
        ]
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
