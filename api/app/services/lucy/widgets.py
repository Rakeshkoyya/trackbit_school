"""Widget materialization — where Lucy's answers become UI, without fabrication.

The model never types a number into a widget. It calls the internal
`render_widget(result_id, type, title, config)` tool, and THIS module extracts
the widget's data from the stored tool result by keys and paths. A key the
model invents doesn't exist in the data and raises `WidgetConfigError`, which
goes back to the model as a tool error to fix — it cannot invent values.

The one exception is `markdown`, which is model prose by design and is rendered
by the frontend as sanitized markdown (no raw HTML), never executed.

Every payload is `{"data": ..., "config": ...}` inside a versioned envelope —
`spec_version` bumps if a widget's data shape ever changes, so old pinned
widgets keep rendering.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.services.lucy.registry import WIDGET_ROW_CAP, ToolResult

SPEC_VERSION = 1


@dataclass(frozen=True)
class ComponentManifest:
    """One renderable component of the School UI Kit (GA §3.1).

    The CATALOG below is the single source of truth: WIDGET_TYPES, the config
    guide and the render_widget schema are all generated from it. `role`
    mirrors the tool registry — an admin-only component never even appears in
    a teacher's render enum."""

    name: str
    summary: str  # one line: what it renders
    when_to_use: str  # the sentence that steers the agent's choice
    config_guide: str  # the config contract shown inside render_widget
    shaper: Callable[[Any, dict], dict] | None  # None → model prose (markdown)
    role: str = "academic"  # "academic" (any member) | "admin"


_PATHS_NOTE = """
Paths are dotted with [i] for list items (e.g. "attendance.pct", "subjects[0].name").
rows_key is a path to a list of objects; omit it when the result itself is a list.
Keys/paths must exist in the tool result — you saw its JSON."""


class WidgetConfigError(ValueError):
    """Bad widget config — reported back to the model as a tool error."""


def _pluck(data: Any, path: str) -> Any:
    """Resolve "a.b[2].c" against nested dicts/lists; raise on a dead end."""
    cur = data
    for raw in path.replace("]", "").split("."):
        parts = raw.split("[")
        key, indexes = parts[0], parts[1:]
        if key:
            if not isinstance(cur, dict) or key not in cur:
                raise WidgetConfigError(f'path "{path}" not found (missing "{key}")')
            cur = cur[key]
        for idx in indexes:
            if not isinstance(cur, list) or not idx.lstrip("-").isdigit() \
                    or not (-len(cur) <= int(idx) < len(cur)):
                raise WidgetConfigError(f'path "{path}" has a bad list index [{idx}]')
            cur = cur[int(idx)]
    return cur


def _rows(data: Any, config: dict, default_key: str | None = None) -> list[dict]:
    key = config.get("rows_key") or default_key
    rows = _pluck(data, key) if key else data
    if not isinstance(rows, list):
        raise WidgetConfigError(
            'rows_key must point at a list of objects '
            f'(got {type(rows).__name__}); set "rows_key" correctly')
    rows = [r for r in rows if isinstance(r, dict)]
    if not rows:
        raise WidgetConfigError("the selected list is empty — nothing to render")
    return rows[:WIDGET_ROW_CAP]


def _num(value: Any) -> float | None:
    try:
        return None if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return None


def _require_keys(rows: list[dict], keys: list[str], what: str) -> None:
    known = set().union(*(r.keys() for r in rows))
    bad = [k for k in keys if k not in known]
    if bad:
        raise WidgetConfigError(
            f'{what} key(s) {bad} not present in the rows; available keys: '
            f'{sorted(known)[:25]}')


# --- shapers -----------------------------------------------------------------

def _shape_table(data: Any, config: dict) -> dict:
    columns = config.get("columns") or []
    if not columns:
        raise WidgetConfigError('table needs "columns": [{key, label?, kind?}]')
    rows = _rows(data, config)
    keys = [c["key"] for c in columns if isinstance(c, dict) and c.get("key")]
    if not keys:
        raise WidgetConfigError("every column needs a key")
    _require_keys(rows, keys, "column")
    cols = [{"key": c["key"],
             "label": c.get("label") or c["key"].replace("_", " ").title(),
             "kind": c.get("kind") or "text"} for c in columns if c.get("key")]
    return {"columns": cols, "rows": [{k: r.get(k) for k in keys} for r in rows]}


