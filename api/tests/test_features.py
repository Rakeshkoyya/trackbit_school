"""`core/features.py` — the tier map itself (`D-106`…`D-111`).

Pure logic, no database. These tests exist to make the *policy* hard to break by
accident: the structural ones (§1) catch a malformed map, and the named ones
(§2) pin the decisions a future edit would otherwise quietly reverse.
"""

import pytest

from app.core.exceptions import PlanLimitError
from app.core.features import (
    FEATURE_LABELS,
    FEATURE_TIER,
    TIER_ADDS,
    TIER_FEATURES,
    TIERS,
    Feature,
    features_for,
    has_feature,
    label_for,
    normalise_plan,
    require_feature,
    tier_at_least,
    tier_for,
)


class _Org:
    """The one attribute the feature helpers actually read."""

    def __init__(self, plan: str):
        self.plan = plan


# ---- §1 structure -----------------------------------------------------
def test_every_feature_is_sold_exactly_once():
    """A feature listed under two tiers would make `FEATURE_TIER` depend on
    dict ordering — the cheapest tier must be the only one that adds it."""
    seen: list[Feature] = [f for tier in TIERS for f in TIER_ADDS[tier]]
    assert len(seen) == len(set(seen))
    assert set(seen) == set(Feature)


def test_tiers_are_cumulative():
    for cheaper, dearer in zip(TIERS, TIERS[1:], strict=False):
        assert TIER_FEATURES[cheaper] < TIER_FEATURES[dearer], (
            f"{dearer} must be a strict superset of {cheaper}")


def test_ultra_includes_everything():
    assert TIER_FEATURES["ultra"] == set(Feature)


def test_feature_tier_names_the_cheapest_tier_that_unlocks_it():
    for feature, tier in FEATURE_TIER.items():
        assert feature in TIER_FEATURES[tier]
        cheaper = TIERS[: TIERS.index(tier)]
        assert all(feature not in TIER_FEATURES[t] for t in cheaper)


def test_every_feature_has_a_label():
    """The upgrade wall renders `label_for` — an unlabelled feature would show
    the raw id ("fees.collection") to a school."""
    missing = [f for f in Feature if f not in FEATURE_LABELS]
    assert missing == []


def test_unknown_plan_reads_as_free():
    """A bad value in the database locks a school out of paid surfaces, never
    out of the app."""
    assert normalise_plan("platinum") == "free"
    assert normalise_plan(None) == "free"
    assert features_for("platinum") == TIER_FEATURES["free"]


def test_tier_at_least_is_ordered():
    assert tier_at_least("max", "pro")
    assert tier_at_least("pro", "pro")
    assert not tier_at_least("pro", "max")
    assert not tier_at_least("free", "ultra")


# ---- §2 the decisions ---------------------------------------------------
@pytest.mark.parametrize("feature", [
    Feature.CAPTURE_ATTENDANCE,
    Feature.CAPTURE_PERIOD,
    Feature.CAPTURE_HOMEWORK,
    Feature.CAPTURE_LESSON_LOG,
    Feature.PLAN_SYLLABUS,
    Feature.PLAN_TIMETABLE,
    Feature.BANDS_PROGRAMME,
    Feature.EVENTS_CALENDAR,
    Feature.INSIGHTS_DAILY_REPORT,
    Feature.STUDENTS_DIRECTORY,
])
def test_d107_the_capture_loop_is_free(feature):
    """`D-107` — free buys the act of recording. A school that stops capturing
    has nothing to upgrade *for*, so moving any of these above free breaks both
    the product principle (P1v2) and the commercial one."""
    assert tier_for(feature) == "free"


def test_d107_the_record_over_time_is_not_free():
    for feature in (Feature.STUDENTS_ACADEMICS, Feature.HOMEWORK_DESK,
                    Feature.EXAMS_BOARD, Feature.FEES_COLLECTION):
        assert tier_for(feature) == "pro"


def test_d108_the_parent_portal_is_max():
    assert tier_for(Feature.PARENT_PORTAL) == "max"
    assert tier_for(Feature.COMMS_GUARDIAN) == "max"


def test_q7_absence_alerts_stay_free():
    """A parent hearing nothing when their child is absent because the school is
    on free is indefensible — this is the one guardian-facing thing free keeps."""
    assert tier_for(Feature.COMMS_ABSENCE_ALERT) == "free"


def test_d109_tasks_is_all_or_nothing_at_max():
    assert tier_for(Feature.TASKS_BOARDS) == "max"
    assert not has_feature(_Org("pro"), Feature.TASKS_BOARDS)
    assert has_feature(_Org("max"), Feature.TASKS_BOARDS)


def test_d111_the_action_rail_is_max_but_the_dashboard_is_not():
    """The diagnosis is free; the one-tap dispatch is paid."""
    assert tier_for(Feature.INSIGHTS_ACTIONS) == "max"
    assert has_feature(_Org("free"), Feature.INSIGHTS_DAILY_REPORT)


def test_mcp_is_the_only_ultra_feature():
    assert TIER_ADDS["ultra"] == {Feature.AGENT_MCP}


# ---- §3 require_feature -------------------------------------------------
def test_require_feature_passes_when_included():
    assert require_feature(_Org("max"), Feature.TASKS_BOARDS) is None


def test_require_feature_raises_402_naming_the_tier():
    with pytest.raises(PlanLimitError) as exc:
        require_feature(_Org("free"), Feature.FEES_COLLECTION)
    err = exc.value
    assert err.status_code == 402
    assert err.code == "plan_limit"  # unchanged contract — errors.ts reads this
    assert err.details["required_tier"] == "pro"
    assert err.details["feature"] == "fees.collection"
    assert err.details["upgrade"] is True
    assert label_for(Feature.FEES_COLLECTION) in err.message


def test_require_feature_quotes_the_cheapest_sufficient_tier():
    """A free school asking for an ultra feature is told "Ultra", not "Pro"."""
    with pytest.raises(PlanLimitError) as exc:
        require_feature(_Org("free"), Feature.AGENT_MCP)
    assert exc.value.details["required_tier"] == "ultra"
