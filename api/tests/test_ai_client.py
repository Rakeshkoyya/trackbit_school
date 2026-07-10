"""V2-P9: the OpenRouter client and the AI-assisted import path.

No test here touches the network. The point of these is the *contract*: AI can
improve on the deterministic heuristic, and can never break it. Every failure mode
— key absent, timeout, 500, rate limit, prose instead of JSON, a hallucinated
column — must land on the heuristic result with no exception escaping.
"""

import json

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


# ── vision: images and PDFs go to the multimodal model ───────────────────────
def test_is_visual_classifies_formats():
    from app.services.ai.client import is_visual
    assert is_visual("timetable.png") and is_visual("syllabus.pdf") and is_visual("s.JPEG")
    assert not is_visual("roster.xlsx") and not is_visual("notes.txt")


def test_image_attachment_is_sent_as_a_data_uri(ai_on, monkeypatch):
    from app.services.ai.client import _user_content
    parts = _user_content("read this", ("t.png", b"\x89PNG..."))
    assert parts[0] == {"type": "text", "text": "read this"}
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_pdf_attachment_is_sent_as_a_file_part(ai_on):
    from app.services.ai.client import _user_content
    parts = _user_content("read this", ("syl.pdf", b"%PDF-1.4"))
    assert parts[1]["type"] == "file"
    assert parts[1]["file"]["filename"] == "syl.pdf"
    assert parts[1]["file"]["file_data"].startswith("data:application/pdf;base64,")


def test_no_attachment_sends_a_plain_string(ai_on):
    """Text-only models (deepseek) reject the content-parts list form."""
    from app.services.ai.client import _user_content
    assert _user_content("hello", None) == "hello"


def test_unsupported_attachment_returns_none_not_an_exception(ai_on, monkeypatch):
    def _explode(*_a, **_kw):
        raise AssertionError("must not call the API for a format no model can read")
    monkeypatch.setattr(ai_client.httpx, "post", _explode)
    assert chat_json("s", "u", attachment=("roster.xlsx", b"PK\x03\x04")) is None


def test_vision_calls_get_the_longer_timeout(ai_on, monkeypatch):
    seen = {}

    def _post(url, **kwargs):
        seen["timeout"] = kwargs["timeout"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "AI_TIMEOUT_SECONDS", 20.0, raising=False)
    monkeypatch.setattr(settings, "AI_VISION_TIMEOUT_SECONDS", 90.0, raising=False)
    monkeypatch.setattr(ai_client.httpx, "post", _post)

    chat_json("s", "u")
    assert seen["timeout"] == 20.0
    chat_json("s", "u", attachment=("x.png", b"\x89PNG"))
    assert seen["timeout"] == 90.0, "OCR would time out on the text budget"


# Built with json.dumps, never a hand-written literal: a raw newline inside a JSON
# string is invalid JSON, and the client would (correctly) discard the whole reply.
OCR_TEXT = "Chapter 1: Food\nSources of food (3)"
OCR_REPLY = json.dumps({"text": OCR_TEXT})
SPLIT_REPLY = json.dumps(
    {"units": [{"title": "Food", "topics": [{"title": "Sources of food", "est_periods": 3}]}]})


def test_ocr_document_returns_transcribed_text(ai_on, monkeypatch):
    from app.services.ai.extract import ocr_document
    monkeypatch.setattr(ai_client.httpx, "post", _reply(OCR_REPLY))
    assert ocr_document("syl.pdf", b"%PDF") == OCR_TEXT


def test_ocr_document_is_none_for_a_spreadsheet(ai_on):
    from app.services.ai.extract import ocr_document
    assert ocr_document("syl.xlsx", b"PK") is None


def test_ocr_document_is_none_when_ai_is_off(ai_off):
    from app.services.ai.extract import ocr_document
    assert ocr_document("syl.pdf", b"%PDF") is None


def test_unreadable_scan_raises_rather_than_faking_an_empty_syllabus(ai_on, monkeypatch):
    """An empty draft would read as "your syllabus has no chapters" — a different,
    and much more confusing, problem than "we couldn't read your file"."""
    from app.core.exceptions import ValidationError
    from app.services.syllabus_import import analyze_file
    monkeypatch.setattr(ai_client.httpx, "post", _reply("{}"))
    with pytest.raises(ValidationError):
        analyze_file(b"%PDF-1.4", "scan.pdf")


def test_pdf_import_flows_ocr_into_the_text_splitter(ai_on, monkeypatch):
    from app.services.syllabus_import import analyze_file
    calls = []

    def _post(url, **kwargs):
        calls.append(kwargs["json"]["model"])
        content = OCR_REPLY if len(calls) == 1 else SPLIT_REPLY
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "AI_MODEL_PARSE", "google/gemini-2.5-flash-lite", raising=False)
    monkeypatch.setattr(settings, "AI_MODEL_DRAFT", "deepseek/deepseek-v4-flash", raising=False)
    monkeypatch.setattr(ai_client.httpx, "post", _post)

    out = analyze_file(b"%PDF-1.4", "scan.pdf")
    assert out["source"] == "ai-ocr" and out["mode"] == "text"
    assert out["units"][0]["title"] == "Food"
    assert out["units"][0]["topics"][0]["est_periods"] == 3
    # OCR must use the multimodal model; structuring uses the reasoning model.
    assert calls == ["google/gemini-2.5-flash-lite", "deepseek/deepseek-v4-flash"]


def test_null_content_does_not_crash(ai_on, monkeypatch):
    """Seen live from deepseek-v4-flash: HTTP 200, `content: null`. Before the
    guard this raised AttributeError inside _extract_json and took the whole
    import request down with a 500."""
    def _post(url, **kwargs):
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "choices": [{"finish_reason": "stop", "message": {"content": None}}]})
    monkeypatch.setattr(ai_client.httpx, "post", _post)
    assert chat_json("s", "u") is None


def test_reasoning_field_is_used_when_content_is_empty(ai_on, monkeypatch):
    """Reasoning models can spend the budget thinking and leave `content` empty
    while the JSON sits in `reasoning`. Take it rather than lose the call."""
    def _post(url, **kwargs):
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "choices": [{"message": {"content": "", "reasoning": '{"ok": true}'}}]})
    monkeypatch.setattr(ai_client.httpx, "post", _post)
    assert chat_json("s", "u") == {"ok": True}


def test_extract_json_tolerates_non_string_content():
    assert _extract_json(None) is None
    assert _extract_json([{"type": "text"}]) is None
    assert _extract_json(42) is None
