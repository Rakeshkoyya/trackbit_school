"""GA-0 — the School UI Kit catalog (GA §3).

Pure tests, no DB: the catalog generates WIDGET_TYPES / config guide / choice
guide from one source of truth, role filtering works at the component level,
and the four new shapers (meter, radar, area_chart, drilldown) extract only
real keys — a fabricated path still raises, exactly like the original 13."""

import pytest

from app.services.lucy.agent import _render_widget_tool
from app.services.lucy.registry import ToolResult
from app.services.lucy.widgets import (
    CATALOG,
    WIDGET_TYPES,
    WidgetConfigError,
    choice_guide,
    config_guide,
    materialize,
    visible_types,
)


def _result(data):
    return ToolResult(data=data, model_view="{}")


def test_catalog_is_the_single_source_of_truth():
    assert set(WIDGET_TYPES) == set(CATALOG)
    for new in ("meter", "radar", "area_chart", "drilldown"):
        assert new in CATALOG
    guide = config_guide()
    choices = choice_guide()
    for name, man in CATALOG.items():
        assert f"- {name}: " in guide
        if name != "markdown":
            assert name in choices
        # every data component has a shaper; markdown alone is model prose
        assert (man.shaper is None) == (name == "markdown")


def test_component_role_filtering_mirrors_the_registry():
    # No admin-only component exists yet, so both roles see the full catalog —
    # but the mechanism (GA-3 modules rely on it) must filter correctly.
    assert visible_types(True) == WIDGET_TYPES
    assert visible_types(False) == WIDGET_TYPES
    admin_tool = _render_widget_tool(True)
    enum = admin_tool["function"]["parameters"]["properties"]["type"]["enum"]
    assert set(enum) == set(WIDGET_TYPES)
    object.__setattr__(CATALOG["meter"], "role", "admin")
    try:
        assert "meter" not in visible_types(False)
        assert "meter" in visible_types(True)
        teacher_tool = _render_widget_tool(False)
        t_enum = teacher_tool["function"]["parameters"]["properties"]["type"]["enum"]
        assert "meter" not in t_enum
        assert "- meter:" not in config_guide(False)
    finally:
        object.__setattr__(CATALOG["meter"], "role", "academic")


def test_meter_shaper():
    data = {"fees": {"collected_pct": 72.5, "pending": "₹1,20,000 pending"}}
    env = materialize("meter", "Collection", _result(data),
                      {"label": "Fee collection", "value_path": "fees.collected_pct",
                       "sub_path": "fees.pending"})
    assert env["data"] == {"label": "Fee collection", "value": 72.5,
                           "sub": "₹1,20,000 pending", "unit": "%"}
    with pytest.raises(WidgetConfigError):  # fabricated path
        materialize("meter", "x", _result(data),
                    {"label": "x", "value_path": "fees.invented"})
    with pytest.raises(WidgetConfigError):  # non-numeric value
        materialize("meter", "x", _result(data),
                    {"label": "x", "value_path": "fees.pending"})


def test_radar_shaper_caps_two_series():
    data = {"skills": [{"area": "Reading", "student": 72, "cls": 61},
                       {"area": "Reasoning", "student": 64, "cls": 66}]}
    env = materialize("radar", "Profile", _result(data),
                      {"rows_key": "skills", "axis_key": "area",
                       "series": [{"key": "student", "label": "Asha"},
                                  {"key": "cls", "label": "Class avg"},
                                  {"key": "student"}]})
    assert [s["key"] for s in env["data"]["series"]] == ["student", "cls"]
    assert env["data"]["rows"][0] == {"x": "Reading", "student": 72.0, "cls": 61.0}
    with pytest.raises(WidgetConfigError):
        materialize("radar", "x", _result(data),
                    {"rows_key": "skills", "axis_key": "area",
                     "series": [{"key": "invented"}]})


def test_area_chart_shaper_is_single_measure():
    data = {"days": [{"d": "Mon", "pct": 92}, {"d": "Tue", "pct": None}]}
    env = materialize("area_chart", "Pulse", _result(data),
                      {"rows_key": "days", "x_key": "d", "y_key": "pct",
                       "unit": "%"})
    assert env["data"]["rows"] == [{"x": "Mon", "v": 92.0}, {"x": "Tue", "v": None}]
    assert env["data"]["unit"] == "%"
    with pytest.raises(WidgetConfigError):
        materialize("area_chart", "x", _result(data), {"rows_key": "days",
                                                       "x_key": "d"})


def test_drilldown_shaper_two_levels():
    data = {"subjects": [{
        "subject": "Maths", "coverage_pct": 64,
        "chapters": [{"name": "Algebra", "state": "done", "note": "3 topics"},
                     {"name": "Geometry"}, "not-a-dict"],
    }]}
    env = materialize("drilldown", "Coverage", _result(data),
                      {"rows_key": "subjects", "label_key": "subject",
                       "stats": [{"label": "Coverage", "key": "coverage_pct"}],
                       "children_key": "chapters", "child_label_key": "name",
                       "child_detail_key": "note", "child_status_key": "state"})
    group = env["data"]["groups"][0]
    assert group["label"] == "Maths"
    assert group["stats"] == [{"label": "Coverage", "value": 64}]
    assert group["children"] == [
        {"label": "Algebra", "detail": "3 topics", "status": "done"},
        {"label": "Geometry", "detail": None, "status": None}]
    with pytest.raises(WidgetConfigError):  # label key not in the rows
        materialize("drilldown", "x", _result(data),
                    {"rows_key": "subjects", "label_key": "invented",
                     "children_key": "chapters", "child_label_key": "name"})
