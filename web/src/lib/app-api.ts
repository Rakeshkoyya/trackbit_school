import { api } from "@/lib/api-client";
import type {
  AdminResetResult,
  Attachment,
  Billing,
  Board,
  BulkMemberInput,
  BulkMembersResult,
  BoardReport,
  BoardsList,
  BoardTable,
  Checkout,
  CompleteResult,
  History,
  Home,
  Member,
  MyTasks,
  NudgeResult,
  OrgDashboard,
  OrgSettings,
  RecurrenceRule,
  RecurringHistory,
  RecurringTemplate,
  Task,
  TaskDetail,
  UsernameCheck,
} from "@/lib/types";

export interface CreateTaskInput {
  board_id: string;
  title: string;
  description?: string | null;
  category?: string | null;
  assignee_id?: string | null;
  due_at?: string | null;
  all_day?: boolean;
  is_critical?: boolean;
  priority?: number;
}

export const appApi = {
  // Home + personal history (S10)
  today: () => api.get<Home>("/me/today"),
  myTasks: () => api.get<MyTasks>("/me/tasks"),
  history: () => api.get<History>("/me/history"),

  // Reports (S6 board report, S7 org dashboard)
  boardReport: (id: string, range: "today" | "week") =>
    api.get<BoardReport>(`/boards/${id}/report?range=${range}`),
  orgDashboard: (range: "today" | "week") =>
    api.get<OrgDashboard>(`/org/dashboard?range=${range}`),
  nudge: (userId: string) => api.post<NudgeResult>(`/org/nudge/${userId}`),

  // Boards
  boards: () => api.get<BoardsList>("/boards"),
  board: (id: string) => api.get<Board>(`/boards/${id}`),
  createBoard: (body: {
    name: string;
    visibility?: string;
    task_scope?: string;
    category?: string;
  }) => api.post<Board>("/boards", body),
  updateBoard: (id: string, body: Record<string, unknown>) =>
    api.patch<Board>(`/boards/${id}`, body),
  deleteBoard: (id: string) => api.del<{ message: string }>(`/boards/${id}`),
  boardTasks: (id: string, includeDone = true) =>
    api.get<Task[]>(`/boards/${id}/tasks?include_done=${includeDone}`),
  boardTable: (id: string) => api.get<BoardTable>(`/boards/${id}/table`),
  boardCategories: (id: string) => api.get<string[]>(`/boards/${id}/categories`),
  createCategory: (id: string, name: string, color?: string) =>
    api.post<{ message: string }>(`/boards/${id}/categories`, { name, color }),
  updateCategory: (id: string, name: string, body: { new_name?: string; color?: string }) =>
    api.patch<{ message: string }>(`/boards/${id}/categories`, { name, ...body }),
  deleteCategory: (id: string, name: string) =>
    api.del<{ message: string }>(`/boards/${id}/categories?name=${encodeURIComponent(name)}`),
  addBoardMember: (id: string, user_id: string) =>
    api.post<Board>(`/boards/${id}/members`, { user_id }),
  removeBoardMember: (id: string, user_id: string) =>
    api.del<Board>(`/boards/${id}/members/${user_id}`),

  // Tasks
  task: (id: string) => api.get<TaskDetail>(`/tasks/${id}`),
  createTask: (body: CreateTaskInput) => api.post<TaskDetail>("/tasks", body),
  editTask: (id: string, body: Record<string, unknown>) =>
    api.patch<TaskDetail>(`/tasks/${id}`, body),
  completeTask: (id: string) => api.post<CompleteResult>(`/tasks/${id}/complete`),
  reopenTask: (id: string) => api.post<Task>(`/tasks/${id}/reopen`),
  claimTask: (id: string) => api.post<Task>(`/tasks/${id}/claim`),
  reassignTask: (id: string, to_user_id: string) =>
    api.post<Task>(`/tasks/${id}/reassign`, { to_user_id }),
  assignTask: (id: string, user_id: string | null) =>
    api.post<Task>(`/tasks/${id}/assign`, { user_id }),
  cancelTask: (id: string) => api.post<{ message: string }>(`/tasks/${id}/cancel`),
  makeRecurring: (id: string, days: string[], time: string | null) =>
    api.post<RecurringTemplate>(`/tasks/${id}/make-recurring`, { days, time }),

  // Recurring templates
  templates: (boardId: string) =>
    api.get<RecurringTemplate[]>(`/recurring?board_id=${boardId}`),
  templateHistory: (id: string) => api.get<RecurringHistory>(`/recurring/${id}/history`),
  createTemplate: (body: {
    board_id: string;
    title: string;
    description?: string | null;
    category?: string | null;
    recurrence: RecurrenceRule;
    default_assignee_id?: string | null;
    is_critical?: boolean;
    priority?: number;
  }) => api.post<RecurringTemplate>("/recurring", body),
  updateTemplate: (id: string, body: Record<string, unknown>) =>
    api.patch<RecurringTemplate>(`/recurring/${id}`, body),
  toggleTemplate: (id: string, active: boolean) =>
    api.post<RecurringTemplate>(`/recurring/${id}/toggle?active=${active}`),
  deleteTemplate: (id: string) => api.del<{ message: string }>(`/recurring/${id}`),

  // Attachments (S2)
  attachments: (taskId: string) => api.get<Attachment[]>(`/tasks/${taskId}/attachments`),
  addNote: (taskId: string, content: string) =>
    api.post<Attachment>(`/tasks/${taskId}/notes`, { content }),
  addPhoto: (taskId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.upload<Attachment>(`/tasks/${taskId}/photos`, form);
  },

  // Org settings + billing (S9)
  settings: () => api.get<OrgSettings>("/org/settings"),
  updateSettings: (body: { name?: string; timezone?: string; report_card_hour?: number }) =>
    api.patch<OrgSettings>("/org/settings", body),
  billing: () => api.get<Billing>("/billing"),
  startCheckout: () => api.post<Checkout>("/billing/checkout"),

  // Members
  members: () => api.get<{ members: Member[] }>("/org/members"),
  inviteMember: (body: { name: string; email: string; role: string }) =>
    api.post<{ user_id: string; name: string; role: string; invite_url: string; pending: boolean }>(
      "/org/members/invite",
      // email_invite: backend emails the join link to the invitee (Resend) AND
      // returns the same link as a fallback the admin can share manually.
      { ...body, mode: "email_invite" },
    ),
  bulkAddMembers: (members: BulkMemberInput[]) =>
    api.post<BulkMembersResult>("/org/members/bulk", { members }),
  checkUsername: (username: string) =>
    api.get<UsernameCheck>(`/org/members/username-available?username=${encodeURIComponent(username)}`),
  resetMemberPassword: (user_id: string, password?: string) =>
    api.post<AdminResetResult>(`/org/members/${user_id}/reset-password`, {
      password: password ?? null,
    }),
  changeRole: (user_id: string, role: string) =>
    api.patch<Member>(`/org/members/${user_id}/role`, { role }),
  removeMember: (user_id: string) =>
    api.del<{ orphaned_tasks: number }>(`/org/members/${user_id}`),
};
