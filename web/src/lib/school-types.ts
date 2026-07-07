// TrackBit School domain types — mirror app/schemas/{academics,students,fees}.py.

export interface AcademicYear {
  id: string;
  label: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
}

export interface Term {
  id: string;
  academic_year_id: string;
  name: string;
  start_date: string;
  end_date: string;
}

export interface Subject {
  id: string;
  name: string;
}

export interface SchoolClass {
  id: string;
  academic_year_id: string;
  name: string;
  section: string | null;
  class_teacher_member_id: string | null;
}

export type CalendarEventType = "holiday" | "exam_block" | "event" | "celebration";

export interface CalendarEvent {
  id: string;
  academic_year_id: string;
  type: CalendarEventType;
  title: string;
  start_date: string;
  end_date: string;
  affects_teaching: boolean;
  notes: string | null;
}

export interface CalendarSummary {
  academic_year_id: string;
  start_date: string;
  end_date: string;
  working_weekdays: number[];
  teaching_days: number;
  events: CalendarEvent[];
}

export interface ClassSubject {
  id: string;
  class_id: string;
  subject_id: string;
  subject_name: string | null;
  teacher_member_id: string | null;
  periods_per_week: number;
}

export interface StudentCategory {
  id: string;
  name: string;
}

export interface Guardian {
  id: string;
  student_id: string;
  name: string;
  relation: string | null;
  phone: string;
  is_primary: boolean;
  notify_opt_out: boolean;
}

export interface StudentListItem {
  id: string;
  admission_no: string;
  full_name: string;
  class_id: string | null;
  roll_no: string | null;
  status: string;
  category_id: string | null;
}

export interface StudentDetail extends StudentListItem {
  class_label: string | null;
  category_name: string | null;
  guardians: Guardian[];
}

export interface RosterAnalyze {
  columns: string[];
  mapping: Record<string, string>;
  rows: Record<string, unknown>[];
  row_count: number;
}

export interface RosterCommitResult {
  created: number;
  skipped: number;
  errors: { row: number; reason: string }[];
}

// ── fees ──────────────────────────────────────────────────────────────────
export interface FeeTemplate {
  installment_number: number;
  label: string | null;
  amount: string;
  due_date: string | null;
}

export interface FeeStructure {
  id: string;
  class_name: string;
  category_id: string | null;
  category_name: string | null;
  academic_year_id: string;
  total_amount: string;
  num_installments: number;
  is_active: boolean;
  templates: FeeTemplate[];
}

export interface Installment {
  id: string;
  installment_number: number;
  label: string | null;
  amount: string;
  due_date: string | null;
  paid_amount: string;
  status: string;
  paid_date: string | null;
}

export interface StudentFeeListItem {
  id: string;
  student_id: string;
  student_name: string;
  class_label: string | null;
  category_name: string | null;
  academic_year_id: string;
  total_fee: string;
  discount: string;
  net_fee: string;
  opening_dues: string;
  paid: string;
  pending: string;
  status: string;
}

export interface StudentFeeDetail {
  id: string;
  student_id: string;
  student_name: string;
  class_label: string | null;
  category_name: string | null;
  academic_year_id: string;
  total_fee: string;
  discount: string;
  net_fee: string;
  opening_dues: string;
  total_payable: string;
  paid: string;
  balance: string;
  status: string;
  installments: Installment[];
}

export interface FeeTransaction {
  id: string;
  installment_id: string | null;
  amount: string;
  type: string;
  note: string | null;
  mode: string | null;
  receipt_number: string | null;
  created_at: string;
  created_by_name: string | null;
}

export interface FeeSummary {
  total_fee: string;
  collected_fee: string;
  pending_installments: number;
  overdue_amount: string;
}
