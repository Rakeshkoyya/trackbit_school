"""V1-14 — presence as a picture: three rings, three named blocks, one month.

The overview used to answer "how is attendance?" with a percentage and a
sparkline. That is a fact, not a morning's work: an admin who reads *91%* still
has to open a tab to learn who the 9% are, whether anybody has rung them, which
teacher is away, and what that broke. This service is the read that makes the
glance sufficient.

Three rules, and they are the whole design:

  * **Three rings, three denominators.** Students, teachers and admin staff are
    three different questions with three different totals, and averaging them
    into one "school attendance" number would describe nobody. A ring nobody has
    marked is neutral and says so — it is never drawn at 0%, and never red.
  * **Named under the threshold, counted over it.** At or under three absentees
    the block names them with the button beside each, because that is a
    morning's work. Above three it collapses to one sentence and a link, because
    fourteen names with fourteen buttons is a screen nobody reads. The threshold
    lives here (`INLINE_LIMIT`) so every surface obeys the same rule.
  * **Nothing is re-derived.** Absence runs come from `AttendanceInsights.streaks`,
    reasons from `absence_reasons`, staff from `staff_presence`, "already done
    today" from `ActionService.done_today`. This composes; it does not compute a
    second version of who was absent.

The month is the tab's visual layer. It is deliberately a **class × day grid**
rather than a line: student attendance sits at ninety-something percent every
day of the year, so a line is a flat line and tells nobody anything, while a bad
day shows up in a grid as a vertical stripe and a struggling class as a
horizontal one. Days nobody marked are their own state — the whole point of the
grid is that it can show a gap in the record, which no percentage can.
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.models import (
    AcademicYear,
    Board,
    Membership,
    SchoolClass,
    StaffAbsence,
    StaffAttendanceDay,
    Student,
    TaskInstance,
    User,
)
from app.schemas.insights import (
    AbsenceProfile,
    AdminWorkRow,
    ClassMonthCell,
    ClassMonthRow,
    PresenceAnomaly,
    PresenceBoard,
    PresenceDay,
    PresenceGroup,
    PresenceMonth,
    PresenceRing,
    PresenceRow,
    TaskRedRow,
)
from app.services.attendance import day_absence_maps, is_day_absent
from app.services.calendar import org_working_days
from app.services.insights.attendance import AttendanceInsights
from app.services.school_clock import today_in
from app.services.staff_attendance import StaffAttendanceService

# The founder's rule, in one place: three or fewer people get named with their
# actions; more than three collapse to a sentence. Not a setting — a school has
# no basis to tune it, and it is the line between "a list" and "a morning".
INLINE_LIMIT = 3
MONTH_DAYS = 30
MAX_PROFILES = 60
MAX_ADMIN_TASKS = 6
# Below this the ring is red, between this and `RING_GOOD` amber. Attendance
# thresholds already live at these numbers on the overview and the tab; a third
# set here would be the drift V1-0 exists to remove.
RING_GOOD = 90.0
RING_FAIR = 80.0


def _plural(n: int, one: str, many: str | None = None) -> str:
    return one if n == 1 else (many or one + "s")


def _tone(pct: float | None, good: float = RING_GOOD, fair: float = RING_FAIR) -> str:
    if pct is None:
        return "neutral"
    return "green" if pct >= good else "amber" if pct >= fair else "red"


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


class PresenceService:
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

    # ── the rings + the three blocks ─────────────────────────────────────────
    def board(self, m: CurrentMember, year_id: uuid.UUID | None = None) -> PresenceBoard:
        """On a school day the board is about TODAY, captured or not.

        It falls back to the last day the school ran only when today is closed —
        on a Sunday or in a vacation every list comes back empty, and an empty
        board would read as *"nobody was absent"* rather than *"the school was
        shut"* (the V1-4 call-board fix). `date`/`is_today`/`school_open` ride on
        the payload so the screen can say which day it is describing and why.
        """
        att = AttendanceInsights(self.db)
        today = self._today(m)
        on = self._anchor(m, att, today)
        year = self._year(m, year_id)

        student_ring, absentees = self._students_today(m, on, year)
        presence = att.staff_presence(m, on)
        roster = StaffAttendanceService(self.db).roster(m, on)

        # One split, used by both rings and both staff blocks. `late` counts as
        # in (V1-4 `S-19`: lateness is a flag to be seen, never a deduction).
        by_role: dict[str, list] = defaultdict(list)
        for r in roster.roster:
            by_role["admins" if r.role == "admin" else "teachers"].append(r)

        rings = [student_ring]
        for key, label in (("teachers", "Teachers"), ("admins", "Admin staff")):
            rows = by_role.get(key, [])
            present = sum(1 for r in rows if r.present)
            rings.append(self._staff_ring(key, label, roster.marked, present, len(rows)))

        away = {a.member_id: a for a in presence.absentees}
        groups = [
            self._student_group(m, absentees, student_ring, on),
            self._teacher_group([away[r.member_id] for r in by_role.get("teachers", [])
                                 if r.member_id in away]),
            # The admin desk is the one thing here that is a question about NOW
            # rather than about a school day — work is overdue on a Sunday too.
            self._admin_group(m, today,
                              [away[r.member_id] for r in by_role.get("admins", [])
                               if r.member_id in away],
                              by_role.get("admins", [])),
        ]

        # The roll. `roll` is the school's whole strength and is populated
        # whether or not anything is marked — the admin asked to be able to read
        # it on any morning. `counted` is the part of it that sits in a marked
        # group, and it is what `in_building` and `away` add up to: adding an
        # unmarked cohort to those would report people present that nobody has
        # claimed to have seen.
        seen = [r for r in rings if r.marked]
        in_building = sum(r.present for r in seen)
        counted = sum(r.counted for r in seen)
        roll = sum(r.total for r in rings)
        not_marked = max(0, roll - counted)
        # NOT `away` — that name is the absent-member map above, and shadowing it
        # here would work today only because the groups are built first.
        away_total = sum(r.absent for r in seen)
        if not seen:
            roll_caption = f"nothing marked yet · {roll} on the roll"
        elif not not_marked:
            roll_caption = (f"of {roll} on the roll" if away_total
                            else f"the whole roll of {roll}")
        else:
            roll_caption = (f"of {counted} marked · {not_marked} of {roll} "
                            "not marked yet")

        parts = []
        for ring in rings:
            parts.append(f"{ring.label.lower()} {ring.caption}" if not ring.marked
                         else f"{ring.present} of {ring.counted} {ring.label.lower()} in")
        headline = "; ".join(parts) + "."
        open_today = bool(org_working_days(self.db, m.org_id, today, today))
        if on != today:
            headline = f"School is closed today — showing {on:%a %d %b}. " + headline
        elif not seen:
            # The whole point of the 2026-08-05 fix: an open morning nobody has
            # captured says so, in the present tense, with today's date on it.
            headline = ("Nothing has been marked yet today. "
                        f"{roll} people are on the roll. ")
        elif not_marked:
            headline = (f"{not_marked} of {roll} on the roll have no register "
                        "open yet. ") + headline
        return PresenceBoard(date=on, is_today=on == today, school_open=open_today,
                             rings=rings, groups=groups, headline=headline,
                             in_building=in_building, roll=roll, counted=counted,
                             not_marked=not_marked, away=away_total,
                             marked=bool(seen), roll_caption=roll_caption)

    def _anchor(self, m: CurrentMember, att: AttendanceInsights, today: date) -> date:
        """The day the board describes.

        **An open day is always today.** Until 2026-08-05 this walked back a
        fortnight for the most recent day anything was captured, so a school
        that had marked nothing by 9am read yesterday's figures under today's
        heading — the admin's whole question ("has the register been taken?")
        answered with last night's answer. A day the school is open and has
        captured nothing is a real state and must be shown as one.

        The fallback survives for CLOSED days only, where it was always the
        right call: on a Sunday every list is empty and an empty board would
        read as "nobody was absent" rather than "the school was shut". There it
        still prefers the last day actually captured over the last day merely
        open, so the rings and the absence runs describe one day.
        """
        if org_working_days(self.db, m.org_id, today, today):
            return today
        marked, _ = day_absence_maps(self.db, m.org_id, today - timedelta(days=14), today)
        days = [d for (_cid, d), n in marked.items() if n]
        return max(days) if days else att._last_school_day(m, today)

    def _staff_ring(self, key: str, label: str, marked: bool,
                    present: int, total: int) -> PresenceRing:
        if not total:
            return PresenceRing(key=key, label=label, marked=False, total=0,
                                caption=f"no {label.lower()} on the roll",
                                tone="neutral", href="/staff")
        if not marked:
            # Not marked is a gap in the record, not a full house and not an
            # empty school. It gets the word, never a figure — but it still
            # carries `total`, because how many staff the school HAS is a fact
            # that does not depend on anyone having marked a register.
            return PresenceRing(key=key, label=label, marked=False, total=total,
                                counted=0, unmarked=total,
                                caption=f"not marked yet · {total} on the roll",
                                tone="neutral", href="/staff")
        # Staff attendance is a single org-wide day row: marked means the whole
        # roster was marked, so `counted` is the whole cohort and `unmarked` 0.
        pct = round(present / total * 100, 1)
        away = total - present
        return PresenceRing(
            key=key, label=label, marked=True, present=present, absent=away,
            total=total, counted=total, unmarked=0, pct=pct,
            caption=(f"everyone in · {pct}%" if not away
                     else f"{away} away · {pct}% in"),
            tone=_tone(pct), href="/staff")

    def _students_today(self, m: CurrentMember, on: date,
                        year: AcademicYear | None) -> tuple[PresenceRing, list]:
        """The student ring, and the absence runs behind it.

        `streaks(min_days=1)` IS today's absentee list — a run of one means
        absent through every marked period of the most recent day their class
        captured. Reusing it rather than writing a second "who is absent" query
        is what keeps this ring and the tab's red list from ever disagreeing.

        Two denominators, and keeping them apart is the whole of the 2026-08-05
        fix. `total` is the school's strength: every active child in the year,
        always, so the admin can read the roll on a morning nobody has marked.
        `counted` is the part of it sitting in a class that HAS marked, and it
        is what the percentage divides by — before this the ring reported the
        marked classes as though they were the school, so one class of twelve
        taking the register rendered as a complete, healthy day.

        The absence runs are narrowed to those same classes for the same reason:
        `streaks` walks each class's own most recent captured day, so a class
        that marked yesterday and not today would otherwise put yesterday's
        absentees in a block sitting under a ring that says nothing is marked.
        """
        att = AttendanceInsights(self.db)
        if year is None:
            return (PresenceRing(key="students", label="Students", marked=False,
                                 caption="no academic year is active", tone="neutral"), [])

        rows = att.streaks(m, min_days=1, year_id=year.id).rows
        marked, _absents = day_absence_maps(self.db, m.org_id, on, on)
        marked_classes = {cid for (cid, _d), n in marked.items() if n}

        # The school's strength — every active child in a class of this year.
        # One grouped query; the per-class sizes are what name the gap below.
        per_class = {
            cid: int(n) for cid, n in self.db.execute(
                select(Student.class_id, func.count(Student.id))
                .join(SchoolClass, SchoolClass.id == Student.class_id)
                .where(Student.org_id == m.org_id, Student.status == "active",
                       SchoolClass.academic_year_id == year.id)
                .group_by(Student.class_id)).all()
        }
        roll = sum(per_class.values())
        classes_total = len(per_class)
        live = [cid for cid in per_class if cid in marked_classes]
        counted = sum(per_class[cid] for cid in live)
        blank_classes = classes_total - len(live)
        note = (f"{blank_classes} of {classes_total} "
                f"{_plural(classes_total, 'class', 'classes')} not marked yet"
                if blank_classes else None)

        if not live:
            return (PresenceRing(
                key="students", label="Students", marked=False, total=roll,
                counted=0, unmarked=roll,
                caption=(f"not marked yet · {roll} on the roll" if roll
                         else "no students on the roll"),
                note=note, tone="neutral"), [])

        rows = [r for r in rows if r.class_id in marked_classes]
        absent_today = len(rows)
        present = max(0, counted - absent_today)
        pct = round(present / counted * 100, 1) if counted else None
        return (PresenceRing(
            key="students", label="Students", marked=True, present=present,
            absent=absent_today, total=roll, counted=counted,
            unmarked=max(0, roll - counted), pct=pct,
            caption=(f"everyone in · {pct}%" if not absent_today
                     else f"{absent_today} away · {pct}% in"),
            note=note, tone=_tone(pct)), rows)

    # ── block 1: the students ────────────────────────────────────────────────
    def _student_group(self, m: CurrentMember, rows: list, ring: PresenceRing,
                       on: date) -> PresenceGroup:
        reasons = AttendanceInsights(self.db).absence_reasons(
            m, [r.student_id for r in rows], on)
        n = len(rows)
        unexplained = sum(1 for r in rows if r.student_id not in reasons)

        if not n:
            if not ring.marked:
                # Never green, and never "nobody is absent". Nothing has been
                # captured, so there is no news either way — the only honest
                # reading is the size of the gap (ux §5).
                return PresenceGroup(
                    key="students", label="Students away", count=0, tone="neutral",
                    headline=(f"No class has taken the register yet — {ring.total} "
                              f"{_plural(ring.total, 'student is', 'students are')} "
                              "on the roll."),
                    inline=True, rows=[], href="/dashboard/attendance",
                    action_label="Take attendance", note=ring.note,
                    note_href="/dashboard/attendance" if ring.note else None)
            return PresenceGroup(
                key="students", label="Students away", count=0, tone="green",
                headline=("Every student is in today."
                          if not ring.unmarked else
                          f"Every one of the {ring.counted} students marked so far "
                          "is in."),
                inline=True, rows=[], href="/dashboard/attendance",
                action_label="Open attendance", note=ring.note,
                note_href="/dashboard/attendance" if ring.note else None)

        out: list[PresenceRow] = []
        # Named only under the threshold — but always ordered worst-first, so
        # the one-liner above and the tab below agree about who matters.
        ordered = sorted(rows, key=lambda r: (r.student_id in reasons, -r.streak,
                                              r.full_name))
        if n <= INLINE_LIMIT:
            for r in ordered:
                code, note = reasons.get(r.student_id, (None, None))
                explained = r.student_id in reasons
                bits = [f"Class {r.class_label}" if r.class_label else "no class"]
                if r.guardian_name:
                    bits.append(r.guardian_name
                                + (f" · {r.guardian_phone}" if r.guardian_phone else ""))
                elif not r.guardian_count:
                    bits.append("no guardian on file")
                if r.class_teacher_name:
                    bits.append(f"class teacher {r.class_teacher_name}")
                bits.append(note or code or "nobody has explained this"
                            if explained else "nobody has explained this")
                out.append(PresenceRow(
                    id=r.student_id, name=r.full_name, subtitle=" · ".join(bits),
                    tone="amber" if explained else "red",
                    href=f"/students/{r.student_id}",
                    badge=f"{r.streak}d",
                    actions=["remind_guardian", "assign_followup"]
                            + ([] if explained else ["record_reason"]),
                    done=([k for k, flag in
                           (("remind_guardian", r.reminded_today),
                            ("assign_followup", r.followup_assigned_today)) if flag])))

        headline = (f"{n} {_plural(n, 'student is', 'students are')} away"
                    + (f" — {unexplained} with no reason on record."
                       if unexplained else ", every one explained."))
        return PresenceGroup(
            key="students", label="Students away", count=n,
            tone="red" if unexplained else "amber", headline=headline,
            inline=n <= INLINE_LIMIT, rows=out, href="/dashboard/attendance",
            action_label="Follow up" if n > INLINE_LIMIT else "Open attendance",
            # The classes still to mark ride along, because "3 away" over a
            # third of the school is a different morning from "3 away" over all
            # of it, and the block is where that gets noticed.
            note=ring.note,
            note_href="/dashboard/attendance" if ring.note else None)

    # ── block 2: the teachers ────────────────────────────────────────────────
    def _teacher_group(self, absentees: list) -> PresenceGroup:
        n = len(absentees)
        uncovered = sum(max(0, a.periods_due - a.periods_covered) for a in absentees)
        if not n:
            return PresenceGroup(
                key="teachers", label="Teachers away", count=0, tone="green",
                headline="Every teacher is in — nothing to cover.",
                rows=[], href="/dashboard/staff", action_label="Open staff")

        out: list[PresenceRow] = []
        if n <= INLINE_LIMIT:
            for a in sorted(absentees,
                            key=lambda a: -(a.periods_due - a.periods_covered)):
                gap = max(0, a.periods_due - a.periods_covered)
                bits = [("On approved leave" if a.on_leave else "Marked away")
                        + (f" — {a.reason}" if a.reason else "")]
                if a.status == "half_day":
                    bits.append(f"half day ({a.portion or 'part'})")
                bits.append(f"{gap} of {a.periods_due} "
                            f"{_plural(a.periods_due, 'period')} uncovered"
                            if a.periods_due else "no lessons today")
                out.append(PresenceRow(
                    id=a.member_id, name=a.name, subtitle=" · ".join(bits),
                    tone="red" if gap else "green", href=None,
                    badge=(f"{gap} to cover" if gap
                           else "covered" if a.periods_due else None),
                    actions=["arrange_cover"] if a.periods_due else []))

        # The founder's phrasing: how many are away, and how many classes have
        # nobody in front of them. Those are two facts and the second is the one
        # that costs a lesson.
        headline = (f"{n} {_plural(n, 'teacher is', 'teachers are')} away"
                    + (f" — {uncovered} {_plural(uncovered, 'class has', 'classes have')} "
                       "nobody assigned." if uncovered else ", every class covered."))
        return PresenceGroup(
            key="teachers", label="Teachers away", count=n,
            tone="red" if uncovered else "amber", headline=headline,
            inline=n <= INLINE_LIMIT, rows=out, href="/dashboard/staff",
            action_label="Manage cover",
            note=(f"{uncovered} {_plural(uncovered, 'period')} to cover" if uncovered
                  else None),
            note_href="/dashboard/staff" if uncovered else None)

    # ── block 3: the admin staff ─────────────────────────────────────────────
    def _admin_group(self, m: CurrentMember, today: date, absentees: list,
                     admin_rows: list) -> PresenceGroup:
        """An absent admin's blast radius is their work, not their periods.

        So this block carries two facts: who is away, and what is sitting
        unfinished across the admin desk today. The second is worth saying on a
        day nobody is absent, which is why it is a `note` rather than a row.
        """
        work = self._admin_work(m, today, [r.member_id for r in admin_rows])
        pending = sum(w.due_today + w.overdue for w in work)
        stranded = sum(w.due_today + w.overdue for w in work if not w.present)
        n = len(absentees)

        out: list[PresenceRow] = []
        by_member = {w.member_id: w for w in work}
        if n and n <= INLINE_LIMIT:
            for a in absentees:
                w = by_member.get(a.member_id)
                carried = (w.due_today + w.overdue) if w else 0
                bits = [("On approved leave" if a.on_leave else "Marked away")
                        + (f" — {a.reason}" if a.reason else "")]
                bits.append(f"{carried} {_plural(carried, 'task')} due or overdue"
                            if carried else "nothing due on them today")
                out.append(PresenceRow(
                    id=a.member_id, name=a.name, subtitle=" · ".join(bits),
                    tone="red" if carried else "amber", href=None,
                    badge=f"{carried} {_plural(carried, 'task')}" if carried else None,
                    actions=["reassign_work"] if carried else []))

        if not n:
            headline = ("Every admin is in"
                        + (f" — {pending} {_plural(pending, 'task is', 'tasks are')} "
                           "due or overdue across the desk." if pending else
                           ", and nothing is overdue."))
            tone = "amber" if pending else "green"
        else:
            headline = (f"{n} admin {_plural(n, 'is', 'are')} away"
                        + (f" — {stranded} {_plural(stranded, 'task is', 'tasks are')} "
                           "sitting with them." if stranded else
                           ", nothing is waiting on them."))
            tone = "red" if stranded else "amber"

        return PresenceGroup(
            key="admins", label="Admin staff", count=n, tone=tone, headline=headline,
            inline=not n or n <= INLINE_LIMIT, rows=out,
            href="/dashboard/attendance#admin", action_label="Take action",
            note=(f"{pending} {_plural(pending, 'task')} due or overdue" if pending
                  else None),
            note_href="/dashboard/tasks" if pending else None)

    # ── the admin desk ───────────────────────────────────────────────────────
    def _admin_work(self, m: CurrentMember, today: date,
                    member_ids: list[uuid.UUID]) -> list[AdminWorkRow]:
        """Every admin and the work on them — two queries, never one per person.

        "Due today" is decided against the org's own day, not UTC's: a task due
        at 23:00 local is due today for the person who has to do it.
        """
        if not member_ids:
            return []
        people = {
            mid: (uid, name, role) for mid, uid, name, role in self.db.execute(
                select(Membership.id, Membership.user_id, User.name, Membership.org_role)
                .join(User, User.id == Membership.user_id)
                .where(Membership.id.in_(member_ids))).all()
        }
        user_ids = [uid for uid, _n, _r in people.values()]
        end_of_day = datetime.combine(today + timedelta(days=1), datetime.min.time(),
                                      tzinfo=UTC)
        rows = self.db.execute(
            select(TaskInstance, Board.name)
            .join(Board, Board.id == TaskInstance.board_id)
            .where(TaskInstance.org_id == m.org_id,
                   TaskInstance.assignee_id.in_(user_ids),
                   TaskInstance.status == "open")
            .order_by(TaskInstance.is_critical.desc(), TaskInstance.due_at)).all()

        by_user: dict[uuid.UUID, list] = defaultdict(list)
        for task, board_name in rows:
            by_user[task.assignee_id].append((task, board_name))

        roster = StaffAttendanceService(self.db).roster(m, today)
        state = {r.member_id: r for r in roster.roster}

        out: list[AdminWorkRow] = []
        for mid in member_ids:
            uid, name, _role = people.get(mid, (None, "Unknown", "admin"))
            if uid is None:
                continue
            mine = by_user.get(uid, [])
            red: list[TaskRedRow] = []
            overdue = critical = due_today = 0
            for task, board_name in mine:
                if task.due_at is None:
                    continue
                days = (today - task.due_at.date()).days
                if task.due_at >= end_of_day:
                    continue
                if days > 0:
                    overdue += 1
                    critical += 1 if task.is_critical else 0
                else:
                    due_today += 1
                if len(red) < MAX_ADMIN_TASKS:
                    red.append(TaskRedRow(
                        task_id=task.id, title=task.title, board_id=task.board_id,
                        board_name=board_name, assignee_name=name,
                        due_at=task.due_at, days_overdue=max(0, days),
                        is_critical=task.is_critical))
            row = state.get(mid)
            carried = overdue + due_today
            out.append(AdminWorkRow(
                member_id=mid, user_id=uid, name=name,
                present=bool(row.present) if row else True,
                on_leave=bool(row.on_leave) if row else False,
                reason=(row.leave_reason or row.note) if row else None,
                open_tasks=len(mine), overdue=overdue, critical_overdue=critical,
                due_today=due_today, rows=red,
                tone=("red" if critical or (overdue and not (row and row.present))
                      else "amber" if carried else "green"),
                summary=(f"{carried} {_plural(carried, 'task')} due or overdue"
                         + (f", {critical} critical" if critical else "")
                         if carried else "nothing due today")))
        out.sort(key=lambda w: (w.present, -(w.overdue + w.due_today), w.name))
        return out

    # ── the month ────────────────────────────────────────────────────────────
    def month(self, m: CurrentMember, year_id: uuid.UUID | None = None,
              days: int = MONTH_DAYS) -> PresenceMonth:
        """Thirty days of presence, shaped so an abnormality is visible.

        Six queries flat for the whole board — the day maps (2), the classes,
        the rosters, the staff days and the staff absences — plus what the
        streaks and staff-presence reads already cost. Never one query per class
        and never one per day.
        """
        today = self._today(m)
        year = self._year(m, year_id)
        since = today - timedelta(days=days - 1)
        out = PresenceMonth(date=today, window_days=days, from_date=since,
                            to_date=today)
        if year is None:
            out.headline = "No academic year is active."
            return out

        # The school's own working days — a Sunday with nothing marked is a
        # closed day, not a capture failure, and the two must not share a cell.
        working = org_working_days(self.db, m.org_id, since, today)

        classes = {
            cid: _label(name, section) for cid, name, section in self.db.execute(
                select(SchoolClass.id, SchoolClass.name, SchoolClass.section)
                .where(SchoolClass.org_id == m.org_id,
                       SchoolClass.academic_year_id == year.id)
                .order_by(SchoolClass.name, SchoolClass.section)).all()
        }
        rosters = {
            cid: int(n) for cid, n in self.db.execute(
                select(Student.class_id, func.count(Student.id))
                .where(Student.org_id == m.org_id, Student.status == "active",
                       Student.class_id.in_(classes.keys()))
                .group_by(Student.class_id)).all()
        } if classes else {}
        student_class = {
            sid: cid for sid, cid in self.db.execute(
                select(Student.id, Student.class_id)
                .where(Student.org_id == m.org_id, Student.status == "active",
                       Student.class_id.in_(classes.keys()))).all()
        } if classes else {}

        marked, absents = day_absence_maps(self.db, m.org_id, since, today)

        # A day the school declared closed but somebody genuinely taught on —
        # an exam Saturday, a sports Sunday — belongs on the grid. V1-4 fixed
        # exactly this in the timesheet: a period actually worked could not be
        # seen because the week dropped every non-working weekday. A closed day
        # with nothing on it is still left out; it is not a gap in the record.
        working = sorted(set(working) | {d for (_cid, d), n in marked.items() if n})
        out.dates = working

        # (class, date) → how many of its students were absent all day.
        absent_by_class_day: dict[tuple[uuid.UUID, date], int] = defaultdict(int)
        absent_days_by_student: dict[uuid.UUID, int] = defaultdict(int)
        for sid, per_day in absents.items():
            cid = student_class.get(sid)
            if cid is None:
                continue
            for d, n in per_day.items():
                if is_day_absent(marked.get((cid, d), 0), n):
                    absent_by_class_day[(cid, d)] += 1
                    absent_days_by_student[sid] += 1

        out.classes = self._class_rows(classes, rosters, working, marked,
                                       absent_by_class_day)
        out.students = self._student_days(working, classes, rosters, marked,
                                          absent_by_class_day)
        out.teachers, out.admins = self._staff_days(m, working)
        out.profiles = self._profiles(m, today, student_class, classes, rosters,
                                      marked, absent_days_by_student)
        att = AttendanceInsights(self.db)
        # The SAME anchor the rings use. Reading staff for the raw calendar day
        # put "nobody is away" under a panorama naming two absent teachers —
        # one screen, two days, and no way for the reader to tell.
        presence = att.staff_presence(m, self._anchor(m, att, today))
        out.staff_absent = [a for a in presence.absentees if a.role != "admin"]
        admin_ids = list(self.db.scalars(
            select(Membership.id).where(
                Membership.org_id == m.org_id, Membership.status == "active",
                Membership.org_role == "admin")))
        out.admin_work = self._admin_work(m, today, admin_ids)
        out.admin_options = [
            PresenceRow(id=w.member_id, name=w.name,
                        subtitle=("in today" if w.present else "away today"),
                        tone="neutral" if w.present else "amber")
            for w in out.admin_work
        ]
        out.anomalies = self._anomalies(out, working)

        rated = [d for d in out.students if d.marked]
        if rated:
            avg = round(sum(d.pct or 0 for d in rated) / len(rated), 1)
            out.headline = (
                f"{avg}% of students present across the {len(rated)} "
                f"{_plural(len(rated), 'day')} marked in the last {days}"
                + (f" — {len(working) - len(rated)} working "
                   f"{_plural(len(working) - len(rated), 'day')} captured nothing."
                   if len(rated) < len(working) else "."))
        else:
            out.headline = (f"No attendance has been marked in the last {days} days — "
                            "there is nothing to draw yet.")
        return out

    def _class_rows(self, classes, rosters, working, marked,
                    absent_by_class_day) -> list[ClassMonthRow]:
        """The grid: one row per class, one cell per working day.

        The cell states are the point. `marked` carries a percentage, `unmarked`
        carries nothing at all — a class that captured nothing on Tuesday must
        not read as a class with a full house on Tuesday, and the grid is the
        only rendering that can show the difference.
        """
        rows: list[ClassMonthRow] = []
        for cid, label in classes.items():
            roster = rosters.get(cid, 0)
            cells: list[ClassMonthCell] = []
            marked_days = absent_total = 0
            for d in working:
                n_marked = marked.get((cid, d), 0)
                if not n_marked:
                    cells.append(ClassMonthCell(date=d, state="unmarked", roster=roster))
                    continue
                absent = absent_by_class_day.get((cid, d), 0)
                marked_days += 1
                absent_total += absent
                pct = round((roster - absent) / roster * 100, 1) if roster else None
                cells.append(ClassMonthCell(date=d, state="marked", absent=absent,
                                            roster=roster, pct=pct))
            pct = (round(sum(c.pct for c in cells if c.pct is not None) / marked_days, 1)
                   if marked_days else None)
            rows.append(ClassMonthRow(
                class_id=cid, class_label=label, roster=roster, cells=cells,
                marked_days=marked_days, absent_days=absent_total, pct=pct,
                tone=_tone(pct)))
        return rows

    def _student_days(self, working, classes, rosters, marked,
                      absent_by_class_day) -> list[PresenceDay]:
        """The org-level day series, denominated ONLY on classes that marked.

        A day where two of twelve classes captured attendance is a day about two
        classes — rolling it up over the whole school's roster would report a
        catastrophic 83% absent and send somebody chasing a phantom.
        """
        out: list[PresenceDay] = []
        for d in working:
            live = [cid for cid in classes if marked.get((cid, d), 0)]
            if not live:
                out.append(PresenceDay(date=d, marked=False))
                continue
            total = sum(rosters.get(cid, 0) for cid in live)
            absent = sum(absent_by_class_day.get((cid, d), 0) for cid in live)
            out.append(PresenceDay(
                date=d, marked=True, present=max(0, total - absent), absent=absent,
                total=total,
                pct=round((total - absent) / total * 100, 1) if total else None))
        return out

    def _staff_days(self, m: CurrentMember,
                    working: list[date]) -> tuple[list[PresenceDay], list[PresenceDay]]:
        """Teachers and admins, per day, over the same window.

        Two queries. A day with no `staff_attendance_days` row is `marked=False`
        — the same distinction the table was created to draw, carried all the
        way to the chart rather than being flattened into a zero.
        """
        if not working:
            return [], []
        roles = {
            mid: role for mid, role in self.db.execute(
                select(Membership.id, Membership.org_role)
                .where(Membership.org_id == m.org_id,
                       Membership.status == "active")).all()
        }
        totals = defaultdict(int)
        for role in roles.values():
            totals["admins" if role == "admin" else "teachers"] += 1

        marked_days = {
            d: did for did, d in self.db.execute(
                select(StaffAttendanceDay.id, StaffAttendanceDay.date)
                .where(StaffAttendanceDay.org_id == m.org_id,
                       StaffAttendanceDay.date >= working[0],
                       StaffAttendanceDay.date <= working[-1])).all()
        }
        away: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        if marked_days:
            day_of = {did: d for d, did in marked_days.items()}
            for day_id, member_id, status in self.db.execute(
                select(StaffAbsence.day_id, StaffAbsence.member_id, StaffAbsence.status)
                .where(StaffAbsence.org_id == m.org_id,
                       StaffAbsence.day_id.in_(day_of.keys()))).all():
                # `late` is present (V1-4 `S-19`) — a flag to be seen, never a
                # deduction, so it does not move this chart.
                if status == "late":
                    continue
                bucket = "admins" if roles.get(member_id) == "admin" else "teachers"
                away[day_of[day_id]][bucket] += 1

        def series(bucket: str) -> list[PresenceDay]:
            total = totals.get(bucket, 0)
            rows = []
            for d in working:
                if d not in marked_days or not total:
                    rows.append(PresenceDay(date=d, marked=False, total=total))
                    continue
                absent = away[d][bucket]
                rows.append(PresenceDay(
                    date=d, marked=True, present=total - absent, absent=absent,
                    total=total, pct=round((total - absent) / total * 100, 1)))
            return rows

        return series("teachers"), series("admins")

    def _profiles(self, m: CurrentMember, today: date, student_class, classes,
                  rosters, marked, absent_days_by_student) -> list[AbsenceProfile]:
        """The table's rows: every student with an absence in the window.

        The denominator is **their class's marked days**, not the calendar — a
        week the class captured nothing is not a week the child attended, and
        counting it as one is how a table starts flattering the school.
        """
        if not absent_days_by_student:
            return []
        att = AttendanceInsights(self.db)
        # The current runs give the streak, the guardian, the class teacher and
        # today's rail history — all of it already decorated. Merging is cheaper
        # and safer than re-deriving any of it.
        current = {r.student_id: r for r in att.streaks(m, min_days=1).rows}
        reasons = att.absence_reasons(m, list(absent_days_by_student), today)

        marked_days_by_class: dict[uuid.UUID, int] = defaultdict(int)
        for (cid, _d), n in marked.items():
            if n:
                marked_days_by_class[cid] += 1

        ids = list(absent_days_by_student)
        names = {
            sid: (name, roll) for sid, name, roll in self.db.execute(
                select(Student.id, Student.full_name, Student.roll_no)
                .where(Student.id.in_(ids))).all()
        }
        out: list[AbsenceProfile] = []
        for sid, n_absent in absent_days_by_student.items():
            cid = student_class.get(sid)
            name, roll = names.get(sid, ("Unknown", None))
            md = marked_days_by_class.get(cid, 0)
            pct = round((md - n_absent) / md * 100, 1) if md else None
            run = current.get(sid)
            code, note = reasons.get(sid, (None, None))
            explained = sid in reasons
            # The sentence, written once here — the table, the overview and Lucy
            # all render THIS rather than each composing their own phrasing.
            summary = (f"absent {n_absent} of {md} marked "
                       f"{_plural(md, 'day')} this month" if md
                       else f"absent {n_absent} {_plural(n_absent, 'day')}")
            if run and run.streak >= 2:
                summary += f" · {run.streak} in a row right now"
            if explained:
                summary += f" · {note or code}"
            out.append(AbsenceProfile(
                student_id=sid, full_name=name, roll_no=roll, class_id=cid,
                class_label=classes.get(cid), days_absent=n_absent, marked_days=md,
                pct=pct, current_streak=run.streak if run else 0,
                absent_today=bool(run), status="explained" if explained else "unexplained",
                reason_code=code, reason_note=note,
                guardian_name=run.guardian_name if run else None,
                guardian_phone=run.guardian_phone if run else None,
                class_teacher_name=run.class_teacher_name if run else None,
                reminded_today=bool(run and run.reminded_today),
                followup_assigned_today=bool(run and run.followup_assigned_today),
                summary=summary,
                # `D-86` again: a run of three or more with nobody explaining it
                # is the red the founder asked for. An explained absence is never
                # red however long it runs — somebody has dealt with it.
                tone=("red" if run and run.streak >= 3 and not explained
                      else "amber" if run else "neutral")))
        out.sort(key=lambda p: (not p.absent_today, -p.current_streak, -p.days_absent,
                                p.full_name))
        return out[:MAX_PROFILES]

    # ── what stands out ──────────────────────────────────────────────────────
    def _anomalies(self, month: PresenceMonth,
                   working: list[date]) -> list[PresenceAnomaly]:
        """The side panel: what in this month is worth a second look.

        Each row is a sentence with the figure it rests on and a place to go.
        Nothing here is a prediction or a score — every one of them is a fact
        already visible in the grid, said out loud so it is not missed.
        """
        out: list[PresenceAnomaly] = []
        rated = [d for d in month.students if d.marked and d.pct is not None]

        # 1. The worst day, but only against a mean it can actually deviate from.
        if len(rated) >= 5:
            mean = sum(d.pct for d in rated) / len(rated)
            worst = min(rated, key=lambda d: d.pct)
            if mean - worst.pct >= 5:
                out.append(PresenceAnomaly(
                    key="worst_day", title=f"{worst.date:%a %d %b} was the thinnest day",
                    detail=(f"{worst.pct}% present against a {round(mean, 1)}% average "
                            f"— {worst.absent} of {worst.total} students away."),
                    tone="amber"))

        # 2. A class trailing the school. Two classes minimum, or "worst of one".
        rated_classes = [c for c in month.classes if c.pct is not None and c.marked_days]
        if len(rated_classes) >= 2:
            school = sum(c.pct for c in rated_classes) / len(rated_classes)
            worst = min(rated_classes, key=lambda c: c.pct)
            if school - worst.pct >= 4:
                out.append(PresenceAnomaly(
                    key="worst_class", title=f"{worst.class_label} is trailing",
                    detail=(f"{worst.pct}% over {worst.marked_days} marked "
                            f"{_plural(worst.marked_days, 'day')}, against "
                            f"{round(school, 1)}% across the school."),
                    tone="amber"))

        # 3. The child the month is actually about.
        if month.profiles:
            top = max(month.profiles, key=lambda p: p.days_absent)
            if top.days_absent >= 3:
                out.append(PresenceAnomaly(
                    key="most_absent",
                    title=f"{top.full_name} has missed the most",
                    detail=((f"Class {top.class_label} — " if top.class_label else "")
                            + top.summary),
                    tone="red" if top.tone == "red" else "amber",
                    href=f"/students/{top.student_id}"))

        # 4. The gap in the record. Named as the school's own, never a child's.
        blank = [d for d in month.students if not d.marked]
        if blank and working:
            out.append(PresenceAnomaly(
                key="capture_gap", title="Days with nothing marked",
                detail=(f"{len(blank)} of {len(working)} working "
                        f"{_plural(len(working), 'day')} captured no attendance at "
                        "all. Those days are blank on the grid, not full."),
                tone="amber" if len(blank) * 3 < len(working) else "red"))

        # 5. Staff. A small roster makes one absence a big percentage, so this
        #    is stated in people rather than percent.
        staff_marked = [d for d in month.teachers if d.marked]
        if staff_marked:
            away_days = sum(d.absent for d in staff_marked)
            if away_days:
                out.append(PresenceAnomaly(
                    key="staff_load",
                    title=f"{away_days} teacher-{_plural(away_days, 'day')} away",
                    detail=(f"across {len(staff_marked)} marked "
                            f"{_plural(len(staff_marked), 'day')} — an average of "
                            f"{round(away_days / len(staff_marked), 1)} teachers "
                            "out on any given day."),
                    tone="neutral", href="/dashboard/staff"))

        # 6. Nothing wrong is a finding too — an empty panel reads as broken.
        if not out:
            out.append(PresenceAnomaly(
                key="steady", title="Nothing stands out",
                detail=("No day, class or student in the last month is far enough "
                        "from the rest to be worth a second look."),
                tone="green"))
        return out
