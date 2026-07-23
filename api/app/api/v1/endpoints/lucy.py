"""Lucy endpoints — chat (SSE), history, pins, pending actions.

The message endpoint is the repo's first streaming response. Two rules keep it
safe on a 20-connection Postgres behind sync workers:

- The REQUEST session does reads only (ownership check, context snapshot). All
  writes happen inside the generator's own short `lucy_session`s, so no row
  stays locked across the stream and the request session can tear down whenever
  FastAPI pleases.
- The generator never holds a session across model I/O — that's `run_agent`'s
  contract (see services/lucy/agent.py).

Frontend consumes this with fetch-streaming (EventSource can't send the bearer
header). Event names: status · tool · text · widget · action · error · done.
"""

import json
import logging
import threading
import uuid
from functools import partial

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic
from app.core.rate_limit import limiter
from app.schemas.lucy import (
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    LucyMeta,
    LucyViewOut,
    LucyViewSummary,
    MessageIn,
    PendingActionOut,
    WidgetOut,
)
from app.services.lucy.agent import run_agent
from app.services.lucy.service import (
    SUGGESTED_PROMPTS,
    LucyService,
    autotitle,
    build_agent_context,
    lucy_session,
    member_session,
    rebuild_member,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # tell nginx-ish proxies not to buffer the stream
}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/meta", response_model=LucyMeta)
def meta(m: CurrentMember = Depends(require_academic)):
    return LucyMeta(ai_configured=settings.ai_configured,
                    suggested_prompts=SUGGESTED_PROMPTS.get(m.org_role, []))


@router.post("/conversations", response_model=ConversationOut)
def create_conversation(body: ConversationCreate,
                        m: CurrentMember = Depends(require_academic),
                        db: Session = Depends(get_db)):
    return LucyService(db).create_conversation(m, body.title)


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(m: CurrentMember = Depends(require_academic),
                       db: Session = Depends(get_db)):
    return LucyService(db).list_conversations(m)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: uuid.UUID,
                     m: CurrentMember = Depends(require_academic),
                     db: Session = Depends(get_db)):
    return LucyService(db).get_conversation(m, conversation_id)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: uuid.UUID,
                        m: CurrentMember = Depends(require_academic),
                        db: Session = Depends(get_db)):
    LucyService(db).delete_conversation(m, conversation_id)


@router.post("/conversations/{conversation_id}/messages")
@limiter.limit("10/minute")
def send_message(request: Request, conversation_id: uuid.UUID, body: MessageIn,
                 m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    # Reads only on the request session: prove ownership, snapshot the context.
    LucyService(db)._own(m, conversation_id)
    ctx = build_agent_context(db, m)
    content = body.content.strip()

    def event_stream():
        action_ids: list[uuid.UUID] = []
        try:
            with lucy_session(ctx.org_id) as sdb:
                sm = rebuild_member(sdb, ctx)
                svc = LucyService(sdb)
                user_msg_id = svc.add_user_message(sm, conversation_id, content)
                history = svc.history_for_model(sm, conversation_id, user_msg_id)

            def propose(spec, params, summary):
                with lucy_session(ctx.org_id) as adb:
                    card = LucyService(adb).propose_action(
                        rebuild_member(adb, ctx), conversation_id,
                        spec, params, summary)
                action_ids.append(uuid.UUID(card["id"]))
                return card

            final = None
            for ev in run_agent(ctx, history, content,
                                member_session=partial(member_session, ctx),
                                propose_action=propose):
                if ev["event"] == "final":
                    final = ev["data"]
                    continue
                yield _sse(ev["event"], ev["data"])

            message_id = None
            if final is not None and (final["content"] or final["widgets"]
                                      or final.get("question")):
                view = final.get("view")
                with lucy_session(ctx.org_id) as sdb:
                    svc2 = LucyService(sdb)
                    sm2 = rebuild_member(sdb, ctx)
                    saved = svc2.save_assistant_message(
                        sm2, conversation_id,
                        final["content"], final["widgets"], final["trace"],
                        action_ids, question=final.get("question"),
                        view_id=view["id"] if view else None)
                    message_id = str(saved.id)
                    if view:
                        svc2.save_view(sm2, conversation_id, view,
                                       final["widgets"])
                if not history:
                    # First exchange — improve on the truncated-question title
                    # off the stream's clock.
                    threading.Thread(
                        target=autotitle,
                        args=(ctx.org_id, conversation_id, content),
                        daemon=True).start()
            yield _sse("done", {"conversation_id": str(conversation_id),
                                "message_id": message_id})
        except Exception:
            logger.exception("lucy stream failed")
            yield _sse("error", {"code": "stream_failed",
                                 "message": "Something went wrong — please try again."})
            yield _sse("done", {"conversation_id": str(conversation_id),
                                "message_id": None})

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers=_SSE_HEADERS)


# -- views (composed answers, GA §5) ------------------------------------------

@router.get("/views", response_model=list[LucyViewSummary])
def list_views(m: CurrentMember = Depends(require_academic),
               db: Session = Depends(get_db)):
    return LucyService(db).list_views(m)


@router.get("/views/{view_id}", response_model=LucyViewOut)
def get_view(view_id: uuid.UUID,
             m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    return LucyService(db).get_view(m, view_id)


@router.post("/views/{view_id}/refresh", response_model=LucyViewOut)
def refresh_view(view_id: uuid.UUID,
                 m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    return LucyService(db).refresh_view(m, view_id)


@router.delete("/views/{view_id}", status_code=204)
def delete_view(view_id: uuid.UUID,
                m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    LucyService(db).delete_view(m, view_id)


# -- widgets / pins ----------------------------------------------------------

@router.get("/pins", response_model=list[WidgetOut])
def pins(m: CurrentMember = Depends(require_academic),
         db: Session = Depends(get_db)):
    return LucyService(db).pins(m)


@router.post("/widgets/{widget_id}/pin", response_model=WidgetOut)
def pin_widget(widget_id: uuid.UUID,
               m: CurrentMember = Depends(require_academic),
               db: Session = Depends(get_db)):
    return LucyService(db).set_pin(m, widget_id, True)


@router.post("/widgets/{widget_id}/unpin", response_model=WidgetOut)
def unpin_widget(widget_id: uuid.UUID,
                 m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    return LucyService(db).set_pin(m, widget_id, False)


@router.post("/widgets/{widget_id}/refresh", response_model=WidgetOut)
def refresh_widget(widget_id: uuid.UUID,
                   m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    return LucyService(db).refresh_widget(m, widget_id)


# -- pending actions (write proposals) ----------------------------------------

@router.post("/actions/{action_id}/confirm", response_model=PendingActionOut)
def confirm_action(action_id: uuid.UUID,
                   m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    return LucyService(db).confirm_action(m, action_id)


@router.post("/actions/{action_id}/cancel", response_model=PendingActionOut)
def cancel_action(action_id: uuid.UUID,
                  m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    return LucyService(db).cancel_action(m, action_id)
