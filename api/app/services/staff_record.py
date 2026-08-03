"""One member of staff's record (V1-16) — where their time went.

Tapping a name on the day-book opens this. It is the person-shaped view of data
five other screens already hold: the day they are having, the month behind it,
what the non-teaching periods went on, and the attendance and leave figures
`StaffMonthService` has computed since V1-4.

**It is a record, not a performance review, and the distinction is enforced
rather than intended** (`D-25`/`S-67`):

  * no score, no rank, no completeness percentage, and no arithmetic anywhere in
    this file that divides what someone did by what they could have done;
  * `days_not_marked` is the *school's* clerical gap and appears in its own word,
    never as an absence (`S-34`);
  * an unfilled free period is a free period (`D-23`) — it is never counted as a
    failure to record, on this screen or in the sentence the model is asked to
    write;
  * the only comparison to a colleague is the load balance the staff tab has
    shown since V1-4, and it is framed as *the school's* distribution problem.

Nothing is recomputed. Today comes from `TimesheetService.day`, the month from
`TimesheetService.month`, attendance and leave from `StaffMonthService.summary`
— so this page and the screens it summarises cannot disagree (`S-51`). The only
query this file issues on its own is the month's category tally, which no other
surface has ever needed.
"""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.work_types import color_for, label_for
from app.models import Membership, TimesheetEntry, User
from app.schemas.insights import (
    DaybookPeriod,
    RecordDaySlot,
    RecordMonthDay,
    RecordPoint,
    RecordSlice,
    StaffRecord,
)
from app.services.ai.staff_record import deterministic_record_summary, record_summary
from app.services.school_clock import today_in
from app.services.staff_month import StaffMonthService, parse_month
from app.services.timesheet import TimesheetService


