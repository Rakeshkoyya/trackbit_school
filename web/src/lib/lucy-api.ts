// Typed wrappers for the Lucy endpoints (REST side; the SSE stream lives in
// components/lucy/use-lucy-stream.ts on top of lib/sse.ts).

import { api } from "@/lib/api-client";
import type {
  LucyConversation,
  LucyConversationDetail,
  LucyMeta,
  LucyViewDetail,
  LucyViewSummary,
  LucyWidget,
  PendingAction,
} from "@/lib/lucy-types";

export const lucyApi = {
  meta: () => api.get<LucyMeta>("/lucy/meta"),

  createConversation: (title?: string) =>
    api.post<LucyConversation>("/lucy/conversations", { title: title ?? null }),
  listConversations: () => api.get<LucyConversation[]>("/lucy/conversations"),
  conversation: (id: string) =>
    api.get<LucyConversationDetail>(`/lucy/conversations/${id}`),
  deleteConversation: (id: string) => api.del<null>(`/lucy/conversations/${id}`),

  views: () => api.get<LucyViewSummary[]>("/lucy/views"),
  view: (id: string) => api.get<LucyViewDetail>(`/lucy/views/${id}`),
  refreshView: (id: string) => api.post<LucyViewDetail>(`/lucy/views/${id}/refresh`),
  deleteView: (id: string) => api.del<null>(`/lucy/views/${id}`),

  pins: () => api.get<LucyWidget[]>("/lucy/pins"),
  pin: (widgetId: string) => api.post<LucyWidget>(`/lucy/widgets/${widgetId}/pin`),
  unpin: (widgetId: string) => api.post<LucyWidget>(`/lucy/widgets/${widgetId}/unpin`),
  refreshWidget: (widgetId: string) =>
    api.post<LucyWidget>(`/lucy/widgets/${widgetId}/refresh`),

  confirmAction: (actionId: string) =>
    api.post<PendingAction>(`/lucy/actions/${actionId}/confirm`),
  cancelAction: (actionId: string) =>
    api.post<PendingAction>(`/lucy/actions/${actionId}/cancel`),
};
