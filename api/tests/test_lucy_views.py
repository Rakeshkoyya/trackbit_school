"""GA-1 — composed views + interactive questions (GA §4/§5).

- ask_user ends the turn with a `question` SSE event and persists the question
  on the assistant message (history rehydrates the chips);
- compose_view can only reference widgets rendered THIS turn (fabrication-proof),
  saves a self-contained lucy_views row (signature = sorted source tools), and
  the view refreshes by re-executing its bindings;
- views are member-private like conversations.

The model is scripted (chat_tools monkeypatched) — no network."""

import json
import uuid

from tests.test_lucy import _add_teacher, _scripted, _setup, _sse_events


def _scripted_dyn(monkeypatch, turns):
    """Like test_lucy._scripted, but a turn may be callable(messages) -> turn,
    so a later turn can read tool replies (e.g. render_widget's widget_id) the
    way a real model does."""
    state = {"i": 0}

    def fake_chat_tools(messages, tools, **kw):
        turn = turns[min(state["i"], len(turns) - 1)]
        state["i"] += 1
        if callable(turn):
            turn = turn(messages)
        content = turn.get("content", "")
        if content:
            yield {"type": "text", "delta": content}
        yield {"type": "message", "content": content,
               "tool_calls": turn.get("tool_calls", [])}

    import app.services.lucy.agent as agent_mod
    monkeypatch.setattr(agent_mod, "chat_tools", fake_chat_tools)


def _last_widget_id(messages):
    for msg in reversed(messages):
        if msg.get("role") == "tool" and "widget_id" in (msg.get("content") or ""):
            return json.loads(msg["content"])["widget_id"]
    raise AssertionError("no widget_id in any tool reply")


def test_ask_user_ends_turn_and_persists(client, cleanup, monkeypatch):
    h, _reg, _year, _klass, kids = _setup(client, cleanup)
    _scripted(monkeypatch, [
        {"content": "Which one do you mean?",
         "tool_calls": [{"id": "q1", "name": "ask_user", "arguments": json.dumps({
             "question": "There are 2 students named like that — which one?",
             "options": [
                 {"label": "Asha Reddy", "detail": "Class 6-A",
                  "value": kids[0]["id"]},
                 {"label": "Bharat Kumar", "detail": "Class 6-A",
                  "value": kids[1]["id"]},
             ]})}]},
        {"content": "should never be reached"},
    ])
    convo = client.post("/api/v1/lucy/conversations", headers=h, json={}).json()
    r = client.post(f"/api/v1/lucy/conversations/{convo['id']}/messages",
                    headers=h, json={"content": "show me the report for A"})
    events = _sse_events(r.text)
    names = [e for e, _ in events]
    # The question ends the turn — no second model turn runs.
    assert "question" in names and names[-1] == "done"
    q = next(d for e, d in events if e == "question")
    assert q["allow_free_text"] is True
    assert [o["value"] for o in q["options"]] == [kids[0]["id"], kids[1]["id"]]
    # The question is persisted on the assistant message for rehydration.
    detail = client.get(f"/api/v1/lucy/conversations/{convo['id']}",
                        headers=h).json()
    assistant = detail["messages"][-1]
    assert assistant["role"] == "assistant"
    assert assistant["question"]["question"].startswith("There are 2 students")


def test_compose_view_saves_refreshes_and_is_member_private(
        client, cleanup, monkeypatch):
    h, reg, _year, _klass, kids = _setup(client, cleanup)

    def compose_turn(messages):
        wid = _last_widget_id(messages)
        return {"tool_calls": [{"id": "c3", "name": "compose_view",
                                "arguments": json.dumps({
                                    "title": "Class 6-A brief",
                                    "summary": "Roster overview",
                                    "sections": [{
                                        "heading": "Students",
                                        "narrative": "The current roster.",
                                        "widget_ids": [wid]}]})}]}

    _scripted_dyn(monkeypatch, [
        {"tool_calls": [{"id": "c1", "name": "search_students",
                         "arguments": json.dumps({})}]},
        {"tool_calls": [{"id": "c2", "name": "render_widget",
                         "arguments": json.dumps({
                             "result_id": "r1", "type": "table",
                             "title": "Students",
                             "config": {"columns": [
                                 {"key": "full_name", "label": "Name"}]}})}]},
        compose_turn,
        {"content": "Here is your brief."},
    ])
    convo = client.post("/api/v1/lucy/conversations", headers=h, json={}).json()
    r = client.post(f"/api/v1/lucy/conversations/{convo['id']}/messages",
                    headers=h, json={"content": "brief me on class 6-A"})
    events = _sse_events(r.text)
    view_ev = next(d for e, d in events if e == "view")
    assert view_ev["title"] == "Class 6-A brief"

    # Saved, listed, and self-contained (real student rows inside).
    views = client.get("/api/v1/lucy/views", headers=h).json()
    assert [v["title"] for v in views] == ["Class 6-A brief"]
    assert views[0]["widget_count"] == 1
    detail = client.get(f"/api/v1/lucy/views/{view_ev['id']}", headers=h).json()
    assert detail["signature"] == "search_students"
    assert detail["sections"][0]["heading"] == "Students"
    rows = detail["widgets"][0]["data"]["rows"]
    assert {r_["full_name"] for r_ in rows} == {k["full_name"] for k in kids}
    # The assistant message links the view.
    convo_detail = client.get(f"/api/v1/lucy/conversations/{convo['id']}",
                              headers=h).json()
    assert convo_detail["messages"][-1]["view_id"] == view_ev["id"]

    # Refresh re-executes the binding with the live role.
    refreshed = client.post(f"/api/v1/lucy/views/{view_ev['id']}/refresh",
                            headers=h).json()
    assert refreshed["refreshed_at"] is not None
    assert {r_["full_name"] for r_ in refreshed["widgets"][0]["data"]["rows"]} \
        == {k["full_name"] for k in kids}

    # Member-private: a same-org teacher cannot read or delete it.
    th, _cred = _add_teacher(client, h, reg["org"]["id"])
    assert client.get(f"/api/v1/lucy/views/{view_ev['id']}",
                      headers=th).status_code == 404
    assert client.delete(f"/api/v1/lucy/views/{view_ev['id']}",
                         headers=th).status_code == 404
    # Owner delete round-trip.
    assert client.delete(f"/api/v1/lucy/views/{view_ev['id']}",
                         headers=h).status_code == 204
    assert client.get("/api/v1/lucy/views", headers=h).json() == []


def test_compose_view_rejects_unrendered_widget_ids(client, cleanup, monkeypatch):
    h, _reg, _year, _klass, _kids = _setup(client, cleanup)
    fake_id = str(uuid.uuid4())
    _scripted(monkeypatch, [
        {"tool_calls": [{"id": "c1", "name": "compose_view",
                         "arguments": json.dumps({
                             "title": "Fabricated",
                             "sections": [{"heading": "X",
                                           "widget_ids": [fake_id]}]})}]},
        {"content": "I could not build that view."},
    ])
    convo = client.post("/api/v1/lucy/conversations", headers=h, json={}).json()
    r = client.post(f"/api/v1/lucy/conversations/{convo['id']}/messages",
                    headers=h, json={"content": "make a view"})
    events = _sse_events(r.text)
    # No view event — the error went back to the model, which answered in prose.
    assert not any(e == "view" for e, _ in events)
    assert client.get("/api/v1/lucy/views", headers=h).json() == []
