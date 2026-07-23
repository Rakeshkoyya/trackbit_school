"""Lucy's agent loop — model turns, tool execution, widget materialization.

The loop is a generator of UI events, and it owns NO database connection: each
tool execution opens a short-lived session via `lucy_session` and closes it
before the next model call. A 45-second completion therefore costs zero
connection slots — the one rule that keeps Lucy inside the Aiven budget.

Event stream (each item `{"event": ..., "data": {...}}`):
    status  {stage, label}            — coarse progress for the UI
    tool    {name, state, label}      — a registry tool started/finished/errored
    text    {delta}                   — narrative tokens
    widget  {<envelope>}              — a materialized widget, ready to render
    action  {<pending action>}        — a write proposal awaiting human confirm
    final   {content, widgets, actions, trace} — loop done; caller persists
    error   {code, message}           — the turn failed (final still follows)

Data fidelity: tool results are stored under short ids (r1, r2 …) and the model
renders them by reference through the internal `render_widget` tool — it picks
the representation, the numbers come from the stored result (widgets.py)."""

import json
import logging
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

from app.core.config import settings
from app.services.ai.client import AgentUnavailable, chat_tools
from app.services.lucy import registry
from app.services.lucy.agent_context import AgentContext
from app.services.lucy.prompts import build_system_prompt
from app.services.lucy.widgets import (
    WidgetConfigError,
    config_guide,
    materialize,
    visible_types,
)

logger = logging.getLogger(__name__)

MAX_WIDGETS_PER_MESSAGE = 8


def _render_widget_tool(is_admin: bool) -> dict:
    """The internal render tool, with enum + guide generated from the catalog
    for this member's role (an admin-only component never reaches a teacher)."""
    return {
        "type": "function",
        "function": {
            "name": "render_widget",
            "description": (
                "Render a widget in the UI from a tool result you already fetched, "
                "referenced by its result_id. This is how you SHOW data — the widget "
                "is built server-side from the real result, so configure keys/paths "
                "that exist in it.\n" + config_guide(is_admin)),
            "parameters": {
                "type": "object",
                "properties": {
                    "result_id": {"type": "string",
                                  "description": "the r<N> id of a fetched result"},
                    "type": {"type": "string", "enum": list(visible_types(is_admin))},
                    "title": {"type": "string",
                              "description": "short human title for the widget"},
                    "config": {"type": "object",
                               "description": "per-type config, see the guide"},
                },
                "required": ["result_id", "type", "title"],
                "additionalProperties": False,
            },
        },
    }


_ASK_USER = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": (
            "Ask the user ONE clarifying question with tappable options, then STOP "
            "— their choice arrives as the next message. Use it when a lookup "
            "matches several entities (two students with the same name: option "
            "label = name + class, value = the id) or a required choice is "
            "genuinely ambiguous. Never ask when there is exactly one match, and "
            "never ask more than one question per turn."),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string",
                                      "description": "what the user sees on the chip"},
                            "value": {"type": "string",
                                      "description": "id/value carried back with the "
                                                     "choice (e.g. a student_id)"},
                            "detail": {"type": "string",
                                       "description": "small print under the label"},
                        },
                        "required": ["label"],
                        "additionalProperties": False,
                    },
                },
                "allow_free_text": {"type": "boolean",
                                    "description": "let the user type their own "
                                                   "answer too (default true)"},
            },
            "required": ["question", "options"],
            "additionalProperties": False,
        },
    },
}

_COMPOSE_VIEW = {
    "type": "function",
    "function": {
        "name": "compose_view",
        "description": (
            "Organize widgets you already rendered THIS turn into one titled, "
            "saved view (a mini-dashboard the user can reopen, refresh and "
            "print). Use it for broad asks — meeting prep, 'full report on X', "
            "'how is class Y doing overall' — after fetching from several tools "
            "and rendering the widgets. Each section groups related widgets under "
            "a heading with an optional 1-2 sentence narrative (no numbers you "
            "did not fetch). Call it at most once, after your last render_widget."),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string",
                          "description": "short name for the view, e.g. "
                                         "'Rohit Sharma — parent meeting brief'"},
                "summary": {"type": "string",
                            "description": "one-line description of what it covers"},
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": {"type": "string"},
                            "narrative": {"type": "string",
                                          "description": "1-2 sentences of context; "
                                                         "cite only fetched data"},
                            "widget_ids": {"type": "array",
                                           "items": {"type": "string"},
                                           "description": "widget_id values returned "
                                                          "by render_widget this turn"},
                        },
                        "required": ["heading", "widget_ids"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["title", "sections"],
            "additionalProperties": False,
        },
    },
}


