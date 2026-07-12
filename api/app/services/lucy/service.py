"""LucyService — conversations, widgets, pins, pending actions; plus the
session discipline that keeps the agent loop connection-free.

Privacy rule: conversations are MEMBER-PRIVATE. Every lookup filters by
`membership_id`, not just `org_id` — a teacher's chat contains their students'
data, and even admins do not read other members' conversations.

`lucy_session` / `member_session` exist because the SSE generator outlives the
request-scoped `get_db` session (FastAPI tears yield-dependencies down before a
StreamingResponse iterates) and, more importantly, because a session must never
sit open across a 45-second model call on a 20-connection Postgres."""

import json
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.context import CurrentMember
from app.core.database import SessionLocal
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models import (
    AcademicYear,
    ClassSubject,
    LucyConversation,
    LucyMessage,
    LucyPendingAction,
    LucyWidget,
    Membership,
    Organization,
    SchoolClass,
    Subject,
    User,
)
from app.schemas.lucy import (
    ConversationDetail,
    ConversationOut,
    MessageOut,
    PendingActionOut,
    WidgetOut,
)
from app.services.lucy import registry
from app.services.lucy.agent_context import AgentContext
from app.services.lucy.widgets import WidgetConfigError, materialize

SUGGESTED_PROMPTS = {
    "admin": [
        "How is the school doing today?",
        "Show me class 6 attendance today",
        "Which subjects are falling behind the syllabus?",
        "Who has overdue fees?",
        "Summarize yesterday's daily report",
    ],
    "teacher": [
        "What's left on my day?",
        "Show my class's attendance today",
        "How is the syllabus pacing in my classes?",
        "Show the latest test results for my class",
    ],
}


