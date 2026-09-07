import { api } from "@/lib/api-client";
import type {
  AcademicYear,
  CalendarEvent,
  CalendarSummary,
  ClassLogBook,
  ClassSubject,
  FeeStructure,
  Guardian,
  HomeworkLogBook,
  HomeworkSheet,
  LeaveBalance,
  LeaveList,
  LeavePolicy,
  LeaveRequest,
  RosterAnalyze,
  RosterCommitResult,
  SchoolClass,
  StaffAttendance,
  StaffDetail,
  StaffDirectory,
  StaffUpdateIn,
  StaffMark,
  StaffMonth,
  StudentHomeworkHistory,
  StudentCategory,
  StudentDetail,
  StudentFeeDetail,
  StudentFeeListItem,
  StudentListItem,
  StudentRecords,
  Subject,
  Term,
  TimesheetDay,
  TimesheetMonth,
  TimesheetWeek,
  WorkType,
} from "@/lib/school-types";

const qs = (params: Record<string, string | undefined>) => {
  const p = Object.entries(params).filter(([, v]) => v != null && v !== "");
  return p.length ? "?" + p.map(([k, v]) => `${k}=${encodeURIComponent(v!)}`).join("&") : "";
};

export const schoolApi = {
  // ── academics (master data) ───────────────────────────────────────────────
  years: () => api.get<AcademicYear[]>("/academics/years"),
  createYear: (b: { label: string; start_date: string; end_date: string; tracking_start_date?: string | null }) =>
    api.post<AcademicYear>("/academics/years", b),
  updateYear: (id: string, b: { label?: string; start_date?: string; end_date?: string; tracking_start_date?: string | null }) =>
    api.patch<AcademicYear>(`/academics/years/${id}`, b),
  activateYear: (id: string) => api.post<AcademicYear>(`/academics/years/${id}/activate`),
  deleteYear: (id: string) => api.del<{ message: string }>(`/academics/years/${id}`),

  terms: (yearId?: string) => api.get<Term[]>(`/academics/terms${qs({ year_id: yearId })}`),
  createTerm: (b: { academic_year_id: string; name: string; start_date: string; end_date: string }) =>
    api.post<Term>("/academics/terms", b),
  /** Rename a term or move its window. The route has existed since P0-C and no
   *  screen ever called it, so correcting "Term 1" to "First Term" meant deleting
   *  the term — which unscopes every chapter filed under it. */
  updateTerm: (id: string, b: { name?: string; start_date?: string; end_date?: string }) =>
    api.patch<Term>(`/academics/terms/${id}`, b),
  deleteTerm: (id: string) => api.del<{ message: string }>(`/academics/terms/${id}`),

  subjects: () => api.get<Subject[]>("/academics/subjects"),
  createSubject: (name: string) => api.post<Subject>("/academics/subjects", { name }),
  deleteSubject: (id: string) => api.del<{ message: string }>(`/academics/subjects/${id}`),

  /** mine narrows a teacher to classes they teach (admins always get all). */
  classes: (yearId?: string, mine?: boolean) =>
    api.get<SchoolClass[]>(`/academics/classes${qs({ year_id: yearId, mine: mine ? "true" : undefined })}`),
  createClass: (b: { academic_year_id: string; name: string; section?: string | null }) =>
    api.post<SchoolClass>("/academics/classes", b),
  /** V1-2 (D-03): the class-teacher picker — the field existed since P0-C and
   *  no screen had ever set it. Pass null to unassign. */
  updateClass: (id: string, b: { name?: string; section?: string | null;
    class_teacher_member_id?: string | null }) =>
    api.patch<SchoolClass>(`/academics/classes/${id}`, b),
  deleteClass: (id: string) => api.del<{ message: string }>(`/academics/classes/${id}`),

  // calendar (M1)
  calendarSummary: (yearId: string) =>
    api.get<CalendarSummary>(`/academics/calendar/summary${qs({ year_id: yearId })}`),
  /** Correct a day in place. Before this, a holiday with the wrong date or a
   *  misspelt name could only be deleted and repainted. */
  updateEvent: (id: string, b: { type?: string; title?: string; start_date?: string;
    end_date?: string; affects_teaching?: boolean; notes?: string | null }) =>
    api.patch<CalendarEvent>(`/academics/calendar/events/${id}`, b),
  deleteEvent: (id: string) => api.del<{ message: string }>(`/academics/calendar/events/${id}`),
  /** One round trip for a drag-selected range (V2-P7). */
  createEvents: (events: import("@/lib/school-types").CalendarEventInput[]) =>
    api.post<CalendarEvent[]>("/academics/calendar/events/bulk", { events }),

  // exam portions (V2-P7): what each exam actually examines
  examPortions: (csId?: string) =>
    api.get<import("@/lib/school-types").ExamPortion[]>(
      `/academics/exam-portions${qs({ class_subject_id: csId })}`),
  setExamPortion: (b: { exam_event_id: string; class_subject_id: string; upto_topic_id: string }) =>
    api.post<import("@/lib/school-types").ExamPortion>("/academics/exam-portions", b),
  deleteExamPortion: (id: string) =>
    api.del<{ message: string }>(`/academics/exam-portions/${id}`),

  /** `mine` narrows a teacher to the subjects SHE teaches on this class — the
   *  same flag `classes()` carries. Without it her picker offered every
   *  subject of the class and five of six chips led to a board the server
   *  correctly refused to fill. The narrowing is the server's, not a filter
   *  applied to a list the browser should never have received. */
  classSubjects: (classId: string, mine?: boolean) =>
    api.get<ClassSubject[]>(
      `/academics/classes/${classId}/subjects${qs({ mine: mine ? "true" : undefined })}`),
  /** The whole year in ONE read (V1-2, S-77) — feeds the by-teacher lens. */
  allClassSubjects: (yearId?: string) =>
    api.get<ClassSubject[]>(`/academics/class-subjects${qs({ year_id: yearId })}`),
  // V1-2 §6 ②: the blank templates the school fills in.
  downloadRosterTemplate: () =>
    api.download("/students/import/template", "students-template.xlsx"),
  downloadStaffTemplate: () =>
    api.download("/org/members/import/template", "staff-template.xlsx"),
  downloadSyllabusTemplate: () =>
    api.download("/planner/syllabus/import/template", "syllabus-template.xlsx"),
  /** Copy another class's subjects (+ syllabus) onto this one — for sibling sections. */
  copyClassSubjects: (classId: string, fromClassId: string, includeSyllabus = true) =>
    api.post<{ subjects_added: number; units_copied: number; topics_copied: number }>(
      `/academics/classes/${classId}/copy-subjects`,
      { from_class_id: fromClassId, include_syllabus: includeSyllabus }),
  /** Periods/week per subject vs the week's capacity, with a suggested split. */
  classAllocation: (classId: string) =>
    api.get<import("@/lib/school-types").ClassAllocation>(`/academics/classes/${classId}/allocation`),
  saveClassAllocation: (classId: string, items: { class_subject_id: string; periods_per_week: number }[]) =>
    api.put<import("@/lib/school-types").ClassAllocation>(`/academics/classes/${classId}/allocation`, { items }),

  /** Per exam: required portion vs teaching periods in the gap — the calendar's live check. */
  examFit: (classId: string) =>
    api.get<import("@/lib/school-types").ExamFit>(`/planner/plan/exam-fit${qs({ class_id: classId })}`),
  /** The class's computed week: actuals where logged, remaining syllabus projected forward. */
  weekSchedule: (classId: string, weekStart?: string) =>
    api.get<import("@/lib/school-types").WeekSchedule>(
      `/planner/plan/week-schedule${qs({ class_id: classId, week_start: weekStart })}`),

  // planner: syllabus + plan + forecast (M1)
  syllabus: (csId: string) =>
    api.get<import("@/lib/school-types").SyllabusUnit[]>(`/planner/syllabus${qs({ class_subject_id: csId })}`),
  addUnit: (b: { class_subject_id: string; title: string; term_id?: string | null }) =>
    api.post<import("@/lib/school-types").SyllabusUnit>("/planner/syllabus/units", b),
  addTopic: (b: { unit_id: string; title: string; est_periods?: number | null }) =>
    api.post<import("@/lib/school-types").SyllabusTopic>("/planner/syllabus/topics", b),
  /** Size (or un-size) a chapter when its term begins. Refused once that term is locked. */
  setTopicEstimate: (topicId: string, estPeriods: number | null) =>
    api.put<import("@/lib/school-types").SyllabusTopic>(
      `/planner/syllabus/topics/${topicId}/estimate`, { est_periods: estPeriods }),
  deleteUnit: (id: string) => api.del<{ message: string }>(`/planner/syllabus/units/${id}`),
  deleteTopic: (id: string) => api.del<{ message: string }>(`/planner/syllabus/topics/${id}`),
  plan: (csId: string) =>
    api.get<import("@/lib/school-types").Plan>(`/planner/plan${qs({ class_subject_id: csId })}`),
  // `termId` scopes the action to one term; omit it to act on the whole year.
  draftPlan: (csId: string, termId?: string | null) =>
    api.post<import("@/lib/school-types").Plan>(
      `/planner/plan/${csId}/draft${qs({ term_id: termId ?? undefined })}`),
  approvePlan: (csId: string, termId?: string | null) =>
    api.post<import("@/lib/school-types").Plan>(
      `/planner/plan/${csId}/approve${qs({ term_id: termId ?? undefined })}`),
  unapprovePlan: (csId: string, termId?: string | null) =>
    api.post<import("@/lib/school-types").Plan>(
      `/planner/plan/${csId}/unapprove${qs({ term_id: termId ?? undefined })}`),
  /** Schedule newly sized chapters after the existing (locked) entries — the
   *  partial-plan growth path. Never reshuffles what's already planned. */
  extendPlan: (csId: string, termId?: string | null) =>
    api.post<import("@/lib/school-types").Plan>(
      `/planner/plan/${csId}/extend${qs({ term_id: termId ?? undefined })}`),
  generatePlan: (csId: string, termId?: string | null) =>
    api.post<import("@/lib/school-types").PlanGenerateResult>(
      `/planner/plan/${csId}/generate${qs({ term_id: termId ?? undefined })}`),

  // ── the syllabus board (SY-1) ─────────────────────────────────────────────
  /** Every chapter the caller may see, grouped by class. Scope is decided by
   *  the server — an admin gets the school, a teacher gets her own subjects. */
  syllabusBoard: (p: {
    yearId?: string; classId?: string; classSubjectId?: string; termId?: string;
  } = {}) =>
    api.get<import("@/lib/syllabus-types").SyllabusBoard>(
      `/planner/syllabus/board${qs({
        year_id: p.yearId, class_id: p.classId,
        class_subject_id: p.classSubjectId, term_id: p.termId,
      })}`),
  /** Difficulty, remarks, title, term — the chapter's own columns. */
  patchChapter: (unitId: string, body: import("@/lib/syllabus-types").ChapterPatch) =>
    api.patch<import("@/lib/school-types").SyllabusUnit>(
      `/planner/syllabus/units/${unitId}`, body),
  /** The reschedule dialog's read: movable chapters + the fixed points. */
  planTimeline: (csId: string, termId?: string | null) =>
    api.get<import("@/lib/syllabus-types").PlanTimeline>(
      `/planner/plan/${csId}/timeline${qs({ term_id: termId ?? undefined })}`),
  /** Move chapters. Saved even when the dates don't hold them — the violations
   *  come back so she can see what she chose (V2-P5: reported, never squeezed). */
  reschedulePlan: (csId: string, chapters: {
    unit_id: string; start_date: string; end_date: string;
  }[]) =>
    api.put<import("@/lib/syllabus-types").RescheduleResult>(
      `/planner/plan/${csId}/schedule`, { chapters }),
  examMap: (classId: string) =>
    api.get<import("@/lib/syllabus-types").ExamMap>(
      `/planner/exam-map${qs({ class_id: classId })}`),
  /** Full replace of one (exam, class-subject) portion. `[]` clears it. */
  setExamPortionChapters: (b: {
    exam_event_id: string; class_subject_id: string; unit_ids: string[];
  }) =>
    api.put<import("@/lib/syllabus-types").ExamMap>("/planner/exam-map/portion", b),
  // ── document ingestion (V2-P7, SPRD2 §5.1) ────────────────────────────────
  /** Staff sheet -> proposed mapping + the gaps a human must close. */
  staffImportAnalyze: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.upload<import("@/lib/school-types").AnalyzeResult>(
      "/org/members/import/analyze", form);
  },
  staffImportCommit: (b: {
    mapping: Record<string, string>;
    rows: Record<string, unknown>[];
    academic_year_id?: string | null;
    default_password?: string | null;
  }) => api.post<import("@/lib/school-types").StaffCommitResult>(
    "/org/members/import/commit", b),

  syllabusImportAnalyze: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.upload<import("@/lib/school-types").SyllabusAnalyzeResult>(
      "/planner/syllabus/import/analyze", form);
  },
  syllabusImportText: (text: string) =>
    api.post<import("@/lib/school-types").SyllabusAnalyzeResult>(
      "/planner/syllabus/import/text", { text }),
  syllabusImportCommit: (b: {
    class_subject_id: string;
    units: import("@/lib/school-types").SyllabusUnitDraft[];
    replace?: boolean;
  }) => api.post<import("@/lib/school-types").SyllabusCommitResult>(
    "/planner/syllabus/import/commit", b),

  // ── post-setup read models (V2-P10) ───────────────────────────────────────
  // `schoolOverview` and `teacherLoad` were removed with Plan → Classes (SY-1),
  // their only caller. Teacher load is answered by Dashboard → Staff, which
  // computes it from real timetable and timesheet rows; the class-readiness
  // gaps are named chapter by chapter on the Syllabus board. Their GET routes
  // still exist and are on V1-13's reported orphan list.
  classOverview: (classId: string) =>
    api.get<import("@/lib/school-types").ClassOverview>(`/overview/classes/${classId}`),

  forecast: (classId: string) =>
    api.get<import("@/lib/school-types").Forecast[]>(`/planner/plan/forecast${qs({ class_id: classId })}`),

  // V1-6 — S-46 her own subjects; D-15 her own class, every subject.
  mySubjects: (yearId?: string) =>
    api.get<import("@/lib/school-types").MySubjects>(`/planner/my-subjects${qs({ year_id: yearId })}`),
  classSyllabus: (classId: string) =>
    api.get<import("@/lib/school-types").ClassSyllabus>(`/planner/class-syllabus/${classId}`),

  // classroom (M2)
  myDay: () => api.get<import("@/lib/school-types").MyDay>("/classroom/my-day"),
  logLesson: (b: {
    class_subject_id: string;
    topic_id?: string | null;
    coverage: string;
    note?: string | null;
    period_id?: string | null;
    period_no?: number | null;
  }) => api.post<{ id: string }>("/classroom/lesson-logs", b),
  deleteLog: (id: string) => api.del<{ message: string }>(`/classroom/lesson-logs/${id}`),
  /** Students → Academics → Class logs: the register for one class-subject. */
  classLogBook: (p: { classSubjectId: string; since?: string; until?: string }) =>
    api.get<ClassLogBook>(`/classroom/class-log${qs({
      class_subject_id: p.classSubjectId, since: p.since, until: p.until })}`),
  /** One entry. No `student_ids` = the class was taught this, which moves the
   *  syllabus. With names on it, it is a line about those children and moves
   *  nothing — a lesson that reached three children is not coverage. */
  addClassLog: (b: {
    class_subject_id: string; date?: string | null; topic_id?: string | null;
    title?: string | null; coverage?: "full" | "partial"; note?: string | null;
    student_ids?: string[];
  }) => api.post<ClassLogBook>("/classroom/class-log", b),
  deleteClassLog: (id: string) => api.del<{ message: string }>(`/classroom/class-log/${id}`),
  homeworkBook: (p: { classSubjectId: string; since?: string; until?: string }) =>
    api.get<HomeworkLogBook>(`/classroom/homework-log${qs({
      class_subject_id: p.classSubjectId, since: p.since, until: p.until })}`),
  /** `student_ids` writes one assignment PER child — never a shared row with a
   *  list on it, because every reader keys on (assignment, student). */
  addHomework: (b: {
    class_subject_id: string; text: string; due_date?: string | null;
    student_id?: string | null; student_ids?: string[];
    /** TT-4: the other classes of a combined period — one row each, never a
     *  shared one. Ignored when the homework names particular children. */
    also_class_subject_ids?: string[];
  }) => api.post<{ id: string; notified_count: number; created_ids: string[] }>(
    "/classroom/homework", b),
  // HW-1: capture-by-exception. An empty `results` list means everyone did it.
  homeworkSheet: (id: string) =>
    api.get<HomeworkSheet>(`/classroom/homework/${id}/sheet`),
  // V1-5: the full verdict vocabulary — late/carried/waived joined not_done and
  // partial. `done` is still the ABSENCE of a row, so it is not in the union.
  checkHomework: (id: string, b: { results: { student_id: string; status: string; note?: string | null }[] }) =>
    api.post<HomeworkSheet>(`/classroom/homework/${id}/check`, b),
  // V1-5 (D-36/S-100): the backlog and its count, and D-37's per-class evening.
  homeworkQueue: (p: { windowDays?: number; classSubjectId?: string } = {}) =>
    api.get<import("@/lib/school-types").HomeworkQueue>(
      `/homework/queue${qs({
        window_days: p.windowDays ? String(p.windowDays) : undefined,
        class_subject_id: p.classSubjectId,
      })}`),
  homeworkLoad: (p: { classId?: string; days?: number } = {}) =>
    api.get<import("@/lib/school-types").HomeworkLoad>(
      `/homework/load${qs({ class_id: p.classId, days: p.days ? String(p.days) : undefined })}`),
  studentHomework: (studentId: string, windowDays?: number) =>
    api.get<StudentHomeworkHistory>(
      `/homework/student/${studentId}${qs({ window_days: windowDays ? String(windowDays) : undefined })}`),
  // period detail page (V2-P6) — everything for one class-period in one call
  periodCard: (classId: string, periodNo: number, onDate?: string, classSubjectId?: string) =>
    api.get<import("@/lib/school-types").PeriodCard>(
      `/periods/card${qs({ class_id: classId, period_no: String(periodNo), on_date: onDate,
        // FB-1a: names the subject when the grid has nothing here. A fallback,
        // never an override — an opened period and the timetable both win.
        class_subject_id: classSubjectId })}`),
  /** FB-1a — the classes, subjects and periods this member could record off the
   *  timetable. Read-only; opens no period. */
  recordable: (onDate?: string) =>
    api.get<import("@/lib/school-types").Recordable>(
      `/periods/recordable${qs({ on_date: onDate })}`),
  openPeriod: (b: { class_id: string; period_no: number; class_subject_id?: string | null; date?: string | null }) =>
    api.post<{ id: string }>("/periods/open", b),
  /** V1-7 (S-147): `eventId` files this against the approved calendar row, so
   *  "what did Diwali cost us in periods?" is answerable. Null = free text. */
  periodNotHeld: (periodId: string, reason: string, eventId?: string | null) =>
    api.post<{ id: string }>(`/periods/${periodId}/not-held`, { reason, event_id: eventId ?? null }),
  closePeriod: (periodId: string) => api.post<{ id: string }>(`/periods/${periodId}/close`),
  reopenPeriod: (periodId: string) => api.post<{ id: string }>(`/periods/${periodId}/reopen`),

  // deep log — optional lesson observations (exception-only, P1v2)
  observations: (csId: string, onDate?: string, periodId?: string) =>
    api.get<import("@/lib/school-types").Observations>(
      `/classroom/observations${qs({ class_subject_id: csId, on_date: onDate, period_id: periodId })}`),
  saveObservationSection: (b: {
    class_subject_id: string;
    section: string;
    date?: string | null;
    period_id?: string | null;
    period_no?: number | null;
    concepts: { concept: string; students: { student_id: string; rating: "excellent" | "needs_work"; note?: string | null }[] }[];
  }) => api.put<import("@/lib/school-types").Observations>("/classroom/observations", b),
  deleteObservationSection: (csId: string, section: string, onDate?: string) =>
    api.del<{ message: string }>(
      `/classroom/observations${qs({ class_subject_id: csId, section, on_date: onDate })}`),

  // student growth report — staff-only (admin all, teachers their own students)
  studentGrowth: (studentId: string) =>
    api.get<import("@/lib/school-types").StudentGrowth>(`/students/${studentId}/growth`),

  // attendance (V2-P2, SPRD2 §5.4) — capture-by-exception
  attendanceRoster: (classId: string, periodNo: number, onDate?: string) =>
    api.get<import("@/lib/school-types").AttendanceRoster>(
      `/attendance/roster${qs({ class_id: classId, period_no: String(periodNo), on_date: onDate })}`,
    ),
  markAttendance: (b: {
    class_id: string;
    period_no: number;
    class_subject_id?: string | null;
    date?: string | null;
    exceptions: { student_id: string; status: "absent" | "late"; late_minutes?: number | null }[];
    /** TT-4: the whole combined room. Writes ONE register PER CLASS — the
     *  exceptions are split by whose roster each child is on. */
    class_ids?: string[];
  }) => api.post<import("@/lib/school-types").AttendanceMarkResult>("/attendance/mark", b),

  // TT-6 — the whole-school register, taken at assembly. The door is the BLOCK
  // (its staff), not the classes: the warden who takes assembly teaches almost
  // none of the school. The classes are the ones the grid puts in the hall at
  // that period, and the save writes ONE register PER CLASS.
  assemblySheet: (sessionId: string, onDate?: string) =>
    api.get<import("@/lib/school-types").AssemblyRoster>(
      `/attendance/assembly${qs({ session_id: sessionId, on_date: onDate })}`),
  markAssembly: (b: {
    session_id: string;
    date?: string | null;
    period_no?: number | null;
    exceptions: { student_id: string; status: "absent" | "late"; late_minutes?: number | null }[];
  }) => api.post<import("@/lib/school-types").AssemblyMarkResult>("/attendance/assembly", b),

  // V1-3 — reasons (D-02), informed absence (S-24), My Class (D-03)
  /** Recorded AFTER capture by admin or teacher; stamps every absent period of
   *  that student-day. Its presence turns a red row amber (D-86). */
  setAbsenceReason: (b: {
    student_id: string; date: string;
    reason_code?: string | null; note?: string | null;
  }) => api.put<{ student_id: string; date: string; updated_periods: number }>(
    "/attendance/absences/reason", b),
  addAbsenceNote: (b: {
    student_id: string; from_date: string; to_date: string;
    reason_code?: string | null; note?: string | null;
    source?: "parent_call" | "office" | "teacher";
  }) => api.post<import("@/lib/school-types").AbsenceNote>("/attendance/absences/notes", b),
  myClasses: () => api.get<import("@/lib/school-types").MyClassList>("/my-class"),
  classRegister: (classId: string, month?: string) =>
    api.get<import("@/lib/school-types").ClassRegister>(
      `/my-class/${classId}/register${qs({ month })}`),

  // My Class, expanded (founder, 2026-08-05). Six reads, one per tab, each
  // composed server-side from the service that already owns those figures.
  myClassOverview: (classId: string) =>
    api.get<import("@/lib/school-types").MyClassOverview>(
      `/my-class/${classId}/overview`),
  myClassStudents: (classId: string, days?: number) =>
    api.get<import("@/lib/school-types").MyClassStudents>(
      `/my-class/${classId}/students${qs({ days: days ? String(days) : undefined })}`),
  myClassHomework: (classId: string, days?: number) =>
    api.get<import("@/lib/school-types").MyClassHomework>(
      `/my-class/${classId}/homework${qs({ days: days ? String(days) : undefined })}`),
  myClassBands: (classId: string) =>
    api.get<import("@/lib/school-types").MyClassBands>(`/my-class/${classId}/bands`),
  /** The SY-1 chapter table for EVERY subject her class takes — the same board
   *  Plan → Syllabus renders, at the one scope Plan no longer offers. */
  myClassSyllabus: (classId: string, termId?: string) =>
    api.get<import("@/lib/syllabus-types").SyllabusBoard>(
      `/my-class/${classId}/syllabus${qs({ term_id: termId })}`),
  /** The homework day book: today in full, earlier days as openable rows. */
  myClassHomeworkDays: (classId: string, p: { page?: number; size?: number } = {}) =>
    api.get<import("@/lib/school-types").MyClassHomeworkDays>(
      `/my-class/${classId}/homework/days${qs({
        page: p.page ? String(p.page) : undefined,
        size: p.size ? String(p.size) : undefined,
      })}`),
  myClassHomeworkDay: (classId: string, on: string) =>
    api.get<import("@/lib/school-types").MyClassHomeworkDay>(
      `/my-class/${classId}/homework/day${qs({ on })}`),
  /** The class teacher's own log about a child — staff-only, append-only. */
  studentNotes: (studentId: string) =>
    api.get<import("@/lib/school-types").StudentNotes>(
      `/my-class/students/${studentId}/notes`),
  addStudentNote: (studentId: string, b: {
    kind: import("@/lib/school-types").StudentNoteKind; note: string;
    /** Set when the note came off a support assessment's sheet — one log about
     *  a child, with a pointer to what occasioned it. */
    assessment_id?: string | null;
  }) => api.post<import("@/lib/school-types").StudentNotes>(
    `/my-class/students/${studentId}/notes`, b),

  /** The month register book for a class this teacher takes — view only.
   *  Same drawing as My Class's grid, behind a wider door: a teacher who may be
   *  asked to take the roll must be able to read it. */
  classRegisterFor: (classId: string, month?: string) =>
    api.get<import("@/lib/school-types").ClassRegister>(
      `/attendance/register${qs({ class_id: classId, month })}`),

  /** Every class this teacher may take the register for, on any date. */
  myAttendance: (onDate?: string) =>
    api.get<import("@/lib/school-types").MyAttendanceBoard>(
      `/attendance/my-classes${qs({ on_date: onDate })}`),

  // daily checks / recommendations (V2-P3, SPRD2 §5.5)
  checks: (classSubjectId: string, onDate?: string) =>
    api.get<import("@/lib/school-types").Checks>(
      `/checks${qs({ class_subject_id: classSubjectId, on_date: onDate })}`,
    ),
  confirmCheck: (checkId: string, exceptions: { student_id: string; status: "not_done" | "note"; note?: string | null }[]) =>
    api.post<import("@/lib/school-types").DailyCheck>(`/checks/${checkId}/confirm`, { exceptions }),

  // sessions (M2 + HS: hostel timetable, homework board, study logs, memories)
  sessions: () => api.get<import("@/lib/school-types").SessionSummary[]>("/sessions"),
  session: (id: string) => api.get<import("@/lib/school-types").SessionDetail>(`/sessions/${id}`),
  createSession: (b: import("@/lib/school-types").SessionWrite) =>
    api.post<import("@/lib/school-types").SessionDetail>("/sessions", b),
  updateSession: (id: string, b: Partial<import("@/lib/school-types").SessionWrite> & { active?: boolean }) =>
    api.patch<import("@/lib/school-types").SessionDetail>(`/sessions/${id}`, b),
  deleteSession: (id: string) => api.del<{ message: string }>(`/sessions/${id}`),
  openMeeting: (sessionId: string) =>
    api.post<import("@/lib/school-types").Meeting>(`/sessions/${sessionId}/meetings`),
  recordAttendance: (meetingId: string, rows: {
    student_id: string; status: string; late_minutes?: number | null; homework_done?: boolean | null;
  }[]) => api.patch<import("@/lib/school-types").Meeting>(`/sessions/meetings/${meetingId}/attendance`, { rows }),
  sessionStudentCard: (meetingId: string, studentId: string) =>
    api.get<import("@/lib/school-types").SessionStudentCard>(
      `/sessions/meetings/${meetingId}/students/${studentId}`),
  setStudentLogs: (meetingId: string, studentId: string, entries: { section: string; note: string }[]) =>
    api.put<import("@/lib/school-types").SessionStudentCard>(
      `/sessions/meetings/${meetingId}/students/${studentId}/logs`, { entries }),
  deleteSessionMedia: (mediaId: string) => api.del<{ message: string }>(`/sessions/media/${mediaId}`),
  // Media upload: presign → direct-to-R2 PUT → confirm; falls back to the
  // pass-through endpoint when R2 isn't configured (dev) or for small files.
  uploadSessionMedia: async (meetingId: string, file: File, opts?: { caption?: string; studentId?: string }) => {
    const DIRECT_LIMIT = 25 * 1024 * 1024;
    if (file.size > DIRECT_LIMIT) {
      const pre = await api.post<import("@/lib/school-types").MediaPresign>(
        `/sessions/meetings/${meetingId}/media/presign`,
        { filename: file.name, content_type: file.type || "application/octet-stream",
          size_bytes: file.size, student_id: opts?.studentId ?? null },
      );
      if (pre.upload_url) {
        const put = await fetch(pre.upload_url, {
          method: "PUT", body: file,
          headers: { "Content-Type": file.type || "application/octet-stream" },
        });
        if (!put.ok) throw new Error("Upload to storage failed");
        return api.post<import("@/lib/school-types").Meeting>(
          `/sessions/meetings/${meetingId}/media/confirm`,
          { key: pre.key, caption: opts?.caption || null, student_id: opts?.studentId ?? null });
      }
    }
    const form = new FormData();
    form.append("file", file);
    if (opts?.caption) form.append("caption", opts.caption);
    if (opts?.studentId) form.append("student_id", opts.studentId);
    return api.upload<import("@/lib/school-types").Meeting>(`/sessions/meetings/${meetingId}/media`, form);
  },

  // daily report + student timeline (V2-P4, SPRD2 §5.6/§5.7)
  dailyReport: (onDate?: string) =>
    api.get<import("@/lib/school-types").DailyReport>(`/reports/daily${qs({ on_date: onDate })}`),
  regenerateReport: (onDate?: string) =>
    api.post<import("@/lib/school-types").DailyReport>(`/reports/daily/regenerate${qs({ on_date: onDate })}`),
  studentTimeline: (studentId: string, onDate?: string) =>
    api.get<import("@/lib/school-types").StudentTimeline>(
      `/students/${studentId}/timeline${qs({ on_date: onDate })}`),

  // director dashboard (M4)
  dashboard: (yearId?: string) =>
    api.get<import("@/lib/school-types").DashboardOverview>(`/dashboard/overview${qs({ year_id: yearId })}`),
  digest: (yearId?: string) =>
    api.get<import("@/lib/school-types").Digest>(`/dashboard/digest${qs({ year_id: yearId })}`),
  createTaskFromAlert: (b: { board_id: string; title: string; description?: string | null }) =>
    api.post<{ id: string }>("/dashboard/alerts/create-task", b),

  // assessments & bands (M3)
  skillAreas: () => api.get<import("@/lib/school-types").SkillArea[]>("/assessments/skill-areas"),
  seedSkills: () => api.post<import("@/lib/school-types").SkillArea[]>("/assessments/skill-areas/seed-defaults"),
  createSkill: (name: string) => api.post<import("@/lib/school-types").SkillArea>("/assessments/skill-areas", { name }),
  deleteSkill: (id: string) => api.del<{ message: string }>(`/assessments/skill-areas/${id}`),
  cycles: (termId?: string) => api.get<import("@/lib/school-types").Cycle[]>(`/assessments/cycles${qs({ term_id: termId })}`),
  createCycle: (b: { term_id?: string; type: string; name: string; date: string; class_id?: string; subject_id?: string }) =>
    api.post<import("@/lib/school-types").Cycle>("/assessments/cycles", b),
  // exams (SC-5): the scores screen's exam-first surface.
  examFeed: (opts?: { classId?: string; limit?: number }) =>
    api.get<import("@/lib/school-types").ExamSummary[]>(
      `/assessments/exams${qs({ class_id: opts?.classId, limit: opts?.limit ? String(opts.limit) : undefined })}`),
  exam: (cycleId: string) =>
    api.get<import("@/lib/school-types").ExamDetail>(`/assessments/exams/${cycleId}`),
  saveExam: (b: import("@/lib/school-types").ExamSaveBody) =>
    api.post<import("@/lib/school-types").ExamDetail>("/assessments/exams", b),
  /** The feed with a page and a total (founder 2026-08-05). A school records
   *  dozens of tests a term and the flat `limit` list left the 31st
   *  unreachable from any screen. */
  examFeedPage: (p: {
    classId?: string; subjectId?: string; examEventId?: string;
    scale?: "minor" | "major"; page?: number; size?: number;
  } = {}) =>
    api.get<import("@/lib/school-types").ExamFeedPage>(
      `/assessments/exams/page${qs({
        class_id: p.classId, subject_id: p.subjectId,
        exam_event_id: p.examEventId, scale: p.scale,
        page: p.page ? String(p.page) : undefined,
        size: p.size ? String(p.size) : undefined,
      })}`),

  // ── the school's own exam calendar (founder, 2026-08-05) ──────────────────
  // `calendar_events` where type='exam_block', as a screen. Marks still go
  // through `saveExam` — one write path for every mark in the product.
  mainExams: (yearId?: string) =>
    api.get<import("@/lib/school-types").MainExamBoard>(
      `/main-exams${qs({ year_id: yearId })}`),
  mainExam: (eventId: string) =>
    api.get<import("@/lib/school-types").MainExamDetail>(`/main-exams/${eventId}`),
  createMainExam: (b: import("@/lib/school-types").MainExamBody) =>
    api.post<import("@/lib/school-types").MainExamRow>("/main-exams", b),
  updateMainExam: (eventId: string, b: import("@/lib/school-types").MainExamBody) =>
    api.patch<import("@/lib/school-types").MainExamRow>(`/main-exams/${eventId}`, b),
  deleteMainExam: (eventId: string) =>
    api.del<{ message: string }>(`/main-exams/${eventId}`),
  // V1-8 (D-80): the exam's second tab — the analysis beside Score's numbers.
  examReport: (cycleId: string) =>
    api.get<import("@/lib/school-types").ExamReport>(`/assessments/exams/${cycleId}/report`),
  // V1-8 (D-53): verify & lock. The locked exam IS the record; editing after it
  // is refused until an ADMIN unlocks with a reason, and the unlock is appended.
  lockExam: (cycleId: string) =>
    api.post<import("@/lib/school-types").ExamDetail>(`/assessments/exams/${cycleId}/lock`),
  unlockExam: (cycleId: string, reason: string) =>
    api.post<import("@/lib/school-types").ExamDetail>(`/assessments/exams/${cycleId}/unlock`, { reason }),
  // V1-8 (D-55): the school's own exam vocabulary. The picker seeds itself on
  // first read, so nobody configures words before recording a test.
  examTypes: (includeRetired?: boolean) =>
    api.get<import("@/lib/school-types").ExamType[]>(
      `/assessments/exam-types${qs({ include_retired: includeRetired ? "true" : undefined })}`),
  createExamType: (b: { name: string; system_type: string; scale?: string }) =>
    api.post<import("@/lib/school-types").ExamType>("/assessments/exam-types", b),
  updateExamType: (id: string, b: { name?: string; scale?: string; active?: boolean; position?: number }) =>
    api.patch<import("@/lib/school-types").ExamType>(`/assessments/exam-types/${id}`, b),
  // V1-8 (D-81): the two report levels. Level 1 is numbers only; level 2 is the
  // narrative over the SAME figures.
  reportCard: (studentId: string) =>
    api.get<import("@/lib/school-types").ReportCard>(`/students/${studentId}/report-card`),
  studentAnalysis: (studentId: string) =>
    api.get<import("@/lib/school-types").StudentAnalysis>(`/students/${studentId}/analysis`),
  classReportCard: (classId: string) =>
    api.get<import("@/lib/school-types").ClassReportCard>(`/assessments/classes/${classId}/report-card`),
  deleteCycle: (id: string) => api.del<{ message: string }>(`/assessments/cycles/${id}`),
  // ── V1-9 · the support programme ───────────────────────────────────────────
  // `categorizeBands` and `applyBandSuggestions` are DELETED (`S-183`): two
  // implicit routes that re-banded a class off whatever test happened last.
  // Movement now goes through the promote preview, which shows its moves first.
  bandSetup: () => api.get<import("@/lib/school-types").BandSubjectSetup[]>("/bands/setup"),
  setMonitoredSubjects: (subjectIds: string[]) =>
    api.put<import("@/lib/school-types").BandSubjectSetup[]>(
      "/bands/setup/monitored", { subject_ids: subjectIds }),
  updateDescriptor: (id: string, b: { text?: string; min_pct?: number }) =>
    api.patch<import("@/lib/school-types").BandDescriptor>(`/bands/setup/descriptors/${id}`, b),
  bandClassBoard: (p: { classId: string; subjectId: string; cycleId?: string; termId?: string }) =>
    api.get<import("@/lib/school-types").BandClassBoard>(
      `/bands/class${qs({ class_id: p.classId, subject_id: p.subjectId, cycle_id: p.cycleId, term_id: p.termId })}`),
  fileBands: (b: {
    class_id: string; subject_id: string; term_id: string; source: string;
    cycle_id?: string | null; rows: { student_id: string; tier: string | null }[];
  }) => api.post<{ message: string }>("/bands/class/file", b),
  bandPromotePreview: (cycleId: string) =>
    api.get<import("@/lib/school-types").BandPromotePreview>(`/bands/promote/${cycleId}`),
  bandPromote: (cycleId: string) =>
    api.post<import("@/lib/school-types").BandPromotePreview>(`/bands/promote/${cycleId}`),
  bandProgramme: (termId?: string) =>
    api.get<import("@/lib/school-types").ProgrammeBoard>(`/bands/programme${qs({ term_id: termId })}`),
  assignBandOwner: (b: {
    student_id: string; subject_id: string; member_id?: string | null;
    term_id?: string | null; goal_text?: string; exit_criterion?: string;
  }) => api.post<{ message: string }>("/bands/owner", b),
  // ── ABC bands v2 (founder 2026-08-04) ──────────────────────────────────────
  // `bandScope` decides whether the nav item exists at all; `bandDistribution`
  // is the ONE read behind the dashboard block and the Overview tab, so the two
  // can never quote different figures for the same morning.
  bandScope: () => api.get<import("@/lib/school-types").BandScope>("/bands/scope"),
  bandDistribution: (termId?: string) =>
    api.get<import("@/lib/school-types").BandDistribution>(
      `/bands/distribution${qs({ term_id: termId })}`),
  bandAllocation: (p: { termId?: string; classId?: string; subjectId?: string } = {}) =>
    api.get<import("@/lib/school-types").AllocationBoard>(
      `/bands/allocation${qs({ term_id: p.termId, class_id: p.classId, subject_id: p.subjectId })}`),
  bandOwnerSuggestions: (studentId: string, subjectId: string) =>
    api.get<import("@/lib/school-types").OwnerSuggestion[]>(
      `/bands/allocation/suggestions${qs({ student_id: studentId, subject_id: subjectId })}`),
  supportList: (memberId?: string) =>
    api.get<import("@/lib/school-types").SupportList>(`/bands/support${qs({ member_id: memberId })}`),
  supportChild: (interventionId: string) =>
    api.get<import("@/lib/school-types").SupportChild>(`/bands/support/${interventionId}`),
  supportSummary: (interventionId: string) =>
    api.get<import("@/lib/school-types").SupportSummary>(
      `/bands/support/${interventionId}/summary`),
  supportCheckIn: (interventionId: string, b: {
    worked_on?: string; what_changed?: string; next_step?: string; ready_to_retest: boolean;
  }) => api.post<import("@/lib/school-types").SupportChild>(
    `/bands/support/${interventionId}/check-in`, b),
  closeSupportPlan: (interventionId: string, b: { status: string; outcome_note?: string }) =>
    api.post<import("@/lib/school-types").SupportChild>(
      `/bands/support/${interventionId}/close`, b),

  // ── ABC bands · My students + her own assessments (founder 2026-08-05) ─────
  // A teacher gets her own assigned children and her own assessments; an admin
  // gets the school's. The narrowing is the SERVICE's — never a client filter.
  myBandStudents: (classId?: string) =>
    api.get<import("@/lib/school-types").MyStudentsBoard>(
      `/bands/my-students${qs({ class_id: classId })}`),
  bandAssessments: (p: {
    classId?: string; status?: string; page?: number; perPage?: number;
  } = {}) => api.get<import("@/lib/school-types").BandAssessmentList>(
    `/bands/assessments${qs({
      class_id: p.classId, status: p.status,
      page: p.page == null ? undefined : String(p.page),
      per_page: p.perPage == null ? undefined : String(p.perPage),
    })}`),
  createBandAssessment: (b: {
    class_id: string; name: string; subject_id?: string | null;
    instructions?: string | null; description?: string | null;
    metric: import("@/lib/school-types").AssessmentMetric;
    max_marks?: number | null; rating_max?: number | null;
    given_on?: string | null; due_date?: string | null;
    covers_all: boolean; student_ids?: string[];
  }) => api.post<import("@/lib/school-types").BandAssessmentRow>("/bands/assessments", b),
  bandAssessmentSheet: (id: string) =>
    api.get<import("@/lib/school-types").BandAssessmentSheet>(`/bands/assessments/${id}`),
  /** Full replace — a child left out goes back to NOT EVALUATED, not to zero. */
  recordBandAssessment: (id: string, b: {
    results: {
      student_id: string; marks?: number | null; rating?: number | null;
      verdict?: string | null; note?: string | null;
    }[];
  }) => api.put<import("@/lib/school-types").BandAssessmentSheet>(
    `/bands/assessments/${id}/results`, b),
  deleteBandAssessment: (id: string) =>
    api.del<{ message: string }>(`/bands/assessments/${id}`),
  // photo score capture (SC-2): photo → AI transcription → deterministic match →
  // human review grid → confirm. Scores persist only on confirm.
  // cycle_id omitted = a draft exam capture (SC-5), saved via saveExam.
  createCapture: (b: { cycle_id?: string; class_id: string; subject_id?: string; skill_area_id?: string; student_ids?: string[]; mode?: "register" | "scripts" }) =>
    api.post<import("@/lib/school-types").Capture>("/assessments/captures", b),
  capture: (id: string) => api.get<import("@/lib/school-types").Capture>(`/assessments/captures/${id}`),
  captures: (opts?: { cycleId?: string; classId?: string }) =>
    api.get<import("@/lib/school-types").CaptureSummary[]>(`/assessments/captures${qs({ cycle_id: opts?.cycleId, class_id: opts?.classId })}`),
  uploadCapturePage: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.upload<import("@/lib/school-types").Capture>(`/assessments/captures/${id}/pages`, form);
  },
  parseCapture: (id: string) => api.post<import("@/lib/school-types").Capture>(`/assessments/captures/${id}/parse`),
  confirmCapture: (id: string, rows: { student_id: string; score: number; max_score: number }[]) =>
    api.post<import("@/lib/school-types").Capture>(`/assessments/captures/${id}/confirm`, { rows }),
  discardCapture: (id: string) => api.post<{ message: string }>(`/assessments/captures/${id}/discard`),
  scoreGrid: (cycleId: string, classId: string) =>
    api.get<import("@/lib/school-types").ScoreGrid>(`/assessments/cycles/${cycleId}/grid${qs({ class_id: classId })}`),
  saveScores: (cycleId: string, rows: { student_id: string; subject_id?: string; skill_area_id?: string; score: number; max_score: number }[]) =>
    api.post<{ message: string }>(`/assessments/cycles/${cycleId}/scores`, { rows }),
  verifyScores: (cycleId: string) => api.post<{ message: string }>(`/assessments/cycles/${cycleId}/verify`),
  classAnalysis: (classId: string) =>
    api.get<import("@/lib/school-types").ClassAnalysis>(`/assessments/classes/${classId}/analysis`),
  /** student → **"C · Hindi"** (`S-186`) for staff directory chips. Never an
   *  average across subjects, never a bare letter, never parent-facing (P4). */
  currentBands: () => api.get<Record<string, string>>("/assessments/bands/current"),
  trends: (classId: string) =>
    api.get<import("@/lib/school-types").SubjectTrend[]>(`/assessments/classes/${classId}/trends`),
  studentInterventions: (studentId: string) =>
    api.get<import("@/lib/school-types").StudentIntervention[]>(
      `/assessments/students/${studentId}/interventions`),
  addClassSubject: (b: {
    class_id: string;
    subject_id: string;
    teacher_member_id?: string | null;
    periods_per_week?: number;
  }) => api.post<ClassSubject>("/academics/class-subjects", b),
  /** Reassign the teacher, or change the weekly period count, in place. Passing
   *  `teacher_member_id: null` un-assigns. Use this rather than delete + re-add:
   *  deleting a class-subject cascades away its syllabus, plan and timetable slots. */
  updateClassSubject: (id: string, b: { teacher_member_id?: string | null; periods_per_week?: number }) =>
    api.patch<ClassSubject>(`/academics/class-subjects/${id}`, b),
  deleteClassSubject: (id: string) => api.del<{ message: string }>(`/academics/class-subjects/${id}`),
  /** `D-130` — move a subject to another teacher, or leave it unassigned.
   *
   *  Its own route because it is the one part of a class-subject a LIVE school
   *  may change: everything else here is setup and freezes at handover, and a
   *  school that cannot hand the 5th's EVS to somebody else in August has a
   *  register, a syllabus and a My Day that are all wrong from that morning. */
  setClassSubjectTeacher: (id: string, teacherMemberId: string | null) =>
    api.put<ClassSubject>(`/academics/class-subjects/${id}/teacher`,
      { teacher_member_id: teacherMemberId }),

  // ── students ──────────────────────────────────────────────────────────────
  categories: () => api.get<StudentCategory[]>("/students/categories"),
  seedCategories: () => api.post<StudentCategory[]>("/students/categories/seed-defaults"),
  createCategory: (name: string) => api.post<StudentCategory>("/students/categories", { name }),
  /** `D-129`: renaming is safe — everything references the category by id. */
  renameCategory: (id: string, name: string) =>
    api.patch<StudentCategory>(`/students/categories/${id}`, { name }),
  /** 409 with the counts while it is still in use; `force` is the confirmed
   *  removal, which un-assigns every student on it. */
  deleteCategory: (id: string, force = false) =>
    api.del<{ message: string }>(
      `/students/categories/${id}${force ? "?force=true" : ""}`),

  students: (p: { class_id?: string; q?: string } = {}) =>
    api.get<StudentListItem[]>(`/students${qs({ class_id: p.class_id, q: p.q })}`),
  /** Students → Academics: the roster with attendance, exams and homework.
   *  Admin gets the school; a teacher gets her classes ∪ her homeroom, and
   *  asking for someone else's class is a 403 with a sentence, not an empty
   *  table (`S-46`). */
  studentRecords: (p: { class_id?: string; q?: string; window_days?: number } = {}) =>
    api.get<StudentRecords>(`/students/records${qs({
      class_id: p.class_id, q: p.q,
      window_days: p.window_days ? String(p.window_days) : undefined,
    })}`),
  student: (id: string) => api.get<StudentDetail>(`/students/${id}`),
  createStudent: (b: Record<string, unknown>) => api.post<StudentDetail>("/students", b),
  updateStudent: (id: string, b: Record<string, unknown>) =>
    api.patch<StudentDetail>(`/students/${id}`, b),
  deleteStudent: (id: string) => api.del<{ message: string }>(`/students/${id}`),
  addGuardian: (studentId: string, b: {
    name: string; phone: string; relation?: string | null;
    is_primary?: boolean; notify_opt_out?: boolean;
  }) => api.post<Guardian>(`/students/${studentId}/guardians`, b),
  /** V1-13: `notify_opt_out` is the one a school actually needs to change later —
   *  a family that asked to stop being messaged (V1-11 counts them apart and
   *  never puts them on the list the office is told to clear). */
  updateGuardian: (id: string, b: {
    name?: string; phone?: string; relation?: string | null;
    is_primary?: boolean; notify_opt_out?: boolean;
  }) => api.patch<Guardian>(`/students/guardians/${id}`, b),
  deleteGuardian: (id: string) => api.del<{ message: string }>(`/students/guardians/${id}`),
  importRosterAnalyze: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.upload<RosterAnalyze>("/students/import/analyze", form);
  },
  importRosterCommit: (b: {
    mapping: Record<string, string>;
    rows: Record<string, unknown>[];
    academic_year_id: string | null;
  }) => api.post<RosterCommitResult>("/students/import/commit", b),

  // ── timetable (V2-P1, SPRD2 §5.3) ─────────────────────────────────────────
  timetableGrid: (classId: string, onDate?: string) =>
    api.get<import("@/lib/school-types").TimetableGrid>(
      `/timetable/grid${qs({ class_id: classId, on_date: onDate })}`,
    ),
  setSlot: (b: {
    class_id: string; weekday: number; period_no: number;
    slot_type?: "subject" | "block";
    class_subject_id?: string | null; session_id?: string | null;
    effective_from?: string;
  }) => api.put<import("@/lib/school-types").TimetableGrid>("/timetable/slot", b),
  /** One block across many classes and days — "assembly, period 1, everyone". */
  setSlotsBulk: (b: {
    class_ids: string[]; weekdays: number[]; period_no: number;
    slot_type?: "subject" | "block";
    class_subject_id?: string | null; session_id?: string | null;
    effective_from?: string;
  }) => api.post<{ written: number; skipped: string[] }>("/timetable/slot/bulk", b),
  clearSlot: (b: { class_id: string; weekday: number; period_no: number; effective_from?: string }) =>
    api.post<import("@/lib/school-types").TimetableGrid>("/timetable/slot/clear", b),
  validateTimetable: () =>
    api.get<import("@/lib/school-types").TimetableClash[]>("/timetable/validate"),
  // ── TT-4: classes taught together as one meeting ──────────────────────────
  combinedPeriods: (onDate?: string) =>
    api.get<import("@/lib/school-types").CombinedPeriod[]>(
      `/timetable/combined${qs({ on_date: onDate })}`),
  /** "These classes sit together in this period." Silences their clash, gives
   *  the teacher one card, and writes her capture to each class's own record. */
  combinePeriods: (b: {
    weekday: number; period_no: number; class_ids: string[];
    note?: string | null; effective_from?: string;
  }) => api.post<import("@/lib/school-types").CombinedPeriod>("/timetable/combine", b),
  /** Split it back up — pass `class_ids` for one class, omit for the lot. */
  uncombinePeriod: (b: {
    combined_id: string; class_ids?: string[]; effective_from?: string;
  }) => api.post<import("@/lib/school-types").CombinedPeriod[]>("/timetable/uncombine", b),
  myWeek: () => api.get<import("@/lib/school-types").TeacherWeek>("/timetable/my-week"),
  periodConfig: (yearId: string) =>
    api.get<import("@/lib/school-types").PeriodConfig>(`/timetable/period-config${qs({ year_id: yearId })}`),
  setPeriodConfig: (b: { academic_year_id: string; periods_per_day: number; period_times: import("@/lib/school-types").PeriodTime[] }) =>
    api.put<import("@/lib/school-types").PeriodConfig>("/timetable/period-config", b),
  // ── TT-2: the bell schedule (when the day happens) ────────────────────────
  bellSchedule: (yearId: string, onDate?: string) =>
    api.get<import("@/lib/school-types").BellSchedule>(
      `/timetable/bell${qs({ year_id: yearId, on_date: onDate })}`),
  /** Reshape the day from `effective_from`. Append-only: the old shape stays. */
  setBellSchedule: (b: {
    academic_year_id: string;
    entries: import("@/lib/school-types").PeriodTime[];
    effective_from?: string; note?: string | null;
  }) => api.put<import("@/lib/school-types").BellSchedule>("/timetable/bell", b),
  bellHistory: (yearId: string) =>
    api.get<import("@/lib/school-types").BellHistory>(
      `/timetable/bell/history${qs({ year_id: yearId })}`),

  // ── TT-2: blocks (a period that is not a subject) ─────────────────────────
  blocks: () => api.get<import("@/lib/school-types").TimetableBlock[]>("/timetable/blocks"),
  createBlock: (b: {
    name: string; kind: string; category_id?: string | null;
    staff_member_ids?: string[]; class_ids?: string[]; owner_member_id?: string | null;
  }) => api.post<import("@/lib/school-types").TimetableBlock>("/timetable/blocks", b),
  updateBlock: (id: string, b: {
    name?: string; kind?: string; category_id?: string | null;
    staff_member_ids?: string[]; class_ids?: string[];
    owner_member_id?: string | null; active?: boolean;
  }) => api.patch<import("@/lib/school-types").TimetableBlock>(`/timetable/blocks/${id}`, b),
  deleteBlock: (id: string) => api.del<void>(`/timetable/blocks/${id}`),

  // ── TT-2: capturing a block (free — `D-114`). Mirrors the session capture
  // calls above but routed through /blocks, which gates on the block's staff.
  openBlock: (blockId: string, onDate?: string) =>
    api.post<import("@/lib/school-types").Meeting>(
      `/blocks/${blockId}/open${qs({ on_date: onDate })}`),
  blockAttendance: (meetingId: string, rows: {
    student_id: string; status: string; late_minutes?: number | null; homework_done?: boolean | null;
  }[]) => api.patch<import("@/lib/school-types").Meeting>(
    `/blocks/meetings/${meetingId}/attendance`, { rows }),
  setBlockNote: (meetingId: string, note: string | null) =>
    api.put<import("@/lib/school-types").Meeting>(
      `/blocks/meetings/${meetingId}/note`, { note }),
  blockStudentCard: (meetingId: string, studentId: string) =>
    api.get<import("@/lib/school-types").SessionStudentCard>(
      `/blocks/meetings/${meetingId}/students/${studentId}`),
  setBlockStudentLogs: (meetingId: string, studentId: string,
                        entries: { section: string; note: string }[]) =>
    api.put<import("@/lib/school-types").SessionStudentCard>(
      `/blocks/meetings/${meetingId}/students/${studentId}/logs`, { entries }),
  deleteBlockMedia: (mediaId: string) => api.del<void>(`/blocks/media/${mediaId}`),
  uploadBlockMedia: async (meetingId: string, file: File,
                           opts?: { caption?: string; studentId?: string }) => {
    const DIRECT_LIMIT = 25 * 1024 * 1024;
    if (file.size > DIRECT_LIMIT) {
      const pre = await api.post<import("@/lib/school-types").MediaPresign>(
        `/blocks/meetings/${meetingId}/media/presign`,
        { filename: file.name, content_type: file.type || "application/octet-stream",
          size_bytes: file.size, student_id: opts?.studentId ?? null },
      );
      if (pre.upload_url) {
        const put = await fetch(pre.upload_url, {
          method: "PUT", body: file,
          headers: { "Content-Type": file.type || "application/octet-stream" },
        });
        if (!put.ok) throw new Error("Upload to storage failed");
        return api.post<import("@/lib/school-types").Meeting>(
          `/blocks/meetings/${meetingId}/media/confirm`,
          { key: pre.key, caption: opts?.caption || null, student_id: opts?.studentId ?? null });
      }
    }
    const form = new FormData();
    form.append("file", file);
    if (opts?.caption) form.append("caption", opts.caption);
    if (opts?.studentId) form.append("student_id", opts.studentId);
    return api.upload<import("@/lib/school-types").Meeting>(
      `/blocks/meetings/${meetingId}/media`, form);
  },
  /** The homework class: subject tabs for a class, and what is live tonight. */
  blockHomework: (meetingId: string, p?: { classId?: string; classSubjectId?: string }) =>
    api.get<import("@/lib/school-types").BlockHomework>(
      `/blocks/meetings/${meetingId}/homework${qs({
        class_id: p?.classId, class_subject_id: p?.classSubjectId })}`),
  blockHomeworkSheet: (meetingId: string, assignmentId: string) =>
    api.get<import("@/lib/school-types").HomeworkSheet>(
      `/blocks/meetings/${meetingId}/homework/${assignmentId}`),
  checkBlockHomework: (meetingId: string, assignmentId: string,
                       results: { student_id: string; status: string; note?: string | null }[]) =>
    api.post<import("@/lib/school-types").HomeworkSheet>(
      `/blocks/meetings/${meetingId}/homework/${assignmentId}/check`, { results }),

  timetableImportAnalyze: (classId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.upload<import("@/lib/school-types").TimetableImportAnalyze>(
      `/timetable/import/analyze${qs({ class_id: classId })}`, form);
  },
  timetableImportCommit: (b: { class_id: string; effective_from?: string; cells: { weekday: number; period_no: number; class_subject_id: string }[] }) =>
    api.post<import("@/lib/school-types").TimetableGrid>("/timetable/import/commit", b),
  timetableDraft: (classId: string) =>
    api.post<import("@/lib/school-types").TimetableDraft>(`/timetable/draft${qs({ class_id: classId })}`),
  /** Whole-school generation: preview (apply=false) or replace the year's grid. */
  timetableGenerate: (b: { academic_year_id: string; effective_from?: string; apply: boolean }) =>
    api.post<import("@/lib/school-types").TimetableGenerate>("/timetable/generate", b),

  // ── fees ────────────────────────────────────────────────────────────────
  // ── V1-10 · the collection board (D-64) ────────────────────────────────────
  // One computation behind every fee screen (`S-152`), so the quarter strip, the
  // class table and the defaulter list cannot disagree with each other.
  collectionBoard: (p: { yearId?: string; quarter?: string } = {}) =>
    api.get<import("@/lib/school-types").CollectionBoard>(
      `/fees/collection${qs({ year_id: p.yearId, quarter: p.quarter })}`),
  feeNotes: (sfId: string) =>
    api.get<import("@/lib/school-types").FeeNote[]>(`/fees/student-fees/${sfId}/notes`),
  addFeeNote: (sfId: string, b: { kind: string; said?: string; promised_date?: string | null }) =>
    api.post<import("@/lib/school-types").FeeNote>(`/fees/student-fees/${sfId}/notes`, b),
  remindFee: (sfId: string) =>
    api.post<import("@/lib/school-types").RemindResult>(`/fees/student-fees/${sfId}/remind`),
  assignFeeFollowup: (sfId: string, b: { member_id: string; board_id?: string }) =>
    api.post<{ task_id: string; message: string }>(`/fees/student-fees/${sfId}/assign`, b),
  /** `D-83`: the assigned teacher's view of ONE student's fee, inside the task. */
  feeFollowup: (taskId: string) =>
    api.get<import("@/lib/school-types").FeeFollowupDetail>(`/fees/followup/${taskId}`),
  structures: (yearId?: string) =>
    api.get<FeeStructure[]>(`/fees/structures${qs({ year_id: yearId })}`),
  createStructure: (b: Record<string, unknown>) => api.post<FeeStructure>("/fees/structures", b),
  studentFees: (p: { year_id?: string; status?: string; search?: string } = {}) =>
    api.get<StudentFeeListItem[]>(
      `/fees/student-fees${qs({ year_id: p.year_id, status: p.status, search: p.search })}`,
    ),
  studentFee: (id: string) => api.get<StudentFeeDetail>(`/fees/student-fees/${id}`),
  enroll: (b: Record<string, unknown>) => api.post<StudentFeeDetail>("/fees/student-fees", b),

  // ── FE-2: lock one student, with the discount agreed at the counter ───────
  /** What she would be billed if nobody changed anything — the class's
   *  structure, already priced and dated. */
  feeSetup: (studentId: string, yearId: string) =>
    api.get<import("@/lib/school-types").FeeSetup>(
      `/fees/setup/${studentId}${qs({ year_id: yearId })}`),
  /** The arithmetic behind a discount, done server-side. Writes nothing — and
   *  the rows it returns are exactly what `enroll` will store. */
  feeSetupPreview: (b: {
    student_id: string; academic_year_id: string;
    /** Pick a structure deliberately — e.g. billing a day scholar on the
     *  Hosteller price because that is what the school agreed. */
    fee_structure_id?: string | null; total_fee?: string | null;
    discount?: string; opening_dues?: string; num_installments?: number | null;
  }) => api.post<import("@/lib/school-types").FeeSetupPreview>(
    "/fees/setup/preview", b),
  updateDiscount: (id: string, b: { discount?: string; opening_dues?: string }) =>
    api.patch<StudentFeeDetail>(`/fees/student-fees/${id}`, b),
  transactions: (id: string) => api.get<import("@/lib/school-types").FeeTransaction[]>(
    `/fees/student-fees/${id}/transactions`,
  ),
  pay: (instId: string, b: {
    amount: string; mode?: string; note?: string; paid_on?: string;
    receipt_number?: string | null;
    /** `D-122` — an already-uploaded object key, so the payment and its proof
     *  land in one round trip. Optional always: a cash payment at the counter
     *  must never be blocked on producing evidence. */
    proof_key?: string | null;
  }) => api.post<StudentFeeDetail>(`/fees/installments/${instId}/pay`, b),
  markPaid: (instId: string) =>
    api.post<StudentFeeDetail>(`/fees/installments/${instId}/mark-paid`),
  undo: (instId: string) => api.post<StudentFeeDetail>(`/fees/installments/${instId}/undo`),
  setDueDate: (instId: string, dueDate: string | null) =>
    api.patch<StudentFeeDetail>(`/fees/installments/${instId}/due-date`,
      { due_date: dueDate }),

  // ── FE-1: the fee desk ────────────────────────────────────────────────────
  /** `D-117` — every class of the year, priced or not. The unpriced row is the
   *  one that matters, so this is a coverage read, not a list of structures. */
  structureCoverage: (yearId: string) =>
    api.get<import("@/lib/school-types").StructureCoverage>(
      `/fees/structures/coverage${qs({ year_id: yearId })}`),
  /** `D-118` — an edit to the admin; archive-and-replace underneath. Students
   *  already set up keep the amount they were set up on. */
  updateStructure: (id: string, b: Record<string, unknown>) =>
    api.put<FeeStructure>(`/fees/structures/${id}`, b),
  /** `D-120` — set a whole class up in one action. Empty `student_ids` means
   *  every active student in the class. */
  applyStructure: (id: string, b: { student_ids?: string[]; skip_existing?: boolean }) =>
    api.post<import("@/lib/school-types").ApplyStructureResult>(
      `/fees/structures/${id}/apply`, b),

  /** `D-121` — the schedule may be re-arranged; the total may not move. */
  splitInstallment: (instId: string, b: { parts?: number; amounts?: string[] }) =>
    api.post<StudentFeeDetail>(`/fees/installments/${instId}/split`, b),
  addInstallment: (sfId: string,
    b: { amount: string; due_date?: string | null; label?: string | null }) =>
    api.post<StudentFeeDetail>(`/fees/student-fees/${sfId}/installments`, b),
  removeInstallment: (instId: string) =>
    api.del<StudentFeeDetail>(`/fees/installments/${instId}`),

  /** FE-3 — correct a record that was set up wrong: the total, the discount,
   *  the previous dues and the whole schedule, as ONE decision. Not a PATCH per
   *  field: every intermediate state would have to balance, so "₹60,000 in 4
   *  should have been ₹45,000 in 6" would be refused at the first step. */
  reviseFee: (sfId: string, b: import("@/lib/school-types").FeeRevise) =>
    api.put<StudentFeeDetail>(`/fees/student-fees/${sfId}/revise`, b),

  /** `D-127` — the transfer, and its undo. */
  closeFeeRecord: (sfId: string, reason?: string) =>
    api.post<StudentFeeDetail>(`/fees/student-fees/${sfId}/close`, { reason }),
  reopenFeeRecord: (sfId: string) =>
    api.post<StudentFeeDetail>(`/fees/student-fees/${sfId}/reopen`),

  /** `D-124` — who did what. Two reads: the whole year (admin2 looking for a
   *  change she noticed) and one child (the family page). */
  feeActivity: (yearId: string) =>
    api.get<import("@/lib/school-types").FeeEvent[]>(
      `/fees/activity${qs({ year_id: yearId })}`),
  feeActivityForStudent: (sfId: string) =>
    api.get<import("@/lib/school-types").FeeEvent[]>(
      `/fees/student-fees/${sfId}/activity`),

  /** `D-122` — proof of payment. */
  feeProofs: (sfId: string) =>
    api.get<import("@/lib/school-types").FeeProof[]>(
      `/fees/student-fees/${sfId}/proofs`),
  deleteFeeProof: (proofId: string) => api.del<void>(`/fees/proofs/${proofId}`),
  /** Pass-through upload — the phone camera lands here. */
  uploadFeeProof: (txnId: string, file: File, caption?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (caption) form.append("caption", caption);
    return api.upload<import("@/lib/school-types").FeeProof>(
      `/fees/transactions/${txnId}/proofs`, form);
  },

  // ── SF-1 staff: attendance · timesheet · leave ────────────────────────────
  staffAttendance: (onDate?: string) =>
    api.get<StaffAttendance>(`/staff/attendance${qs({ on_date: onDate })}`),
  /** Full replace of the day's exception set — "everyone in, on time" is empty.
   *  `marks` carries D-04's half-day/late; `absent_member_ids` is the pre-V1-4
   *  shorthand for plain absence and still works. */
  markStaffAttendance: (b: {
    date?: string; marks?: StaffMark[];
    absent_member_ids?: string[]; notes?: Record<string, string>;
  }) => api.post<StaffAttendance>("/staff/attendance", b),
  /** D-78 — days worked out of working days. Admin: everyone. Teacher: herself. */
  staffMonth: (p: { month?: string; member_id?: string } = {}) =>
    api.get<StaffMonth>(`/staff/month${qs(p)}`),

  // ── the staff directory (founder, 2026-08-05) ───────────────────────────
  // The people screen, not the accounts screen. `updateStaff` is one PATCH for
  // one form: profile, role and homeroom together, because that is how an admin
  // edits a person. `class_teacher_of` writes the CLASS — there is no
  // class-teacher role to set.
  staffDirectory: () => api.get<StaffDirectory>("/staff/directory"),
  staffDetail: (memberId: string) =>
    api.get<StaffDetail>(`/staff/directory/${memberId}`),
  updateStaff: (memberId: string, b: StaffUpdateIn) =>
    api.patch<StaffDetail>(`/staff/directory/${memberId}`, b),

  workTypes: () => api.get<WorkType[]>("/staff/work-types"),
  timesheetWeek: (p: { member_id?: string; week_start?: string } = {}) =>
    api.get<TimesheetWeek>(`/staff/timesheet/week${qs(p)}`),
  timesheetDay: (p: { member_id?: string; on_date?: string } = {}) =>
    api.get<TimesheetDay>(`/staff/timesheet/day${qs(p)}`),
  timesheetMonth: (p: { member_id?: string; month?: string } = {}) =>
    api.get<TimesheetMonth>(`/staff/timesheet/month${qs(p)}`),
  setTimesheetEntry: (b: { date: string; period_no: number; work_type: string; note?: string | null; member_id?: string }) =>
    api.put<TimesheetDay>("/staff/timesheet/entry", b),
  clearTimesheetEntry: (p: { on_date: string; period_no: number; member_id?: string }) =>
    api.del<TimesheetDay>(`/staff/timesheet/entry${qs({ ...p, period_no: String(p.period_no) })}`),
  orgTimesheetToday: (onDate?: string) =>
    api.get<TimesheetWeek[]>(`/staff/timesheet/today${qs({ on_date: onDate })}`),

  leavePolicy: () => api.get<LeavePolicy>("/staff/leave/policy"),
  setLeavePolicy: (b: LeavePolicy) => api.put<LeavePolicy>("/staff/leave/policy", b),
  leaveBalance: (memberId?: string) =>
    api.get<LeaveBalance>(`/staff/leave/balance${qs({ member_id: memberId })}`),
  leaveRequests: (p: { status?: string; mine?: boolean } = {}) =>
    api.get<LeaveList>(`/staff/leave${qs({ status: p.status, mine: p.mine ? "true" : undefined })}`),
  applyLeave: (b: {
    start_date: string; end_date: string; reason: string;
    is_half_day?: boolean; portion?: "am" | "pm" | null;
  }) =>
    api.post<LeaveRequest>("/staff/leave", b),
  decideLeave: (id: string, b: { action: "approved" | "rejected"; note?: string | null }) =>
    api.post<LeaveRequest>(`/staff/leave/${id}/decision`, b),
  cancelLeave: (id: string) => api.post<LeaveRequest>(`/staff/leave/${id}/cancel`),
};
