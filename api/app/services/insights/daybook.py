"""The day-book (V1-16) — the whole staff's day as one page.

The school already captured all of this. The timetable knows who stood in front
of which class; the timesheet knows what the rest of the day went on; staff
attendance knows who never came in; the substitution board knows who took
somebody else's period. Four tables, and until now **no surface put them side by
side**: the admin could read one teacher's week (`/timesheet`), or one period's
live board (`/staff/today`), and had to hold the school's day in their head.

So this is one grid — teachers down, periods across, every cell carrying what that
person was doing — plus the one figure that grid implies: **how much of the
school's teaching capacity was spoken for.**

Its population is the **teaching staff** (founder call, 2026-08-06). Office roles
are on no period grid, so counting their day here invented free periods nobody
had asked for and made the denominator impossible to check against a timetable —
see the note in `board`.

Three rules it exists to hold, all of them inherited:

  1. **It is a record, not a score** (`D-25`/`S-67`). There is no completeness
     percentage per person, no ranking, no "adoption" figure, and no path from
     anything here to pay. `S-76` deleted a tile that counted unlogged free
     periods precisely because it was the school's adoption rate wearing a
     workload figure's clothes, and it was at its reddest at 8:30am.
  2. **A free period is free** (`D-23`). An empty cell is the lightest mark on
     the page — never red, never a gap to be filled in, never counted against
     anybody. What the timesheet ADDS is the coloured cells, so those are the
     only ones that carry a hue.
  3. **It reads the same rows every other staff screen reads.** `org_day` is the
     three-query batch `TimesheetService` already owns, complete with the away
     and cover unions `S-72`/`Q-37` added. Writing a second version here would
     make the day-book and the timesheet disagree about the same Tuesday, which
     is `S-51`'s whole lesson.

The board anchors on the date it is asked for and says what that date WAS — a
Sunday reads "the school was shut", not "nobody was working" (the V1-4 call-board
fix, and V1-14 extended it to presence; this is the third surface to need it).
"""

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.staff import not_operator
from app.core.work_types import SLATE, color_for, label_for
from app.models import AcademicYear, Membership
from app.schemas.insights import (
    Daybook,
    DaybookCell,
    DaybookPeriod,
    DaybookRow,
    DaybookSlice,
)
from app.services.calendar import day_lock
from app.services.school_clock import breaks_of, day_periods, today_in
from app.services.timesheet import TimesheetService

#: Slices past this fold into "Other work". A ring of eleven arcs is a colour
#: quiz, not a chart — and the five-colour budget (`core/work_types.py`) means
#: the eleventh has no hue of its own to be read by anyway.
MAX_SLICES = 5

TEACHING_COLOR = "teaching"  # resolved to the chart green client-side
FREE_COLOR = "free"


