"""Lucy — agentic chat layer (LU-1).

What matters here:
- the registry filters tools by role and returns business errors AS DATA the
  model can read (a teacher probing another class gets `not_your_student`
  back as a tool result, not a 500);
- widget materialization is fidelity-safe — numbers come from the stored tool
  result, and a key the model invents raises instead of rendering junk;
- the SSE endpoint streams tool/widget/text/done events and persists the
  assistant message + widgets from REAL tool data (asserted against the DB);
- conversations are member-private, pins round-trip, AI-off degrades politely.

The model is always scripted (chat_tools is monkeypatched) — no network."""

import json
import types
import uuid

from sqlalchemy import select

from app.core.context import CurrentMember
from app.models import Membership, Organization, User
from app.services.lucy import registry
from app.services.lucy.registry import REGISTRY, ToolResult
from app.services.lucy.widgets import WidgetConfigError, materialize
from tests.conftest import AdminSession


def _membership(user_id, org_id):
    db = AdminSession()
    try:
        return db.scalar(select(Membership).where(
            Membership.user_id == uuid.UUID(user_id),
            Membership.org_id == uuid.UUID(org_id)))
    finally:
        db.close()


def _setup(client, cleanup, n_students=2):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Lucy Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6",
                              "section": "A"}).json()
    kids = [client.post("/api/v1/students", headers=h,
                        json={"admission_no": f"L{i}", "full_name": name,
                              "class_id": klass["id"], "roll_no": str(i)}).json()
            for i, name in enumerate(["Asha Reddy", "Bharat Kumar"][:n_students], 1)]
    return h, reg, year, klass, kids


def _add_teacher(client, admin_h, org_id):
    bulk = client.post("/api/v1/org/members/bulk", headers=admin_h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"],
                              "password": "supersecret1"}).json()
    return {"Authorization": f"Bearer {login['access_token']}"}, cred


def _scripted(monkeypatch, turns):
    """Replace the model with a script: each turn = {content?, tool_calls?}."""
    state = {"i": 0}

    def fake_chat_tools(messages, tools, **kw):
        turn = turns[min(state["i"], len(turns) - 1)]
        state["i"] += 1
        content = turn.get("content", "")
        if content:
            yield {"type": "text", "delta": content}
        yield {"type": "message", "content": content,
               "tool_calls": turn.get("tool_calls", [])}

    import app.services.lucy.agent as agent_mod
    monkeypatch.setattr(agent_mod, "chat_tools", fake_chat_tools)


def _sse_events(text):
    events = []
    for block in text.strip().split("\n\n"):
        name = data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if name:
            events.append((name, data))
    return events


# --- registry units ----------------------------------------------------------

def test_registry_role_filtering_and_schemas():
    teacher = types.SimpleNamespace(is_admin=False)
    admin = types.SimpleNamespace(is_admin=True)
    teacher_tools = {t["function"]["name"] for t in registry.to_openai_tools(teacher)}
    admin_tools = {t["function"]["name"] for t in registry.to_openai_tools(admin)}
    # Teachers never even see the fee/admin surfaces (P: teachers never see fees).
    assert "get_fee_summary" not in teacher_tools
    assert "get_overdue_fees" not in teacher_tools
    assert "get_school_overview" not in teacher_tools
    assert {"get_attendance_roster", "get_student_growth",
            "search_students"} <= teacher_tools
    assert {"get_fee_summary", "get_dashboard"} <= admin_tools
    # Valid function-tool schemas throughout.
    for t in registry.to_openai_tools(admin):
        assert t["type"] == "function"
        assert t["function"]["parameters"]["type"] == "object"