def _shape_stat_group(data: Any, config: dict) -> dict:
    items = config.get("items") or []
    if not items:
        raise WidgetConfigError('stat_group needs "items": [{label, value_path}]')
    out = []
    for it in items[:12]:
        if not it.get("label") or not it.get("value_path"):
            raise WidgetConfigError("each stat needs label and value_path")
        out.append({
            "label": it["label"],
            "value": _pluck(data, it["value_path"]),
            "sub": _pluck(data, it["sub_path"]) if it.get("sub_path") else None,
            "tone": it.get("tone") or "neutral",
        })
    return {"items": out}


def _shape_chart(data: Any, config: dict) -> dict:
    x_key = config.get("x_key")
    series = config.get("series") or []
    if not x_key or not series:
        raise WidgetConfigError('charts need "x_key" and "series": [{key, label?}]')
    rows = _rows(data, config)
    skeys = [s["key"] for s in series if isinstance(s, dict) and s.get("key")]
    _require_keys(rows, [x_key, *skeys], "chart")
    return {
        "x_key": "x",
        "series": [{"key": s["key"], "label": s.get("label") or s["key"]}
                   for s in series if s.get("key")],
        "rows": [{"x": r.get(x_key), **{k: _num(r.get(k)) for k in skeys}}
                 for r in rows],
    }


def _shape_donut(data: Any, config: dict) -> dict:
    if config.get("slices"):
        slices = [{"label": s["label"], "value": _num(_pluck(data, s["value_path"]))}
                  for s in config["slices"][:12]
                  if s.get("label") and s.get("value_path")]
    else:
        label_key, value_key = config.get("label_key"), config.get("value_key")
        if not label_key or not value_key:
            raise WidgetConfigError(
                'donut needs label_key+value_key or "slices": [{label, value_path}]')
        rows = _rows(data, config)
        _require_keys(rows, [label_key, value_key], "donut")
        slices = [{"label": str(r.get(label_key)), "value": _num(r.get(value_key))}
                  for r in rows[:12]]
    slices = [s for s in slices if s["value"] is not None]
    if not slices:
        raise WidgetConfigError("no numeric slices resolved")
    return {"slices": slices}


def _shape_rag_board(data: Any, config: dict) -> dict:
    label_key, status_key = config.get("label_key"), config.get("status_key")
    if not label_key or not status_key:
        raise WidgetConfigError("rag_board needs label_key and status_key")
    rows = _rows(data, config)
    _require_keys(rows, [label_key, status_key], "rag_board")
    detail_key = config.get("detail_key")
    return {"items": [{
        "label": str(r.get(label_key)),
        "status": str(r.get(status_key) or "none").lower(),
        "detail": str(r.get(detail_key)) if detail_key and r.get(detail_key) is not None else None,
    } for r in rows]}


def _shape_roster_grid(data: Any, config: dict) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("roster"), list):
        raise WidgetConfigError(
            "roster_grid only renders get_attendance_roster results")
    return {
        "summary": {k: data.get(k) for k in
                    ("class_label", "period_no", "date", "marked",
                     "present_count", "absent_count", "late_count")},
        "students": [{
            "name": s.get("full_name"), "roll_no": s.get("roll_no"),
            "status": s.get("status"), "late_minutes": s.get("late_minutes"),
        } for s in data["roster"][:WIDGET_ROW_CAP]],
    }


def _shape_timeline(data: Any, config: dict) -> dict:
    title_key = config.get("title_key")
    if not title_key:
        raise WidgetConfigError("timeline needs title_key (and optional time_key/"
                                "detail_key/status_key)")
    rows = _rows(data, config, default_key="periods" if isinstance(data, dict) else None)
    _require_keys(rows, [title_key], "timeline")
    tk, dk, sk = config.get("time_key"), config.get("detail_key"), config.get("status_key")
    return {"entries": [{
        "time": str(r.get(tk)) if tk and r.get(tk) is not None else None,
        "title": str(r.get(title_key)),
        "detail": str(r.get(dk)) if dk and r.get(dk) is not None else None,
        "status": str(r.get(sk)) if sk and r.get(sk) is not None else None,
    } for r in rows]}


