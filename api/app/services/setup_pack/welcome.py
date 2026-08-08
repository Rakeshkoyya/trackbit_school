"""The handover sheet (SETUP-REDESIGN-PLAN §7, G8).

The last thing that happens to a school: a one-page document the operator prints
or emails, saying who logs in where, what the school can change itself, and what
to ask us for.

Until now handover was a timestamp and nothing else. `create_school` returned the
admin's temp password in an API response the operator had to notice and copy, and
after that there was no artefact at all — no school code, no portal address,
nothing to hand a principal.

**It deliberately contains no passwords.** Every password here is hashed on the
way in and cannot be read back, so a sheet claiming to carry them would either be
lying or forcing a reset nobody asked for. Passwords are handed over at the
moment they are generated — the import screen shows staff logins once — and this
sheet says so plainly rather than leaving a blank the operator wonders about.
"""

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.worksheet import Worksheet

from app.core.config import settings

_TITLE = Font(bold=True, size=15)
_HEAD = Font(bold=True)
_MUTED = Font(color="666666")


def _writer(ws: Worksheet):
    row = {"n": 1}

    def line(text: str = "", font: Font | None = None) -> None:
        cell = ws.cell(row=row["n"], column=2, value=text)
        if font:
            cell.font = font
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        row["n"] += 1

    return line


def build_welcome(*, school_name: str, school_code: str | None,
                  admin_logins: list[tuple[str, str]],
                  parent_portal_enabled: bool) -> bytes:
    """`admin_logins` is [(person's name, the email or username they sign in with)]."""
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    wb = Workbook()
    ws = wb.active
    ws.title = "Welcome"
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 96
    line = _writer(ws)

    line(f"Welcome to TrackBit — {school_name}", _TITLE)
    line("Everything below is ready. Keep this sheet.", _MUTED)
    line()

    line("SIGNING IN", _HEAD)
    line(f"Staff — teachers and admins:   {base}/login")
    for name, login in admin_logins:
        line(f"   {name} signs in as {login}")
    if not admin_logins:
        line("   (no admin account on record — tell us and we will create one)")
    line("Passwords were given to you separately, at the moment each account was "
         "created. They are stored hashed and cannot be read back, so if one is "
         "lost use 'Forgot password' on the sign-in page — nobody, including us, "
         "can look it up.", _MUTED)
    line("Everyone is asked to choose their own password the first time they "
         "sign in.", _MUTED)
    line()

    line("PARENTS", _HEAD)
    if parent_portal_enabled and school_code:
        line(f"Parent portal:   {base}/parent/login")
        line(f"Your school code:   {school_code}")
        line("A parent signs in with the school code, their mobile number and "
             "their child's date of birth. Nothing else. That is why the dates of "
             "birth on the register matter — a child without one has a parent who "
             "cannot get in.", _MUTED)
    elif not parent_portal_enabled:
        line("The parent portal is switched off for your school. Tell us when you "
             "want it on.")
    else:
        line("The parent portal has no school code yet — tell us and we will "
             "issue one.")
    line()

    line("YOUR FIRST DAY", _HEAD)
    for step in (
        "Sign in and change your password.",
        "Check the class list and the timetable look right.",
        "Ask your teachers to sign in once, so nobody is locked out on a Monday "
        "morning.",
        "Teachers mark attendance and log homework from their own screen — there "
        "is nothing to set up first.",
    ):
        line(f"   • {step}")
    line()

    line("WHAT YOU CAN CHANGE YOURSELF", _HEAD)
    for item in (
        "Admit, transfer and remove students — one at a time, or a whole list at "
        "the start of a year.",
        "Add and remove staff, and reset their passwords.",
        "Fix a date of birth, a phone number or a guardian's name.",
        "Declare a holiday or an exam week.",
        "Fees: structures, collection, receipts.",
        "Everything your teachers do every day.",
    ):
        line(f"   • {item}")
    line()

    line("WHAT TO ASK US FOR", _HEAD)
    line("Your school's structure is set up and maintained by TrackBit, so it "
         "cannot drift by accident once teachers are working against it. Send us "
         "an email and we will make the change:")
    for item in (
        "A new class or section, or a class that has closed.",
        "A new subject, or a change to who teaches what.",
        "A change to the weekly period allocation or the timetable.",
        "Chapters added to the syllabus — including a term you had not planned "
        "yet when we set you up.",
        "The academic year, its terms, or the daily bell schedule.",
    ):
        line(f"   • {item}")
    line()
    line("If you are not sure which side something falls on, just ask us.", _MUTED)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def welcome_filename(school_name: str | None) -> str:
    safe = "".join(ch for ch in (school_name or "")
                   if ch.isalnum() or ch in " -_").strip()
    slug = safe.replace(" ", "-") if safe else "School"
    return f"TrackBit-Welcome-{slug}.xlsx"