@contextmanager
def lucy_session(org_id: uuid.UUID):
    """A short-lived app-role session with RLS engaged for this org."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT set_config('app.current_org_id', :oid, true)"),
                   {"oid": str(org_id)})
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def rebuild_member(db: Session, ctx: AgentContext) -> CurrentMember:
    """Rehydrate a CurrentMember in a fresh session from the frozen context."""
    user = db.get(User, ctx.user_id)
    org = db.get(Organization, ctx.org_id)
    membership = db.get(Membership, ctx.membership_id)
    if user is None or org is None or membership is None or membership.status != "active":
        raise ForbiddenError("Your session is no longer valid.", code="revoked")
    return CurrentMember(user=user, org=org, membership=membership)


@contextmanager
def member_session(ctx: AgentContext):
    """Fresh (db, CurrentMember) pair for exactly one tool execution."""
    with lucy_session(ctx.org_id) as db:
        yield db, rebuild_member(db, ctx)


def build_agent_context(db: Session, m: CurrentMember) -> AgentContext:
    """Snapshot everything the loop needs about the member — plain data only."""
    year = db.scalar(select(AcademicYear).where(
        AcademicYear.org_id == m.org_id, AcademicYear.is_active.is_(True)))
    classes: list[dict] = []
    if m.is_teacher:
        rows = db.execute(
            select(SchoolClass.id, SchoolClass.name, SchoolClass.section, Subject.name)
            .select_from(ClassSubject)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.org_id == m.org_id,
                   ClassSubject.teacher_member_id == m.membership.id)
            .order_by(SchoolClass.name, SchoolClass.section)).all()
        by_class: dict[uuid.UUID, dict] = {}
        for cid, cname, section, subject in rows:
            label = f"{cname}-{section}" if section else cname
            entry = by_class.setdefault(cid, {"id": str(cid), "label": label,
                                              "subjects": []})
            entry["subjects"].append(subject)
        classes = list(by_class.values())
    today, weekday = AgentContext.today_parts()
    return AgentContext(
        org_id=m.org_id, org_name=m.org.name, membership_id=m.membership.id,
        user_id=m.user_id, member_name=m.user.name or "there", role=m.org_role,
        today=today, weekday=weekday,
        year_id=year.id if year else None,
        year_label=year.label if year else None,
        classes=classes,
    )


def _widget_out(w: LucyWidget) -> WidgetOut:
    payload = w.payload or {}
    return WidgetOut(
        id=w.id, conversation_id=w.conversation_id, message_id=w.message_id,
        type=w.type, title=w.title, spec_version=w.spec_version,
        data=payload.get("data"), config=payload.get("config") or {},
        source_tool=w.source_tool, pinned=w.pinned, pinned_at=w.pinned_at,
        refreshed_at=w.refreshed_at, created_at=w.created_at)


def _action_out(a: LucyPendingAction) -> PendingActionOut:
    return PendingActionOut(
        id=a.id, conversation_id=a.conversation_id, message_id=a.message_id,
        tool=a.tool, summary=a.summary, params=a.params or {}, status=a.status,
        result=a.result, error=a.error, expires_at=a.expires_at,
        created_at=a.created_at)


class LucyService:
    def __init__(self, db: Session):
        self.db = db

    # -- conversations ------------------------------------------------------

    def _own(self, m: CurrentMember, conversation_id: uuid.UUID) -> LucyConversation:
        convo = self.db.scalar(select(LucyConversation).where(
            LucyConversation.id == conversation_id,
            LucyConversation.org_id == m.org_id,
            LucyConversation.membership_id == m.membership.id))
        if convo is None:
            raise NotFoundError("Conversation", str(conversation_id))
        return convo

    def create_conversation(self, m: CurrentMember,
                            title: str | None = None) -> ConversationOut:
        convo = LucyConversation(org_id=m.org_id, membership_id=m.membership.id,
                                 title=title)
        self.db.add(convo)
        self.db.flush()
        return ConversationOut.model_validate(convo, from_attributes=True)

    def list_conversations(self, m: CurrentMember,
                           limit: int = 30) -> list[ConversationOut]:
        rows = self.db.scalars(
            select(LucyConversation).where(
                LucyConversation.org_id == m.org_id,
                LucyConversation.membership_id == m.membership.id)
            .order_by(LucyConversation.updated_at.desc()).limit(limit))
        return [ConversationOut.model_validate(c, from_attributes=True) for c in rows]

    def get_conversation(self, m: CurrentMember,
                         conversation_id: uuid.UUID) -> ConversationDetail:
        convo = self._own(m, conversation_id)
        messages = self.db.scalars(
            select(LucyMessage)
            .options(selectinload(LucyMessage.widgets))
            .where(LucyMessage.conversation_id == convo.id,
                   LucyMessage.org_id == m.org_id)
            .order_by(LucyMessage.created_at)).all()
        actions = self.db.scalars(
            select(LucyPendingAction)
            .where(LucyPendingAction.conversation_id == convo.id,
                   LucyPendingAction.org_id == m.org_id)
            .order_by(LucyPendingAction.created_at)).all()
        self._expire_stale(actions)
        by_message: dict[uuid.UUID | None, list[LucyPendingAction]] = {}
        for a in actions:
            by_message.setdefault(a.message_id, []).append(a)
        return ConversationDetail(
            id=convo.id, title=convo.title, created_at=convo.created_at,
            updated_at=convo.updated_at,
            messages=[MessageOut(
                id=msg.id, role=msg.role, content=msg.content,
                created_at=msg.created_at,
                widgets=[_widget_out(w) for w in msg.widgets],
                actions=[_action_out(a) for a in by_message.get(msg.id, [])],
            ) for msg in messages])

    def delete_conversation(self, m: CurrentMember,
                            conversation_id: uuid.UUID) -> None:
        self.db.delete(self._own(m, conversation_id))
        self.db.flush()

    # -- messages -----------------------------------------------------------

    def add_user_message(self, m: CurrentMember, conversation_id: uuid.UUID,
                         content: str) -> uuid.UUID:
        convo = self._own(m, conversation_id)
        if convo.title is None:
            convo.title = content.strip()[:80]
        convo.updated_at = datetime.now(UTC)
        msg = LucyMessage(org_id=m.org_id, conversation_id=convo.id,
                          role="user", content=content.strip())
        self.db.add(msg)
        self.db.flush()
        return msg.id

    def history_for_model(self, m: CurrentMember, conversation_id: uuid.UUID,
                          before_message_id: uuid.UUID) -> list[dict[str, str]]:
        """The last N text turns, oldest-first, excluding the message being
        answered. Tool traces are not replayed — text is the durable context."""
        self._own(m, conversation_id)
        rows = self.db.scalars(
            select(LucyMessage)
            .where(LucyMessage.conversation_id == conversation_id,
                   LucyMessage.org_id == m.org_id,
                   LucyMessage.id != before_message_id)
            .order_by(LucyMessage.created_at.desc())
            .limit(settings.LUCY_HISTORY_MESSAGES)).all()
        return [{"role": msg.role, "content": msg.content}
                for msg in reversed(rows) if msg.content.strip()]

    def save_assistant_message(self, m: CurrentMember, conversation_id: uuid.UUID,
                               content: str, widgets: list[dict],
                               trace: list[dict],
                               action_ids: list[uuid.UUID] | None = None,
                               ) -> MessageOut:
        convo = self._own(m, conversation_id)
        convo.updated_at = datetime.now(UTC)
        msg = LucyMessage(org_id=m.org_id, conversation_id=convo.id,
                          role="assistant", content=content,
                          meta={"trace": trace} if trace else None)
        self.db.add(msg)
        self.db.flush()
        rows: list[LucyWidget] = []
        for env in widgets:
            row = LucyWidget(
                id=uuid.UUID(env["id"]), org_id=m.org_id,
                conversation_id=convo.id, message_id=msg.id,
                type=env["type"], title=env["title"],
                spec_version=env["spec_version"],
                payload={"data": env["data"], "config": env["config"]},
                source_tool=env.get("source_tool"),
                source_params=env.get("source_params"))
            self.db.add(row)
            rows.append(row)
        for aid in action_ids or []:
            action = self.db.get(LucyPendingAction, aid)
            if action is not None and action.org_id == m.org_id:
                action.message_id = msg.id
        self.db.flush()
        return MessageOut(id=msg.id, role="assistant", content=content,
                          created_at=msg.created_at,
                          widgets=[_widget_out(w) for w in rows])

    # -- widgets / pins -----------------------------------------------------

    def _own_widget(self, m: CurrentMember, widget_id: uuid.UUID) -> LucyWidget:
        widget = self.db.scalar(
            select(LucyWidget).join(
                LucyConversation, LucyConversation.id == LucyWidget.conversation_id)
            .where(LucyWidget.id == widget_id, LucyWidget.org_id == m.org_id,
                   LucyConversation.membership_id == m.membership.id))
        if widget is None:
            raise NotFoundError("Widget", str(widget_id))
        return widget

    def set_pin(self, m: CurrentMember, widget_id: uuid.UUID,
                pinned: bool) -> WidgetOut:
        widget = self._own_widget(m, widget_id)
        widget.pinned = pinned
        widget.pinned_at = datetime.now(UTC) if pinned else None
        self.db.flush()
        return _widget_out(widget)

    def pins(self, m: CurrentMember) -> list[WidgetOut]:
        rows = self.db.scalars(
            select(LucyWidget).join(
                LucyConversation, LucyConversation.id == LucyWidget.conversation_id)
            .where(LucyWidget.org_id == m.org_id, LucyWidget.pinned.is_(True),
                   LucyConversation.membership_id == m.membership.id)
            .order_by(LucyWidget.pinned_at.desc())).all()
        return [_widget_out(w) for w in rows]

    def refresh_widget(self, m: CurrentMember, widget_id: uuid.UUID) -> WidgetOut:
        """Re-execute the widget's source tool with its stored params and
        re-materialize with the stored config. Role is re-checked (a widget
        pinned as admin does not survive a demotion). Falls back to the stored
        snapshot on any failure — a pin board must never 500."""
        widget = self._own_widget(m, widget_id)
        if not widget.source_tool:
            return _widget_out(widget)
        spec = registry.REGISTRY.get(widget.source_tool)
        if spec is None or (spec.role == "admin" and not m.is_admin):
            return _widget_out(widget)
        execution = registry.execute(spec, m, self.db, widget.source_params or {})
        if not execution.ok:
            return _widget_out(widget)
        try:
            env = materialize(widget.type, widget.title, execution.result,
                              (widget.payload or {}).get("config"))
        except WidgetConfigError:
            return _widget_out(widget)
        widget.payload = {"data": env["data"], "config": env["config"]}
        widget.refreshed_at = datetime.now(UTC)
        self.db.flush()
        return _widget_out(widget)

    # -- pending actions (write proposals) -----------------------------------

    def propose_action(self, m: CurrentMember, conversation_id: uuid.UUID,
                       spec: registry.ToolSpec, params: dict,
                       summary: str) -> dict:
        # JSON-safe round-trippable params: uuid/date become strings that
        # parse_params coerces back at confirm time; lists/objects survive.
        safe_params = registry.to_jsonable(params)
        action = LucyPendingAction(
            org_id=m.org_id, conversation_id=conversation_id,
            membership_id=m.membership.id, tool=spec.name,
            params=safe_params, summary=summary,
            expires_at=datetime.now(UTC) + timedelta(
                minutes=settings.LUCY_ACTION_EXPIRE_MINUTES))
        self.db.add(action)
        self.db.flush()
        return {
            "id": str(action.id), "tool": spec.name, "summary": summary,
            "params_preview": [
                {"label": k.replace("_", " "),
                 "value": v if isinstance(v, str) else json.dumps(v, default=str)}
                for k, v in safe_params.items()],
            "status": "proposed",
            "expires_at": action.expires_at.isoformat(),
        }

    def _own_action(self, m: CurrentMember,
                    action_id: uuid.UUID) -> LucyPendingAction:
        action = self.db.scalar(select(LucyPendingAction).where(
            LucyPendingAction.id == action_id,
            LucyPendingAction.org_id == m.org_id,
            LucyPendingAction.membership_id == m.membership.id))
        if action is None:
            raise NotFoundError("Action", str(action_id))
        return action

    def _expire_stale(self, actions: list[LucyPendingAction]) -> None:
        now = datetime.now(UTC)
        for a in actions:
            if a.status == "proposed" and a.expires_at < now:
                a.status = "expired"
                a.resolved_at = now

    def confirm_action(self, m: CurrentMember,
                       action_id: uuid.UUID) -> PendingActionOut:
        action = self._own_action(m, action_id)
        self._expire_stale([action])
        if action.status != "proposed":
            raise ConflictError(f"This action is already {action.status}.",
                                code="action_resolved")
        spec = registry.REGISTRY.get(action.tool)
        if spec is None:
            raise NotFoundError("Tool", action.tool)
        if spec.role == "admin" and not m.is_admin:
            raise ForbiddenError("This action requires an admin.", code="admin_only")
        execution = registry.execute(spec, m, self.db, action.params or {})
        action.resolved_at = datetime.now(UTC)
        if execution.ok:
            action.status = "executed"
            action.result = {"data": execution.result.data} \
                if execution.result is not None else None
        else:
            action.status = "failed"
            action.error = execution.error_message or execution.error_code
        self.db.flush()
        return _action_out(action)

    def cancel_action(self, m: CurrentMember,
                      action_id: uuid.UUID) -> PendingActionOut:
        action = self._own_action(m, action_id)
        if action.status == "proposed":
            action.status = "cancelled"
            action.resolved_at = datetime.now(UTC)
            self.db.flush()
        return _action_out(action)
