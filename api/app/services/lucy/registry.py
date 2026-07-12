"""Lucy's tool registry — every data surface the agent can touch.

Deliberately transport-agnostic: a ToolSpec knows nothing about FastAPI, SSE or
widgets, so the same registry can later back an MCP server 1:1 (the founder's
stated roadmap). Three rules keep it safe:

- **Tools wrap services, never tables.** Every handler calls an existing
  service method with the real `CurrentMember`, so org scoping (law 1),
  teacher scoping (`not_your_student`, `not_your_class`) and the fee fence
  (admin-only) hold exactly as they do in the REST API.
- **Role filtering happens at schema time.** A teacher's model never even sees
  the admin-only tools — cheaper than erroring, and nothing to jailbreak.
- **Business errors go back to the model, not up the stack.** An `AppError`
  becomes a tool-result payload the model can read and correct course on; only
  genuine bugs propagate.

Write tools (`kind="write"`) additionally carry `confirm=True`: the agent loop
never runs their handler directly — it files a pending action for the human to
confirm (the AI doctrine's human-confirm surface).
"""

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import CurrentMember
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

# Rows the MODEL sees per list — the full data always reaches the widget layer.
DEFAULT_ROW_CAP = 50
# Rows a materialized widget keeps — plenty for any table the UI can render.
WIDGET_ROW_CAP = 300


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    params_schema: dict[str, Any]  # pure JSON Schema (object)
    handler: Callable[..., Any]  # (m, db, **params) -> Pydantic model | list | dict
    role: str = "academic"  # "academic" (any member) | "admin"
    kind: str = "read"  # "read" | "write"
    confirm: bool = False  # write tools: propose-then-confirm
    row_cap: int = DEFAULT_ROW_CAP
    widgets: tuple[str, ...] = ()  # widget types this result renders well as
    default_widget: str = "table"


@dataclass
class ToolResult:
    """One executed tool call: full data for widgets, a capped view for the model."""

    data: Any  # JSON-safe, uncapped — the widget layer's source of truth
    model_view: str  # compact JSON string, row-capped + char-truncated
    supported_widgets: tuple[str, ...] = ()
    default_widget: str = "table"
    # (tool_name, raw_params) — stamped by the agent loop so a widget built from
    # this result can refresh itself later.
    source: tuple[str, dict] | None = None


@dataclass
class ToolExecution:
    ok: bool
    result: ToolResult | None = None
    error_code: str = ""
    error_message: str = ""
    details: dict = field(default_factory=dict)


REGISTRY: dict[str, ToolSpec] = {}


def tool(name: str, description: str, params: dict[str, Any] | None = None, *,
         role: str = "academic", kind: str = "read", confirm: bool = False,
         row_cap: int = DEFAULT_ROW_CAP, widgets: tuple[str, ...] = ("table",),
         default_widget: str | None = None) -> Callable:
    """Register a handler as an agent tool. `params` maps arg name → property
    schema; mark required ones with `"required": True` inside the property."""

    props: dict[str, Any] = {}
    required: list[str] = []
    for pname, pschema in (params or {}).items():
        pschema = dict(pschema)
        if pschema.pop("required", False):
            required.append(pname)
        props[pname] = pschema

    schema = {"type": "object", "properties": props, "required": required,
              "additionalProperties": False}

    def deco(fn: Callable) -> Callable:
        REGISTRY[name] = ToolSpec(
            name=name, description=description, params_schema=schema, handler=fn,
            role=role, kind=kind, confirm=confirm, row_cap=row_cap,
            widgets=widgets, default_widget=default_widget or widgets[0])
        return fn

    return deco


def visible_tools(m: CurrentMember) -> list[ToolSpec]:
    """The tools this member's model is allowed to see (stable order)."""
    return [spec for _, spec in sorted(REGISTRY.items())
            if spec.role != "admin" or m.is_admin]


def to_openai_tools(m: CurrentMember) -> list[dict[str, Any]]:
    return [{
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.params_schema,
        },
    } for spec in visible_tools(m)]


# ---------------------------------------------------------------------------
# Param validation / coercion — the model sends strings; handlers want types.

