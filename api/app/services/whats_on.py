"""What's on — the read side `calendar_events` has never had (V1-7).

The school has painted holidays, exams, celebrations and events onto its year
calendar for a year, and the product has never once mentioned any of them back
to a human: the table's only consumer is the effective-days engine, whose job is
to *subtract* it from the teaching total. The single most-asked question about a
calendar — **what is on this week** — had no surface anywhere.

**One computation, three sources, many renderings** (ux §9, `S-121`):

  * student birthdays, DERIVED from `students.date_of_birth` (V1-2). Never
    stored as an event. If this file ever writes a birthday row, `S-121` was
    lost and the module has forked its own truth.
  * staff birthdays, from `memberships.date_of_birth` (`D-56`, self-entered).
  * the school's own `calendar_events`.

The catalogue is deliberately NOT a fourth source of the feed. A suggestion is
not a date on the school's calendar until a human approves it (`D-57`), and the
feed renders only what is true. Suggestions reach the admin through
`suggestions()` and nobody else — `Q-64` (a): the teacher's strip is never
provisional, because its whole value is that it costs zero attention and is
never wrong.

Nothing here writes `calendar_events` except `approve()`, which requires a human
press (`S-122`, made structural by `D-57`).
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.indian_states import normalise
from app.models import (
    AcademicYear,
    CalendarEvent,
    EventDecision,
    Membership,
    Observance,
    SchoolClass,
    Student,
    User,
)
from app.schemas.events import (
    ApproveIn,
    CatalogueBrowse,
    CatalogueRow,
    CostIn,
    CostMove,
    DecisionOut,
    DismissIn,
    FeedItem,
    LockCost,
    SuggestionOut,
    WhatsOn,
)
from app.services.calendar import (
    DEFAULT_WORKING_WEEKDAYS,
    event_rows,
    expand_blocked_dates,
    expand_partial_blocks,
)
from app.services.periods import visible_class_ids
from app.services.school_clock import today_in

# `S-126` — horizon by kind, not one "next 7 days". The founder's 7 days is
# right for a birthday and wrong for Independence Day: flag hoisting, rehearsals
# and a parent notice need two to three weeks. A calendar row surfaces over the
# full horizon; a birthday only once it is close.
DEFAULT_HORIZON = 21
BIRTHDAY_HORIZON = 7
MAX_FEED = 40

# The browse filter's "every state" value. An explicit sentinel rather than an
# empty string because the browser's query-string helper drops empty params —
# which would have made "All states" silently mean "my state", the one bug this
# filter cannot afford.
ALL_STATES_TOKEN = "all"

# The three lock levels (`D-58`) as (affects_teaching, keeps blocks_periods).
_LOCK = {
    "closed": (True, False),
    "periods": (True, True),
    "open": (False, False),
}


def _label(k: SchoolClass | None) -> str | None:
    if k is None:
        return None
    return k.name + (f"-{k.section}" if k.section else "")


def _same_day(dob: date, d: date) -> bool:
    """Day-and-month match, with 29 Feb landing on 28 Feb in a common year —
    otherwise a leap-year child is wished once every four years."""
    if dob.month == 2 and dob.day == 29:
        try:
            date(d.year, 2, 29)
        except ValueError:
            return d.month == 2 and d.day == 28
    return dob.month == d.month and dob.day == d.day


def nearest_working_day(d: date, working: set[date], horizon: int = 7) -> date:
    """`S-128` — the vacation birthday.

    A child born in mid-May never gets wished, for their whole time at the
    school, because the school is shut. Real schools wish them on the last
    working day before the break. Walk backwards first (the school's own habit),
    then forwards; if neither finds a working day inside the horizon the real
    date is returned and the card says it honestly rather than inventing one.
    """
    if d in working:
        return d
    for step in range(1, horizon + 1):
        back = d - timedelta(days=step)
        if back in working:
            return back
        fwd = d + timedelta(days=step)
        if fwd in working:
            return fwd
    return d


class WhatsOnService:
    def __init__(self, db: Session):
        self.db = db

    # ── shared reads ─────────────────────────────────────────────────────────
    def _year(self, org_id: uuid.UUID, year_id: uuid.UUID | None = None) -> AcademicYear | None:
        q = select(AcademicYear).where(AcademicYear.org_id == org_id)
        q = (q.where(AcademicYear.id == year_id) if year_id
             else q.where(AcademicYear.is_active.is_(True)))
        return self.db.scalar(q)

    def _working_set(self, year: AcademicYear | None, org_id: uuid.UUID,
                     start: date, end: date) -> set[date]:
        """Working days in the window. Uses the year's own weekdays + blocked
        dates rather than `calendar.org_working_days` only because the caller
        already has the year in hand; the definition is identical."""
        if year is None:
            return set()
        events = list(self.db.scalars(select(CalendarEvent).where(
            CalendarEvent.org_id == org_id,
            CalendarEvent.academic_year_id == year.id)))
        blocked = expand_blocked_dates(event_rows(events))
        ww = set(year.working_weekdays or DEFAULT_WORKING_WEEKDAYS)
        out, d = set(), start
        while d <= end:
            if d.weekday() in ww and d not in blocked:
                out.add(d)
            d += timedelta(days=1)
        return out

    # ── the feed ─────────────────────────────────────────────────────────────
    def feed(self, m: CurrentMember, on_date: date | None = None,
             horizon: int = DEFAULT_HORIZON, *, for_admin: bool = False,
             class_id: uuid.UUID | None = None) -> WhatsOn:
        """The school's feed, or one class's birthdays.

        `class_id` is the teacher's surface (founder, 2026-08-05). Standing in
        6-A she is shown 6-A's birthdays and **nothing else** — not the school's
        calendar, not a colleague's. Those are the admin's to act on, and a strip
        carrying them is the everything-feed she has already learned to ignore.
        Still one computation (`S-121`): the same rows, scoped — never a second
        birthday reader with its own idea of a leap year or a vacation.

        A class row is a roster read, so it obeys the one class-read rule
        (`periods.visible_class_ids`, AT-1) and is **blocked with a sentence
        rather than filtered to an empty list** (`S-46`) — a teacher shown
        nothing for a class she may not see would read it as a class with no
        birthdays.
        """
        if class_id is not None:
            allowed = visible_class_ids(self.db, m)
            if allowed is not None and class_id not in allowed:
                raise ForbiddenError("This is not your class.",
                                     code="not_your_class")
        today = on_date or today_in(m.org.timezone)
        end = today + timedelta(days=horizon)
        year = self._year(m.org_id)
        # Birthdays roll onto a working day, so the window has to look a week
        # either side of the horizon to find one.
        working = self._working_set(year, m.org_id, today - timedelta(days=7),
                                    end + timedelta(days=7))

        items: list[FeedItem] = []
        if class_id is None:
            items += self._calendar_items(m, today, end)
        items += self._birthday_items(m, today, end, working, class_id=class_id)

        items.sort(key=lambda i: (i.on_date, i.source != "calendar", i.title))
        for it in items:
            it.days_away = (it.on_date - today).days

        known, total = self._dob_coverage(m, class_id=class_id)
        out = WhatsOn(
            date=today,
            today=[i for i in items if i.on_date == today],
            upcoming=[i for i in items if i.on_date > today][:MAX_FEED],
            dob_known=known, dob_total=total,
        )
        if for_admin:
            out.pending_suggestions = len(self.suggestions(m, horizon=90))
        return out

    def _calendar_items(self, m: CurrentMember, start: date, end: date) -> list[FeedItem]:
        events = self.db.scalars(
            select(CalendarEvent)
            .where(CalendarEvent.org_id == m.org_id,
                   CalendarEvent.end_date >= start, CalendarEvent.start_date <= end)
            .order_by(CalendarEvent.start_date))
        out: list[FeedItem] = []
        for e in events:
            # A multi-day block shows on the day it starts (or today, if it is
            # already running) — one row, not five.
            shows_on = max(e.start_date, start)
            span = "" if e.start_date == e.end_date else f" · until {_fmt(e.end_date)}"
            detail = {
                "holiday": "School closed", "exam_block": "Exam",
                "celebration": "Celebration", "event": "Event",
            }.get(e.type, e.type)
            if e.blocks_periods:
                detail += f" · periods {', '.join(str(p) for p in e.blocks_periods)}"
            elif not e.affects_teaching:
                detail += " · school open"
            out.append(FeedItem(
                source="calendar", on_date=shows_on, title=e.title,
                detail=detail + span,
                event_id=e.id, event_type=e.type,
                affects_teaching=e.affects_teaching, blocks_periods=e.blocks_periods))
        return out

    def _birthday_items(self, m: CurrentMember, start: date, end: date,
                        working: set[date], *,
                        class_id: uuid.UUID | None = None) -> list[FeedItem]:
        """`S-133` — the day, never the age. A DOB on a class list, or "turns 12
        today" on a screen shown to a room, is a cost with no benefit; the full
        date stays on the student's own record where the register needs it."""
        b_end = min(end, start + timedelta(days=BIRTHDAY_HORIZON))
        q = (select(Student, SchoolClass)
             .outerjoin(SchoolClass, SchoolClass.id == Student.class_id)
             .where(Student.org_id == m.org_id, Student.status == "active",
                    Student.date_of_birth.is_not(None)))
        if class_id is not None:
            q = q.where(Student.class_id == class_id)
        rows = self.db.execute(q).all()
        out: list[FeedItem] = []
        for s, klass in rows:
            for d in _dates_between(start, b_end):
                if not _same_day(s.date_of_birth, d):
                    continue
                shown = nearest_working_day(d, working) if working else d
                if shown < start or shown > end:
                    shown = d
                out.append(FeedItem(
                    source="birthday", on_date=shown,
                    actual_date=d if shown != d else None,
                    title=s.full_name, detail="Birthday",
                    student_id=s.id, class_label=_label(klass)))
                break

        # A class row is about that class's children. A colleague's birthday is
        # the staffroom's business and reaches the admin's notice instead.
        if class_id is not None:
            return out

        staff = self.db.execute(
            select(Membership, User.name)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == m.org_id, Membership.status == "active",
                   Membership.date_of_birth.is_not(None))
        ).all()
        for mem, name in staff:
            for d in _dates_between(start, b_end):
                if not _same_day(mem.date_of_birth, d):
                    continue
                shown = nearest_working_day(d, working) if working else d
                if shown < start or shown > end:
                    shown = d
                out.append(FeedItem(
                    source="staff_birthday", on_date=shown,
                    actual_date=d if shown != d else None,
                    title=name or "A colleague", detail="Birthday · staff",
                    member_id=mem.id))
                break
        return out

    def _dob_coverage(self, m: CurrentMember, *,
                      class_id: uuid.UUID | None = None) -> tuple[int, int]:
        """`S-124` — the figure with its denominator. An empty card that says
        *"birthdays known for 41 of 486 students"* tells you how to fill it; an
        empty card that says nothing looks broken.

        The denominator is the feed's own scope: a class row quoting the whole
        school's coverage would be a figure about somebody else's students.
        """
        where = [Student.org_id == m.org_id, Student.status == "active"]
        if class_id is not None:
            where.append(Student.class_id == class_id)
        total = self.db.scalar(select(func.count(Student.id)).where(*where)) or 0
        known = self.db.scalar(select(func.count(Student.id)).where(
            *where, Student.date_of_birth.is_not(None))) or 0
        return int(known), int(total)

    # ── the catalogue, scoped to this school (`D-61`) ────────────────────────
    def suggestions(self, m: CurrentMember, horizon: int = 90,
                    on_date: date | None = None, *,
                    include_minor: bool = False) -> list[SuggestionOut]:
        """Catalogue entries this school has not decided on yet.

        Scoped by **address → state** and **board** (`D-61`) — both facts setup
        already collects for other reasons, so a school is never asked to
        declare a region or a religion. A NULL `state`/`board` on the entry
        means everybody.

        Dismissal keys on `key`, not on the row (`S-148`): saying *"we don't
        observe this"* has to survive into next year's catalogue, or the same
        suggestion returns every year and the admin learns to ignore the feed.
        """
        today = on_date or today_in(m.org.timezone)
        end = today + timedelta(days=horizon)
        # V1-19 — `states` is a set, and the school's own value is free text
        # normalised to a canonical token. A school whose state we cannot place
        # sees the all-India rows and no regional ones: thin, but never wrong.
        # The old `Observance.state == (m.org.state or "")` compared against
        # `""` for an unset school, which matched nothing and read identically
        # to an empty catalogue — the failure had no symptom.
        token = normalise(m.org.state)
        state_clause = (
            Observance.states.is_(None) if token is None
            else or_(Observance.states.is_(None), Observance.states.any(token)))
        stmt = (select(Observance)
                .where(Observance.is_active.is_(True),
                       Observance.date >= today, Observance.date <= end,
                       state_clause,
                       or_(Observance.board.is_(None),
                           Observance.board == (m.org.board or ""))))
        # `S-125`, and it only became visible once a real corpus existed: the
        # catalogue holds the whole UN list, so an unfiltered queue over a year
        # returns ~250 rows — "World Steelpan Day" beside Independence Day — and
        # on the calendar it paints a third of the year as "decide me". A card
        # with something on it every single day stops being read inside a week.
        # Minor dates stay in the catalogue and stay searchable in Show events;
        # they just never queue themselves.
        if not include_minor:
            stmt = stmt.where(Observance.tier == "major")
        rows = list(self.db.scalars(stmt.order_by(Observance.date)))
        if not rows:
            return []

        decisions = self.db.execute(
            select(EventDecision.observance_key, EventDecision.action,
                   EventDecision.observance_id)
            .where(EventDecision.org_id == m.org_id,
                   EventDecision.observance_key.in_([r.key for r in rows]))).all()
        dismissed = {k for k, action, _ in decisions if action == "dismissed"}
        approved: dict[uuid.UUID, int] = defaultdict(int)
        for _k, action, oid in decisions:
            if action == "approved" and oid:
                approved[oid] += 1

        out: list[SuggestionOut] = []
        for r in rows:
            if r.key in dismissed:
                continue
            # `prep_days` is deliberately NOT a second filter here. The horizon
            # already bounds this list, and this is the admin's decision queue —
            # hiding an undecided date because its rehearsal window has not
            # opened means the queue silently disagrees with itself week to
            # week. `S-126` is about *ordering* and about when a date reaches
            # the CARD; the queue shows everything still open.
            out.append(SuggestionOut(
                id=r.id, key=r.key, name=r.name, date=r.date, end_date=r.end_date,
                kind=r.kind, tier=r.tier, prep_days=r.prep_days, tradition=r.tradition,
                source=r.source, note=r.note, days_away=(r.date - today).days,
                approved_count=approved.get(r.id, 0)))
        return out

    # ── the catalogue, browsable (V1-20, "Show events") ──────────────────────
    def browse(self, m: CurrentMember, *, state: str | None = None,
               year: int | None = None, q: str | None = None,
               include_minor: bool = True, limit: int = 500) -> CatalogueBrowse:
        """The whole researched corpus, filterable by state — the table behind
        the year calendar's **Show events** button.

        Deliberately NOT scoped to the school's own state by default the way
        `suggestions()` is. The two answer different questions: the feed asks
        *"what should I act on"* (and must stay narrow, or nobody reads it),
        this asks *"what is in the calendar you shipped"* (and must be complete,
        or the admin cannot tell a missing date from an unscoped one). The
        school's own state is the **preselected** filter, not a fence.

        `applies_here` rides on every row so the table can say which of them
        would actually reach this school — the one thing a bare list of national
        holidays cannot tell a principal in Kerala.
        """
        token = normalise(m.org.state)
        # Three cases, and collapsing any two of them makes the screen lie:
        #   state is None  → the caller has not chosen; default to this school's
        #                    own state, which is what the dropdown shows first.
        #   state == ""    → the caller explicitly asked for every state.
        #   otherwise      → that state.
        # Treating None and "" alike would render "Kerala" in the picker over a
        # table containing every state in the country.
        if state is None:
            want = token
        elif state.strip().lower() in ("", ALL_STATES_TOKEN):
            want = None
        else:
            want = normalise(state)

        stmt = select(Observance).where(Observance.is_active.is_(True))
        if want:
            stmt = stmt.where(or_(Observance.states.is_(None),
                                  Observance.states.any(want)))
        if year:
            stmt = stmt.where(func.extract("year", Observance.date) == year)
        if q:
            stmt = stmt.where(Observance.name.ilike(f"%{q.strip()}%"))
        if not include_minor:
            stmt = stmt.where(Observance.tier == "major")
        rows = list(self.db.scalars(stmt.order_by(Observance.date, Observance.name)
                                    .limit(limit)))

        # What THIS school decided — one query, keyed on the stable `key` so a
        # dismissal made against last year's row still reads as decided.
        decisions: dict[str, set[str]] = defaultdict(set)
        if rows:
            for key, action in self.db.execute(
                    select(EventDecision.observance_key, EventDecision.action)
                    .where(EventDecision.org_id == m.org_id,
                           EventDecision.observance_key.in_([r.key for r in rows]))).all():
                decisions[key].add(action)

        # The dropdown's options and the year tabs come from the corpus itself,
        # so the filter can never offer a value that returns nothing.
        all_states: set[str] = set()
        years: set[int] = set()
        for st, yr in self.db.execute(
                select(Observance.states, func.extract("year", Observance.date))
                .where(Observance.is_active.is_(True))).all():
            all_states.update(st or ())
            if yr:
                years.add(int(yr))

        out = CatalogueBrowse(
            org_state=token, filter_state=want,
            years=sorted(years), states=sorted(all_states), total=len(rows))
        for r in rows:
            actions = decisions.get(r.key, set())
            out.rows.append(CatalogueRow(
                id=r.id, key=r.key, name=r.name, date=r.date, end_date=r.end_date,
                kind=r.kind, tier=r.tier, states=r.states, tradition=r.tradition,
                source=r.source, note=r.note,
                applies_here=(not r.states) or (token is not None and token in r.states),
                decided=bool(actions), approved="approved" in actions))
        return out

    # ── the decision (`D-57` — approval is the commit) ───────────────────────
    def approve(self, m: CurrentMember, observance_id: uuid.UUID,
                body: ApproveIn) -> DecisionOut:
        """The only route from the catalogue to `calendar_events`, and it needs
        a human press every time (`S-122`).

        The date is **the admin's**, pre-filled from the suggestion but editable
        (`D-79`) — which is what makes *"Christmas — school closed, 25 Dec"* and
        *"Christmas celebration — runs as usual, 22 Dec"* two approvals from one
        suggested row, and what removes the wrong-date risk structurally instead
        of accepting it.
        """
        obs = self.db.scalar(select(Observance).where(Observance.id == observance_id))
        if obs is None:
            raise NotFoundError("Suggestion")
        year = self._year(m.org_id)
        if year is None:
            raise ValidationError("Create an academic year before approving dates.")
        start = body.start_date
        end = body.end_date or start
        if start < year.start_date or end > year.end_date:
            raise ValidationError(
                "That date is outside the academic year "
                f"({year.start_date:%d %b %Y} – {year.end_date:%d %b %Y}).")

        affects, keep_periods = _LOCK[body.lock]
        event = CalendarEvent(
            org_id=m.org_id, academic_year_id=year.id, type=body.event_type,
            title=(body.title or obs.name).strip(), start_date=start, end_date=end,
            affects_teaching=affects,
            blocks_periods=body.blocks_periods if keep_periods else None,
            # The school's row remembers where the date came from — the admin
            # approved a suggestion, not a fact they typed (`S-150`).
            notes=body.note or f"Approved from: {obs.source}",
        )
        self.db.add(event)
        self.db.flush()

        decision = EventDecision(
            org_id=m.org_id, observance_id=obs.id, observance_key=obs.key,
            action="approved", calendar_event_id=event.id,
            decided_by_member_id=m.membership.id, note=body.note)
        self.db.add(decision)
        self.db.flush()
        return DecisionOut.model_validate(decision)

    def dismiss(self, m: CurrentMember, observance_id: uuid.UUID,
                body: DismissIn) -> DecisionOut:
        """`S-148` — append-only and permanent. A dismissal is a row, not a
        delete, and it keys on the observance's stable `key` so next year's
        entry does not come back."""
        obs = self.db.scalar(select(Observance).where(Observance.id == observance_id))
        if obs is None:
            raise NotFoundError("Suggestion")
        decision = EventDecision(
            org_id=m.org_id, observance_id=obs.id, observance_key=obs.key,
            action="dismissed", decided_by_member_id=m.membership.id, note=body.note)
        self.db.add(decision)
        self.db.flush()
        return DecisionOut.model_validate(decision)

    # ── `S-143` the cost, before they commit ─────────────────────────────────
    def lock_cost(self, m: CurrentMember, body: CostIn) -> LockCost:
        """What locking these dates costs, said before the admin commits.

        `D-59` defers "adjusting the plan", but half of that adjustment is not
        deferrable and already happens: `effective_periods` is computed live, so
        the instant three days are locked for Diwali every class-subject's
        remaining capacity shrinks and RAG colours move across the school with
        nothing explaining why. A principal who sees six subjects turn amber
        after locking a holiday concludes the system is broken.

        A second caller of `PlannerService.forecast_org` (DASH3 PR-6), not a new
        engine — which is the only reason this is affordable on a sheet.
        """
        from app.services.planner import PlannerService  # noqa: PLC0415

        year = self._year(m.org_id, body.academic_year_id)
        if year is None:
            raise NotFoundError("Academic year")
        start, end = body.start_date, body.end_date or body.start_date
        if end < start:
            raise ValidationError("end_date must be on or after start_date.")

        affects, keep_periods = _LOCK[body.lock]
        periods = body.blocks_periods if keep_periods else None
        ppd = max(year.periods_per_day or 8, 1)

        existing = list(self.db.scalars(select(CalendarEvent).where(
            CalendarEvent.org_id == m.org_id,
            CalendarEvent.academic_year_id == year.id)))
        rows = event_rows(existing)
        already = expand_blocked_dates(rows)
        already_partial = expand_partial_blocks(rows)
        ww = set(year.working_weekdays or DEFAULT_WORKING_WEEKDAYS)

        working = [d for d in _dates_between(start, end) if d.weekday() in ww]
        blocked_already = sum(1 for d in working if d in already)
        out = LockCost(working_days=len(working), already_blocked=blocked_already)

        if affects:
            for d in working:
                if d in already:
                    continue
                if periods:
                    fresh = {int(p) for p in periods} - already_partial.get(d, set())
                    out.periods_lost += len(fresh)
                    out.days_lost += round(len(fresh) / ppd, 2)
                else:
                    lost_already = len(already_partial.get(d, set()))
                    out.periods_lost += max(0, ppd - lost_already)
                    out.days_lost += 1
            out.days_lost = round(out.days_lost, 2)

        planner = PlannerService(self.db)
        if out.periods_lost:
            before = {f.class_subject_id: f for f in planner.forecast_org(m, year.id)}
            hypothetical = rows + [(start, end, True, list(periods) if periods else None)]
            after = {f.class_subject_id: f
                     for f in planner.forecast_org(m, year.id, extra_events=hypothetical)}
            for cs_id, b in before.items():
                a = after.get(cs_id)
                if a is None or a.status == b.status:
                    continue
                # Only a RAG move is a move. `unplanned` → `unplanned` is not a
                # cost, and neither is a status word changing shade of neutral.
                if b.status in ("green", "amber", "red") and a.status in (
                        "green", "amber", "red"):
                    out.moves.append(CostMove(
                        class_label=b.class_label, subject_name=b.subject_name,
                        from_status=b.status, to_status=a.status))
            out.unaffected = max(0, len(before) - len(out.moves))

        out.sentence = _cost_sentence(out, start, end, affects, periods)
        return out