class DaybookService:
    def __init__(self, db: Session):
        self.db = db

    def _year(self, org_id: uuid.UUID) -> AcademicYear | None:
        return self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == org_id, AcademicYear.is_active.is_(True)))

    def _roles(self, org_id: uuid.UUID) -> dict[uuid.UUID, str]:
        return {
            mid: role for mid, role in self.db.execute(
                select(Membership.id, Membership.org_role)
                .where(Membership.org_id == org_id, Membership.status == "active",
                       not_operator())).all()
        }

    def _has_timetable(self, org_id: uuid.UUID) -> set[uuid.UUID]:
        """Members who hold a class-subject — used only to sort the timetabled
        above the untimetabled, never to exclude anybody. A teacher with no
        class-subject (a warden running evening study, a teacher between
        assignments) still belongs on this page; `board` decides membership by
        role, and this only decides the order it reads in."""
        from app.models import ClassSubject  # noqa: PLC0415
        return {
            mid for (mid,) in self.db.execute(
                select(ClassSubject.teacher_member_id.distinct())
                .where(ClassSubject.org_id == org_id,
                       ClassSubject.teacher_member_id.is_not(None))).all()
        }

    # ── the board ────────────────────────────────────────────────────────────
    def board(self, m: CurrentMember, on: date | None = None,
              year_id: uuid.UUID | None = None) -> Daybook:
        today = today_in(m.org.timezone)
        on = on or today
        year = self._year(m.org_id)
        period_times = year.period_times if year else []
        periods = day_periods(period_times, year.periods_per_day if year else 8)
        working = set(year.working_weekdays or [0, 1, 2, 3, 4, 5]) if year \
            else {0, 1, 2, 3, 4, 5}
        lock = day_lock(self.db, m.org_id, on, year_id or (year.id if year else None))

        book = Daybook(
            date=on, is_today=on == today, weekday=on.weekday(),
            is_working_day=on.weekday() in working and not lock.closed,
            periods=[DaybookPeriod(period_no=p.period_no, start=p.start, end=p.end)
                     for p in periods],
            breaks=[DaybookPeriod(period_no=b.after_period_no, start=b.start,
                                  end=b.end, label=b.label)
                    for b in breaks_of(period_times)],
            locked_periods=sorted(lock.periods),
            closed_reason=(lock.events[0].title if lock.closed and lock.events else None),
        )

        rows = TimesheetService(self.db).org_day(m, on)
        roles = self._roles(m.org_id)
        teaches = self._has_timetable(m.org_id)

        # A period nobody was ever asked to work is NOT a free period.
        #
        # Found by looking at the board on a Sunday: it read "not a school day,
        # nothing was expected of anybody" and then drew forty-three cells
        # labelled FREE and a ring saying 4% of the day was spoken for. Both
        # halves of that are the same mistake `day_lock` was written for
        # (`S-145`) — locking removes a period from what is ASKED FOR, so it
        # leaves the denominator entirely rather than becoming capacity the
        # school failed to use. Anything actually recorded on such a day still
        # shows, because it still happened (`Q-65`).
        def expected(period_no: int) -> bool:
            return book.is_working_day and period_no not in lock.periods

        # The tally. Every counter is a count of PERIOD SLOTS, and the
        # denominator excludes the ones nobody could have worked: a person on
        # leave has no free periods (`S-72`), and a locked period is not capacity
        # the school lost — it is capacity it never had that day (`Q-65`).
        buckets: dict[str, int] = defaultdict(int)
        teaching = cover = work = free = away = 0

        for r in rows:
            day = r.days[0] if r.days else None
            if day is None:
                continue
            # The board is the TEACHING staff's day (founder call, 2026-08-06).
            #
            # It used to be every active membership, and an office admin holds no
            # timetable and files no timesheet — so all eight of their periods
            # fell through to `free`. On this 24-teacher school that put two admin
            # rows and 16 invented free periods into the tally: the headline
            # counted 184 "staff periods" for a school that timetables 21 × 8 =
            # 168, the ring read 64 free against the 48 anyone counting the grid
            # arrives at, and the 16 had no name anywhere on the page.
            #
            # Nobody asked the office for a period, so those slots are not
            # capacity the school failed to use — they are capacity it never had.
            # That is the same rule `expected()` applies to a locked period a few
            # lines down, and the reason both leave the denominator rather than
            # becoming free time somebody has to account for.
            #
            # The whole row goes, cells included, so `teaching + work + free`
            # still equals `slots_total`. ⚠️ The cost, accepted with the call: a
            # cover period taken by a NON-teacher is not on this board (nothing
            # restricts a substitute to org_role 'teacher' — `assign` checks only
            # that the member is active). It is still on `/staff/today` and the
            # cover board, which is where cover is actually arranged.
            role = roles.get(r.member_id, "teacher")
            if role != "teacher":
                continue
            cells: list[DaybookCell] = []
            for slot in day.slots:
                kind = slot.kind
                if kind in ("class", "cover"):
                    cells.append(DaybookCell(
                        period_no=slot.period_no, kind=kind, label=slot.class_label,
                        detail=slot.subject_name, color=TEACHING_COLOR))
                    if kind == "class":
                        teaching += 1
                    else:
                        cover += 1
                elif kind == "work":
                    cells.append(DaybookCell(
                        period_no=slot.period_no, kind="work",
                        label=slot.work_label or label_for(slot.work_type or "", m.org),
                        detail=slot.note, work_type=slot.work_type,
                        color=color_for(slot.work_type or "", m.org)))
                    work += 1
                    buckets[slot.work_type or "other"] += 1
                elif not expected(slot.period_no):
                    cells.append(DaybookCell(period_no=slot.period_no, kind="closed",
                                             color=FREE_COLOR))
                elif kind == "away":
                    cells.append(DaybookCell(period_no=slot.period_no, kind="away",
                                             detail=slot.note, color=FREE_COLOR))
                    away += 1
                else:
                    cells.append(DaybookCell(period_no=slot.period_no, kind="free",
                                             color=FREE_COLOR))
                    free += 1
            book.rows.append(DaybookRow(
                member_id=r.member_id, name=r.member_name, role=role,
                cells=cells, teaching=day.teaching_count, cover=day.cover_count,
                work=day.work_count,
                free=sum(1 for c in cells if c.kind == "free"),
                away_reason=r.away_reason,
                # The one sentence a row needs: what this person's day was, in
                # the order it matters. Never a verdict.
                summary=self._row_summary(day.teaching_count, day.cover_count,
                                          day.work_count, r.away_reason),
                teaches=r.member_id in teaches))

        # Teachers first and inside that the fullest day first, so the page opens
        # on the people the timetable actually loaded. Alphabetical inside a tie
        # keeps the order stable between refreshes.
        book.rows.sort(key=lambda x: (x.role != "teacher", not x.teaches,
                                      -(x.teaching + x.cover + x.work), x.name))

        capacity = teaching + cover + work + free
        book.slots_total = capacity
        book.slots_teaching = teaching + cover
        book.slots_work = work
        book.slots_free = free
        book.slots_away = away
        # No denominator on a day nobody was asked to work: a share of nothing
        # is not 0% and it is not 100%, it is a figure that does not exist.
        book.occupied_pct = (round(((teaching + cover + work) / capacity) * 100, 1)
                             if capacity and book.is_working_day else None)
        book.slices = self._slices(m, teaching + cover, buckets, free)
        book.headline = self._headline(book)
        return book

    def _row_summary(self, teaching: int, cover: int, work: int,
                     away_reason: str | None) -> str:
        if away_reason:
            return f"Away — {away_reason}"
        parts: list[str] = []
        if teaching:
            parts.append(f"{teaching} class{'' if teaching == 1 else 'es'}")
        if cover:
            parts.append(f"{cover} covered")
        if work:
            parts.append(f"{work} recorded")
        return " · ".join(parts) or "No classes today"

    def _slices(self, m: CurrentMember, teaching: int, buckets: dict[str, int],
                free: int) -> list[DaybookSlice]:
        """The ring: teaching · what the timesheet says the rest went on · free.

        Ordered so the ring reads outward from the school's core act, and folded
        at `MAX_SLICES` because past that the arcs are thinner than their own
        borders. The fold is NAMED ("3 more categories"), never silent.
        """
        out = [DaybookSlice(key="teaching", label="Teaching", periods=teaching,
                            color=TEACHING_COLOR)]
        ranked = sorted(buckets.items(), key=lambda kv: (-kv[1], kv[0]))
        for key, n in ranked[:MAX_SLICES]:
            out.append(DaybookSlice(key=key, label=label_for(key, m.org), periods=n,
                                    color=color_for(key, m.org)))
        rest = ranked[MAX_SLICES:]
        if rest:
            out.append(DaybookSlice(
                key="__rest", label=f"{len(rest)} more categories",
                periods=sum(n for _k, n in rest), color=SLATE))
        out.append(DaybookSlice(key="free", label="Free or unrecorded", periods=free,
                                color=FREE_COLOR))
        return [s for s in out if s.periods > 0]

    def _headline(self, book: Daybook) -> str:
        """A sentence, not a number (ux §1). It has to distinguish three days a
        bare percentage cannot: a closed school, a school that ran, and a school
        whose staff have not written anything down yet."""
        if book.closed_reason or not book.is_working_day:
            why = (f"The school was closed — {book.closed_reason}."
                   if book.closed_reason
                   else "Not a school day, so nothing was expected of anybody.")
            # Anything genuinely recorded on a closed day is still said — an
            # exam Saturday and a warden's evening are real work, and the last
            # thing this board may do is tell someone it did not happen.
            done = book.slots_teaching + book.slots_work
            if done:
                return (f"{why} {done} period{'' if done == 1 else 's'} were "
                        "recorded anyway.")
            return why
        if not book.slots_total:
            return "No timetable for this day yet, so there is no day to show."
        pct = book.occupied_pct or 0
        recorded = book.slots_work
        # The denominator is named, not just printed (ux §: every figure carries
        # its denominator). "184 staff periods" was the figure nobody could
        # reconcile against a 21-teacher timetable — saying whose periods they
        # are is what makes the number checkable by hand.
        on_duty = sum(1 for r in book.rows
                      if any(c.kind != "away" for c in r.cells))
        base = (f"{pct:g}% of the day's {book.slots_total} period slots across "
                f"{on_duty} teacher{'' if on_duty == 1 else 's'} were spoken "
                f"for — {book.slots_teaching} teaching")
        if recorded:
            base += f" and {recorded} recorded as other work"
        base += f", {book.slots_free} free."
        if not recorded:
            base += " Nobody has filled in a timesheet entry yet."
        return base

    # ── the overview's glimpse ───────────────────────────────────────────────
    def glimpse(self, m: CurrentMember, on: date | None = None,
                limit: int = 10) -> Daybook:
        """The same board, trimmed to what fits on the overview.

        Deliberately the same computation and the same payload shape — the
        summary block and the tab it links to cannot disagree about a figure
        neither of them computed twice.
        """
        book = self.board(m, on)
        book.rows_total = len(book.rows)
        book.rows = book.rows[:limit]
        return book
