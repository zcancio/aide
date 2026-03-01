"""
Tests for tier classifier.

Validates routing logic for L3/L4 tiers (L2 removed).
"""

from __future__ import annotations

from backend.services.classifier import classify


def test_simple_update_routes_to_l3():
    """Simple updates route to L3 (Sonnet)."""
    snapshot = {"entities": {"item_1": {"name": "Milk"}}}
    result = classify("Mark Sarah as attending", snapshot, has_schema=True)
    assert result.tier == "L3"
    assert result.reason == "simple_update"


def test_question_routes_to_l4():
    """Pure questions route to L4."""
    snapshot = {"entities": {"guest_1": {"name": "Sarah", "status": "attending"}}}
    result = classify("How many guests are attending?", snapshot, has_schema=True)
    assert result.tier == "L4"
    assert result.reason == "pure_query"


def test_no_schema_routes_to_l4():
    """First message (no schema) routes to L4 (Architect)."""
    snapshot = {"entities": {}}
    result = classify("Plan a graduation party", snapshot, has_schema=False)
    assert result.tier == "L4"
    assert result.reason == "no_schema"


def test_structural_change_routes_to_l3():
    """Structural changes route to L3 (Sonnet)."""
    snapshot = {"entities": {"item_1": {"name": "Milk"}}}
    result = classify("Add a new section for decorations", snapshot, has_schema=True)
    assert result.tier == "L3"
    assert result.reason == "structural_change"


def test_mutation_with_query_routes_to_l3():
    """Multi-intent messages route to L3 (Sonnet)."""
    snapshot = {"entities": {"guest_1": {"name": "Linda"}}}
    result = classify("Add Aunt Linda and do we have enough food?", snapshot, has_schema=True)
    assert result.tier == "L3"
    assert result.reason == "complex_message"


def test_complex_message_routes_to_l3():
    """Messages with many commas route to L3."""
    snapshot = {"entities": {"item_1": {"name": "Milk"}}}
    result = classify("Add milk, eggs, bread, cheese to the list", snapshot, has_schema=True)
    assert result.tier == "L3"
    assert result.reason == "complex_message"


def test_track_keyword_routes_to_l3():
    """'track' keyword indicates new field, routes to L3."""
    snapshot = {"entities": {"item_1": {"name": "Milk"}}}
    result = classify("track the price for each item", snapshot, has_schema=True)
    assert result.tier == "L3"
    assert result.reason == "structural_change"


def test_empty_snapshot_routes_to_l4():
    """Empty snapshot routes to L4 (Architect)."""
    snapshot = {}
    result = classify("we need milk and eggs", snapshot, has_schema=False)
    assert result.tier == "L4"
    assert result.reason == "no_schema"


def test_question_with_mutation_routes_to_l3():
    """Questions that also include mutations route to L3 not L4."""
    snapshot = {"entities": {"item_1": {"name": "Milk"}}}
    result = classify("Add eggs and do we have enough for 10 people?", snapshot, has_schema=True)
    assert result.tier == "L3"
    assert result.reason == "complex_message"


def test_classifier_accuracy_benchmark():
    """
    Benchmark classifier accuracy on a diverse set of examples.

    Target: >90% accuracy matching expected tier routing.
    L2 removed - simple updates now go to L3.
    First messages (no_schema) now go to L4.
    """
    test_cases = [
        # (message, has_schema, expected_tier, description)
        ("Mark item as done", True, "L3", "simple update"),
        ("Add olive oil", True, "L3", "simple addition"),
        ("Mike's out", True, "L3", "simple status change"),
        ("How many items?", True, "L4", "pure query"),
        ("What's the total?", True, "L4", "pure query"),
        ("Who's coming?", True, "L4", "pure query"),
        ("Plan a party", False, "L4", "first message"),
        ("Add a category for drinks", True, "L3", "structural"),
        ("Track prices", True, "L3", "new field"),
        ("Add milk, eggs, bread, and cheese", True, "L3", "complex"),
    ]

    snapshot_with_schema = {"entities": {"item_1": {"name": "Test"}}}
    snapshot_empty = {"entities": {}}

    correct = 0
    total = len(test_cases)

    for message, has_schema, expected_tier, description in test_cases:
        snapshot = snapshot_with_schema if has_schema else snapshot_empty
        result = classify(message, snapshot, has_schema)
        if result.tier == expected_tier:
            correct += 1
        else:
            print(f"MISS: {description} - got {result.tier}, expected {expected_tier}")

    accuracy = correct / total
    print(f"Classifier accuracy: {accuracy:.1%} ({correct}/{total})")
    assert accuracy >= 0.9, f"Classifier accuracy {accuracy:.1%} below 90% target"