class StaffRecordService:
    def __init__(self, db: Session):
        self.db = db

    def _resolve(self, m: CurrentMember, member_id: uuid.UUID) -> tuple[uuid.UUID, str, str]:
        """Admins read anyone in their org; a teacher reads only themselves.

        Same rule as `TimesheetService._resolve_member`, restated here because
        this payload carries the attendance and leave figures too — a screen that
        merges two services must be no more permissive than the stricter one.
        """
        if not m.is_admin and member_id != m.membership.id:
            raise ForbiddenError("You can only open your own record")
        row = self.db.execute(
            select(Membership.id, User.name, Membership.org_role)
            .join(User, User.id == Membership.user_id)
            .where(Membership.id == member_id, Membership.org_id == m.org_id)).first()
        if row is None:
            raise NotFoundError("Member")
        return row[0], row[1], row[2]

    def record(self, m: CurrentMember, member_id: uuid.UUID,
               month: str | None = None, on: date | None = None) -> StaffRecord:
        mid, name, role = self._resolve(m, member_id)
        today = today_in(m.org.timezone)
        on = on or today
        month = month or f"{on:%Y-%m}"
        start, end = parse_month(month)

        day = TimesheetService(self.db).day(m, mid, on)
        grid = TimesheetService(self.db).month(m, mid, month)

        rec = StaffRecord(
            member_id=mid, name=name, role=role, month=month,
            start_date=start, end_date=end, date=on, is_today=on == today,
            today_breaks=[DaybookPeriod(period_no=b.after_period_no, start=b.start,
                                        end=b.end, label=b.label)
                          for b in day.breaks],
            evening_labels=day.evening_labels,
            away_reason=next((s.note for s in day.slots if s.kind == "away"), None),
        )

        for slot in day.slots:
            rec.today.append(RecordDaySlot(
                period_no=slot.period_no, start=slot.start, end=slot.end, kind=slot.kind,
                label=(f"{slot.class_label}" if slot.kind in ("class", "cover")
                       else slot.work_label),
                detail=(slot.subject_name if slot.kind in ("class", "cover")
                        else slot.note),
                work_type=slot.work_type,
                color=("teaching" if slot.kind in ("class", "cover")
                       else color_for(slot.work_type or "", m.org) if slot.kind == "work"
                       else "free")))
        rec.today_summary = self._day_summary(day)

        for d in grid.days:
            busy = d.teaching + d.cover + d.work
            rec.days.append(RecordMonthDay(
                date=d.date, weekday=d.weekday, state=d.state, label=d.label,
                teaching=d.teaching, cover=d.cover, work=d.work, free=d.free,
                busy=busy))
            # The line plots days that have happened. A closed day joins it only
            # if something was actually recorded on it — plotting every Sunday as
            # zero draws a sawtooth that says nothing about anybody's workload.
            if d.state != "future" and (d.state == "working" or busy > 0
                                        or d.state in ("leave", "holiday")):
                rec.series.append(RecordPoint(date=d.date, teaching=d.teaching + d.cover,
                                              work=d.work))
        # A RECORD stops at today.
        #
        # `TimesheetMonth` totals the whole month including days that have not
        # happened, which is right for the teacher's own planning grid and wrong
        # here: on the 2nd of August this page read "38 of 38 periods (100%)"
        # and the summary called it a month's work. A record of the future is a
        # forecast wearing a record's clothes, and this is the one page that must
        # not be one.
        counted = [d for d in rec.days if d.state != "future"]
        rec.teaching_periods = sum(d.teaching for d in counted)
        rec.cover_periods = sum(d.cover for d in counted)
        rec.work_periods = sum(d.work for d in counted)
        rec.evening_sessions = grid.evening_sessions
        busiest = max((d for d in rec.days if d.state == "working"),
                      key=lambda d: d.busy, default=None)
        if busiest is not None and busiest.busy:
            rec.busiest_day, rec.busiest_periods = busiest.date, busiest.busy

        # The same window the totals used, so the ring's slices add up to the
        # figure beside it. They came from two different day sets once, and the
        # page showed teaching at 100% next to three categories at 3% each.
        rec.slices = self._slices(m, mid, start, min(end, today),
                                  rec.teaching_periods + rec.cover_periods)

        summary = StaffMonthService(self.db).summary(m, month, mid)
        if summary.rows:
            row = summary.rows[0]
            rec.working_days = row.working_days
            rec.days_marked = row.days_marked
            rec.days_not_marked = row.days_not_marked
            rec.days_present = row.days_present
            rec.days_absent = row.days_absent
            rec.half_days = row.half_days
            rec.lates = row.lates
            rec.leave_days = row.leave_days
            rec.leave_remaining = row.leave_remaining

        self._write(m, rec)
        return rec

    # ── the month's categories, the one query this file owns ─────────────────
    def _slices(self, m: CurrentMember, mid: uuid.UUID, start: date, end: date,
                teaching: int) -> list[RecordSlice]:
        out = [RecordSlice(key="teaching", label="Teaching", periods=teaching,
                           color="teaching")]
        for work_type, n in self.db.execute(
            select(TimesheetEntry.work_type, func.count(TimesheetEntry.id))
            .where(TimesheetEntry.org_id == m.org_id, TimesheetEntry.member_id == mid,
                   TimesheetEntry.date >= start, TimesheetEntry.date <= end)
            .group_by(TimesheetEntry.work_type)
            .order_by(func.count(TimesheetEntry.id).desc())).all():
            out.append(RecordSlice(key=work_type, label=label_for(work_type, m.org),
                                   periods=int(n), color=color_for(work_type, m.org)))
        return [s for s in out if s.periods > 0]

    def _day_summary(self, day) -> str:
        if any(s.kind == "away" for s in day.slots):
            reason = next((s.note for s in day.slots if s.kind == "away"), None)
            return f"Away today{f' — {reason}' if reason else ''}."
        parts: list[str] = []
        if day.teaching_count:
            parts.append(f"{day.teaching_count} class"
                         f"{'' if day.teaching_count == 1 else 'es'}")
        if day.cover_count:
            parts.append(f"{day.cover_count} covered for a colleague")
        if day.work_count:
            parts.append(f"{day.work_count} recorded as other work")
        if day.free_count:
            parts.append(f"{day.free_count} free")
        if not parts:
            return "Nothing on the timetable today."
        return " · ".join(parts).capitalize() + "."

    # ── the written part ─────────────────────────────────────────────────────
    def _write(self, m: CurrentMember, rec: StaffRecord) -> None:
        """The template every staff record is written to.

        Four blocks, in this order and no other: **where the time went** (the
        figures, each with its denominator), **highlights** (what this person
        did that the school would not otherwise notice), **worth a look** (gaps
        in the SCHOOL's record and load imbalance — never a judgement of the
        person), and the **written summary**, which only ever voices the three
        lists above.
        """
        total = rec.teaching_periods + rec.cover_periods + rec.work_periods
        month_label = rec.start_date.strftime("%B")

        if total:
            for s in rec.slices[:4]:
                share = round((s.periods / total) * 100)
                rec.where_time_went.append(
                    f"{s.label} — {s.periods} of {total} periods ({share}%)")
        if rec.evening_sessions:
            rec.where_time_went.append(
                f"Evening sessions — {rec.evening_sessions} in {month_label}, "
                "counted beside the periods, never inside them")

        biggest = next((s for s in rec.slices if s.key != "teaching"), None)
        if biggest:
            rec.highlights.append(
                f"Most non-teaching time went on {biggest.label.lower()} "
                f"— {biggest.periods} period{'' if biggest.periods == 1 else 's'}")
        if rec.cover_periods:
            rec.highlights.append(
                f"Stood in for a colleague {rec.cover_periods} "
                f"time{'' if rec.cover_periods == 1 else 's'}")
        if rec.busiest_day and rec.busiest_periods:
            # Not `%-d`: that directive does not exist on Windows, where this
            # runs in dev, and it raises rather than degrading.
            rec.highlights.append(
                f"Fullest day was {rec.busiest_day.day} "
                f"{rec.busiest_day:%b} with {rec.busiest_periods} periods")
        if rec.days_marked and rec.days_absent == 0:
            rec.highlights.append(
                "In on the only day the office marked" if rec.days_marked == 1
                else f"In on every one of the {rec.days_marked} days that were marked")

        # `days_not_marked` is the office's gap, and it is said as one. Reading it
        # as anything about this person is the single easiest way to turn a
        # record into an accusation.
        if rec.days_not_marked:
            rec.watch.append(
                f"{rec.days_not_marked} working day"
                f"{'' if rec.days_not_marked == 1 else 's'} in {month_label} "
                "had no staff attendance taken — the school's record, not theirs")
        if rec.leave_days:
            rec.watch.append(
                f"{rec.leave_days:g} day{'' if rec.leave_days == 1 else 's'} of "
                f"approved leave, {rec.leave_remaining:g} left in the allowance")
        if rec.lates:
            rec.watch.append(
                f"Marked late on {rec.lates} day{'' if rec.lates == 1 else 's'} "
                "— a flag to be seen, never a deduction")

        rec.headline = (
            f"{rec.name} was recorded in {total} period"
            f"{'' if total == 1 else 's'} across {month_label} — "
            f"{rec.teaching_periods} teaching"
            + (f", {rec.cover_periods} covering" if rec.cover_periods else "")
            + (f" and {rec.work_periods} of other work." if rec.work_periods
               else ". No non-teaching periods were written down, which under "
                    "the school's own rule means they were free.")
        ) if total else (
            f"Nothing is recorded for {rec.name} in {month_label} yet.")

        facts = {
            "name": rec.name, "role": rec.role, "month": month_label,
            "where_time_went": rec.where_time_went,
            "highlights": rec.highlights, "watch": rec.watch,
        }
        source, text = record_summary(facts)
        rec.summary = text or deterministic_record_summary(facts)
        rec.summary_source = source