def _shape_report_card(data: Any, config: dict) -> dict:
    if not isinstance(data, dict) or "sections" not in data:
        raise WidgetConfigError("report_card only renders get_daily_report results")
    highlights = data.get("highlights") or {}
    return {
        "for_date": data.get("for_date"),
        "status": data.get("status"),
        "risks": highlights.get("risks") or [],
        "ambiguities": highlights.get("ambiguities") or [],
        "wins": highlights.get("wins") or [],
        "sections": [{"heading": s.get("heading"), "lines": s.get("lines") or []}
                     for s in (highlights.get("sections") or data.get("sections") or [])
                     if isinstance(s, dict)],
    }


def _shape_student_card(data: Any, config: dict) -> dict:
    title_path = config.get("title_path")
    if not title_path:
        raise WidgetConfigError('student_card needs title_path and "fields"')
    fields = [{"label": f["label"], "value": _pluck(data, f["value_path"])}
              for f in (config.get("fields") or [])[:16]
              if f.get("label") and f.get("value_path")]
    return {
        "title": str(_pluck(data, title_path)),
        "subtitle": str(_pluck(data, config["subtitle_path"]))
        if config.get("subtitle_path") else None,
        "fields": fields,
    }


def _shape_alert_list(data: Any, config: dict) -> dict:
    rows = _rows(data, config, default_key="alerts" if isinstance(data, dict) else None)
    title_key = config.get("title_key") or "title"
    _require_keys(rows, [title_key], "alert_list")
    dk = config.get("detail_key") or "detail"
    sk = config.get("severity_key") or "severity"
    return {"alerts": [{
        "title": str(r.get(title_key)),
        "detail": str(r.get(dk)) if r.get(dk) is not None else None,
        "severity": str(r.get(sk)) if r.get(sk) is not None else "info",
    } for r in rows]}


def _shape_progress(data: Any, config: dict) -> dict:
    label_key = config.get("label_key")
    if not label_key:
        raise WidgetConfigError("progress needs label_key plus pct_key or "
                                "done_key+total_key")
    rows = _rows(data, config)
    _require_keys(rows, [label_key], "progress")
    pct_key, done_key, total_key = (config.get("pct_key"), config.get("done_key"),
                                    config.get("total_key"))
    items = []
    for r in rows:
        if pct_key:
            pct = _num(r.get(pct_key))
        elif done_key and total_key:
            done, total = _num(r.get(done_key)), _num(r.get(total_key))
            pct = round(done / total * 100, 1) if done is not None and total else None
        else:
            raise WidgetConfigError("progress needs pct_key or done_key+total_key")
        dk = config.get("detail_key")
        items.append({"label": str(r.get(label_key)), "pct": pct,
                      "detail": str(r.get(dk)) if dk and r.get(dk) is not None else None})
    return {"items": items}


def _shape_meter(data: Any, config: dict) -> dict:
    label, value_path = config.get("label"), config.get("value_path")
    if not label or not value_path:
        raise WidgetConfigError('meter needs "label" and "value_path" (a 0-100 number)')
    value = _num(_pluck(data, value_path))
    if value is None:
        raise WidgetConfigError(f'value_path "{value_path}" did not resolve to a number')
    sub = _pluck(data, config["sub_path"]) if config.get("sub_path") else None
    return {"label": str(label), "value": value,
            "sub": None if sub is None else str(sub),
            "unit": str(config.get("unit") or "%")}