def _dates_between(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _fmt(d: date) -> str:
    """"15 Aug". `%-d` is glibc-only and this product is developed on Windows —
    lstrip the zero instead of shipping a format string that raises there."""
    return d.strftime("%d %b").lstrip("0")


def _cost_sentence(cost: LockCost, start: date, end: date, affects: bool,
                   periods: list[int] | None) -> str:
    """One sentence, and it leads (ux §1 — a sentence, not a number)."""
    span = _fmt(start) if start == end else f"{_fmt(start)}–{_fmt(end)}"
    if not affects:
        return f"{span} stays a full teaching day — this only marks the calendar."
    if not cost.working_days:
        return f"{span} is not a working day, so nothing is lost."
    if not cost.periods_lost:
        return f"{span} is already closed — locking it again costs nothing."
    what = ("periods " + ", ".join(str(p) for p in periods)) if periods else "the whole day"
    head = f"Locking {span} ({what}) removes {cost.periods_lost} periods."
    if not cost.moves:
        return head + " No class-subject changes colour."
    named = ", ".join(f"{mv.class_label} {mv.subject_name} {mv.from_status}→{mv.to_status}"
                      for mv in cost.moves[:3])
    more = "" if len(cost.moves) <= 3 else f" and {len(cost.moves) - 3} more"
    return f"{head} {named}{more}. {cost.unaffected} others are unaffected."
