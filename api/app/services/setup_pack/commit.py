"""Write the pack (SETUP-REDESIGN-PLAN §7, phase P3).

Runs only after `validate()` reports no blockers, and only from the operator's
screen. Three properties it must have:

  * **One transaction.** Nothing here commits — it flushes and lets the request's
    session own the boundary. A pack that fails on the Timetable sheet must leave
    no classes behind, because a half-built school is worse than a rejected file.
  * **Re-runnable.** The operator uploads the corrected pack three times. Every
    write is keyed on something natural (year label, class + section, class +
    subject, admission number, teacher name) so the second upload updates rather
    than doubles.
  * **Additive on syllabus** (D-4). "Later they add more data" is the normal path
    for a mid-year school: it sends Terms 1–2 in August and Term 3 in December.
    Appending must never require destroying what already has teaching logged
    against it, so `replace_syllabus` defaults to False and is the caller's
    deliberate choice.

Students and staff are **not** written here. `RosterImporter.commit` and
`StaffImporter.commit` already own guardians, category creation, DOB refusal,
global-username collisions and the "same name in this org" skip — all of it
learned from real school files. Both read their values through
`val(row, field) → row[mapping[field]]`, so an identity mapping over the pack's
own field names drives them unchanged. The pack's Students columns were named to
match `roster_import.TARGET_FIELDS` exactly for this reason.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    CalendarEvent,
    ClassSubject,
    ExamPortion,
    ExamPortionUnit,
    FeeInstallmentTemplate,
    FeeStructure,
    Membership,
    Organization,
    SchoolClass,
    Student,
    Subject,
    SyllabusUnit,
    Term,
    TimetableSlot,
    User,
)
from app.schemas.fees import StudentFeeCreate
from app.services import bell
from app.services.fees import FeeService
from app.services.planner import PlannerService
from app.services.roster_import import RosterImporter
from app.services.setup_pack.parse import ParsedPack, fill_down
from app.services.setup_pack.specs import (
    BY_KEY,
    EXAMS_KEY,
    EXAMS_TITLE,
    PLANS_KEY,
    PLANS_TITLE,
)
from app.services.setup_pack.validate import term_windows, to_date, to_int
from app.services.staff_import import StaffImporter
from app.services.syllabus_import import SyllabusImporter

WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6}
WEEK_SPANS = {"mon fri": [0, 1, 2, 3, 4], "mon sat": [0, 1, 2, 3, 4, 5],
              "mon sun": [0, 1, 2, 3, 4, 5, 6]}
# The Calendar sheet's two words, and what the calendar module calls them.
# "exam" is deliberately absent: a term IS its exam, so the exam dates live on
# the Terms sheet and the block is written from there. A calendar row that only
# knew *when* an exam week was left the syllabus and the exam unacquainted.
EVENT_TYPES = {"holiday": "holiday", "event": "event"}

# Violations that mean "this plan cannot be taught as written", so locking it
# would be promising something the calendar cannot deliver. Everything else —
# notably `unsized` — is a state the school is allowed to be in.
UNLOCKABLE = {"capacity", "coverage"}
DEFAULT_PERIOD_MINUTES = 40
DEFAULT_FIRST_PERIOD = "08:30"


@dataclass
class SheetResult:
    key: str
    title: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class CommitResult:
    academic_year_id: uuid.UUID | None = None
    sheets: list[SheetResult] = field(default_factory=list)
    # Staff logins, to be handed over — never logged, never persisted.
    credentials: list[dict] = field(default_factory=list)

    def sheet(self, key: str) -> SheetResult:
        return next(s for s in self.sheets if s.key == key)


def _norm(text: str | None) -> str:
    return (text or "").strip().lower()


def _norm_title(text: str | None) -> str:
    """Chapter titles are matched across two sheets a human filled in, so a
    double space between words must not stop a portion resolving."""
    return " ".join(str(text or "").strip().lower().split())


def _identity(fields: list[str]) -> dict[str, str]:
    """The mapping that lets the existing importers read pack rows directly."""
    return {f: f for f in fields}


def _units_from_rows(rows: list[dict]) -> list[dict]:
    """Flat pack rows → the nested `units` shape `SyllabusImporter` expects.

    The one real difference from `syllabus_import.rows_to_units`: **Topic is
    optional** (D-5). The founder's reference file has no Topic column at all —
    schools plan by chapter — so a chapter with no topic rows becomes one topic
    named for the chapter, carrying the chapter's periods. Coverage stays correct
    because `core/coverage.py` weights by topic periods, and one topic holding
    the chapter's periods is arithmetically the chapter.

    Keyed on (term, chapter) like the original: the same chapter name may
    legitimately appear in two terms, and merging them would fuse two planning
    windows into one.
    """
    units: list[dict] = []
    current: tuple[str | None, str] | None = None

    for row in rows:
        chapter = (row.get("chapter") or "").strip()
        if not chapter:
            continue
        term = (row.get("term") or "").strip() or None
        key = (term, chapter)
        if key != current:
            units.append({"title": chapter, "term": term, "topics": []})
            current = key
        units[-1]["topics"].append({
            "title": chapter,
            "est_periods": to_int(row.get("periods")),
        })
    return [u for u in units if u["topics"]]


class PackCommitter:
    def __init__(self, db: Session):
        self.db = db

    # ── entry point ──────────────────────────────────────────────────────────
    def commit(self, m: CurrentMember, pack: ParsedPack, *,
               replace_syllabus: bool = False) -> CommitResult:
        result = CommitResult()
        year = self._school(m, pack, result)
        result.academic_year_id = year.id
        exams = self._terms(m, pack, year, result)
        staff = self._staff(m, pack, result)
        classes = self._classes(m, pack, year, staff, result)
        offered = self._assignments(m, pack, classes, staff, result)
        self._syllabus(m, pack, classes, offered, result, replace_syllabus)
        self._calendar(m, pack, year, result)
        self._portions(m, exams, offered, result)
        self._students(m, pack, year, result)
        self._timetable(m, pack, year, classes, offered, result)
        self._fees(m, pack, year, result)
        # Last, and only after the calendar and the exams exist: a plan paces
        # around holidays and exam blocks, so generating before them would lay
        # teaching onto days the school is shut.
        self._plans(m, year, offered, result)
        self.db.flush()
        return result

    def _result(self, result: CommitResult, key: str) -> SheetResult:
        out = SheetResult(key=key, title=BY_KEY[key].title)
        result.sheets.append(out)
        return out

    # ── 1. the school and its year ───────────────────────────────────────────
    def _school(self, m: CurrentMember, pack: ParsedPack,
                result: CommitResult) -> AcademicYear:
        out = self._result(result, "school")
        label = (pack.setting("year_label") or "").strip()
        start = to_date(pack.setting("year_start"))
        end = to_date(pack.setting("year_end"))

        year = self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == m.org_id, AcademicYear.label == label))
        if year is None:
            year = AcademicYear(org_id=m.org_id, label=label, start_date=start,
                                end_date=end, is_active=True)
            self.db.add(year)
            out.created += 1
        else:
            year.start_date, year.end_date = start, end
            out.updated += 1

        year.tracking_start_date = to_date(pack.setting("tracking_start"))
        year.working_weekdays = WEEK_SPANS.get(
            " ".join(_norm(pack.setting("working_days")).replace("-", " ").split()),
            [0, 1, 2, 3, 4, 5])
        year.periods_per_day = to_int(pack.setting("periods_per_day")) or 8
        year.period_times = self._period_times(pack, year.periods_per_day)
        self.db.flush()
        # TT-2: the pack still describes the day with four numbers, and that is
        # the school's STARTING shape. Opening it as a bell schedule is what
        # makes every later edit — a 15:30 homework block, a moved lunch — an
        # append rather than an overwrite of what the school first told us.
        # `ensure` is idempotent, so re-uploading a pack never rewrites a day the
        # school has since changed.
        bell.ensure(self.db, m.org_id, year, list(year.period_times or []),
                    year.tracking_start_date or year.start_date or date.today())
        self._activate(m, year)
        self._organization(m, pack, out)
        self.db.flush()
        if year.tracking_start_date:
            out.notes.append(
                f"Tracking starts {year.tracking_start_date:%d %b %Y} — the school "
                f"joined part-way through the year.")
        return year

    def _activate(self, m: CurrentMember, year: AcademicYear) -> None:
        """Exactly one active year. The pack is scoped to one, so uploading it is
        a statement about which year the school is running."""
        for other in self.db.scalars(select(AcademicYear).where(
                AcademicYear.org_id == m.org_id, AcademicYear.id != year.id)):
            other.is_active = False
        year.is_active = True

    def _period_times(self, pack: ParsedPack, periods: int) -> list[dict]:
        """The bell schedule, built from four numbers. Left out entirely rather
        than half-invented if the school did not give a readable start time."""
        first = (pack.setting("first_period_start") or DEFAULT_FIRST_PERIOD).strip()
        try:
            hour, minute = (int(p) for p in first.split(":")[:2])
        except ValueError:
            return []
        length = to_int(pack.setting("period_minutes")) or DEFAULT_PERIOD_MINUTES
        lunch_after = to_int(pack.setting("lunch_after_period"))
        lunch_len = to_int(pack.setting("lunch_minutes")) or 0

        def hhmm(total: int) -> str:
            return f"{(total // 60) % 24:02d}:{total % 60:02d}"

        clock = hour * 60 + minute
        times: list[dict] = []
        for number in range(1, periods + 1):
            times.append({"start": hhmm(clock), "end": hhmm(clock + length),
                          "kind": "period"})
            clock += length
            if lunch_after and number == lunch_after and lunch_len:
                times.append({"start": hhmm(clock), "end": hhmm(clock + lunch_len),
                              "kind": "lunch"})
                clock += lunch_len
        return times

    def _organization(self, m: CurrentMember, pack: ParsedPack,
                      out: SheetResult) -> None:
        """Only overwrite what the school actually filled in — the operator typed
        the name and state when creating the org, and a blank cell must not wipe
        it (a blank means 'not known', everywhere)."""
        org = m.org
        for key, attr in (("school_name", "name"), ("address", "address"),
                          ("state", "state"), ("board", "board")):
            value = pack.setting(key)
            if value:
                setattr(org, attr, value.strip())
        # The parent-login code. Upper-cased because `parent_auth` matches it
        # case-insensitively, and refused if another school holds it — the
        # column is UNIQUE, and a clash would send one school's parents to
        # another school's door.
        code = (pack.setting("school_code") or "").strip().upper()
        if code and code != (org.school_code or "").upper():
            clash = self.db.scalar(select(Organization.name).where(
                func.upper(Organization.school_code) == code,
                Organization.id != org.id))
            if clash:
                raise ValidationError(
                    f"School code {code} already belongs to {clash}. "
                    f"A code identifies one school to its parents.")
            org.school_code = code
            out.notes.append(f"Parent-login code set to {code}.")

        portal = pack.setting("parent_portal")
        if portal:
            org.parent_portal_enabled = _norm(portal) in {"yes", "true", "y"}
            if not org.parent_portal_enabled:
                out.notes.append("Parent portal is off — parents cannot log in.")

    # ── 2. terms ─────────────────────────────────────────────────────────────
    def _terms(self, m: CurrentMember, pack: ParsedPack, year: AcademicYear,
               result: CommitResult) -> dict[str, uuid.UUID]:
        """A term and its exam, written together (founder, 2026-08-08).

        The school states one date range — when the term exam runs. From it: the
        term ends on the exam's last day and starts the day after the previous
        term's exam; and an `exam_block` sits on the exam dates, so the planner
        treats them as non-teaching and paces the syllabus into the days before.
        `term_windows` owns that derivation for both the validator and here, so
        the two cannot disagree.

        Returns {lowercased term name: exam_event_id} for the portion pass.
        """
        out = self._result(result, "terms")
        existing = {_norm(t.name): t for t in self.db.scalars(select(Term).where(
            Term.org_id == m.org_id, Term.academic_year_id == year.id))}
        exams: dict[str, uuid.UUID] = {}

        for window in term_windows(pack):
            name, start, end = window["name"], window["start"], window["end"]
            if not name or not start or not end:
                out.skipped += 1
                continue
            term = existing.get(_norm(name))
            if term is None:
                term = Term(org_id=m.org_id, academic_year_id=year.id, name=name,
                            start_date=start, end_date=end)
                self.db.add(term)
                out.created += 1
            else:
                term.start_date, term.end_date = start, end
                out.updated += 1
            self.db.flush()

            event = self._exam_event(m, year, window["exam_name"],
                                     window["exam_start"] or end, end)
            exams[_norm(name)] = event.id
        self.db.flush()
        if exams:
            out.notes.append(
                f"{len(exams)} term exam(s) placed on the calendar — each term "
                f"ends on its exam's last day.")
        return exams

    # ── 3. staff ─────────────────────────────────────────────────────────────
    def _staff(self, m: CurrentMember, pack: ParsedPack,
               result: CommitResult) -> dict[str, uuid.UUID]:
        """Delegates to StaffImporter, then applies the pack's Role column —
        which that importer has no concept of, since it only ever made teachers.

        Returns {lowercased name: membership_id} for the class-teacher and
        assignment passes that follow.
        """
        out = self._result(result, "staff")
        rows = [
            # `employee_id` is the pack's word for what staff_import calls a
            # username; `assignments` stays empty because the pack gives each
            # assignment its own row on its own sheet.
            {"full_name": r.get("full_name"), "username": r.get("employee_id"),
             "email": r.get("email"), "phone": r.get("phone"),
             "date_of_birth": r.get("date_of_birth"), "assignments": None}
            for r in pack.rows("staff")
        ]
        report = StaffImporter(self.db).commit(
            m, mapping=_identity(["full_name", "username", "email", "phone",
                                  "date_of_birth", "assignments"]),
            rows=rows, academic_year_id=None)
        out.created = report["created_count"]
        out.skipped = report["skipped"]
        result.credentials = report["created"]

        self._apply_roles(m, pack, out)
        return self._membership_map(m)

    def _apply_roles(self, m: CurrentMember, pack: ParsedPack,
                     out: SheetResult) -> None:
        """Two roles only. Anything that is not 'admin' is a teacher — wardens
        and coordinators included."""
        admins = {_norm(r.get("full_name")) for r in pack.rows("staff")
                  if _norm(r.get("role")) == "admin"}
        if not admins:
            return
        for membership, user in self.db.execute(
                select(Membership, User).join(User, User.id == Membership.user_id)
                .where(Membership.org_id == m.org_id)).all():
            if _norm(user.name) in admins and membership.org_role != "admin":
                membership.org_role = "admin"
                out.updated += 1
        self.db.flush()

    def _membership_map(self, m: CurrentMember) -> dict[str, uuid.UUID]:
        return {
            _norm(user.name): membership.id
            for membership, user in self.db.execute(
                select(Membership, User).join(User, User.id == Membership.user_id)
                .where(Membership.org_id == m.org_id,
                       Membership.status == "active")).all()
        }

    # ── 4. classes ───────────────────────────────────────────────────────────
    def _classes(self, m: CurrentMember, pack: ParsedPack, year: AcademicYear,
                 staff: dict[str, uuid.UUID],
                 result: CommitResult) -> dict[tuple[str, str], uuid.UUID]:
        out = self._result(result, "classes")
        existing = {
            (_norm(c.name), _norm(c.section)): c
            for c in self.db.scalars(select(SchoolClass).where(
                SchoolClass.org_id == m.org_id,
                SchoolClass.academic_year_id == year.id))
        }
        known: dict[tuple[str, str], uuid.UUID] = {}

        for row in pack.rows("classes"):
            name = (row.get("class_name") or "").strip()
            section = (row.get("section") or "").strip() or None
            if not name:
                out.skipped += 1
                continue
            key = (_norm(name), _norm(section))
            klass = existing.get(key)
            if klass is None:
                klass = SchoolClass(org_id=m.org_id, academic_year_id=year.id,
                                    name=name, section=section)
                self.db.add(klass)
                self.db.flush()
                existing[key] = klass
                out.created += 1
            else:
                out.updated += 1
            teacher = _norm(row.get("class_teacher"))
            if teacher and teacher in staff:
                klass.class_teacher_member_id = staff[teacher]
            known[key] = klass.id
        self.db.flush()
        return known

    # ── 5. assignments (and the subject list) ────────────────────────────────
    def _assignments(self, m: CurrentMember, pack: ParsedPack,
                     classes: dict[tuple[str, str], uuid.UUID],
                     staff: dict[str, uuid.UUID],
                     result: CommitResult) -> dict[tuple[str, str, str], uuid.UUID]:
        """Creates the subject list as a side effect — there is no Subjects
        sheet, because a subject nobody teaches is not a fact about a school.

        Returns {(class, section, subject): class_subject_id}.
        """
        out = self._result(result, "assignments")
        subjects = {_norm(s.name): s for s in self.db.scalars(
            select(Subject).where(Subject.org_id == m.org_id))}
        existing = {
            (cs.class_id, cs.subject_id): cs
            for cs in self.db.scalars(select(ClassSubject).where(
                ClassSubject.org_id == m.org_id))
        }
        offered: dict[tuple[str, str, str], uuid.UUID] = {}

        for row in pack.rows("assignments"):
            name = (row.get("class_name") or "").strip()
            section = (row.get("section") or "").strip()
            subject_name = (row.get("subject") or "").strip()
            if not name or not subject_name:
                out.skipped += 1
                continue
            subject = subjects.get(_norm(subject_name))
            if subject is None:
                subject = Subject(org_id=m.org_id, name=subject_name)
                self.db.add(subject)
                self.db.flush()
                subjects[_norm(subject_name)] = subject

            # A blank section is the whole point of one sheet for one school:
            # it means every section of that class.
            targets = [k for k in classes
                       if k[0] == _norm(name)
                       and (not section or k[1] == _norm(section))]
            if not targets:
                out.skipped += 1
                continue
            # `periods_per_week` is NOT NULL, so "not decided yet" is 0 here —
            # which is exactly how `readiness._classes` already reads it
            # ("N of M allocations have periods/week"). It is a state, not a
            # weekly budget of zero.
            ppw = to_int(row.get("periods_per_week")) or 0
            teacher = staff.get(_norm(row.get("teacher")))

            for key in targets:
                class_id = classes[key]
                cs = existing.get((class_id, subject.id))
                if cs is None:
                    cs = ClassSubject(org_id=m.org_id, class_id=class_id,
                                      subject_id=subject.id, periods_per_week=ppw)
                    self.db.add(cs)
                    self.db.flush()
                    existing[(class_id, subject.id)] = cs
                    out.created += 1
                else:
                    cs.periods_per_week = ppw
                    out.updated += 1
                if teacher:
                    cs.teacher_member_id = teacher
                offered[(*key, _norm(subject_name))] = cs.id
        self.db.flush()
        return offered

    # ── 6. syllabus ──────────────────────────────────────────────────────────
    def _syllabus(self, m: CurrentMember, pack: ParsedPack,
                  classes: dict[tuple[str, str], uuid.UUID],
                  offered: dict[tuple[str, str, str], uuid.UUID],
                  result: CommitResult, replace: bool) -> None:
        out = self._result(result, "syllabus")
        rows = fill_down(pack.rows("syllabus"),
                         ("class_name", "section", "subject", "term", "chapter"))
        grouped: dict[uuid.UUID, list[dict]] = {}

        for row in rows:
            name, section = _norm(row.get("class_name")), _norm(row.get("section"))
            subject = _norm(row.get("subject"))
            if not row.get("chapter"):
                out.skipped += 1
                continue
            targets = [k for k in classes
                       if k[0] == name and (not section or k[1] == section)]
            landed = False
            for key in targets:
                cs_id = offered.get((*key, subject))
                if cs_id is not None:
                    grouped.setdefault(cs_id, []).append(row)
                    landed = True
            if not landed:
                out.skipped += 1

        importer = SyllabusImporter(self.db)
        for cs_id, cs_rows in grouped.items():
            units = _units_from_rows(cs_rows)
            if not units:
                continue
            report = importer.commit(m, class_subject_id=cs_id, units=units,
                                     replace=replace)
            out.created += report["units_created"]
        if out.created:
            out.notes.append(
                "Existing chapters were REPLACED for every class-subject in the "
                "sheet." if replace else
                "Chapters were added to whatever was already there.")

    # ── 7. calendar ──────────────────────────────────────────────────────────
    def _calendar(self, m: CurrentMember, pack: ParsedPack, year: AcademicYear,
                  result: CommitResult) -> None:
        out = self._result(result, "calendar")
        existing = {
            (_norm(e.title), e.start_date): e
            for e in self.db.scalars(select(CalendarEvent).where(
                CalendarEvent.org_id == m.org_id,
                CalendarEvent.academic_year_id == year.id))
        }
        for row in pack.rows("calendar"):
            title = (row.get("title") or "").strip()
            start = to_date(row.get("start_date"))
            if not title or start is None:
                out.skipped += 1
                continue
            end = to_date(row.get("end_date")) or start
            kind = EVENT_TYPES.get(_norm(row.get("type")), "event")
            event = existing.get((_norm(title), start))
            if event is None:
                self.db.add(CalendarEvent(
                    org_id=m.org_id, academic_year_id=year.id, type=kind,
                    title=title, start_date=start, end_date=end,
                    # A holiday and an exam block both remove teaching days from
                    # the plan; an event is a working day with something on it,
                    # which is exactly how the pack describes the three.
                    affects_teaching=kind in {"holiday", "exam_block"}))
                out.created += 1
            else:
                event.type, event.end_date = kind, end
                out.updated += 1
        self.db.flush()

    # ── 8. students ──────────────────────────────────────────────────────────
    def _students(self, m: CurrentMember, pack: ParsedPack, year: AcademicYear,
                  result: CommitResult) -> None:
        out = self._result(result, "students")
        fields = ["full_name", "admission_no", "roll_no", "class_name", "section",
                  "date_of_birth", "category", "father_name", "father_phone",
                  "mother_name", "mother_phone"]
        report = RosterImporter(self.db).commit(
            m, mapping=_identity(fields), rows=pack.rows("students"),
            academic_year_id=year.id)
        out.created = report["created"]
        out.skipped = report["skipped"]
        if report["unresolved"]:
            out.notes.append(
                f"{len(report['unresolved'])} date(s) of birth could not be read — "
                f"those parents cannot log in until they are fixed.")

    # ── 9. timetable ─────────────────────────────────────────────────────────
    def _timetable(self, m: CurrentMember, pack: ParsedPack, year: AcademicYear,
                   classes: dict[tuple[str, str], uuid.UUID],
                   offered: dict[tuple[str, str, str], uuid.UUID],
                   result: CommitResult) -> None:
        out = self._result(result, "timetable")
        rows = pack.rows("timetable")
        if not rows:
            out.notes.append("No timetable — teachers will see no periods on My Day.")
            return
        effective = year.tracking_start_date or year.start_date or date.today()
        existing = {
            (s.class_id, s.weekday, s.period_no): s
            for s in self.db.scalars(select(TimetableSlot).where(
                TimetableSlot.org_id == m.org_id,
                TimetableSlot.effective_to.is_(None)))
        }

        for row in rows:
            key = (_norm(row.get("class_name")), _norm(row.get("section")))
            class_id = classes.get(key)
            cs_id = offered.get((*key, _norm(row.get("subject"))))
            weekday = WEEKDAYS.get(_norm(row.get("day")))
            period = to_int(row.get("period"))
            if class_id is None or cs_id is None or weekday is None or not period:
                out.skipped += 1
                continue
            slot = existing.get((class_id, weekday, period))
            if slot is None:
                self.db.add(TimetableSlot(
                    org_id=m.org_id, class_id=class_id, weekday=weekday,
                    period_no=period, class_subject_id=cs_id,
                    effective_from=effective))
                out.created += 1
            else:
                slot.class_subject_id = cs_id
                out.updated += 1
        self.db.flush()

    # ── 9b. exam portions ────────────────────────────────────────────────────
    def _portions(self, m: CurrentMember, exams: dict[str, uuid.UUID],
                  offered: dict[tuple[str, str, str], uuid.UUID],
                  result: CommitResult) -> None:
        """Map each term's syllabus onto that term's exam.

        No sheet states this. A term IS its exam, so what the exam examines is
        every chapter filed under that term — asking a school to restate it
        would be asking the same fact twice and inviting the two to disagree.

        Set-shaped, matching `exam_portions` + `exam_portion_units`, which is
        what the exam-fit panel and the teacher's "finish before the paper" view
        both read.
        """
        out = SheetResult(key=EXAMS_KEY, title=EXAMS_TITLE)
        result.sheets.append(out)
        if not exams:
            out.notes.append("No term exams — the syllabus has nothing to be "
                             "measured against yet.")
            return
        terms = {_norm(t.name): t.id for t in self.db.scalars(
            select(Term).where(Term.org_id == m.org_id))}

        for term_name, event_id in exams.items():
            term_id = terms.get(term_name)
            if term_id is None:
                continue
            for cs_id in dict.fromkeys(offered.values()):
                units = list(self.db.scalars(
                    select(SyllabusUnit)
                    .where(SyllabusUnit.org_id == m.org_id,
                           SyllabusUnit.class_subject_id == cs_id,
                           SyllabusUnit.term_id == term_id)
                    .order_by(SyllabusUnit.position)))
                if not units:
                    continue
                self._write_portion(m, event_id, cs_id, units)
                out.created += 1
        self.db.flush()

    def _write_portion(self, m: CurrentMember, event_id: uuid.UUID,
                       cs_id: uuid.UUID, units: list) -> None:
        portion = self.db.scalar(select(ExamPortion).where(
            ExamPortion.org_id == m.org_id,
            ExamPortion.exam_event_id == event_id,
            ExamPortion.class_subject_id == cs_id))
        if portion is None:
            portion = ExamPortion(org_id=m.org_id, exam_event_id=event_id,
                                  class_subject_id=cs_id)
            self.db.add(portion)
            self.db.flush()
        else:
            self.db.execute(delete(ExamPortionUnit).where(
                ExamPortionUnit.org_id == m.org_id,
                ExamPortionUnit.portion_id == portion.id))
        for unit in units:
            self.db.add(ExamPortionUnit(org_id=m.org_id, portion_id=portion.id,
                                        unit_id=unit.id))

    def _exam_event(self, m: CurrentMember, year: AcademicYear, title: str,
                    start: date, end: date) -> CalendarEvent:
        """The term's exam block. Deliberately does NOT touch the Terms result's
        counters — "2 terms created" must mean two terms, not two terms plus
        their two exam blocks. The block count is stated in that sheet's note."""
        event = self.db.scalar(select(CalendarEvent).where(
            CalendarEvent.org_id == m.org_id,
            CalendarEvent.academic_year_id == year.id,
            CalendarEvent.type == "exam_block",
            CalendarEvent.title == title,
            CalendarEvent.start_date == start))
        if event is None:
            event = CalendarEvent(
                org_id=m.org_id, academic_year_id=year.id, type="exam_block",
                title=title, start_date=start, end_date=end,
                affects_teaching=True)
            self.db.add(event)
            self.db.flush()
        else:
            event.end_date = end
        return event

    # ── 11. the plans (not a sheet) ──────────────────────────────────────────
    def _plans(self, m: CurrentMember, year: AcademicYear,
               offered: dict[tuple[str, str, str], uuid.UUID],
               result: CommitResult) -> None:
        """Generate and approve every class-subject's plan.

        This is the step whose absence made a freshly imported school open on a
        dashboard full of *"has no plan yet"* — setup was finished and the school
        was being told it was not. The wizard's tenth step did this; one upload
        has to do it too.

        Per TERM, not per year: a school that has planned only Term 1 gets Term 1
        locked and Term 2 left open, which is exactly `Plan.status='partial'` and
        the mid-year guarantee (D-4). A term with no chapters is skipped in
        silence — there is nothing there to promise.
        """
        out = SheetResult(key=PLANS_KEY, title=PLANS_TITLE)
        result.sheets.append(out)
        planner = PlannerService(self.db)
        terms = list(self.db.scalars(select(Term).where(
            Term.org_id == m.org_id, Term.academic_year_id == year.id)
            .order_by(Term.start_date)))
        unfit: list[str] = []

        for cs_id in dict.fromkeys(offered.values()):
            for term in terms or [None]:
                term_id = term.id if term else None
                try:
                    report = planner.generate_plan(m, cs_id, term_id)
                except (ValidationError, NotFoundError):
                    # Nothing sized in this window — a state, not a failure.
                    continue
                # `fits=False` is NOT on its own a reason to leave a plan
                # unlocked. The commonest cause is an `unsized` chapter, which
                # is the normal mid-year state — `approve_plan` locks what IS
                # scheduled and leaves the unsized ones open to be sized later
                # (D-4). Only refuse when the plan promises teaching the
                # calendar cannot deliver.
                blocking = {v.code for v in report.violations} & UNLOCKABLE
                if blocking:
                    unfit.append(term.name if term else "the year")
                    continue
                try:
                    planner.approve_plan(m, cs_id, term_id)
                    out.created += 1
                except (ValidationError, NotFoundError):
                    # Already approved, or nothing scheduled to lock.
                    out.skipped += 1
        self.db.flush()

        if out.created:
            out.notes.append(
                f"{out.created} term plan(s) generated and locked — the school "
                f"opens with no 'no plan yet' warnings.")
        if unfit:
            names = ", ".join(sorted(set(unfit)))
            out.notes.append(
                f"Left unlocked because the syllabus does not fit the teaching "
                f"days available: {names}. Nothing was approved for those — a "
                f"plan that cannot be taught is worse than none.")

    # ── 10. fees ─────────────────────────────────────────────────────────────
    def _fees(self, m: CurrentMember, pack: ParsedPack, year: AcademicYear,
              result: CommitResult) -> None:
        """One structure per class; its installment rows are replaced wholesale,
        because a fee plan is read as a set and a half-updated one would present
        a total nobody agreed to."""
        out = self._result(result, "fees")
        grouped: dict[tuple[str, int], list[dict]] = {}
        for row in pack.rows("fees"):
            name = (row.get("class_name") or "").strip()
            total = to_int(row.get("total_amount"))
            if not name or total is None:
                out.skipped += 1
                continue
            grouped.setdefault((name, total), []).append(row)

        for (name, total), rows in grouped.items():
            structure = self.db.scalar(select(FeeStructure).where(
                FeeStructure.org_id == m.org_id,
                FeeStructure.academic_year_id == year.id,
                FeeStructure.class_name == name))
            if structure is None:
                structure = FeeStructure(
                    org_id=m.org_id, class_name=name, academic_year_id=year.id,
                    total_amount=total, num_installments=len(rows),
                    created_by=m.user_id)
                self.db.add(structure)
                self.db.flush()
                out.created += 1
            else:
                structure.total_amount = total
                structure.num_installments = len(rows)
                out.updated += 1
                for old in self.db.scalars(select(FeeInstallmentTemplate).where(
                        FeeInstallmentTemplate.fee_structure_id == structure.id)):
                    self.db.delete(old)
                self.db.flush()
            self._installments(m, structure, rows)
            self._enrol_class(m, year, structure, out)
        self.db.flush()

    def _enrol_class(self, m: CurrentMember, year: AcademicYear,
                     structure: FeeStructure, out: SheetResult) -> None:
        """Put every student of the class onto the structure.

        A structure and its templates say what a CLASS pays; `student_fees` and
        `installments` say what a CHILD owes, quarter by quarter. Only the second
        pair is readable — `services/collection.py` groups real installments by
        due-date window, so a school imported with structures but no enrolments
        opens the fee screen on an empty quarter and concludes the import failed.

        `FeeService.enroll` is the one path that creates both, and it already
        knows how to copy a structure's templates onto a child, so this asks it
        rather than writing the rows again.
        """
        students = list(self.db.scalars(
            select(Student).join(SchoolClass, SchoolClass.id == Student.class_id)
            .where(Student.org_id == m.org_id,
                   SchoolClass.academic_year_id == year.id,
                   SchoolClass.name == structure.class_name,
                   Student.status == "active")))
        if not students:
            return
        fees = FeeService(self.db)
        for student in students:
            try:
                fees.enroll(m, StudentFeeCreate(
                    student_id=student.id, academic_year_id=year.id,
                    total_fee=structure.total_amount,
                    fee_structure_id=structure.id))
                out.created += 1
            except (ConflictError, ValidationError, NotFoundError):
                # Already enrolled for this year — the re-upload case.
                out.skipped += 1

    def _installments(self, m: CurrentMember, structure: FeeStructure,
                      rows: list[dict]) -> None:
        """Appended through `structure.templates`, not by setting the foreign key.

        Setting `fee_structure_id` alone writes the right row but leaves the
        parent's in-session collection empty, and `FeeService.enroll` reads that
        collection to copy a schedule onto each child. The rows landed and every
        student got one lump instalment with no due date — which is `unscheduled`,
        so the quarter-wise fee screen showed nothing at all.
        """
        for number, row in enumerate(rows, start=1):
            structure.templates.append(FeeInstallmentTemplate(
                org_id=m.org_id,
                installment_number=to_int(row.get("installment_no")) or number,
                label=(row.get("installment_name") or "").strip() or None,
                amount=to_int(row.get("amount")) or 0,
                due_date=to_date(row.get("due_date"))))
        self.db.flush()


__all__ = ["CommitResult", "PackCommitter", "SheetResult"]