def _shape_radar(data: Any, config: dict) -> dict:
    axis_key = config.get("axis_key")
    series = [s for s in (config.get("series") or [])
              if isinstance(s, dict) and s.get("key")][:2]
    if not axis_key or not series:
        raise WidgetConfigError(
            'radar needs "axis_key" and "series": [{key, label?}] (max 2 series)')
    rows = _rows(data, config)
    skeys = [s["key"] for s in series]
    _require_keys(rows, [axis_key, *skeys], "radar")
    return {
        "series": [{"key": s["key"], "label": s.get("label") or s["key"]}
                   for s in series],
        "rows": [{"x": r.get(axis_key), **{k: _num(r.get(k)) for k in skeys}}
                 for r in rows[:12]],
    }


def _shape_area(data: Any, config: dict) -> dict:
    x_key, y_key = config.get("x_key"), config.get("y_key")
    if not x_key or not y_key:
        raise WidgetConfigError(
            'area_chart needs "x_key" and "y_key" (ONE measure over time)')
    rows = _rows(data, config)
    _require_keys(rows, [x_key, y_key], "area_chart")
    return {"label": str(config.get("label") or y_key.replace("_", " ")),
            "unit": str(config.get("unit") or ""),
            "rows": [{"x": r.get(x_key), "v": _num(r.get(y_key))} for r in rows]}


def _shape_drilldown(data: Any, config: dict) -> dict:
    label_key = config.get("label_key")
    children_key = config.get("children_key")
    child_label_key = config.get("child_label_key")
    if not label_key or not children_key or not child_label_key:
        raise WidgetConfigError(
            'drilldown needs "label_key", "children_key" and "child_label_key" '
            "(plus optional stats / child_detail_key / child_status_key)")
    rows = _rows(data, config)
    _require_keys(rows, [label_key], "drilldown")
    stats_cfg = [s for s in (config.get("stats") or [])
                 if isinstance(s, dict) and s.get("label") and s.get("key")][:6]
    cdk, csk = config.get("child_detail_key"), config.get("child_status_key")
    groups = []
    for r in rows:
        raw = r.get(children_key)
        children = [c for c in raw if isinstance(c, dict)] if isinstance(raw, list) else []
        groups.append({
            "label": str(r.get(label_key)),
            "stats": [{"label": s["label"], "value": r.get(s["key"])}
                      for s in stats_cfg],
            "children": [{
                "label": str(c.get(child_label_key)),
                "detail": str(c.get(cdk)) if cdk and c.get(cdk) is not None else None,
                "status": str(c.get(csk)) if csk and c.get(csk) is not None else None,
            } for c in children[:60]],
        })
    return {"groups": groups}


# --- the catalog (GA §3.2) ---------------------------------------------------