def test_param_coercion_and_model_view_truncation():
    spec = REGISTRY["get_attendance_roster"]
    parsed = registry.parse_params(spec, {
        "class_id": "1b4e28ba-2fa1-11d2-883f-0016d3cca427",
        "period_no": "3", "on_date": "2026-07-10"})
    assert isinstance(parsed["class_id"], uuid.UUID)
    assert parsed["period_no"] == 3
    assert parsed["on_date"].isoformat() == "2026-07-10"
    try:
        registry.parse_params(spec, {"class_id": "nope", "period_no": 1})
        raise AssertionError("bad uuid must fail")
    except ValueError:
        pass
    try:
        registry.parse_params(spec, {"class_id": str(uuid.uuid4()),
                                     "period_no": 1, "bogus": 1})
        raise AssertionError("unknown params must fail")
    except ValueError:
        pass
    # Row cap: the model sees a capped view, the data keeps everything.
    rows = [{"n": i} for i in range(200)]
    view = registry.build_model_view(rows, 50)
    assert "150 more rows omitted" in view


def test_widget_materialization_is_fidelity_safe():
    result = ToolResult(
        data=[{"full_name": "Asha", "pct": 91.0}, {"full_name": "Bharat", "pct": 62.5}],
        model_view="[]", supported_widgets=("table",), default_widget="table")
    env = materialize("table", "Scores", result,
                      {"columns": [{"key": "full_name", "label": "Name"},
                                   {"key": "pct", "kind": "pct"}]})
    assert [r["full_name"] for r in env["data"]["rows"]] == ["Asha", "Bharat"]
    assert env["data"]["columns"][0]["label"] == "Name"
    # A key the model invented cannot render — fabrication is structurally out.
    try:
        materialize("table", "x", result, {"columns": [{"key": "made_up"}]})
        raise AssertionError("invented key must fail")
    except WidgetConfigError as exc:
        assert "made_up" in str(exc)
    # stat_group plucks values from the REAL result by path.
    nested = ToolResult(data={"attendance": {"pct": 87.5}}, model_view="{}")
    env = materialize("stat_group", "Attendance", nested,
                      {"items": [{"label": "Attendance %",
                                  "value_path": "attendance.pct"}]})
    assert env["data"]["items"][0]["value"] == 87.5


# --- scoping through the registry ---------------------------------------------

def test_scoped_service_error_comes_back_as_tool_data(client, cleanup, db_session):
    h, reg, _year, _klass, kids = _setup(client, cleanup)
    _th, cred = _add_teacher(client, h, reg["org"]["id"])
    ms = _membership(cred["user_id"], reg["org"]["id"])
    user = db_session.get(User, uuid.UUID(cred["user_id"]))
    org = db_session.get(Organization, uuid.UUID(reg["org"]["id"]))
    membership = db_session.get(Membership, ms.id)
    teacher = CurrentMember(user=user, org=org, membership=membership)
    execution = registry.execute(REGISTRY["get_student_growth"], teacher,
                                 db_session, {"student_id": kids[0]["id"]})
    assert execution.ok is False
    assert execution.error_code == "not_your_student"


# --- conversations: privacy + CRUD ---------------------------------------------

def test_conversations_are_member_private(client, cleanup):
    h, reg, *_ = _setup(client, cleanup, n_students=0)
    convo = client.post("/api/v1/lucy/conversations", headers=h, json={}).json()
    assert client.get(f"/api/v1/lucy/conversations/{convo['id']}",
                      headers=h).status_code == 200
    # Another member of the SAME org cannot read it — member-private, not org-wide.
    th, _cred = _add_teacher(client, h, reg["org"]["id"])
    assert client.get(f"/api/v1/lucy/conversations/{convo['id']}",
                      headers=th).status_code == 404
    assert client.post(f"/api/v1/lucy/conversations/{convo['id']}/messages",
                       headers=th, json={"content": "hi"}).status_code == 404
    # Delete round-trip.
    assert client.delete(f"/api/v1/lucy/conversations/{convo['id']}",
                         headers=h).status_code == 204
    assert client.get(f"/api/v1/lucy/conversations/{convo['id']}",
                      headers=h).status_code == 404


# --- the chat stream: scripted agent, real data ---------------------------------

