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
        tools = registry.to_openai_tools(m) + [_render_widget_tool(m.is_admin)]
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
                    actions=actions, trace=trace, member_session=member_session,
                    propose_action=propose_action)
                # _handle_tool_call returns (ui_events, tool_reply_for_model)
                yield from reply[0]
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "content": reply[1]})

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
                                      "actions": actions, "trace": trace}}


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
                      widgets: list, actions: list, trace: list,
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
