import { api } from "@/lib/api-client";
import type {
  AcademicYear,
  ClassSubject,
  FeeStructure,
  FeeSummary,
  Guardian,
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

  classSubjects: (classId: string) =>
    api.get<ClassSubject[]>(`/academics/classes/${classId}/subjects`),
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