def test_chat_stream_widgets_pins_and_history(client, cleanup, monkeypatch):
    h, reg, _year, _klass, kids = _setup(client, cleanup)
    _scripted(monkeypatch, [
        {"tool_calls": [{"id": "c1", "name": "search_students",
                         "arguments": json.dumps({})}]},
        {"tool_calls": [{"id": "c2", "name": "render_widget",
                         "arguments": json.dumps({
                             "result_id": "r1", "type": "table",
                             "title": "Students of 6-A",
                             "config": {"columns": [
                                 {"key": "full_name", "label": "Name"},
                                 {"key": "roll_no"}]}})}]},
        {"content": "Here are your students."},
    ])
    convo = client.post("/api/v1/lucy/conversations", headers=h, json={}).json()
    r = client.post(f"/api/v1/lucy/conversations/{convo['id']}/messages",
                    headers=h, json={"content": "show me my students"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _sse_events(r.text)
    names = [e for e, _ in events]
    assert "widget" in names and "text" in names and names[-1] == "done"
    tool_states = [d["state"] for e, d in events if e == "tool"]
    assert tool_states == ["started", "finished"]
    widget_ev = next(d for e, d in events if e == "widget")
    # The widget's rows are the REAL students from the DB, not model output.
    assert {r_["full_name"] for r_ in widget_ev["data"]["rows"]} == \
           {k["full_name"] for k in kids}
    done = events[-1][1]
    assert done["message_id"]

    # History restores the widget; the user message titled the conversation.
    detail = client.get(f"/api/v1/lucy/conversations/{convo['id']}",
                        headers=h).json()
    assert detail["title"] == "show me my students"
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assistant = detail["messages"][1]
    assert assistant["content"] == "Here are your students."
    assert assistant["widgets"][0]["type"] == "table"
    assert assistant["widgets"][0]["source_tool"] == "search_students"

    # Pin → pin board → refresh (re-executes the source tool) → unpin.
    wid = assistant["widgets"][0]["id"]
    assert client.post(f"/api/v1/lucy/widgets/{wid}/pin",
                       headers=h).json()["pinned"] is True
    pins = client.get("/api/v1/lucy/pins", headers=h).json()
    assert [p["id"] for p in pins] == [wid]
    refreshed = client.post(f"/api/v1/lucy/widgets/{wid}/refresh", headers=h).json()
    assert refreshed["refreshed_at"] is not None
    assert {r_["full_name"] for r_ in refreshed["data"]["rows"]} == \
           {k["full_name"] for k in kids}
    assert client.post(f"/api/v1/lucy/widgets/{wid}/unpin",
                       headers=h).json()["pinned"] is False
    assert client.get("/api/v1/lucy/pins", headers=h).json() == []


def test_bad_widget_config_bounces_back_to_model(client, cleanup, monkeypatch):
    """An invented column key doesn't crash the stream — the model gets the
    error as a tool reply and can answer in prose."""
    h, _reg, _year, _klass, _kids = _setup(client, cleanup)
    _scripted(monkeypatch, [
        {"tool_calls": [{"id": "c1", "name": "search_students",
                         "arguments": json.dumps({})}]},
        {"tool_calls": [{"id": "c2", "name": "render_widget",
                         "arguments": json.dumps({
                             "result_id": "r1", "type": "table", "title": "x",
                             "config": {"columns": [{"key": "invented"}]}})}]},
        {"content": "Could not chart that, but there are 2 students."},
    ])
    convo = client.post("/api/v1/lucy/conversations", headers=h, json={}).json()
    r = client.post(f"/api/v1/lucy/conversations/{convo['id']}/messages",
                    headers=h, json={"content": "chart something odd"})
    events = _sse_events(r.text)
    assert not [e for e, _ in events if e == "widget"]
    assert events[-1][0] == "done" and events[-1][1]["message_id"]


# --- AI off ------------------------------------------------------------------

def test_ai_off_meta_and_polite_error(client, cleanup):
    h, *_ = _setup(client, cleanup, n_students=0)
    meta = client.get("/api/v1/lucy/meta", headers=h).json()
    assert meta["ai_configured"] is False
    assert meta["suggested_prompts"]
    convo = client.post("/api/v1/lucy/conversations", headers=h, json={}).json()
    r = client.post(f"/api/v1/lucy/conversations/{convo['id']}/messages",
                    headers=h, json={"content": "hello"})
    events = _sse_events(r.text)
    err = next(d for e, d in events if e == "error")
    assert err["code"] == "ai_unconfigured"
    assert events[-1][0] == "done"
