"""P1-A: effective-teaching-days engine (SPRD §5.1 done-when). Pure — no DB."""

from datetime import date

from app.services import calendar as cal

MON_SAT = [0, 1, 2, 3, 4, 5]
# A Monday.
WK = date(2026, 4, 6)
YEAR_START, YEAR_END = date(2026, 4, 1), date(2027, 3, 31)


def _eff(pps, blocked):
    return cal.effective_periods(
        pps, WK, working_weekdays=MON_SAT, blocked=blocked,
        year_start=YEAR_START, year_end=YEAR_END,
    )


def test_full_week_gives_all_periods():
    assert _eff(6, set()) == 6.0  # Mon–Sat all teaching → full periods


def test_one_holiday_scales_down():
    # block the Wednesday → 5 of 6 working days available
    assert _eff(6, {date(2026, 4, 8)}) == 5.0


def test_exam_block_whole_week_zeroes_periods():
    blocked = set(cal.expand_blocked_dates([(WK, date(2026, 4, 11), True)]))  # Mon–Sat
    assert _eff(6, blocked) == 0.0


def test_non_teaching_event_does_not_block():
    # affects_teaching=False must NOT remove the day
    blocked = cal.expand_blocked_dates([(date(2026, 4, 8), date(2026, 4, 8), False)])
    assert blocked == set()
    assert _eff(6, blocked) == 6.0


def test_teaching_days_counts_working_minus_blocked():
    # one ordinary week Mon–Sun with a Sunday off = 6 working days; block 1 → 5
    blocked = {date(2026, 4, 8)}
    assert cal.teaching_days(WK, date(2026, 4, 12), MON_SAT, blocked) == 5


def test_sunday_is_not_a_teaching_day():
    assert not cal.is_teaching_day(date(2026, 4, 12), set(MON_SAT), set())  # Sunday


# ── DB-backed: the summary endpoint applies events to the year ────────────────
import uuid  # noqa: E402


def test_calendar_summary_reflects_events(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Cal Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()

    base = client.get(f"/api/v1/academics/calendar/summary?year_id={year['id']}", headers=h).json()
    assert base["teaching_days"] > 300  # Mon–Sat across a year

    # a 6-working-day exam block removes exactly its working days from the total
    client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": year["id"], "type": "exam_block", "title": "Exams",
        "start_date": "2026-09-21", "end_date": "2026-09-30"})  # Mon 21 – Wed 30
    after = client.get(f"/api/v1/academics/calendar/summary?year_id={year['id']}", headers=h).json()
    assert after["teaching_days"] < base["teaching_days"]
    assert len(after["events"]) == 1
