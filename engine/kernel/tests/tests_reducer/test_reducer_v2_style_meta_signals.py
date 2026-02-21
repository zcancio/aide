"""
AIde v2 Reducer — Style, Meta, and Signal Tests

Tests for style.set, style.entity, meta.set, meta.annotate, meta.constrain,
voice, escalate, and batch signals.
"""

import pytest

from engine.kernel.reducer_v2 import empty_snapshot, reduce

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def empty():
    return empty_snapshot()


@pytest.fixture
def state_with_entity(empty):
    result = reduce(empty, {"t": "entity.create", "id": "item_one", "p": {"name": "Item One"}})
    assert result.accepted
    return result.snapshot


# ============================================================================
# style.set
# ============================================================================


class TestStyleSet:
    def test_sets_global_styles(self, empty):
        result = reduce(
            empty,
            {"t": "style.set", "p": {"primary_color": "#2D2D2A", "font_family": "Inter", "density": "comfortable"}},
        )
        assert result.accepted
        styles = result.snapshot["styles"]["global"]
        assert styles["primary_color"] == "#2D2D2A"
        assert styles["font_family"] == "Inter"
        assert styles["density"] == "comfortable"

    def test_merges_with_existing_styles(self, empty):
        result = reduce(empty, {"t": "style.set", "p": {"primary_color": "#fff"}})
        snap = result.snapshot
        result = reduce(snap, {"t": "style.set", "p": {"font_family": "Georgia"}})
        assert result.accepted
        styles = result.snapshot["styles"]["global"]
        assert styles["primary_color"] == "#fff"  # Preserved
        assert styles["font_family"] == "Georgia"  # Added

    def test_increments_sequence(self, empty):
        result = reduce(empty, {"t": "style.set", "p": {"x": 1}})
        assert result.snapshot["_sequence"] == 1

    def test_empty_props_ok(self, empty):
        result = reduce(empty, {"t": "style.set", "p": {}})
        assert result.accepted


# ============================================================================
# style.entity
# ============================================================================


class TestStyleEntity:
    def test_sets_entity_styles(self, state_with_entity):
        result = reduce(
            state_with_entity,
            {"t": "style.entity", "ref": "item_one", "p": {"highlight": True, "color": "#e53e3e"}},
        )
        assert result.accepted
        entity = result.snapshot["entities"]["item_one"]
        assert entity["_styles"]["highlight"] is True
        assert entity["_styles"]["color"] == "#e53e3e"
        # Also in styles.entities
        assert result.snapshot["styles"]["entities"]["item_one"]["highlight"] is True

    def test_merges_entity_styles(self, state_with_entity):
        result = reduce(state_with_entity, {"t": "style.entity", "ref": "item_one", "p": {"a": 1}})
        snap = result.snapshot
        result = reduce(snap, {"t": "style.entity", "ref": "item_one", "p": {"b": 2}})
        assert result.accepted
        entity = result.snapshot["entities"]["item_one"]
        assert entity["_styles"]["a"] == 1
        assert entity["_styles"]["b"] == 2

    def test_reject_nonexistent_entity(self, empty):
        result = reduce(empty, {"t": "style.entity", "ref": "nobody", "p": {"x": 1}})
        assert not result.accepted
        assert "ENTITY_NOT_FOUND" in result.reason

    def test_reject_missing_ref(self, empty):
        result = reduce(empty, {"t": "style.entity", "p": {"x": 1}})
        assert not result.accepted
        assert "MISSING_REF" in result.reason

    def test_reject_removed_entity(self, state_with_entity):
        result = reduce(state_with_entity, {"t": "entity.remove", "ref": "item_one"})
        snap = result.snapshot
        result = reduce(snap, {"t": "style.entity", "ref": "item_one", "p": {"x": 1}})
        assert not result.accepted
        assert "ENTITY_NOT_FOUND" in result.reason


# ============================================================================
# meta.set
# ============================================================================


