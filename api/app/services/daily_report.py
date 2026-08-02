"""Daily report agent (V2-M6, SPRD2 §5.6) — the school's day, assembled + written.

Deterministic aggregation first (numbers never come from a model), then
`report_write` voices it. Runs from the org, not a request, so it builds a synthetic
admin context to reuse the module services (planner forecast, sessions). Idempotent:
`generate` upserts one row per (org, for_date) and never overwrites a `final` the
admin has annotated.

Ambiguity rules (unit-tested, §5.6 done-when):
  * attendance-without-log — a class had attendance but no lesson log,
  * log-without-attendance — a class was logged but attendance wasn't taken,
  * plan-red streak       — a class-subject is red on plan pace,
  * repeat absentee ≥3d   — a student absent 3+ of the last 5 days.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.models import (
    AcademicYear,
    CheckResult,
    ClassPeriod,
    ClassSubject,
    DailyCheck,
    DailyReport,
    HomeworkAssignment,
    HomeworkCheck,
    HomeworkResult,
    LessonLog,
    Membership,
    Organization,
    SchoolClass,
    Student,
    Subject,
    TimetableSlot,
    Transaction,
    User,
)
from app.schemas.reports_daily import DailyReportOut, ReportHighlights, ReportSection
from app.services.ai import report_summary, report_write
from app.services.ai.report import deterministic_summary
from app.services.attendance import day_absence_maps, is_day_absent
from app.services.calendar import day_lock
from app.services.planner import PlannerService
from app.services.sessions import SessionService

ABSENTEE_WINDOW_DAYS = 5
ABSENTEE_THRESHOLD = 3


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


class DailyReportService:
    def __init__(self, db: Session):
        self.db = db

    # ── context ──────────────────────────────────────────────────────────────
    def _synth_member(self, org: Organization) -> CurrentMember | None:
        """A synthetic admin context so jobs can reuse services that take a member.
        Only org scoping is used by those reads."""
        membership = self.db.scalar(
            select(Membership).where(
                Membership.org_id == org.id, Membership.org_role == "admin",
                Membership.status == "active").limit(1)
        ) or self.db.scalar(select(Membership).where(Membership.org_id == org.id).limit(1))
        if membership is None:
            return None
        user = self.db.get(User, membership.user_id)
        return CurrentMember(user=user, org=org, membership=membership)

    def _day_bounds(self, tz: str, d: date) -> tuple[datetime, datetime]:
        z = ZoneInfo(tz)
        start = datetime.combine(d, time.min, tzinfo=z)
        return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)

    def _class_labels(self, org_id: uuid.UUID) -> dict[uuid.UUID, str]:
        return {c.id: _label(c.name, c.section)
                for c in self.db.scalars(select(SchoolClass).where(SchoolClass.org_id == org_id))}

    def _cs_meta(self, org_id: uuid.UUID) -> dict[uuid.UUID, tuple[uuid.UUID, str]]:
        """class_subject_id → (class_id, "6-A Science")."""
        rows = self.db.execute(
            select(ClassSubject.id, ClassSubject.class_id, Subject.name, SchoolClass.name, SchoolClass.section)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .where(ClassSubject.org_id == org_id)
        ).all()
        return {csid: (cid, f"{_label(cn, sec)} {sname}") for csid, cid, sname, cn, sec in rows}

    def _today_slots(self, org_id: uuid.UUID, d: date) -> list[TimetableSlot]:
        return list(self.db.scalars(
            select(TimetableSlot).where(
                TimetableSlot.org_id == org_id, TimetableSlot.weekday == d.weekday(),
                TimetableSlot.effective_from <= d,
                or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > d),
            )))

    # ── ambiguity rules the SF-1/HW-1 capture made answerable (DASH3 §6) ──────
    def _staff_ambiguities(self, m: CurrentMember, d: date) -> list[str]:
        """Staff away with periods nobody is covering.

        Before SF-1 this could not be said at all. It goes in ambiguities rather
        than risks deliberately: the school may well have merged the classes and
        simply not told the app, so this is a "did we handle it?" not an
        accusation. Silent when staff attendance was never taken — an unmarked
        morning is not a full house, and it is also not evidence of absence.
        """
        from app.services.insights.attendance import AttendanceInsights  # noqa: PLC0415

        presence = AttendanceInsights(self.db).staff_presence(m, d)
        if not presence.marked:
            return []
        out: list[str] = []
        for a in presence.absentees:
            uncovered = a.periods_due - a.periods_covered
            if uncovered > 0:
                out.append(
                    f"{a.name} was away with {uncovered} period(s) uncovered — "
                    "was a substitute arranged?")
        return out

    def _homework_streak_ambiguities(self, m: CurrentMember) -> list[str]:
        """Students missing homework repeatedly. Named, because HW-1 finally can."""
        from app.services.homework import HomeworkService  # noqa: PLC0415

        rows = HomeworkService(self.db).overview(m).needs_attention[:3]
        return [
            f"{r.full_name} ({r.class_label}) has missed homework "
            f"{r.not_done + r.partial} time(s) recently — worth a word home."
            for r in rows
        ]

    # ── assembly ─────────────────────────────────────────────────────────────
    def _assemble(
        self, m: CurrentMember, d: date, *, include_fees: bool,
    ) -> tuple[list[tuple[str, list[str]]], dict[str, list[str]]]:
        org_id = m.org_id
        cs_meta = self._cs_meta(org_id)
        class_labels = self._class_labels(org_id)
        slots = self._today_slots(org_id, d)
        # V1-7 `S-145`: periods the school locked are not expected, so they
        # cannot be "not marked" or "not logged". Without this the report for
        # 15 August reads as the worst capture day of the year, and the
        # attendance-without-log ambiguity fires on every class in the school.
        lock = day_lock(self.db, org_id, d)
        if lock.closed:
            slots = []
        elif lock.periods:
            slots = [s for s in slots if s.period_no not in lock.periods]

        # Only ATTENDANCE-MARKED periods count as marked; a period opened but
        # never submitted is not a capture (V2-P6).
        marks = list(self.db.scalars(
            select(ClassPeriod).where(
                ClassPeriod.org_id == org_id, ClassPeriod.date == d,
                ClassPeriod.attendance_marked_at.is_not(None))
            .options(selectinload(ClassPeriod.exceptions))))
        marked_keys = {(mk.class_id, mk.period_no) for mk in marks}
        marked_cs: set[uuid.UUID] = {
            s.class_subject_id for s in slots if (s.class_id, s.period_no) in marked_keys}
        absences = sum(1 for mk in marks for e in mk.exceptions if e.status == "absent")
        lates = sum(1 for mk in marks for e in mk.exceptions if e.status == "late")
        unmarked = [s for s in slots if (s.class_id, s.period_no) not in marked_keys]

        logged_cs = set(self.db.scalars(
            select(LessonLog.class_subject_id).where(
                LessonLog.org_id == org_id, LessonLog.date == d)))
        timetabled_cs = {s.class_subject_id for s in slots}
        unlogged_cs = timetabled_cs - logged_cs

        # ── ambiguities ──
        ambiguities: list[str] = []
        for csid in sorted(marked_cs - logged_cs, key=lambda c: cs_meta.get(c, (None, ""))[1]):
            ambiguities.append(
                f"{cs_meta.get(csid, (None, '?'))[1]} had attendance but no lesson log — was it logged?")
        for csid in sorted((logged_cs & timetabled_cs) - marked_cs,
                           key=lambda c: cs_meta.get(c, (None, ""))[1]):
            ambiguities.append(
                f"{cs_meta.get(csid, (None, '?'))[1]} was logged but attendance wasn't taken.")
        ambiguities.extend(self._staff_ambiguities(m, d))
        ambiguities.extend(self._homework_streak_ambiguities(m))

        # ── sections ──
        att_lines = [f"{len(marked_keys)} of {len(slots)} periods marked · "
                     f"{absences} absent · {lates} late"]
        if unmarked:
            names = sorted({class_labels.get(s.class_id, "?") for s in unmarked})
            att_lines.append(f"{len(unmarked)} period(s) not marked: {', '.join(names[:6])}")

        teach_lines = [f"{len(logged_cs & timetabled_cs)} of {len(timetabled_cs)} timetabled classes logged"]
        if unlogged_cs:
            labels = sorted(cs_meta.get(c, (None, "?"))[1] for c in unlogged_cs)
            teach_lines.append(f"Not logged: {', '.join(labels[:6])}")

        hw_given = self.db.scalar(select(func.count(HomeworkAssignment.id)).where(
            HomeworkAssignment.org_id == org_id, HomeworkAssignment.date == d)) or 0
        start_utc, end_utc = self._day_bounds(m.org.timezone, d)
        hw_checked = self.db.scalar(select(func.count(HomeworkCheck.id)).where(
            HomeworkCheck.org_id == org_id, HomeworkCheck.checked_at >= start_utc,
            HomeworkCheck.checked_at < end_utc)) or 0
        hw_lines = [f"{hw_given} homework set · {hw_checked} check(s) recorded"]
        # Who actually didn't do it, now that we know (HW-1). Counted across
        # today's checks so the report says something a count never could.
        hw_missed = self.db.scalar(
            select(func.count(HomeworkResult.id))
            .join(HomeworkCheck, HomeworkCheck.id == HomeworkResult.check_id)
            .where(HomeworkResult.org_id == org_id,
                   HomeworkCheck.checked_at >= start_utc,
                   HomeworkCheck.checked_at < end_utc)) or 0
        if hw_checked:
            hw_lines.append(
                f"{hw_missed} student(s) hadn't done it" if hw_missed
                else "Everyone who was checked had done it")
        # Homework past its deadline that nobody has gone through. A missing check
        # is the teacher's gap, and saying nothing lets it accumulate silently.
        hw_unchecked = self.db.scalar(
            select(func.count(HomeworkAssignment.id))
            .outerjoin(HomeworkCheck, HomeworkCheck.assignment_id == HomeworkAssignment.id)
            .where(HomeworkAssignment.org_id == org_id, HomeworkCheck.id.is_(None),
                   func.coalesce(HomeworkAssignment.due_date, HomeworkAssignment.date) < d,
                   HomeworkAssignment.date >= d - timedelta(days=14))) or 0
        if hw_unchecked:
            hw_lines.append(f"{hw_unchecked} past homework still unchecked")

        confirmed = self.db.scalar(select(func.count(DailyCheck.id)).where(
            DailyCheck.org_id == org_id, DailyCheck.date == d,
            DailyCheck.confirmed_at.isnot(None))) or 0
        not_done = self.db.scalar(
            select(func.count(CheckResult.id))
            .join(DailyCheck, DailyCheck.id == CheckResult.check_id)
            .where(CheckResult.org_id == org_id, DailyCheck.date == d,
                   CheckResult.status == "not_done")) or 0
        check_lines = [f"{confirmed} check(s) confirmed · {not_done} student flag(s)"]

        sessions = SessionService(self.db).records(m, on_date=d)
        attended = sum(s.present + s.late for s in sessions)
        sess_lines = [f"{len(sessions)} session(s) run · {attended} attended"] if sessions else []

        # plan pace via forecast (reuse planner)
        red: list[str] = []
        amber: list[str] = []
        year = self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == org_id, AcademicYear.is_active.is_(True)))
        if year is not None:
            planner = PlannerService(self.db)
            for cid in self.db.scalars(select(SchoolClass.id).where(
                    SchoolClass.org_id == org_id, SchoolClass.academic_year_id == year.id)):
                for r in planner.forecast(m, cid):
                    if r.status == "red":
                        red.append(f"{r.class_label} {r.subject_name} — {r.weeks_behind}w behind plan")
                    elif r.status == "amber":
                        amber.append(f"{r.class_label} {r.subject_name} — slipping")
        pace_lines = [*[f"🔴 {x}" for x in red], *[f"🟠 {x}" for x in amber]] or ["All classes on pace"]

        sections: list[tuple[str, list[str]]] = [
            ("Attendance", att_lines),
            ("Teaching", teach_lines),
            ("Homework", hw_lines),
            ("Checks", check_lines),
        ]
        if sessions:
            sections.append(("After-school sessions", sess_lines))
        sections.append(("Plan pace", pace_lines))

        # fees (admin section only, §3.3)
        if include_fees:
            collected = self.db.scalar(select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.org_id == org_id, Transaction.type == "payment",
                Transaction.created_at >= start_utc, Transaction.created_at < end_utc)) or 0
            sections.append(("Fees", [f"₹{collected:,.0f} collected today"]))

        # ── repeat absentees (≥3 of last 5 days) ──
        # V1-0d: reads the SAME day-absence maps as the streaks board (ux §9).
        # The old query counted any day with any absent exception, so a child
        # who came in late twice could be reported as a repeat absentee.
        win_start = d - timedelta(days=ABSENTEE_WINDOW_DAYS - 1)
        marked_by_class, absents_by_student = day_absence_maps(
            self.db, org_id, win_start, d)
        repeat_absentees: list[str] = []
        if absents_by_student:
            info = {
                sid: (name, cid) for sid, name, cid in self.db.execute(
                    select(Student.id, Student.full_name, Student.class_id)
                    .where(Student.org_id == org_id, Student.status == "active",
                           Student.id.in_(absents_by_student.keys()))).all()
            }
            for sid, days in absents_by_student.items():
                name, cid = info.get(sid, (None, None))
                if name is None or cid is None:
                    continue
                n = sum(1 for day, n_absent in days.items()
                        if is_day_absent(marked_by_class.get((cid, day), 0), n_absent))
                if n >= ABSENTEE_THRESHOLD:
                    repeat_absentees.append(
                        f"{name} absent {n} of last {ABSENTEE_WINDOW_DAYS} days")
            repeat_absentees.sort()

        # ── highlights ──
        risks = [f"{x}" for x in red] + repeat_absentees
        if len(unlogged_cs) >= max(2, len(timetabled_cs) // 2) and timetabled_cs:
            risks.append(f"{len(unlogged_cs)} classes still unlogged")
        wins: list[str] = []
        if sessions:
            wins.append(f"{len(sessions)} session(s) run · {attended} attended")
        greens = len(timetabled_cs) - len(unlogged_cs)
        if greens > 0 and not unlogged_cs:
            wins.append("Every timetabled class logged today ✓")
        highlights = {"risks": risks, "ambiguities": ambiguities, "wins": wins}
        return sections, highlights

    # ── generate (upsert) ────────────────────────────────────────────────────
    def generate(self, org: Organization, for_date: date, *, only_if_draft: bool = False,
                 include_fees: bool = True) -> DailyReport | None:
        existing = self.db.scalar(
            select(DailyReport).where(
                DailyReport.org_id == org.id, DailyReport.for_date == for_date))
        if existing is not None and existing.status == "final":
            return existing  # never overwrite an annotated final
        if only_if_draft and existing is None:
            return None
        m = self._synth_member(org)
        if m is None:
            return existing
        sections, highlights = self._assemble(m, for_date, include_fees=include_fees)
        source, content_md = report_write(
            org.name, for_date.isoformat(), sections, highlights)
        # The headline is written once, at generate time, and stored — the dashboard
        # must not pay for a model round-trip on every load.
        summary_source, summary = report_summary(
            org.name, for_date.isoformat(), sections, highlights)
        stored = {
            **highlights,
            "summary": summary,
            "summary_source": summary_source,
            "sections": [{"heading": h, "lines": ls} for h, ls in sections],
        }
        if existing is None:
            existing = DailyReport(org_id=org.id, for_date=for_date)
            self.db.add(existing)
        existing.content_md = content_md
        existing.highlights = stored
        existing.generated_at = datetime.now(UTC)
        existing.status = "draft"
        self.db.flush()
        return existing

    # ── endpoint: get-or-create for the admin's org ──────────────────────────
    def get_or_create(self, m: CurrentMember, on_date: date | None = None) -> DailyReportOut:
        d = on_date or datetime.now(ZoneInfo(m.org.timezone)).date()
        report = self.db.scalar(
            select(DailyReport).where(DailyReport.org_id == m.org_id, DailyReport.for_date == d))
        if report is None:
            report = self.generate(m.org, d, include_fees=m.is_admin)
        return self._to_out(report)

    def _to_out(self, report: DailyReport) -> DailyReportOut:
        h = report.highlights or {}
        sections = [ReportSection(heading=s["heading"], lines=s.get("lines", []))
                    for s in h.get("sections", [])]
        summary = h.get("summary", "")
        if not summary:
            # A row written before the briefing existed. Compose the headline from
            # what was stored rather than showing an empty card — deterministic, so
            # this costs nothing and never calls a model on a read path.
            summary = deterministic_summary(
                [(s.heading, s.lines) for s in sections],
                {k: h.get(k, []) for k in ("risks", "ambiguities", "wins")})
        return DailyReportOut(
            id=report.id, for_date=report.for_date, generated_at=report.generated_at,
            status=report.status, content_md=report.content_md,
            highlights=ReportHighlights(
                risks=h.get("risks", []), ambiguities=h.get("ambiguities", []),
                wins=h.get("wins", []), summary=summary,
                summary_source=h.get("summary_source", "fixture")),
            sections=sections)