def _tool_label(name: str) -> str:
    return name.removeprefix("get_").replace("_", " ")


def run_agent(
    ctx: AgentContext,
    history: list[dict[str, str]],
    user_content: str,
    *,
    member_session: Callable,  # contextmanager: () -> (db, CurrentMember)
    propose_action: Callable[..., dict] | None = None,
) -> Iterator[dict[str, Any]]:
    """Run one Lucy turn. `member_session` is a zero-arg contextmanager yielding
    a fresh (db, CurrentMember) pair — opened per tool call, never held across
    model I/O. `propose_action(spec, params, summary)` files a write proposal
    and returns its card data (LU-3); without it, write tools report disabled."""

    # The member's tool schemas need a CurrentMember once, up front.
    with member_session() as (db, m):
        tools = registry.to_openai_tools(m) + [
            _render_widget_tool(m.is_admin), _ASK_USER, _COMPOSE_VIEW]
        specs = {s.name: s for s in registry.visible_tools(m)}

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(ctx)},
        *history,
        {"role": "user", "content": user_content},
    ]

    results: dict[str, registry.ToolResult] = {}
    widgets: list[dict] = []
    actions: list[dict] = []
    trace: list[dict] = []
    # One question and one composed view per turn (GA §4/§5); a question ends it.
    extras: dict[str, Any] = {"question": None, "view": None}
    content = ""
    started = time.monotonic()

    def out_of_budget() -> bool:
        return time.monotonic() - started > settings.LUCY_WALL_SECONDS

    try:
        for _turn in range(settings.LUCY_MAX_ITERATIONS):
            yield {"event": "status", "data": {"stage": "thinking",
                                               "label": "Thinking…"}}
            message: dict[str, Any] = {}
            for ev in chat_tools(messages, tools):
                if ev["type"] == "text":
                    yield {"event": "text", "data": {"delta": ev["delta"]}}
                elif ev["type"] == "message":
                    message = ev
            content = message.get("content") or content
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                break

            messages.append({
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": [{"id": tc["id"], "type": "function",
                                "function": {"name": tc["name"],
                                             "arguments": tc["arguments"]}}
                               for tc in tool_calls],
            })

            for tc in tool_calls:
                reply = _handle_tool_call(
                    tc, ctx=ctx, specs=specs, results=results, widgets=widgets,
                    actions=actions, trace=trace, extras=extras,
                    member_session=member_session, propose_action=propose_action)
                # _handle_tool_call returns (ui_events, tool_reply_for_model)
                yield from reply[0]
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": reply[1]})

            if extras["question"] is not None:
                # The turn ends on a question — the answer starts the next one.
                break

            if out_of_budget():
                yield {"event": "status",
                       "data": {"stage": "thinking", "label": "Wrapping up…"}}
                content = yield from _wrap_up(messages)
                break
        else:
            # Tool budget exhausted without a plain answer — force one.
            yield {"event": "status",
                   "data": {"stage": "thinking", "label": "Wrapping up…"}}
            content = yield from _wrap_up(messages)
    except AgentUnavailable as exc:
        code = "ai_unconfigured" if str(exc) == "ai_unconfigured" else "ai_unavailable"
        friendly = ("Lucy needs an AI key to be configured." if code == "ai_unconfigured"
                    else "Lucy could not reach the AI service — please try again.")
        yield {"event": "error", "data": {"code": code, "message": friendly}}
        content = content or friendly
    except Exception:
        logger.exception("lucy agent loop crashed")
        yield {"event": "error",
               "data": {"code": "agent_failed",
                        "message": "Something went wrong — please try again."}}
        content = content or "Something went wrong — please try again."

    yield {"event": "final", "data": {"content": content, "widgets": widgets,
                                      "actions": actions, "trace": trace,
                                      "question": extras["question"],
                                      "view": extras["view"]}}