CATALOG: dict[str, ComponentManifest] = {man.name: man for man in [
    ComponentManifest(
        "table", "data table",
        "lists and detail rows",
        "{rows_key?, columns: [{key, label?, kind?: text|number|pct|badge|date}], "
        "group_by?, sort_by?}", _shape_table),
    ComponentManifest(
        "stat_group", "headline number tiles",
        "a few headline numbers",
        "{items: [{label, value_path, sub_path?, "
        "tone?: neutral|success|warning|danger}]}", _shape_stat_group),
    ComponentManifest(
        "bar_chart", "vertical bars",
        "comparison across categories",
        "{rows_key?, x_key, series: [{key, label?}]}", _shape_chart),
    ComponentManifest(
        "line_chart", "multi-series trend lines",
        "trend over time",
        "{rows_key?, x_key, series: [{key, label?}]}", _shape_chart),
    ComponentManifest(
        "area_chart", "one filled measure over time",
        "the shape of ONE measure over time (e.g. daily attendance %)",
        "{rows_key?, x_key, y_key, label?, unit?}", _shape_area),
    ComponentManifest(
        "donut", "parts of a whole",
        "distribution / parts of a whole",
        "{rows_key?, label_key, value_key} or {slices: [{label, value_path}]}",
        _shape_donut),
    ComponentManifest(
        "meter", "a single gauge",
        "one standalone percentage (fee collection %, attendance %, pace %)",
        "{label, value_path, sub_path?, unit?}", _shape_meter),
    ComponentManifest(
        "radar", "profile shape across axes",
        "a profile across skill areas or subjects (max 2 series)",
        "{rows_key?, axis_key, series: [{key, label?}] (max 2)}", _shape_radar),
    ComponentManifest(
        "rag_board", "green/amber/red status board",
        "syllabus or health status per item",
        "{rows_key?, label_key, status_key, detail_key?}  "
        "(status values green/amber/red)", _shape_rag_board),
    ComponentManifest(
        "roster_grid", "one class-period's attendance sheet",
        "one class-period's attendance",
        "{} (attendance roster results only)", _shape_roster_grid),
    ComponentManifest(
        "drilldown", "two-level expandable list",
        "grouped data with expandable children (chapters→topics, units→topics)",
        "{rows_key?, label_key, stats?: [{label, key}], children_key, "
        "child_label_key, child_detail_key?, child_status_key?}", _shape_drilldown),
    ComponentManifest(
        "timeline", "time-ordered entries",
        "a student's or teacher's day, period by period",
        "{rows_key?, title_key, time_key?, detail_key?, status_key?}",
        _shape_timeline),
    ComponentManifest(
        "report_card", "the generated daily report",
        "the daily report",
        "{} (daily report results only)", _shape_report_card),
    ComponentManifest(
        "student_card", "one entity's identity + facts",
        "one student's profile facts",
        "{title_path, subtitle_path?, fields: [{label, value_path}]}",
        _shape_student_card),
    ComponentManifest(
        "alert_list", "prioritized warnings",
        "warnings and alerts, worst first",
        "{rows_key?, title_key?, detail_key?, severity_key?}", _shape_alert_list),
    ComponentManifest(
        "progress", "completion bars per item",
        "completion per item",
        "{rows_key?, label_key, pct_key?, done_key?, total_key?, detail_key?}",
        _shape_progress),
    ComponentManifest(
        "markdown", "your own prose",
        "prose only — when no data component fits",
        "{md} (your own prose — never invent numbers, cite tool data)", None),
]}

WIDGET_TYPES = tuple(CATALOG)


def visible_types(is_admin: bool) -> tuple[str, ...]:
    """Component names this member's model may render (mirrors tool visibility)."""
    return tuple(n for n, man in CATALOG.items()
                 if man.role != "admin" or is_admin)


def config_guide(is_admin: bool = True) -> str:
    """The per-type config cheat-sheet inside render_widget's description."""
    lines = [f"- {n}: {man.config_guide}" for n, man in CATALOG.items()
             if man.role != "admin" or is_admin]
    return "Widget types and their config:\n" + "\n".join(lines) + _PATHS_NOTE


def choice_guide(is_admin: bool = True) -> str:
    """The when-to-use line for the system prompt, generated from the catalog."""
    return "; ".join(f"{man.when_to_use} → {n}" for n, man in CATALOG.items()
                     if (man.role != "admin" or is_admin) and n != "markdown")


# Back-compat constant (full catalog view).
CONFIG_GUIDE = config_guide()


def materialize(widget_type: str, title: str, result: ToolResult | None,
                config: dict[str, Any] | None, *,
                source_tool: str | None = None,
                source_params: dict | None = None) -> dict[str, Any]:
    """Build a widget envelope from a REAL tool result (or model prose for
    markdown). Raises WidgetConfigError with a model-fixable message."""
    config = config or {}
    if widget_type == "markdown":
        md = config.get("md")
        if not isinstance(md, str) or not md.strip():
            raise WidgetConfigError('markdown needs config {"md": "..."}')
        data: dict[str, Any] = {"md": md}
    else:
        man = CATALOG.get(widget_type)
        if man is None or man.shaper is None:
            raise WidgetConfigError(
                f"unknown widget type {widget_type!r}; valid: {', '.join(WIDGET_TYPES)}")
        if result is None:
            raise WidgetConfigError("result_id does not match a fetched tool result")
        data = man.shaper(result.data, config)
    return {
        "id": str(uuid.uuid4()),
        "spec_version": SPEC_VERSION,
        "type": widget_type,
        "title": title or "",
        "data": data,
        "config": config,
        "source_tool": source_tool,
        "source_params": source_params,
        "pinned": False,
        "refreshed_at": None,
    }
