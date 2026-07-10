"""V2-P9: the OpenRouter client and the AI-assisted import path.

No test here touches the network. The point of these is the *contract*: AI can
improve on the deterministic heuristic, and can never break it. Every failure mode
— key absent, timeout, 500, rate limit, prose instead of JSON, a hallucinated
column — must land on the heuristic result with no exception escaping.
"""

import httpx
import pytest

from app.core.config import settings
from app.services.ai import client as ai_client
from app.services.ai.client import _extract_json, chat_json
from app.services.ai.extract import phrase_gap_question, split_syllabus_text, suggest_mapping
from app.services.ingest import FieldSpec, build_analysis

SPECS = [
    FieldSpec("full_name", ["teacher name", "name"], required=True, label="name"),
    FieldSpec("phone", ["mobile", "phone"], label="phone number"),
]


@pytest.fixture
def ai_on(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-test", raising=False)
    monkeypatch.setattr(settings, "AI_MAX_RETRIES", 1, raising=False)


@pytest.fixture
def ai_off(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "", raising=False)


def _reply(content: str, status: int = 200):
    """Build a fake OpenRouter chat-completions response."""
    def _post(url, **kwargs):
        request = httpx.Request("POST", url)
        body = {"choices": [{"message": {"content": content}}]}
        return httpx.Response(status, json=body, request=request)
    return _post


def _boom(exc: Exception):
    def _post(*_a, **_kw):
        raise exc
    return _post


# ── the client ───────────────────────────────────────────────────────────────
def test_no_key_means_no_network_call(ai_off, monkeypatch):
    """The whole offline story rests on this: with no key we never even dial."""
    def _explode(*_a, **_kw):
        raise AssertionError("chat_json must not touch the network without a key")
    monkeypatch.setattr(ai_client.httpx, "post", _explode)
    assert chat_json("sys", "user") is None


def test_happy_path_returns_the_parsed_object(ai_on, monkeypatch):
    monkeypatch.setattr(ai_client.httpx, "post", _reply('{"mapping": {"full_name": "Name"}}'))
    assert chat_json("sys", "user") == {"mapping": {"full_name": "Name"}}


def test_json_wrapped_in_a_fence_is_still_parsed(ai_on, monkeypatch):
    """Not every OpenRouter model honours response_format — don't throw away a
    good answer because it arrived inside a markdown fence."""
    fenced = 'Sure! Here you go:\n```json\n{"question": "Which column?"}\n```\nHope that helps.'
    monkeypatch.setattr(ai_client.httpx, "post", _reply(fenced))
    assert chat_json("sys", "user") == {"question": "Which column?"}


@pytest.mark.parametrize("content", ["not json at all", "[1, 2, 3]", ""])
def test_unparseable_reply_falls_back_to_none(ai_on, monkeypatch, content):
    """A JSON array is valid JSON but not the object shape callers expect."""
    monkeypatch.setattr(ai_client.httpx, "post", _reply(content))
    assert chat_json("sys", "user") is None


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retryable_status_eventually_returns_none(ai_on, monkeypatch, status):
    monkeypatch.setattr(ai_client.httpx, "post", _reply("{}", status=status))
    assert chat_json("sys", "user") is None


def test_client_side_error_does_not_retry(ai_on, monkeypatch):
    """A 401 (bad key) or 404 (bad model slug) is our bug — retrying wastes the
    admin's time on a spinner that was never going to succeed."""
    calls = []

    def _post(url, **kwargs):
        calls.append(url)
        return httpx.Response(401, json={"error": "no"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(ai_client.httpx, "post", _post)
    assert chat_json("sys", "user") is None
    assert len(calls) == 1


def test_timeout_returns_none(ai_on, monkeypatch):
    monkeypatch.setattr(ai_client.httpx, "post", _boom(httpx.ReadTimeout("slow")))
    assert chat_json("sys", "user") is None


def test_malformed_envelope_returns_none(ai_on, monkeypatch):
    """No `choices` key — a proxy error page, say."""
    def _post(url, **kwargs):
        return httpx.Response(200, json={"error": "upstream"}, request=httpx.Request("POST", url))
    monkeypatch.setattr(ai_client.httpx, "post", _post)
    assert chat_json("sys", "user") is None


def test_extract_json_is_pure():
    assert _extract_json('{"a": 1}') == {"a": 1}
    assert _extract_json('prefix {"a": 1} suffix') == {"a": 1}
    assert _extract_json("no braces here") is None
    assert _extract_json('"a string"') is None


# ── suggest_mapping: propose, never decide ───────────────────────────────────
def test_suggest_mapping_rejects_a_hallucinated_column(ai_on, monkeypatch):
    monkeypatch.setattr(
        ai_client.httpx, "post",
        _reply('{"mapping": {"full_name": "Column That Does Not Exist"}}'))
    got = suggest_mapping("staff", ["full_name"], ["Naam", "Mob"], [{"Naam": "Ramesh"}])
    assert got == {}, "a column the file doesn't have must never reach the importer"


def test_suggest_mapping_rejects_a_field_we_did_not_ask_about(ai_on, monkeypatch):
    monkeypatch.setattr(
        ai_client.httpx, "post",
        _reply('{"mapping": {"full_name": "Naam", "salary": "Mob"}}'))
    got = suggest_mapping("staff", ["full_name"], ["Naam", "Mob"], [])
    assert got == {"full_name": "Naam"}


def test_suggest_mapping_is_a_noop_when_ai_is_off(ai_off):
    assert suggest_mapping("staff", ["full_name"], ["Naam"], []) == {}


# ── build_analysis: the heuristic is the floor ───────────────────────────────
def test_ai_maps_a_column_the_heuristic_could_not(ai_on, monkeypatch):
    """"Naam" matches no keyword. The model recognises it; the admin confirms it."""
    monkeypatch.setattr(
        ai_client.httpx, "post", _reply('{"mapping": {"full_name": "Naam"}}'))
    analysis = build_analysis("staff", ["Naam", "Extra"], [{"Naam": "Ramesh"}], SPECS)

    assert analysis.mapping["full_name"] == "Naam"
    assert analysis.missing_required == [], "the gap is closed, so no question is asked"
    assert "full_name" in analysis.low_confidence, "an AI proposal always wants a human glance"
    assert analysis.source == "ai"
    assert analysis.unmapped_columns == ["Extra"]


def test_ai_never_overrides_an_exact_heuristic_match(ai_on, monkeypatch):
    """A column literally called "Name" is not a judgement call. Don't pay a model
    to second-guess it — and don't let it make a deterministic result random."""
    def _explode(*_a, **_kw):
        raise AssertionError("no AI call when every field mapped by keyword")
    monkeypatch.setattr(ai_client.httpx, "post", _explode)

    analysis = build_analysis("staff", ["Name", "Mobile"], [{"Name": "R"}], SPECS)
    assert analysis.mapping == {"full_name": "Name", "phone": "Mobile"}
    assert analysis.source == "heuristic"


def test_ai_cannot_assign_one_column_to_two_fields(ai_on, monkeypatch):
    monkeypatch.setattr(
        ai_client.httpx, "post",
        _reply('{"mapping": {"full_name": "Solo", "phone": "Solo"}}'))
    analysis = build_analysis("staff", ["Solo"], [{"Solo": "x"}], SPECS)
    assert list(analysis.mapping.values()) == ["Solo"]


def test_ai_failure_leaves_the_heuristic_result_intact(ai_on, monkeypatch):
    """The whole contract in one test: the model 500s, and the import still works
    exactly as it would with no key at all — gap found, question asked."""
    monkeypatch.setattr(ai_client.httpx, "post", _reply("{}", status=500))
    analysis = build_analysis("staff", ["Naam", "Extra"], [{"Naam": "R"}], SPECS)

    assert analysis.missing_required == ["full_name"]
    assert analysis.questions[0]["field"] == "full_name"
    assert analysis.questions[0]["source"] == "fixture", "phrasing fell back too"
    assert analysis.source == "heuristic"


# ── question phrasing + syllabus splitting ───────────────────────────────────
def test_ai_phrases_the_question_but_the_validator_found_it(ai_on, monkeypatch):
    monkeypatch.setattr(
        ai_client.httpx, "post",
        _reply('{"question": "Which column has the teacher\'s full name?"}'))
    q = phrase_gap_question("staff", "full_name", "name", ["Naam"])
    assert q["question"] == "Which column has the teacher's full name?"
    assert q["source"] == "ai"
    assert q["options"] == ["Naam"] and q["skippable"] is True


def test_question_phrasing_falls_back_on_a_bad_reply(ai_on, monkeypatch):
    monkeypatch.setattr(ai_client.httpx, "post", _reply('{"question": "   "}'))
    q = phrase_gap_question("staff", "full_name", "name", [])
    assert q["question"] == "Which column holds each teacher's name?"
    assert q["source"] == "fixture"


def test_ai_syllabus_split_is_cleaned(ai_on, monkeypatch):
    monkeypatch.setattr(ai_client.httpx, "post", _reply(
        '{"units": ['
        '{"title": "Food", "topics": [{"title": "Sources", "est_periods": "3"},'
        ' {"title": "", "est_periods": 1}]},'
        '{"title": "Empty", "topics": []},'
        '{"title": "", "topics": [{"title": "orphan"}]},'
        '"garbage"]}'))
    units = split_syllabus_text("Chapter 1: Food\nSources")
    assert units == [{"title": "Food", "topics": [{"title": "Sources", "est_periods": 3}]}]


def test_syllabus_split_falls_back_when_ai_returns_nothing_usable(ai_on, monkeypatch):
    monkeypatch.setattr(ai_client.httpx, "post", _reply('{"units": []}'))
    units = split_syllabus_text("Chapter 1: Food\nSources of food (3)")
    assert units == [{"title": "Food", "topics": [{"title": "Sources of food", "est_periods": 3}]}]


def test_syllabus_split_offline_uses_the_heuristic(ai_off):
    units = split_syllabus_text("Chapter 2: Materials\nSorting - 4 periods")
    assert units == [{"title": "Materials", "topics": [{"title": "Sorting", "est_periods": 4}]}]