def _wrap_up(messages: list[dict]) -> Any:
    """One forced tool-less turn so the user always gets prose. (Generator —
    yields text events, returns the final content via StopIteration.value.)"""
    closing = messages + [{
        "role": "user",
        "content": ("(system note) The tool budget for this message is used up. "
                    "Answer now with what you already fetched, briefly, in the "
                    "user's language. Do not call tools."),
    }]
    content = ""
    for ev in chat_tools(closing, []):
        if ev["type"] == "text":
            yield {"event": "text", "data": {"delta": ev["delta"]}}
        elif ev["type"] == "message":
            content = ev.get("content") or ""
    return content


def _handle_tool_call(tc: dict, *, ctx: AgentContext, specs: dict, results: dict,
                      widgets: list, actions: list, trace: list, extras: dict,
                      member_session: Callable, propose_action: Callable | None,
                      ) -> tuple[list[dict], str]:
    """Execute one tool call; returns (ui_events, tool_reply_for_model)."""
    events: list[dict] = []
    name = tc["name"]
    try:
        args = json.loads(tc["arguments"]) if tc["arguments"].strip() else {}
        if not isinstance(args, dict):
            raise ValueError("arguments must be a JSON object")
    except ValueError as exc:
        return events, json.dumps(
            {"error": "bad_arguments", "message": f"unparseable arguments: {exc}"})

    if name == "render_widget":
        return _render(args, results=results, widgets=widgets, events=events)
    if name == "ask_user":
        return _ask(args, extras=extras, events=events)
    if name == "compose_view":
        return _compose(args, widgets=widgets, extras=extras, events=events)

    spec = specs.get(name)
    if spec is None:
        return events, json.dumps(
            {"error": "unknown_tool",
             "message": f"{name} is not one of your tools"})

    if spec.kind == "write":
        return _propose(spec, args, ctx=ctx, actions=actions, trace=trace,
                        events=events, propose_action=propose_action)

    label = _tool_label(name)
    events.append({"event": "tool",
                   "data": {"name": name, "state": "started",
                            "label": f"Checking {label}…"}})
    with member_session() as (db, m):
        execution = registry.execute(spec, m, db, args)
    trace.append({"tool": name, "params": args, "ok": execution.ok,
                  **({} if execution.ok else {"error": execution.error_code})})
    if not execution.ok:
        events.append({"event": "tool",
                       "data": {"name": name, "state": "error", "label": label}})
        return events, json.dumps({"error": execution.error_code,
                                   "message": execution.error_message,
                                   "details": execution.details})

    rid = f"r{len(results) + 1}"
    results[rid] = execution.result
    results[rid].source = (name, args)
    events.append({"event": "tool",
                   "data": {"name": name, "state": "finished", "label": label}})
    reply = (
        f"result_id: {rid}\n"
        f"widgets that fit this result: {', '.join(execution.result.supported_widgets)} "
        f"(default: {execution.result.default_widget})\n"
        f"data: {execution.result.model_view}")
    return events, reply


def _render(args: dict, *, results: dict, widgets: list,
            events: list) -> tuple[list[dict], str]:
    wtype = args.get("type") or ""
    rid = args.get("result_id") or ""
    result = results.get(rid)
    if len(widgets) >= MAX_WIDGETS_PER_MESSAGE:
        return events, json.dumps(
            {"error": "too_many_widgets",
             "message": "widget budget for this message reached — summarize instead"})
    try:
        source_tool, source_params = getattr(result, "source", (None, None))
        envelope = materialize(
            wtype, args.get("title") or "", result, args.get("config"),
            source_tool=source_tool,
            source_params={k: str(v) for k, v in (source_params or {}).items()})
    except WidgetConfigError as exc:
        return events, json.dumps({"error": "bad_widget_config", "message": str(exc)})
    widgets.append(envelope)
    events.append({"event": "widget", "data": envelope})
    return events, json.dumps({"ok": True, "widget_id": envelope["id"],
                               "note": "rendered — do not repeat its numbers in prose"})