_TYPE_CHECKS = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _coerce(pname: str, pschema: dict, value: Any) -> Any:
    fmt = pschema.get("format")
    if fmt == "uuid":
        if not isinstance(value, str):
            raise ValueError(f"{pname} must be a UUID string")
        try:
            return uuid.UUID(value)
        except ValueError as exc:
            raise ValueError(f"{pname} is not a valid UUID: {value!r}") from exc
    if fmt == "date":
        if not isinstance(value, str):
            raise ValueError(f"{pname} must be an ISO date string (YYYY-MM-DD)")
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{pname} is not a valid date: {value!r}") from exc
    expected = _TYPE_CHECKS.get(pschema.get("type", "string"))
    if expected and not isinstance(value, expected):
        # Models love sending "3" for an integer — meet them halfway.
        if expected is int and isinstance(value, str) and value.lstrip("-").isdigit():
            return int(value)
        raise ValueError(f"{pname} must be of type {pschema.get('type')}")
    if pschema.get("enum") and value not in pschema["enum"]:
        raise ValueError(f"{pname} must be one of {pschema['enum']}")
    return value


def parse_params(spec: ToolSpec, raw: dict[str, Any]) -> dict[str, Any]:
    """Validate + coerce a model-supplied argument object against the spec."""
    props = spec.params_schema["properties"]
    unknown = set(raw) - set(props)
    if unknown:
        raise ValueError(f"unknown parameter(s): {', '.join(sorted(unknown))}")
    missing = [r for r in spec.params_schema["required"] if raw.get(r) is None]
    if missing:
        raise ValueError(f"missing required parameter(s): {', '.join(missing)}")
    return {k: _coerce(k, props[k], v) for k, v in raw.items() if v is not None}


# ---------------------------------------------------------------------------
# Result shaping

def to_jsonable(obj: Any) -> Any:
    """Pydantic models / lists / dicts → plain JSON-safe python."""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(mode="json")
    elif isinstance(obj, list):
        obj = [to_jsonable(x) for x in obj]
    elif isinstance(obj, dict):
        obj = {str(k): to_jsonable(v) for k, v in obj.items()}
    # Final safety net for stragglers (Decimal, UUID, date) at any depth.
    return json.loads(json.dumps(obj, default=str))


def _cap_rows(data: Any, cap: int) -> Any:
    """Row-cap the MODEL's view; the full data is untouched elsewhere."""
    if isinstance(data, list) and len(data) > cap:
        return data[:cap] + [{"__truncated__": f"{len(data) - cap} more rows omitted"}]
    if isinstance(data, dict):
        return {k: (_cap_rows(v, cap) if isinstance(v, list) else v)
                for k, v in data.items()}
    return data


def build_model_view(data: Any, cap: int) -> str:
    view = json.dumps(_cap_rows(data, cap), separators=(",", ":"), default=str)
    limit = settings.LUCY_TOOL_RESULT_MAX_CHARS
    if len(view) > limit:
        view = view[:limit] + f'... [truncated at {limit} chars — the full data is ' \
                              f'still available to render_widget]'
    return view


def execute(spec: ToolSpec, m: CurrentMember, db: Session,
            raw_params: dict[str, Any]) -> ToolExecution:
    """Run a tool with the member's real authority. Business errors come back
    as data (the model reads them and corrects course); bugs propagate."""
    try:
        params = parse_params(spec, raw_params)
    except ValueError as exc:
        return ToolExecution(ok=False, error_code="bad_params", error_message=str(exc))
    try:
        out = spec.handler(m, db, **params)
    except AppError as exc:
        return ToolExecution(ok=False, error_code=exc.code, error_message=exc.message,
                             details=exc.details or {})
    except Exception:
        logger.exception("lucy tool %s crashed", spec.name)
        return ToolExecution(ok=False, error_code="tool_failed",
                             error_message="The tool hit an internal error.")
    data = to_jsonable(out)
    return ToolExecution(ok=True, result=ToolResult(
        data=data,
        model_view=build_model_view(data, spec.row_cap),
        supported_widgets=spec.widgets,
        default_widget=spec.default_widget,
    ))