class TestMetaSet:
    def test_sets_title(self, empty):
        result = reduce(empty, {"t": "meta.set", "p": {"title": "Sophie's Graduation Party"}})
        assert result.accepted
        assert result.snapshot["meta"]["title"] == "Sophie's Graduation Party"

    def test_sets_identity(self, empty):
        result = reduce(empty, {"t": "meta.set", "p": {"identity": "graduation_coordinator"}})
        assert result.accepted
        assert result.snapshot["meta"]["identity"] == "graduation_coordinator"

    def test_updates_existing_meta(self, empty):
        result = reduce(empty, {"t": "meta.set", "p": {"title": "Old Title"}})
        snap = result.snapshot
        result = reduce(snap, {"t": "meta.set", "p": {"title": "New Title"}})
        assert result.accepted
        assert result.snapshot["meta"]["title"] == "New Title"

    def test_sets_both_title_and_identity(self, empty):
        result = reduce(
            empty,
            {"t": "meta.set", "p": {"title": "My Aide", "identity": "some_context"}},
        )
        assert result.accepted
        assert result.snapshot["meta"]["title"] == "My Aide"
        assert result.snapshot["meta"]["identity"] == "some_context"

    def test_extra_meta_fields_stored(self, empty):
        result = reduce(empty, {"t": "meta.set", "p": {"custom_field": "value"}})
        assert result.accepted
        assert result.snapshot["meta"]["custom_field"] == "value"

    def test_increments_sequence(self, empty):
        result = reduce(empty, {"t": "meta.set", "p": {"title": "x"}})
        assert result.snapshot["_sequence"] == 1


# ============================================================================
# meta.annotate
# ============================================================================


class TestMetaAnnotate:
    def test_adds_annotation(self, empty):
        result = reduce(empty, {"t": "meta.annotate", "p": {"note": "Guest count updated.", "pinned": False}})
        assert result.accepted
        annotations = result.snapshot["meta"]["annotations"]
        assert len(annotations) == 1
        assert annotations[0]["note"] == "Guest count updated."
        assert annotations[0]["pinned"] is False

    def test_pinned_annotation(self, empty):
        result = reduce(empty, {"t": "meta.annotate", "p": {"note": "Important!", "pinned": True}})
        assert result.accepted
        assert result.snapshot["meta"]["annotations"][0]["pinned"] is True

    def test_annotation_has_ts_and_seq(self, empty):
        result = reduce(empty, {"t": "meta.annotate", "p": {"note": "Note", "pinned": False}})
        annotation = result.snapshot["meta"]["annotations"][0]
        assert "ts" in annotation
        assert "seq" in annotation

    def test_multiple_annotations_appended(self, empty):
        snap = empty
        for i in range(3):
            result = reduce(snap, {"t": "meta.annotate", "p": {"note": f"Note {i}", "pinned": False}})
            snap = result.snapshot
        assert len(snap["meta"]["annotations"]) == 3
        assert snap["meta"]["annotations"][2]["note"] == "Note 2"


# ============================================================================
# meta.constrain
# ============================================================================


class TestMetaConstrain:
    def test_adds_structural_constraint(self, empty):
        snap = empty
        result = reduce(snap, {"t": "entity.create", "id": "guests", "p": {}})
        snap = result.snapshot
        result = reduce(
            snap,
            {
                "t": "meta.constrain",
                "id": "max_guests",
                "rule": "max_children",
                "parent": "guests",
                "value": 50,
                "message": "Max 50 guests",
            },
        )
        assert result.accepted
        assert "max_guests" in result.snapshot["meta"]["constraints"]
        constraint = result.snapshot["meta"]["constraints"]["max_guests"]
        assert constraint["rule"] == "max_children"
        assert constraint["value"] == 50

    def test_strict_constraint_rejects_violating_state(self, empty):
        snap = empty
        result = reduce(snap, {"t": "entity.create", "id": "guests", "p": {}})
        snap = result.snapshot
        # Add 3 children
        for i in range(3):
            result = reduce(snap, {"t": "entity.create", "id": f"guest_{i}", "parent": "guests", "p": {}})
            snap = result.snapshot

        # Strict max_children = 2, but we have 3
        result = reduce(
            snap,
            {
                "t": "meta.constrain",
                "id": "max_2",
                "rule": "max_children",
                "parent": "guests",
                "value": 2,
                "strict": True,
            },
        )
        assert not result.accepted
        assert "STRICT_CONSTRAINT_VIOLATED" in result.reason

    def test_non_strict_constraint_with_violation_accepted(self, empty):
        snap = empty
        result = reduce(snap, {"t": "entity.create", "id": "guests", "p": {}})
        snap = result.snapshot
        for i in range(3):
            result = reduce(snap, {"t": "entity.create", "id": f"guest_{i}", "parent": "guests", "p": {}})
            snap = result.snapshot

        result = reduce(
            snap,
            {
                "t": "meta.constrain",
                "id": "soft_max",
                "rule": "max_children",
                "parent": "guests",
                "value": 2,
                "strict": False,
            },
        )
        assert result.accepted  # Non-strict: accepted even with violation

    def test_reject_missing_id(self, empty):
        result = reduce(empty, {"t": "meta.constrain", "rule": "max_children"})
        assert not result.accepted
        assert "MISSING_ID" in result.reason

    def test_updates_existing_constraint(self, empty):
        result = reduce(empty, {"t": "meta.constrain", "id": "c1", "rule": "max_children", "value": 10})
        snap = result.snapshot
        result = reduce(snap, {"t": "meta.constrain", "id": "c1", "rule": "max_children", "value": 20})
        assert result.accepted
        assert result.snapshot["meta"]["constraints"]["c1"]["value"] == 20
        assert len(result.snapshot["meta"]["constraints"]) == 1