def _ask(args: dict, *, extras: dict, events: list) -> tuple[list[dict], str]:
    """Show a clarifying question with option chips and END the turn (GA §4)."""
    question = str(args.get("question") or "").strip()
    raw_options = args.get("options") or []
    options = [{
        "label": str(o["label"]).strip(),
        "value": str(o["value"]).strip() if o.get("value") else None,
        "detail": str(o["detail"]).strip() if o.get("detail") else None,
    } for o in raw_options
        if isinstance(o, dict) and str(o.get("label") or "").strip()][:6]
    if not question or not options:
        return events, json.dumps(
            {"error": "bad_question",
             "message": "ask_user needs a question and 1-6 options with labels"})
    if extras["question"] is not None:
        return events, json.dumps(
            {"error": "already_asked",
             "message": "one question per turn — stop and wait for the answer"})
    extras["question"] = {
        "question": question,
        "options": options,
        "allow_free_text": bool(args.get("allow_free_text", True)),
    }
    events.append({"event": "question", "data": extras["question"]})
    return events, json.dumps({
        "ok": True,
        "note": ("Question shown with options — STOP now. The user's choice "
                 "arrives as their next message.")})


def _compose(args: dict, *, widgets: list, extras: dict,
             events: list) -> tuple[list[dict], str]:
    """Group this turn's rendered widgets into one saved view (GA §5). The
    model can only reference widget ids it already materialized — a view is
    fabrication-proof by construction."""
    title = str(args.get("title") or "").strip()
    raw_sections = args.get("sections") or []
    if not title or not isinstance(raw_sections, list) or not raw_sections:
        return events, json.dumps(
            {"error": "bad_view", "message": "compose_view needs a title and "
                                             "at least one section"})
    known = {env["id"] for env in widgets}
    sections = []
    for s in raw_sections[:8]:
        if not isinstance(s, dict) or not str(s.get("heading") or "").strip():
            return events, json.dumps(
                {"error": "bad_view", "message": "every section needs a heading"})
        ids = [str(w) for w in (s.get("widget_ids") or [])]
        unknown = [w for w in ids if w not in known]
        if unknown:
            return events, json.dumps(
                {"error": "unknown_widget_ids",
                 "message": f"widget id(s) {unknown} were not rendered this turn "
                            "— use the widget_id values render_widget returned"})
        if not ids:
            return events, json.dumps(
                {"error": "bad_view",
                 "message": "every section needs at least one widget_id"})
        sections.append({
            "heading": str(s["heading"]).strip(),
            "narrative": str(s["narrative"]).strip() if s.get("narrative") else None,
            "widget_ids": ids,
        })
    extras["view"] = {
        "id": str(uuid.uuid4()),
        "title": title[:120],
        "summary": str(args.get("summary") or "").strip()[:300] or None,
        "sections": sections,
    }
    events.append({"event": "view", "data": extras["view"]})
    return events, json.dumps({
        "ok": True, "view_id": extras["view"]["id"],
        "note": ("View composed and shown — it is saved for the user to reopen. "
                 "Close with 1-2 sentences; do not repeat its contents.")})


def _propose(spec, args: dict, *, ctx: AgentContext, actions: list, trace: list,
             events: list, propose_action: Callable | None) -> tuple[list[dict], str]:
    if propose_action is None:
        return events, json.dumps(
            {"error": "writes_disabled",
             "message": "write actions are not enabled in this conversation"})
    try:
        parsed = registry.parse_params(spec, {k: v for k, v in args.items()
                                              if k != "summary"})
    except ValueError as exc:
        return events, json.dumps({"error": "bad_params", "message": str(exc)})
    summary = str(args.get("summary") or "").strip() or spec.description[:120]
    card = propose_action(spec, parsed, summary)
    actions.append(card)
    trace.append({"tool": spec.name, "params": {k: str(v) for k, v in parsed.items()},
                  "ok": True, "proposed": True})
    events.append({"event": "action", "data": card})
    return events, json.dumps({
        "ok": True, "action_id": card["id"],
        "note": ("Proposed — the user must tap Confirm in the UI before it runs. "
                 "Do NOT assume it executed; tell the user it awaits their confirmation."),
    })
