import { api } from "@/lib/api-client";
import type {
  AcademicYear,
  CalendarEvent,
  CalendarSummary,
  ClassSubject,
  FeeStructure,
  FeeSummary,
  Guardian,
  RosterAnalyze,
  RosterCommitResult,
  SchoolClass,
  StudentCategory,
  StudentDetail,
  StudentFeeDetail,
  StudentFeeListItem,
  StudentListItem,
  Subject,
  Term,
} from "@/lib/school-types";

const qs = (params: Record<string, string | undefined>) => {
  const p = Object.entries(params).filter(([, v]) => v != null && v !== "");
  return p.length ? "?" + p.map(([k, v]) => `${k}=${encodeURIComponent(v!)}`).join("&") : "";
};

export const schoolApi = {
  // ── academics (master data) ───────────────────────────────────────────────
  years: () => api.get<AcademicYear[]>("/academics/years"),
  createYear: (b: { label: string; start_date: string; end_date: string }) =>
    api.post<AcademicYear>("/academics/years", b),
  activateYear: (id: string) => api.post<AcademicYear>(`/academics/years/${id}/activate`),
  deleteYear: (id: string) => api.del<{ message: string }>(`/academics/years/${id}`),

  terms: (yearId?: string) => api.get<Term[]>(`/academics/terms${qs({ year_id: yearId })}`),
  createTerm: (b: { academic_year_id: string; name: string; start_date: string; end_date: string }) =>
    api.post<Term>("/academics/terms", b),
  deleteTerm: (id: string) => api.del<{ message: string }>(`/academics/terms/${id}`),

  subjects: () => api.get<Subject[]>("/academics/subjects"),
  createSubject: (name: string) => api.post<Subject>("/academics/subjects", { name }),
  deleteSubject: (id: string) => api.del<{ message: string }>(`/academics/subjects/${id}`),

  classes: (yearId?: string) => api.get<SchoolClass[]>(`/academics/classes${qs({ year_id: yearId })}`),
  createClass: (b: { academic_year_id: string; name: string; section?: string | null }) =>
    api.post<SchoolClass>("/academics/classes", b),
  deleteClass: (id: string) => api.del<{ message: string }>(`/academics/classes/${id}`),

  // calendar (M1)
  calendarSummary: (yearId: string) =>
    api.get<CalendarSummary>(`/academics/calendar/summary${qs({ year_id: yearId })}`),
  createEvent: (b: {
    academic_year_id: string;
    type: string;
    title: string;
    start_date: string;
    end_date: string;
    affects_teaching?: boolean;
  }) => api.post<CalendarEvent>("/academics/calendar/events", b),
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

  classSubjects: (classId: string) =>
    api.get<ClassSubject[]>(`/academics/classes/${classId}/subjects`),
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
  generatePlan: (csId: string, termId?: string | null) =>
    api.post<import("@/lib/school-types").PlanGenerateResult>(
      `/planner/plan/${csId}/generate${qs({ term_id: termId ?? undefined })}`),
  planComments: (csId: string, includeResolved = false) =>
    api.get<import("@/lib/school-types").PlanComment[]>(
      `/planner/plan/${csId}/comments${qs({ include_resolved: includeResolved ? "true" : undefined })}`),
  addPlanComment: (csId: string, b: { text: string; topic_id?: string | null }) =>
    api.post<import("@/lib/school-types").PlanComment>(`/planner/plan/${csId}/comments`, b),
  resolvePlanComment: (id: string) =>
    api.post<import("@/lib/school-types").PlanComment>(`/planner/plan/comments/${id}/resolve`),

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

  topicProgress: (csId: string) =>
    api.get<import("@/lib/school-types").TopicProgressRow[]>(
      `/planner/plan/${csId}/progress`),

  // ── post-setup read models (V2-P10) ───────────────────────────────────────
  schoolOverview: (yearId?: string) =>
    api.get<import("@/lib/school-types").SchoolOverview>(
      `/overview/school${qs({ year_id: yearId })}`),
  classOverview: (classId: string) =>
    api.get<import("@/lib/school-types").ClassOverview>(`/overview/classes/${classId}`),
  teacherLoad: () =>
    api.get<import("@/lib/school-types").TeacherLoadRow[]>("/overview/teacher-load"),

  // setup wizard (V2-P5, SPRD2 §5.1)
  wizardState: () => api.get<import("@/lib/school-types").WizardState>("/wizard/state"),
  wizardAdvance: (b: { to_step: number; payload?: Record<string, unknown> }) =>
    api.post<import("@/lib/school-types").WizardState>("/wizard/advance", b),
  wizardComplete: () => api.post<import("@/lib/school-types").WizardState>("/wizard/complete"),
  wizardReset: () => api.post<import("@/lib/school-types").WizardState>("/wizard/reset"),
  forecast: (classId: string) =>
    api.get<import("@/lib/school-types").Forecast[]>(`/planner/plan/forecast${qs({ class_id: classId })}`),

  // classroom (M2)
  myDay: () => api.get<import("@/lib/school-types").MyDay>("/classroom/my-day"),
  logLesson: (b: { class_subject_id: string; topic_id?: string | null; coverage: string }) =>
    api.post<{ id: string }>("/classroom/lesson-logs", b),
  addHomework: (b: { class_subject_id: string; text: string; due_date?: string | null; student_id?: string | null }) =>
    api.post<{ id: string; notified_count: number }>("/classroom/homework", b),
  checkHomework: (id: string, b: { done_count: number; total_count: number }) =>
    api.post<{ id: string }>(`/classroom/homework/${id}/check`, b),
  compliance: () => api.get<import("@/lib/school-types").Compliance>("/classroom/compliance"),

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
  }) => api.post<import("@/lib/school-types").AttendanceMarkResult>("/attendance/mark", b),

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
  uploadEvidence: (meetingId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.upload<import("@/lib/school-types").Meeting>(`/sessions/meetings/${meetingId}/photo`, form);
  },
  sessionRecords: () => api.get<import("@/lib/school-types").SessionRecord[]>("/sessions/records"),
  setStudentLogs: (meetingId: string, rows: { student_id: string; note: string; subject_id?: string | null }[]) =>
    api.put<import("@/lib/school-types").Meeting>(`/sessions/meetings/${meetingId}/logs`, { rows }),
  homeworkBoard: (meetingId: string) =>
    api.get<import("@/lib/school-types").HomeworkBoard>(`/sessions/meetings/${meetingId}/homework`),
  deleteSessionMedia: (mediaId: string) => api.del<{ message: string }>(`/sessions/media/${mediaId}`),
  // Media upload: presign → direct-to-R2 PUT → confirm; falls back to the
  // pass-through endpoint when R2 isn't configured (dev) or for small files.
  uploadSessionMedia: async (meetingId: string, file: File, caption?: string) => {
    const DIRECT_LIMIT = 25 * 1024 * 1024;
    if (file.size > DIRECT_LIMIT) {
      const pre = await api.post<import("@/lib/school-types").MediaPresign>(
        `/sessions/meetings/${meetingId}/media/presign`,
        { filename: file.name, content_type: file.type || "application/octet-stream", size_bytes: file.size },
      );
      if (pre.upload_url) {
        const put = await fetch(pre.upload_url, {
          method: "PUT", body: file,
          headers: { "Content-Type": file.type || "application/octet-stream" },
        });
        if (!put.ok) throw new Error("Upload to storage failed");
        return api.post<import("@/lib/school-types").Meeting>(
          `/sessions/meetings/${meetingId}/media/confirm`, { key: pre.key, caption: caption || null });
      }
    }
    const form = new FormData();
    form.append("file", file);
    if (caption) form.append("caption", caption);
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
  createCycle: (b: { term_id: string; type: string; name: string; date: string }) =>
    api.post<import("@/lib/school-types").Cycle>("/assessments/cycles", b),
  scoreGrid: (cycleId: string, classId: string) =>
    api.get<import("@/lib/school-types").ScoreGrid>(`/assessments/cycles/${cycleId}/grid${qs({ class_id: classId })}`),
  saveScores: (cycleId: string, rows: { student_id: string; subject_id?: string; skill_area_id?: string; score: number; max_score: number }[]) =>
    api.post<{ message: string }>(`/assessments/cycles/${cycleId}/scores`, { rows }),
  verifyScores: (cycleId: string) => api.post<{ message: string }>(`/assessments/cycles/${cycleId}/verify`),
  bandBoard: (classId: string, termId?: string) =>
    api.get<import("@/lib/school-types").BandBoard>(`/assessments/bands${qs({ class_id: classId, term_id: termId })}`),
  setBand: (b: { student_id: string; term_id: string; tier: string; note?: string | null }) =>
    api.post<{ message: string }>("/assessments/bands", b),
  bandHistory: (studentId: string) =>
    api.get<import("@/lib/school-types").BandHistoryRow[]>(`/assessments/students/${studentId}/bands`),
  skillProfile: (studentId: string) =>
    api.get<import("@/lib/school-types").SkillProfile>(`/assessments/students/${studentId}/skill-profile`),
  trends: (classId: string) =>
    api.get<import("@/lib/school-types").SubjectTrend[]>(`/assessments/classes/${classId}/trends`),
  studentInterventions: (studentId: string) =>
    api.get<import("@/lib/school-types").Intervention[]>(`/assessments/students/${studentId}/interventions`),
  createIntervention: (b: { student_id: string; term_id: string; goal_text: string; target_tier: string; board_id: string; items: string[] }) =>
    api.post<import("@/lib/school-types").Intervention>("/assessments/interventions", b),
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

  // ── students ──────────────────────────────────────────────────────────────
  categories: () => api.get<StudentCategory[]>("/students/categories"),
  seedCategories: () => api.post<StudentCategory[]>("/students/categories/seed-defaults"),
  createCategory: (name: string) => api.post<StudentCategory>("/students/categories", { name }),
  deleteCategory: (id: string) => api.del<{ message: string }>(`/students/categories/${id}`),

  students: (p: { class_id?: string; q?: string } = {}) =>
    api.get<StudentListItem[]>(`/students${qs({ class_id: p.class_id, q: p.q })}`),
  student: (id: string) => api.get<StudentDetail>(`/students/${id}`),
  createStudent: (b: Record<string, unknown>) => api.post<StudentDetail>("/students", b),
  updateStudent: (id: string, b: Record<string, unknown>) =>
    api.patch<StudentDetail>(`/students/${id}`, b),
  deleteStudent: (id: string) => api.del<{ message: string }>(`/students/${id}`),
  addGuardian: (studentId: string, b: Record<string, unknown>) =>
    api.post<Guardian>(`/students/${studentId}/guardians`, b),
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
  setSlot: (b: { class_id: string; weekday: number; period_no: number; class_subject_id: string; effective_from?: string }) =>
    api.put<import("@/lib/school-types").TimetableGrid>("/timetable/slot", b),
  clearSlot: (b: { class_id: string; weekday: number; period_no: number; effective_from?: string }) =>
    api.post<import("@/lib/school-types").TimetableGrid>("/timetable/slot/clear", b),
  validateTimetable: () =>
    api.get<import("@/lib/school-types").TimetableClash[]>("/timetable/validate"),
  myWeek: () => api.get<import("@/lib/school-types").TeacherWeek>("/timetable/my-week"),
  periodConfig: (yearId: string) =>
    api.get<import("@/lib/school-types").PeriodConfig>(`/timetable/period-config${qs({ year_id: yearId })}`),
  setPeriodConfig: (b: { academic_year_id: string; periods_per_day: number; period_times: import("@/lib/school-types").PeriodTime[] }) =>
    api.put<import("@/lib/school-types").PeriodConfig>("/timetable/period-config", b),
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
  feeSummary: (yearId?: string) => api.get<FeeSummary>(`/fees/summary${qs({ year_id: yearId })}`),
  structures: (yearId?: string) =>
    api.get<FeeStructure[]>(`/fees/structures${qs({ year_id: yearId })}`),
  createStructure: (b: Record<string, unknown>) => api.post<FeeStructure>("/fees/structures", b),
  studentFees: (p: { year_id?: string; status?: string; search?: string } = {}) =>
    api.get<StudentFeeListItem[]>(
      `/fees/student-fees${qs({ year_id: p.year_id, status: p.status, search: p.search })}`,
    ),
  studentFee: (id: string) => api.get<StudentFeeDetail>(`/fees/student-fees/${id}`),
  enroll: (b: Record<string, unknown>) => api.post<StudentFeeDetail>("/fees/student-fees", b),
  updateDiscount: (id: string, b: { discount?: string; opening_dues?: string }) =>
    api.patch<StudentFeeDetail>(`/fees/student-fees/${id}`, b),
  transactions: (id: string) => api.get<import("@/lib/school-types").FeeTransaction[]>(
    `/fees/student-fees/${id}/transactions`,
  ),
  pay: (instId: string, b: { amount: string; mode?: string; note?: string }) =>
    api.post<StudentFeeDetail>(`/fees/installments/${instId}/pay`, b),
  markPaid: (instId: string) => api.post<StudentFeeDetail>(`/fees/installments/${instId}/mark-paid`),
  undo: (instId: string) => api.post<StudentFeeDetail>(`/fees/installments/${instId}/undo`),
};
