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

  classSubjects: (classId: string) =>
    api.get<ClassSubject[]>(`/academics/classes/${classId}/subjects`),

  // planner: syllabus + plan + forecast (M1)
  syllabus: (csId: string) =>
    api.get<import("@/lib/school-types").SyllabusUnit[]>(`/planner/syllabus${qs({ class_subject_id: csId })}`),
  addUnit: (b: { class_subject_id: string; title: string }) =>
    api.post<import("@/lib/school-types").SyllabusUnit>("/planner/syllabus/units", b),
  addTopic: (b: { unit_id: string; title: string; est_periods?: number }) =>
    api.post<import("@/lib/school-types").SyllabusTopic>("/planner/syllabus/topics", b),
  deleteUnit: (id: string) => api.del<{ message: string }>(`/planner/syllabus/units/${id}`),
  deleteTopic: (id: string) => api.del<{ message: string }>(`/planner/syllabus/topics/${id}`),
  plan: (csId: string) =>
    api.get<import("@/lib/school-types").Plan>(`/planner/plan${qs({ class_subject_id: csId })}`),
  draftPlan: (csId: string) =>
    api.post<import("@/lib/school-types").Plan>(`/planner/plan/${csId}/draft`),
  approvePlan: (csId: string) =>
    api.post<import("@/lib/school-types").Plan>(`/planner/plan/${csId}/approve`),
  forecast: (classId: string) =>
    api.get<import("@/lib/school-types").Forecast[]>(`/planner/plan/forecast${qs({ class_id: classId })}`),

  // classroom (M2)
  myDay: () => api.get<import("@/lib/school-types").MyDay>("/classroom/my-day"),
  logLesson: (b: { class_subject_id: string; topic_id?: string | null; coverage: string }) =>
    api.post<{ id: string }>("/classroom/lesson-logs", b),
  addHomework: (b: { class_subject_id: string; text: string; due_date?: string | null }) =>
    api.post<{ id: string; notified_count: number }>("/classroom/homework", b),
  checkHomework: (id: string, b: { done_count: number; total_count: number }) =>
    api.post<{ id: string }>(`/classroom/homework/${id}/check`, b),
  compliance: () => api.get<import("@/lib/school-types").Compliance>("/classroom/compliance"),

  // sessions (M2)
  sessions: () => api.get<import("@/lib/school-types").SessionSummary[]>("/sessions"),
  session: (id: string) => api.get<import("@/lib/school-types").SessionDetail>(`/sessions/${id}`),
  createSession: (b: { name: string; weekdays: number[]; time?: string | null; student_ids: string[] }) =>
    api.post<import("@/lib/school-types").SessionDetail>("/sessions", b),
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

  // director dashboard (M4)
  dashboard: (yearId?: string) =>
    api.get<import("@/lib/school-types").DashboardOverview>(`/dashboard/overview${qs({ year_id: yearId })}`),
  digest: (yearId?: string) =>
    api.get<import("@/lib/school-types").Digest>(`/dashboard/digest${qs({ year_id: yearId })}`),
  createTaskFromAlert: (b: { board_id: string; title: string; description?: string | null }) =>
    api.post<{ id: string }>("/dashboard/alerts/create-task", b),
  addClassSubject: (b: {
    class_id: string;
    subject_id: string;
    teacher_member_id?: string | null;
    periods_per_week?: number;
  }) => api.post<ClassSubject>("/academics/class-subjects", b),
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
