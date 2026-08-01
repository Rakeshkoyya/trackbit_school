"""The overview — one block per module, and the rail of what is waiting.

The admin opens this page without a question in mind. Its job is to give them
one, and to make opening a tab a decision rather than a search. Three rules keep
it honest:

  * **Two or three figures per module, never one and never six.** A single
    number ("78%") is unreadable without its denominator; six turn the overview
    into the tab it was supposed to summarise.
  * **Every section carries names.** "3 periods uncovered" sends the admin
    looking; "Priya away — 3 periods, none covered" does not. This is the same
    rule the modules follow (DASH3), applied to the summary.
  * **Not captured is never captured-as-zero.** An unmarked morning reads as
    "nothing marked yet", never as 0% present or a full house; unchecked
    homework is excluded from completion rather than counted as missed.

Deliberately cheap: every figure is taken from a roll-up a module already
computes, so the overview never grows a second set of numbers that could
disagree with the tab it links to. The boards it calls are the batched ones, and
it runs them once per page load — not once per figure.
"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.schemas.insights import (
    OverviewBoard,
    OverviewMetric,
    OverviewNote,
    OverviewSection,
    QuickAction,
)
from app.services.insights.attendance import AttendanceInsights
from app.services.insights.exams import ExamInsights
from app.services.insights.homework import HomeworkInsights
from app.services.insights.tasks import TaskInsights
from app.services.insights.workload import WorkloadInsights
from app.services.school_clock import today_in

# Tone order, worst first — a section wears the worst tone of its metrics, so a
# green section is a real all-clear.
_RANK = {"red": 3, "amber": 2, "green": 1, "neutral": 0}
MAX_NOTES = 3
MAX_ACTIONS = 6


def _tone(pct: float | None, good: float, fair: float) -> str:
    if pct is None:
        return "neutral"
    return "green" if pct >= good else "amber" if pct >= fair else "red"


def _worst(*tones: str) -> str:
    return max(tones, key=lambda t: _RANK.get(t, 0)) if tones else "neutral"


def _plural(n: int, one: str, many: str | None = None) -> str:
    return one if n == 1 else (many or one + "s")


class OverviewService:
    def __init__(self, db: Session):
        self.db = db

    def board(self, m: CurrentMember, year_id: uuid.UUID | None = None) -> OverviewBoard:
        from app.services.dashboard import DashboardService  # noqa: PLC0415

        today: date = today_in(m.org.timezone)
        ds = DashboardService(self.db)
        year = ds._year(m, year_id)
        yid = year.id if year else None

        # One read of each module's roll-up. `AttendanceInsights.board` would
        # recompute the streak walk, so the pieces are taken directly instead.
        att = AttendanceInsights(self.db)
        pulse = ds.attendance_pulse(m, year.id) if year else None
        capture = att.capture_grid(m, today, yid)
        presence = att.staff_presence(m, today)
        streaks = att.streaks(m, year_id=yid)
        workload = WorkloadInsights(self.db)
        now = workload.now(m)
        leave = workload._leave_pulse(m, today)
        homework = HomeworkInsights(self.db).board(m)
        tasks = TaskInsights(self.db).board(m)
        rag = ds._rag_rows(m, year.id) if year else []
        exams = ExamInsights(self.db).board(m, yid)

        out = OverviewBoard(
            date=today, phase=now.phase, period_no=now.period_no,
            period_label=self._period_label(now))
        out.sections = [
            self._attendance(pulse, capture, streaks),
            self._staff(presence, leave, now),
            self._syllabus(rag),
            self._homework(homework),
            self._tasks(tasks),
            self._exams(exams),
        ]
        out.actions = self._actions(capture, presence, leave, streaks, homework,
                                    tasks, rag, now)
        return out

    # ── the school clock ─────────────────────────────────────────────────────
    @staticmethod
    def _period_label(now) -> str | None:
        if now.phase == "period" and now.period_no:
            window = f" · {now.period_start}–{now.period_end}" if now.period_start else ""
            return f"Period {now.period_no}{window}"
        return {
            "break": "Break", "before": "Before school", "after": "After school",
            "holiday": "School closed", "unset": None,
        }.get(now.phase)

    # ── M1 attendance ────────────────────────────────────────────────────────
    def _attendance(self, pulse, capture, streaks) -> OverviewSection:
        today = pulse.today if pulse else None
        present = today.present_pct if today else None
        pending = max(0, capture.expected - capture.marked)
        streak_n = len(streaks.rows)

        present_tone = _tone(present, 90, 80)
        # Nothing marked yet is a capture state, not a bad day — it must never
        # render red, or every morning opens on a red board.
        capture_tone = ("neutral" if not capture.expected
                        else "green" if not pending
                        else "amber" if capture.marked else "neutral")
        streak_tone = "red" if streak_n else "green"

        metrics = [
            OverviewMetric(
                key="present", label="Present today",
                value=f"{present}%" if present is not None else "—",
                sub=(f"{today.absent} absent · {today.late} late" if today
                     else "no period marked yet"),
                tone=present_tone, href="/dashboard/attendance",
                spark=[d.present_pct for d in (pulse.days if pulse else [])]),
            OverviewMetric(
                key="capture", label="Periods captured",
                value=(f"{capture.marked}/{capture.expected}" if capture.expected
                       else str(capture.marked)),
                sub=("no timetable runs today" if not capture.expected
                     else "the whole timetable is in" if not pending
                     else f"{pending} still to mark"),
                tone=capture_tone, href="/dashboard/attendance"),
            OverviewMetric(
                key="streaks", label=f"Absent {streaks.min_days}+ days",
                value=str(streak_n),
                sub=("nobody on a run of absences" if not streak_n
                     else f"{_plural(streak_n, 'student')} running"),
                tone=streak_tone, href="/dashboard/attendance"),
        ]

        notes = [
            OverviewNote(
                text=(f"{r.full_name}"
                      + (f" ({r.class_label})" if r.class_label else "")
                      + f" — absent {r.streak} days"),
                tone="red", href=f"/students/{r.student_id}")
            for r in streaks.rows[:MAX_NOTES]
        ]
        if len(notes) < MAX_NOTES:
            for row in capture.rows:
                gap = sum(1 for c in row.cells if c.state == "pending")
                if gap:
                    notes.append(OverviewNote(
                        text=f"{row.class_label} — {gap} {_plural(gap, 'period')} unmarked",
                        tone="amber", href="/dashboard/attendance"))
                if len(notes) >= MAX_NOTES:
                    break

        if not capture.expected:
            headline = "No timetable runs today."
        elif not capture.marked:
            headline = f"Nothing marked yet — {capture.expected} periods are due."
        elif present is None:
            headline = f"{capture.marked} of {capture.expected} periods captured."
        else:
            headline = (f"{present}% present across {capture.marked} of "
                        f"{capture.expected} periods.")

        return OverviewSection(
            key="attendance", label="Attendance", href="/dashboard/attendance",
            headline=headline, metrics=metrics, notes=notes,
            tone=_worst(present_tone, capture_tone, streak_tone))

    # ── M3 staff ─────────────────────────────────────────────────────────────
    def _staff(self, presence, leave, now) -> OverviewSection:
        uncovered = sum(max(0, a.periods_due - a.periods_covered)
                        for a in presence.absentees)
        presence_tone = ("neutral" if not presence.marked
                         else "red" if presence.absent > 2
                         else "amber" if presence.absent else "green")
        cover_tone = "red" if uncovered else "green"
        leave_tone = "amber" if leave.pending else "green"

        metrics = [
            OverviewMetric(
                key="present", label="In today",
                value=(f"{presence.present}/{presence.total}" if presence.marked
                       else "not marked"),
                sub=(f"{presence.absent} away · {presence.on_leave} on leave"
                     if presence.marked else "nobody has taken staff attendance"),
                tone=presence_tone, href="/staff"),
            OverviewMetric(
                key="uncovered", label="Periods uncovered", value=str(uncovered),
                sub=("every absent teacher's class has cover" if not uncovered
                     else "classes with nobody assigned"),
                tone=cover_tone, href="/dashboard/staff"),
            OverviewMetric(
                key="leave", label="Leave waiting", value=str(leave.pending),
                sub=(f"{leave.on_leave_today} on leave today" if leave.on_leave_today
                     else "no application waiting"),
                tone=leave_tone, href="/staff/leave"),
        ]

        notes = [
            OverviewNote(
                text=(f"{a.name} away"
                      + (f" — {a.reason}" if a.reason else "")
                      + (f" · {a.periods_due - a.periods_covered} of {a.periods_due} "
                         f"{_plural(a.periods_due, 'period')} uncovered"
                         if a.periods_due else "")),
                tone="red" if a.periods_due > a.periods_covered else "amber",
                href="/dashboard/staff")
            for a in presence.absentees[:MAX_NOTES]
        ]
        for r in leave.queue[: max(0, MAX_NOTES - len(notes))]:
            notes.append(OverviewNote(
                text=(f"{r.member_name} — {r.days} {_plural(r.days, 'day')} leave "
                      f"from {r.start_date:%d %b}"
                      + (f" · {r.warnings[0]}" if r.warnings else "")),
                tone="amber", href="/staff/leave"))

        if now.phase == "period" and now.period_no:
            headline = (f"Period {now.period_no} — {len(now.teaching)} teaching, "
                        f"{len(now.free)} free, {len(now.absent)} away.")
        elif now.phase == "holiday":
            headline = "School is closed today."
        elif not presence.marked:
            headline = "Staff attendance has not been taken today."
        elif presence.absent:
            headline = (f"{presence.absent} of {presence.total} staff away"
                        + (f", {uncovered} {_plural(uncovered, 'period')} uncovered."
                           if uncovered else ", every class covered."))
        else:
            headline = "Everyone is in today."

        return OverviewSection(
            key="staff", label="Staff & cover", href="/dashboard/staff",
            headline=headline, metrics=metrics, notes=notes,
            tone=_worst(presence_tone, cover_tone, leave_tone))

    # ── M2 syllabus ──────────────────────────────────────────────────────────
    def _syllabus(self, rag) -> OverviewSection:
        rated = [r for r in rag if r.status in ("green", "amber", "red")]
        on_track = sum(1 for r in rated if r.status == "green")
        behind = sum(1 for r in rated if r.status == "red")
        slipping = sum(1 for r in rated if r.status == "amber")
        unplanned = sum(1 for r in rag if r.status == "unplanned")
        unsized = sum(r.unestimated_topics for r in rag)
        pct = round(on_track / len(rated) * 100) if rated else None

        pace_tone = _tone(pct, 80, 60)
        behind_tone = "red" if behind else "amber" if slipping else "green"

        metrics = [
            OverviewMetric(
                key="pace", label="On track", value=f"{pct}%" if pct is not None else "—",
                sub=(f"{on_track} of {len(rated)} class-subjects" if rated
                     else "no plan has been approved yet"),
                tone=pace_tone, href="/dashboard/syllabus"),
            OverviewMetric(
                key="behind", label="Behind plan", value=str(behind),
                sub=(f"{slipping} slipping" if slipping else "nothing a week behind"),
                tone=behind_tone, href="/dashboard/syllabus"),
            # `unplanned` and `unestimated` are STATES, not pace (V2-P11). They
            # stay neutral here so they can never be read as a RAG colour — and
            # when nothing is unplanned the cell reports the *other* state rather
            # than a zero next to a sub-line about four unsized chapters.
            (OverviewMetric(
                key="unplanned", label="Not planned yet", value=str(unplanned),
                sub=(f"{unsized} {_plural(unsized, 'chapter')} not sized" if unsized
                     else "class-subjects with nothing scheduled"),
                tone="neutral", href="/plan/week")
             if unplanned or not unsized else
             OverviewMetric(
                 key="unplanned", label="Chapters to size", value=str(unsized),
                 sub="scheduled once the term sizes them", tone="neutral",
                 href="/plan/syllabus")),
        ]

        worst = sorted((r for r in rag if r.weeks_behind > 0),
                       key=lambda r: -r.weeks_behind)[:MAX_NOTES]
        notes = [
            OverviewNote(
                text=(f"{r.class_label} {r.subject_name} — {r.weeks_behind} "
                      f"{_plural(r.weeks_behind, 'week')} behind"),
                tone="red" if r.status == "red" else "amber", href="/dashboard/syllabus")
            for r in worst
        ]
        for r in (x for x in rag if x.current_term_unplanned):
            if len(notes) >= MAX_NOTES:
                break
            notes.append(OverviewNote(
                text=f"{r.class_label} {r.subject_name} — this term is not planned",
                tone="amber", href="/plan/week"))

        if not rag:
            headline = "No class-subject has a syllabus yet."
        elif not rated:
            headline = f"{unplanned} class-subjects have a syllabus but no plan."
        elif behind:
            headline = (f"{on_track} of {len(rated)} class-subjects are on track; "
                        f"{behind} {_plural(behind, 'is', 'are')} a week or more behind.")
        else:
            headline = f"{on_track} of {len(rated)} class-subjects are on track."

        return OverviewSection(
            key="syllabus", label="Syllabus pace", href="/dashboard/syllabus",
            headline=headline, metrics=metrics, notes=notes,
            tone=_worst(pace_tone, behind_tone))

    # ── M4 homework ──────────────────────────────────────────────────────────
    def _homework(self, board) -> OverviewSection:
        ov = board.overview
        completion = ov.overall_completion
        unchecked = sum(t.unchecked_overdue for t in ov.teachers)
        missing = len(ov.needs_attention)

        done_tone = _tone(completion * 100 if completion is not None else None, 75, 60)
        # Unchecked past its due date is the teacher's gap, and the one homework
        # figure that is never the student's miss (HW-1).
        check_tone = "red" if unchecked > 5 else "amber" if unchecked else "green"

        metrics = [
            OverviewMetric(
                key="completion", label=f"Done ({ov.window_days}d)",
                value=f"{round(completion * 100)}%" if completion is not None else "—",
                sub=(f"{ov.checked} of {ov.assigned} sets checked" if ov.assigned
                     else "no homework set in the window"),
                tone=done_tone, href="/dashboard/homework",
                spark=[d.completion for d in board.daily]),
            OverviewMetric(
                key="unchecked", label="Unchecked past due", value=str(unchecked),
                sub=("everything set has been checked" if not unchecked
                     else "set, due, and never gone through"),
                tone=check_tone, href="/dashboard/homework"),
            OverviewMetric(
                key="missing", label="Keep missing it", value=str(missing),
                sub=("nobody is repeatedly missing homework" if not missing
                     else "students on a run of not-done"),
                tone="red" if missing else "green", href="/dashboard/homework"),
        ]

        notes = [
            OverviewNote(
                text=(f"{s.full_name} ({s.class_label}) — {s.not_done} missed"
                      + (f", {s.streak} in a row" if s.streak > 1 else "")),
                tone="red", href=f"/students/{s.student_id}")
            for s in ov.needs_attention[:MAX_NOTES]
        ]
        for t in sorted(ov.teachers, key=lambda t: -t.unchecked_overdue):
            if len(notes) >= MAX_NOTES or not t.unchecked_overdue:
                break
            notes.append(OverviewNote(
                text=(f"{t.teacher_name} — {t.unchecked_overdue} "
                      f"{_plural(t.unchecked_overdue, 'set')} set but never checked"),
                tone="amber", href="/dashboard/homework"))

        if not ov.assigned:
            headline = f"No homework was set in the last {ov.window_days} days."
        elif completion is None:
            headline = (f"{ov.assigned} sets given out, none checked — "
                        "completion is unknown, not zero.")
        else:
            headline = (f"{round(completion * 100)}% of checked homework was done"
                        + (f"; {unchecked} {_plural(unchecked, 'set')} are past due "
                           "and unchecked." if unchecked else "."))

        return OverviewSection(
            key="homework", label="Homework", href="/dashboard/homework",
            headline=headline, metrics=metrics, notes=notes,
            tone=_worst(done_tone, check_tone, "red" if missing else "green"))

    # ── M5 tasks + duties ────────────────────────────────────────────────────
    def _tasks(self, board) -> OverviewSection:
        duty = board.duty_completion
        overdue_tone = ("red" if board.critical_overdue
                        else "amber" if board.overdue else "green")
        duty_tone = _tone(duty * 100 if duty is not None else None, 80, 60)

        metrics = [
            OverviewMetric(
                key="open", label="Open tasks", value=str(board.open),
                sub=(f"{board.unassigned} with nobody on them" if board.unassigned
                     else "all assigned"),
                tone="neutral", href="/dashboard/tasks"),
            OverviewMetric(
                key="overdue", label="Overdue", value=str(board.overdue),
                sub=(f"{board.critical_overdue} critical" if board.critical_overdue
                     else "nothing critical" if board.overdue else "nothing overdue"),
                tone=overdue_tone, href="/dashboard/tasks"),
            OverviewMetric(
                key="duties", label="Duties done today",
                value=f"{round(duty * 100)}%" if duty is not None else "—",
                sub=("attendance, logs and checks for periods actually due"
                     if duty is not None else "no periods were due today"),
                tone=duty_tone, href="/dashboard/tasks"),
        ]

        notes = [
            OverviewNote(
                # A task due earlier today is not "0 days overdue" — the phrase
                # reads as a rounding error rather than as today's deadline.
                text=(f"{r.title} — "
                      + ("due today" if r.days_overdue <= 0
                         else f"{r.days_overdue} {_plural(r.days_overdue, 'day')} overdue")
                      + (f" · {r.assignee_name}" if r.assignee_name else "")),
                tone="red" if r.is_critical else "amber", href=f"/boards/{r.board_id}")
            for r in board.red_rows[:MAX_NOTES]
        ]

        if not board.open and not board.overdue:
            headline = "No task is open."
        elif board.overdue:
            headline = (f"{board.open} open, {board.overdue} overdue"
                        + (f" ({board.critical_overdue} critical)."
                           if board.critical_overdue else "."))
        else:
            headline = f"{board.open} open, nothing overdue."

        return OverviewSection(
            key="tasks", label="Tasks & duties", href="/dashboard/tasks",
            headline=headline, metrics=metrics, notes=notes,
            tone=_worst(overdue_tone, duty_tone))

    # ── M6 exams ─────────────────────────────────────────────────────────────
    def _exams(self, board) -> OverviewSection:
        # "Weakest of one subject" is not a finding, so a school with a single
        # scored subject gets its latest exam instead of a ranking it cannot
        # support — the same honesty guard the syllabus board applies to ranks.
        weakest = board.by_subject[-1] if len(board.by_subject) > 1 else None
        latest = board.recent[0] if board.recent else None
        if weakest is not None:
            third = OverviewMetric(
                key="weakest", label="Weakest subject", value=weakest.label,
                sub=(f"{weakest.avg_pct}% over {weakest.exams} "
                     f"{_plural(weakest.exams, 'exam')}"),
                tone="neutral", href="/dashboard/exams")
        else:
            third = OverviewMetric(
                key="weakest", label="Latest exam",
                value=(f"{latest.avg_pct}%" if latest and latest.avg_pct is not None
                       else latest.name if latest else "—"),
                sub=(f"{latest.name} · {latest.scored}/{latest.roster} scored" if latest
                     else "two scored subjects to compare"),
                tone="neutral",
                href=f"/students/scores/exam/{latest.cycle_id}" if latest
                else "/dashboard/exams")

        # No tone on an average: the school's own grading standard decides what
        # 62% means, and inventing a threshold here would be a judgement the
        # board has no basis for.
        metrics = [
            OverviewMetric(
                key="avg", label="Average this year",
                value=f"{board.avg_pct}%" if board.avg_pct is not None else "—",
                sub=(f"across {board.exams} {_plural(board.exams, 'exam')}"
                     if board.exams else "no exam recorded yet"),
                tone="neutral", href="/dashboard/exams"),
            OverviewMetric(
                key="scored", label="Marks entered", value=str(board.scored),
                sub=("student results in the year" if board.scored
                     else "nothing captured yet"),
                tone="neutral", href="/students/scores"),
            third,
        ]

        notes = [
            OverviewNote(
                text=(f"{e.name}"
                      + (f" · {e.class_label}" if e.class_label else "")
                      + (f" {e.subject_name}" if e.subject_name else "")
                      + (f" — {e.avg_pct}% avg" if e.avg_pct is not None else "")
                      + (f", {e.scored}/{e.roster} scored" if e.roster else "")),
                # Participation, always beside the average: an 88% from 9 of 42
                # students is not an 88% class.
                tone=("amber" if e.participation is not None and e.participation < 0.8
                      else "neutral"),
                href=f"/students/scores/exam/{e.cycle_id}")
            for e in board.recent[:MAX_NOTES]
        ]

        headline = ("No exam has been recorded this year."
                    if not board.exams
                    else f"{board.exams} {_plural(board.exams, 'exam')} recorded"
                         + (f", averaging {board.avg_pct}%." if board.avg_pct is not None
                            else ", none scored yet."))

        return OverviewSection(
            key="exams", label="Exams & scores", href="/dashboard/exams",
            headline=headline, metrics=metrics, notes=notes, tone="neutral")

    # ── the rail ─────────────────────────────────────────────────────────────
    def _actions(self, capture, presence, leave, streaks, homework, tasks, rag,
                 now) -> list[QuickAction]:
        """What is waiting, and the screen that clears it.

        Each entry is conditional on its own count, so the rail empties itself as
        the day is dealt with. Ordered worst-first and capped — a rail of twelve
        is a to-do list nobody reads.
        """
        actions: list[QuickAction] = []
        pending = max(0, capture.expected - capture.marked)
        uncovered = sum(max(0, a.periods_due - a.periods_covered)
                        for a in presence.absentees)
        unchecked = sum(t.unchecked_overdue for t in homework.overview.teachers)

        if uncovered:
            actions.append(QuickAction(
                key="cover", label="Assign cover", count=uncovered, tone="red",
                detail=(f"{uncovered} {_plural(uncovered, 'period')} today have no "
                        "teacher assigned"),
                href="/dashboard/staff"))
        if not presence.marked and now.phase in ("period", "break", "after"):
            actions.append(QuickAction(
                key="staff_attendance", label="Take staff attendance", tone="amber",
                detail="Nobody has marked who is in today", href="/staff"))
        if leave.pending:
            actions.append(QuickAction(
                key="leave", label="Decide on leave", count=leave.pending, tone="amber",
                detail=(f"{leave.pending} {_plural(leave.pending, 'application')} "
                        "waiting on you"),
                href="/staff/leave"))
        if streaks.rows:
            n = len(streaks.rows)
            actions.append(QuickAction(
                key="streaks", label="Call guardians", count=n, tone="red",
                detail=(f"{n} {_plural(n, 'student')} absent "
                        f"{streaks.min_days}+ days running"),
                href="/dashboard/attendance"))
        # Chasing unmarked periods only makes sense once the day is under way.
        if pending and now.phase in ("period", "break", "after"):
            actions.append(QuickAction(
                key="capture", label="Chase attendance", count=pending, tone="amber",
                detail=f"{pending} {_plural(pending, 'period')} still unmarked today",
                href="/dashboard/attendance"))
        if tasks.critical_overdue:
            actions.append(QuickAction(
                key="critical", label="Clear critical tasks", count=tasks.critical_overdue,
                tone="red",
                detail=(f"{tasks.critical_overdue} critical "
                        f"{_plural(tasks.critical_overdue, 'task')} past due"),
                href="/dashboard/tasks"))
        if unchecked:
            actions.append(QuickAction(
                key="unchecked", label="Chase homework checks", count=unchecked,
                tone="amber",
                detail=(f"{unchecked} {_plural(unchecked, 'set')} past due with no "
                        "check recorded"),
                href="/dashboard/homework"))
        no_plan = sum(1 for r in rag if r.current_term_unplanned)
        if no_plan:
            actions.append(QuickAction(
                key="unplanned", label="Plan this term", count=no_plan, tone="amber",
                detail=(f"{no_plan} class-{_plural(no_plan, 'subject')} have nothing "
                        "scheduled for the term running now"),
                href="/plan/week"))

        actions.sort(key=lambda a: -_RANK.get(a.tone, 0))
        return actions[:MAX_ACTIONS]