# ============================================================================
# Signal handling: voice
# ============================================================================


class TestVoiceSignal:
    def test_voice_accepted_with_signal(self, empty):
        result = reduce(empty, {"t": "voice", "text": "Guest list updated."})
        assert result.accepted
        assert result.signal is not None
        assert result.signal["type"] == "voice"
        assert result.signal["text"] == "Guest list updated."

    def test_voice_does_not_mutate_snapshot(self, empty):
        result = reduce(empty, {"t": "voice", "text": "Something."})
        assert result.accepted
        assert result.snapshot["_sequence"] == 0  # No mutation

    def test_voice_empty_text(self, empty):
        result = reduce(empty, {"t": "voice", "text": ""})
        assert result.accepted
        assert result.signal["text"] == ""


# ============================================================================
# Signal handling: escalate
# ============================================================================


class TestEscalateSignal:
    def test_escalate_accepted_with_signal(self, empty):
        result = reduce(
            empty,
            {"t": "escalate", "tier": "L3", "reason": "structural_change", "extract": "Needs schema design."},
        )
        assert result.accepted
        assert result.signal is not None
        assert result.signal["type"] == "escalate"
        assert result.signal["tier"] == "L3"
        assert result.signal["reason"] == "structural_change"
        assert result.signal["extract"] == "Needs schema design."

    def test_escalate_does_not_mutate_snapshot(self, empty):
        result = reduce(empty, {"t": "escalate", "tier": "L3", "reason": "x"})
        assert result.accepted
        assert result.snapshot["_sequence"] == 0


# ============================================================================
# Signal handling: batch.start / batch.end
# ============================================================================


class TestBatchSignals:
    def test_batch_start_accepted_with_signal(self, empty):
        result = reduce(empty, {"t": "batch.start"})
        assert result.accepted
        assert result.signal["type"] == "batch.start"

    def test_batch_end_accepted_with_signal(self, empty):
        result = reduce(empty, {"t": "batch.end"})
        assert result.accepted
        assert result.signal["type"] == "batch.end"

    def test_batch_signals_do_not_mutate_snapshot(self, empty):
        result = reduce(empty, {"t": "batch.start"})
        assert result.snapshot["_sequence"] == 0
        result2 = reduce(result.snapshot, {"t": "batch.end"})
        assert result2.snapshot["_sequence"] == 0


# ============================================================================
# Unknown primitive
# ============================================================================


class TestUnknownPrimitive:
    def test_unknown_type_rejected(self, empty):
        result = reduce(empty, {"t": "collection.create", "id": "test"})
        assert not result.accepted
        assert "UNKNOWN_PRIMITIVE" in result.reason

    def test_missing_type_rejected(self, empty):
        result = reduce(empty, {"id": "test"})
        assert not result.accepted
        assert "MISSING_TYPE" in result.reason
