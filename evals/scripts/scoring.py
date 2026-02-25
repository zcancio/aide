"""
AIde Prompt Scoring Rubric

Produces numeric scores (0.0–1.0) per dimension, comparable across:
  - Model versions (Haiku 4.5 → Haiku 5, Sonnet 4.5 → Sonnet 5)
  - Prompt versions (v3.0 → v3.1 → v4.0)
  - Runs over time (regression detection)

Dimensions:
  1. Validity    — Does the output parse? Does it use valid primitives?
  2. Voice       — Does it follow AIde voice rules?
  3. Structure   — Correct emission order, display hints, entity IDs?
  4. Efficiency  — Token economy, output compactness
  5. Fidelity    — Does it actually do what the user asked?

Each dimension is 0.0–1.0. Composite is a weighted average.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VOICE_PATTERNS = [
    (r"\bI\s+(updated|created|added|changed|found|counted|checked|set|moved|removed)", "first_person_action", 1.0),
    (r"\bI('m| am| will| can| did)\b", "first_person", 0.8),
    (r"(?i)^(Great|Nice|Awesome|Perfect|Sure|Got it|No problem|Of course)", "encouragement", 1.0),
    (r"(?i)What else can I help", "filler_offer", 0.6),
    (r"(?i)Here's what I", "filler_narration", 0.6),
    (r"(?i)Let me (check|look|see|find)", "self_narration", 0.5),
    (r"(?i)Based on (the|your|my)", "hedging", 0.3),
    (r"[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f900-\U0001f9ff]", "emoji", 1.0),
]

VALID_DISPLAY_HINTS = {"page", "section", "card", "list", "table", "checklist", "metric", "text", "image", "row"}

VALID_TYPES = {
    "entity.create", "entity.update", "entity.remove", "entity.move", "entity.reorder",
    "rel.set", "rel.remove", "rel.constrain",
    "style.set", "style.entity",
    "meta.set", "meta.update", "meta.annotate", "meta.constrain",
    "voice", "escalate", "clarify", "batch.start", "batch.end",
}

# Composite weights (must sum to 1.0)
DIMENSION_WEIGHTS = {
    "validity": 0.30,
    "voice": 0.20,
    "structure": 0.25,
    "efficiency": 0.10,
    "fidelity": 0.15,
}

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class DimensionScore:
    """Score for one dimension with breakdown."""
    name: str
    score: float  # 0.0–1.0
    checks: dict[str, float] = field(default_factory=dict)  # sub-check → score
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": round(self.score, 3),
            "checks": {k: round(v, 3) for k, v in self.checks.items()},
            "notes": self.notes,
        }


@dataclass
class ScenarioScore:
    """Full score for one scenario."""
    name: str
    tier: str
    model: str
    prompt_version: str
    dimensions: dict[str, DimensionScore] = field(default_factory=dict)
    composite: float = 0.0
    latency_ms: int = 0
    output_tokens: int = 0
    cache_hit_pct: float = 0.0

    def compute_composite(self):
        total = 0.0
        for dim_name, weight in DIMENSION_WEIGHTS.items():
            if dim_name in self.dimensions:
                total += self.dimensions[dim_name].score * weight
        self.composite = total

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "tier": self.tier,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "composite": round(self.composite, 3),
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "latency_ms": self.latency_ms,
            "output_tokens": self.output_tokens,
            "cache_hit_pct": round(self.cache_hit_pct, 1),
        }


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_jsonl(text: str) -> tuple[list[dict], list[str]]:
    """Parse JSONL, strip code fences. Returns (lines, errors)."""
    parsed, errors = [], []
    for i, line in enumerate(text.strip().split("\n")):
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError as e:
            errors.append(f"Line {i+1}: {e}")
    return parsed, errors


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------

def score_validity(text: str, tier: str) -> DimensionScore:
    """
    Can the output be consumed by the pipeline?

    Sub-checks:
      - parseable: all lines parse as JSON (L2/L3) or is text (L4)
      - no_fences: no markdown code fences
      - valid_types: all 't' values are recognized primitives/signals
      - valid_json_structure: each line has required fields for its type
    """
    checks = {}
    notes = []

    if tier == "L4":
        # L4 should be plain text, not JSON
        stripped = text.strip()
        is_json_blob = False
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and ("primitives" in obj or "response" in obj):
                is_json_blob = True
        except json.JSONDecodeError:
            pass

        checks["is_plain_text"] = 0.0 if is_json_blob else 1.0
        checks["not_empty"] = 1.0 if len(stripped) > 0 else 0.0

        if is_json_blob:
            notes.append("L4 output is JSON blob — should be plain text")

        score = sum(checks.values()) / max(len(checks), 1)
        return DimensionScore("validity", score, checks, notes)

    # L2/L3: JSONL validation
    parsed, errors = parse_jsonl(text)

    # Parseable
    total_lines = len(parsed) + len(errors)
    checks["parseable"] = len(parsed) / max(total_lines, 1) if total_lines > 0 else 0.0
    if errors:
        notes.append(f"{len(errors)} parse errors")

    # No fences
    fence_lines = [l for l in text.strip().split("\n") if l.strip().startswith("```")]
    checks["no_fences"] = 1.0 if not fence_lines else 0.0

    # Valid types
    if parsed:
        known = sum(1 for p in parsed if p.get("t") in VALID_TYPES)
        checks["valid_types"] = known / len(parsed)
        unknown = [p.get("t") for p in parsed if p.get("t") not in VALID_TYPES]
        if unknown:
            notes.append(f"Unknown types: {unknown[:3]}")
    else:
        checks["valid_types"] = 0.0

    # Structural validity per line
    if parsed:
        valid_struct = 0
        for p in parsed:
            t = p.get("t", "")
            if t == "entity.create" and "id" in p and "parent" in p:
                valid_struct += 1
            elif t == "entity.update" and "ref" in p and "p" in p:
                valid_struct += 1
            elif t in ("voice", "escalate", "clarify", "batch.start", "batch.end", "style.set",
                       "meta.set", "meta.update", "entity.remove", "entity.move",
                       "entity.reorder", "rel.set", "rel.remove", "style.entity",
                       "meta.annotate", "meta.constrain", "rel.constrain"):
                valid_struct += 1  # Signals/meta are structurally simple
            # else: unrecognized → 0
        checks["valid_structure"] = valid_struct / len(parsed)
    else:
        checks["valid_structure"] = 0.0

    # Not empty
    checks["not_empty"] = 1.0 if parsed else 0.0

    score = sum(checks.values()) / max(len(checks), 1)
    return DimensionScore("validity", score, checks, notes)


def score_voice(text: str, tier: str) -> DimensionScore:
    """
    Does the output follow AIde voice rules?

    Checks voice lines (L2/L3) or full text (L4) against violation patterns.
    Each violation has a severity weight.
    """
    checks = {}
    notes = []

    # Extract voice text
    voice_texts = []
    if tier == "L4":
        voice_texts = [text.strip()]
    else:
        parsed, _ = parse_jsonl(text)
        voice_texts = [p.get("text", "") for p in parsed if p.get("t") == "voice"]

    if not voice_texts:
        # No voice output to evaluate — neutral (not penalized, not rewarded)
        return DimensionScore("voice", 1.0, {"no_voice_to_check": 1.0}, ["No voice lines emitted"])

    total_severity = 0.0
    violation_count = 0

    for vt in voice_texts:
        for pattern, label, severity in VOICE_PATTERNS:
            if re.search(pattern, vt):
                violation_count += 1
                total_severity += severity
                notes.append(f"{label}: \"{vt[:50]}...\"" if len(vt) > 50 else f"{label}: \"{vt}\"")

    # Score: 1.0 if no violations, degrades with severity
    # Cap at 3.0 total severity for a full zero
    checks["violation_count"] = max(0.0, 1.0 - (violation_count / max(len(voice_texts) * 2, 1)))
    checks["severity_score"] = max(0.0, 1.0 - (total_severity / 3.0))

    # Voice length check (should be under 100 chars per line)
    if tier != "L4":
        over_limit = sum(1 for vt in voice_texts if len(vt) > 100)
        checks["under_100_chars"] = 1.0 - (over_limit / max(len(voice_texts), 1))

    score = sum(checks.values()) / max(len(checks), 1)
    return DimensionScore("voice", score, checks, notes)


def score_structure(text: str, tier: str, scenario_hints: dict | None = None, snapshot: dict | None = None) -> DimensionScore:
    """
    Correct emission order, display hints, entity IDs, tier-specific behavior.

    scenario_hints: optional dict with expected behaviors like:
      - "expect_escalation": True
      - "expect_mutation": True
      - "expect_table_not_cards": True
      - "expect_batch": True
      - "expect_meta_set": True
      - "expect_page_entity": True
      - "max_lines": 4
    snapshot: current entity state (used to seed parent resolution)
    """
    checks = {}
    notes = []
    hints = scenario_hints or {}

    if tier == "L4":
        # L4 structure is simple — just check it's not JSONL
        parsed, _ = parse_jsonl(text)
        jsonl_lines = [p for p in parsed if p.get("t") in VALID_TYPES]
        checks["no_jsonl_emission"] = 1.0 if not jsonl_lines else 0.0
        score = checks["no_jsonl_emission"]
        return DimensionScore("structure", score, checks, notes)

    parsed, _ = parse_jsonl(text)
    if not parsed:
        return DimensionScore("structure", 0.0, {"has_output": 0.0}, ["No parseable output"])

    # Emission order: meta before entities
    if hints.get("expect_meta_set", False):
        meta_idx = next((i for i, p in enumerate(parsed) if p.get("t") in ("meta.set", "meta.update")), -1)
        first_entity = next((i for i, p in enumerate(parsed) if p.get("t") == "entity.create"), len(parsed))
        checks["meta_before_entities"] = 1.0 if (meta_idx >= 0 and meta_idx < first_entity) else 0.0

    # Parents before children — seed with existing entities from snapshot
    seen_ids = {"root", "page"}
    if snapshot:
        seen_ids.update(snapshot.get("entities", {}).keys())
    parent_violations = 0
    entity_creates = [p for p in parsed if p.get("t") == "entity.create"]
    for p in entity_creates:
        parent = p.get("parent", "")
        if parent and parent not in seen_ids:
            parent_violations += 1
        seen_ids.add(p.get("id", ""))
    if entity_creates:
        checks["parents_before_children"] = 1.0 - (parent_violations / len(entity_creates))

    # Display hints valid
    hint_entities = [p for p in parsed if p.get("t") == "entity.create" and p.get("display")]
    if hint_entities:
        valid = sum(1 for p in hint_entities if p["display"] in VALID_DISPLAY_HINTS)
        checks["display_hints_valid"] = valid / len(hint_entities)

    # Entity IDs: snake_case, descriptive
    id_entities = [p for p in parsed if p.get("t") == "entity.create" and p.get("id")]
    if id_entities:
        good_ids = 0
        for p in id_entities:
            eid = p["id"]
            # snake_case, no uppercase, descriptive (not item_1)
            is_snake = bool(re.match(r"^[a-z][a-z0-9_]*$", eid))
            not_generic = not bool(re.match(r"^(item|row|section|entity)_\d+$", eid))
            if is_snake and not_generic:
                good_ids += 1
        checks["entity_ids_quality"] = good_ids / len(id_entities)

    # For update-only turns with no creates, check basic structural correctness
    updates = [p for p in parsed if p.get("t") == "entity.update"]
    if updates and not entity_creates:
        # All updates have ref and p — basic well-formedness
        well_formed = sum(1 for p in updates if p.get("ref") and p.get("p"))
        checks["updates_well_formed"] = well_formed / len(updates)
        # Check refs target existing entities (if snapshot available)
        if snapshot:
            existing = set(snapshot.get("entities", {}).keys())
            valid_refs = sum(1 for p in updates if p.get("ref") in existing)
            checks["refs_exist"] = valid_refs / len(updates)
            missing = [p.get("ref") for p in updates if p.get("ref") not in existing]
            if missing:
                notes.append(f"Unknown refs: {missing[:3]}")

    # Scenario-specific checks
    if hints.get("expect_escalation"):
        has_esc = any(p.get("t") == "escalate" for p in parsed)
        checks["has_escalation"] = 1.0 if has_esc else 0.0
        # Check escalation has reason + tier
        escs = [p for p in parsed if p.get("t") == "escalate"]
        if escs:
            has_reason = all(p.get("reason") for p in escs)
            has_tier = all(p.get("tier") for p in escs)
            checks["escalation_complete"] = (1.0 if has_reason else 0.0 + 1.0 if has_tier else 0.0) / 2

    if hints.get("expect_mutation"):
        mutations = [p for p in parsed if p.get("t") in ("entity.update", "entity.create", "entity.remove")]
        checks["has_mutation"] = 1.0 if mutations else 0.0

    if hints.get("expect_table_not_cards"):
        # Check that "player" entities are rows, not cards
        player_entities = [p for p in parsed if p.get("t") == "entity.create" and "player" in p.get("id", "")]
        if player_entities:
            cards = sum(1 for p in player_entities if p.get("display") == "card")
            checks["table_not_cards"] = 1.0 if cards == 0 else 0.0

    if hints.get("expect_batch"):
        has_start = any(p.get("t") == "batch.start" for p in parsed)
        has_end = any(p.get("t") == "batch.end" for p in parsed)
        checks["has_batch_signals"] = 1.0 if (has_start and has_end) else 0.0

    if hints.get("expect_page_entity"):
        has_page = any(p.get("t") == "entity.create" and p.get("display") == "page" for p in parsed)
        checks["has_page_entity"] = 1.0 if has_page else 0.0

    if hints.get("max_lines"):
        checks["compact_output"] = 1.0 if len(parsed) <= hints["max_lines"] else max(0.0, 1.0 - (len(parsed) - hints["max_lines"]) / 10)

    if hints.get("no_entity_creation"):
        creates = [p for p in parsed if p.get("t") == "entity.create"]
        checks["no_entity_creation"] = 1.0 if not creates else 0.0

    # Orphan detection — entity.remove on a parent without moving all children first
    if snapshot and tier in ("L2", "L3"):
        orphans = snapshot.get("orphans", [])
        if orphans:
            checks["no_orphans"] = 0.0
            notes.append(f"Orphaned entities: {orphans} — parent was removed without moving all children first")
        # Only add the check if a remove happened this turn
        elif any(p.get("t") == "entity.remove" for p in parsed):
            checks["no_orphans"] = 1.0

    score = sum(checks.values()) / max(len(checks), 1) if checks else 1.0
    return DimensionScore("structure", score, checks, notes)


def score_efficiency(output_tokens: int, tier: str, scenario_hints: dict | None = None, output_text: str = "") -> DimensionScore:
    """
    Token economy. Lower is better within correctness bounds.

    Scored relative to expected token ranges per tier/scenario type.
    Budget scales with operation count for L2.
    """
    checks = {}
    notes = []
    hints = scenario_hints or {}

    # Expected output token ranges by tier
    expected = hints.get("expected_tokens", None)
    if expected is None:
        if tier == "L2":
            # Scale budget with number of operations
            op_count = 1
            if output_text:
                parsed, _ = parse_jsonl(output_text)
                op_count = max(len(parsed), 1)
            # ~30 tokens per operation is reasonable for L2
            expected = (15 * op_count, max(100, 50 * op_count))
        elif tier == "L3":
            expected = (80, 1200)  # Lowered floor — v3.1 prompts produce leaner output
        else:
            expected = (20, 200)  # L4 text answers

    low, high = expected
    if output_tokens <= high:
        checks["within_budget"] = 1.0
    elif output_tokens <= high * 1.5:
        checks["within_budget"] = 0.5
        notes.append(f"{output_tokens} tokens (budget: {low}-{high})")
    else:
        checks["within_budget"] = 0.0
        notes.append(f"{output_tokens} tokens — well over budget {high}")

    # Bonus for being in the sweet spot
    if low <= output_tokens <= high:
        checks["in_sweet_spot"] = 1.0
    elif output_tokens < low:
        # Under budget could mean incomplete output
        checks["in_sweet_spot"] = 0.7
        notes.append(f"Under minimum ({output_tokens} < {low}) — may be incomplete")
    else:
        checks["in_sweet_spot"] = max(0.0, 1.0 - (output_tokens - high) / high)

    score = sum(checks.values()) / max(len(checks), 1)
    return DimensionScore("efficiency", score, checks, notes)


def score_fidelity(text: str, tier: str, scenario_hints: dict | None = None, snapshot: dict | None = None, user_message: str = "") -> DimensionScore:
    """
    Does the output actually address what the user asked?

    This is the hardest dimension to score automatically. We check:
    - Scenario-specific content markers (entity names, field values)
    - Appropriate tier behavior (L2 mutates, L3 creates, L4 answers)
    - No dangling refs (updates to non-existent entities = lost intent)
    - Data preservation: numbers, dollar amounts, and specific values from
      the user message should appear somewhere in the output
    """
    checks = {}
    notes = []
    hints = scenario_hints or {}

    parsed, _ = parse_jsonl(text) if tier != "L4" else ([], [])

    # Content markers — scenario-specific strings that should appear in output
    markers = hints.get("content_markers", [])
    if markers:
        found = 0
        text_lower = text.lower()
        for marker in markers:
            if marker.lower() in text_lower:
                found += 1
        checks["content_markers"] = found / len(markers)
        missing = [m for m in markers if m.lower() not in text_lower]
        if missing:
            notes.append(f"Missing markers: {missing[:3]}")

    # Data preservation — extract concrete data points from user message
    # and verify they appear somewhere in the output
    if user_message and tier in ("L2", "L3"):
        # Extract dollar amounts ($120, $5.50, etc.)
        dollar_amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', user_message)
        # Extract standalone numbers that look like data (not "3" in "3pm")
        # but catch things like "120", "22", scores, quantities
        numbers = re.findall(r'\b\d{2,}\b', user_message)
        # Extract time patterns (10:00, 7pm, etc.)
        times = re.findall(r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)\b', user_message)

        data_points = dollar_amounts + times
        # Add numbers that aren't part of already-found dollar amounts or times
        for n in numbers:
            if not any(n in dp for dp in data_points):
                data_points.append(n)

        if data_points:
            output_text = text.lower()
            found = 0
            missing_data = []
            for dp in data_points:
                # Strip $ for matching (model might store as number not string)
                clean = dp.replace('$', '').replace(',', '').strip()
                if clean in output_text or dp.lower() in output_text:
                    found += 1
                else:
                    missing_data.append(dp)
            checks["data_preserved"] = found / len(data_points)
            if missing_data:
                notes.append(f"Data from message not in output: {missing_data}")

    # Turn-level content expectations — specific strings that MUST appear in output
    # Use for contextual data that the regex-based data_preserved can't catch
    # (temporal phrases, qualifiers, store names, etc.)
    expect_in = hints.get("expect_in_output", [])
    if expect_in:
        output_lower = text.lower()
        found = 0
        missing = []
        for phrase in expect_in:
            if phrase.lower() in output_lower:
                found += 1
            else:
                missing.append(phrase)
        checks["context_captured"] = found / len(expect_in)
        if missing:
            notes.append(f"Context from message not captured: {missing}")

    # Dangling refs — updates to entities that don't exist mean user intent was lost
    if snapshot and tier in ("L2", "L3"):
        existing = set(snapshot.get("entities", {}).keys())
        # Also count entities created earlier in this same output
        for p in parsed:
            if p.get("t") == "entity.create" and p.get("id"):
                existing.add(p["id"])
        updates = [p for p in parsed if p.get("t") == "entity.update"]
        if updates:
            dangling = [p.get("ref") for p in updates if p.get("ref") not in existing]
            checks["no_dangling_refs"] = 1.0 if not dangling else max(0.0, 1.0 - len(dangling) / len(updates))
            if dangling:
                notes.append(f"Dangling refs (intent lost): {dangling[:3]}")

    # Check for exclusive boolean props that should be relationships.
    # If the model sets a boolean prop to true that another sibling already has true,
    # it should have used rel.set instead of entity.update.
    if snapshot and tier in ("L2", "L3") and parsed:
        entities = snapshot.get("entities", {})
        EXCLUSIVE_PROPS = {"hosting", "active", "current", "current_turn", "assigned", "selected"}
        for p in parsed:
            if p.get("t") != "entity.update":
                continue
            props = p.get("p", {})
            for prop_name, prop_val in props.items():
                if prop_val is True and prop_name in EXCLUSIVE_PROPS:
                    checks["use_rel_not_bool"] = 0.0
                    notes.append(f"'{prop_name}' should be a relationship (rel.set), not a boolean prop")
                    break

    # Tier-appropriate behavior
    if tier == "L2":
        # L2 should mutate state or signal (escalate/clarify)
        has_mutation = any(p.get("t") in (
            "entity.update", "entity.create", "entity.remove",
            "rel.set", "rel.remove",
        ) for p in parsed)
        has_signal = any(p.get("t") in ("escalate", "clarify") for p in parsed)
        checks["tier_appropriate"] = 1.0 if (has_mutation or has_signal) else 0.0

        # L2 duplicate-creation: if L2 creates an entity under a parent that has
        # exactly ONE existing child with similar shape AND the parent is not a
        # table/list/checklist (which naturally accumulate rows), the user likely
        # meant to update the existing entity.
        if snapshot:
            entities = snapshot.get("entities", {})
            creates = [p for p in parsed if p.get("t") == "entity.create"]
            accumulating_displays = {"table", "list", "checklist"}
            for c in creates:
                parent = c.get("parent", "")
                new_id = c.get("id", "")
                new_props = set(c.get("p", {}).keys()) - {"title"}
                if len(new_props) < 2:
                    continue
                # Check parent's display type — tables accumulate, don't flag
                parent_ent = entities.get(parent, {})
                parent_display = parent_ent.get("display", "")
                if parent_display in accumulating_displays:
                    continue
                # Find existing siblings
                siblings = [eid for eid, ent in entities.items()
                            if ent.get("parent") == parent and eid != new_id]
                if len(siblings) == 1:
                    sib_id = siblings[0]
                    sib_props = set(entities[sib_id].get("props", {}).keys()) - {"title"}
                    overlap = new_props & sib_props
                    if len(overlap) >= 2:
                        checks["no_duplicate_create"] = 0.0
                        notes.append(f"L2 created {new_id} but {sib_id} is the only sibling under non-table parent — update instead?")

    elif tier == "L3":
        # L3 should create entities
        has_creates = any(p.get("t") == "entity.create" for p in parsed)
        checks["tier_appropriate"] = 1.0 if has_creates else 0.0

    elif tier == "L4":
        # L4 should produce a substantive text answer
        stripped = text.strip()
        checks["has_content"] = 1.0 if len(stripped) > 10 else 0.0
        checks["not_json"] = 0.0 if stripped.startswith("{") else 1.0

    # Clarify signal checks (from turn-level hints)
    has_clarify = any(p.get("t") == "clarify" for p in parsed) if parsed else False
    if hints.get("should_clarify"):
        # Turn expects a clarify signal — penalize if model guessed instead
        checks["emitted_clarify"] = 1.0 if has_clarify else 0.0
        if not has_clarify:
            notes.append("Expected clarify signal for ambiguous input — model guessed instead of asking")
        else:
            # Bonus: check clarify has text and options
            clarifies = [p for p in parsed if p.get("t") == "clarify"]
            has_text = all(p.get("text") for p in clarifies)
            has_options = all(p.get("options") and len(p["options"]) >= 2 for p in clarifies)
            if has_text and has_options:
                checks["clarify_quality"] = 1.0
            elif has_text:
                checks["clarify_quality"] = 0.7
                notes.append("Clarify has text but missing options")
            else:
                checks["clarify_quality"] = 0.3
                notes.append("Clarify signal lacks text")

    # Clarify resolution checks — user answered a previous clarify, model must act on it
    if hints.get("resolves_clarify"):
        # Model should NOT re-ask — user already gave their answer
        checks["no_re_clarify"] = 0.0 if has_clarify else 1.0
        if has_clarify:
            notes.append("Model re-asked for clarification after user already answered — should have acted")
        # Model should emit at least one mutation (entity.update, entity.remove, rel.set, etc.)
        mutation_types = {"entity.update", "entity.remove", "entity.create", "rel.set", "rel.remove"}
        has_mutation = any(p.get("t") in mutation_types for p in parsed) if parsed else False
        checks["applied_resolution"] = 1.0 if has_mutation else 0.0
        if not has_mutation:
            notes.append("User answered clarify but model emitted no mutations — answer was ignored")
        else:
            notes.append("Clarify resolved: model applied mutations based on user's answer")

    # Removal check — model should emit entity.remove
    if hints.get("removes_chore"):
        has_remove = any(p.get("t") == "entity.remove" for p in parsed) if parsed else False
        checks["emitted_remove"] = 1.0 if has_remove else 0.0
        if not has_remove:
            # Also accept entity.update with active=false or similar deactivation
            has_deactivate = any(
                p.get("t") == "entity.update" and
                p.get("props", {}).get("active") is False
                for p in parsed
            ) if parsed else False
            if has_deactivate:
                checks["emitted_remove"] = 0.8
                notes.append("Used entity.update to deactivate instead of entity.remove — acceptable")
            else:
                notes.append("Expected entity.remove for chore removal — model didn't remove anything")

    # Unassign check — model should rel.remove the assignment, NOT entity.remove the chore
    if hints.get("unassigns_chore"):
        has_rel_remove = any(p.get("t") == "rel.remove" for p in parsed) if parsed else False
        has_entity_remove = any(p.get("t") == "entity.remove" for p in parsed) if parsed else False
        if has_rel_remove and not has_entity_remove:
            checks["unassign_method"] = 1.0
            notes.append("Correctly used rel.remove to unassign — chore entity preserved")
        elif has_rel_remove and has_entity_remove:
            checks["unassign_method"] = 0.3
            notes.append("Used rel.remove but ALSO entity.remove — chore was deleted from tracker")
        elif has_entity_remove and not has_rel_remove:
            checks["unassign_method"] = 0.2
            notes.append("Used entity.remove instead of rel.remove — destroyed the chore entity "
                         "instead of just unassigning it. 'Remove alex's chore' means take it "
                         "off alex's plate, not delete vacuuming from the tracker.")
        else:
            # Maybe used entity.update to clear assigned_to prop?
            has_update = any(p.get("t") == "entity.update" for p in parsed) if parsed else False
            if has_update:
                checks["unassign_method"] = 0.5
                notes.append("Used entity.update — works but rel.remove is the correct primitive for unassignment")
            else:
                checks["unassign_method"] = 0.0
                notes.append("No unassignment operation found — expected rel.remove")

    # "Already have X" — item should leave the remaining list (done=true or entity.remove)
    if hints.get("marks_done_or_removes"):
        has_done = any(
            p.get("t") == "entity.update" and p.get("p", {}).get("done") is True
            for p in parsed
        ) if parsed else False
        has_remove = any(p.get("t") == "entity.remove" for p in parsed) if parsed else False
        if has_done or has_remove:
            checks["item_resolved"] = 1.0
            method = "marked done" if has_done else "removed"
            notes.append(f"Item {method} — no longer on remaining list")
        else:
            checks["item_resolved"] = 0.0
            notes.append("Item should be done or removed — 'already have' means don't need to buy")

    # Correction / un-check — model must set done=false (reverse a previous check-off)
    if hints.get("unchecks_eggs"):
        has_uncheck = any(
            p.get("t") == "entity.update" and p.get("p", {}).get("done") is False
            for p in parsed
        ) if parsed else False
        if has_uncheck:
            checks["state_reversed"] = 1.0
            notes.append("Correctly reversed done state — eggs back on remaining list")
        else:
            checks["state_reversed"] = 0.0
            notes.append("Expected done=false to un-check eggs — model didn't reverse previous state")

    # Update existing entity with new detail (quantity, note, qualifier)
    if hints.get("updates_chicken"):
        has_update = any(
            p.get("t") == "entity.update" and "chicken" in p.get("ref", "").lower()
            for p in parsed
        ) if parsed else False
        if has_update:
            checks["detail_added"] = 1.0
            notes.append("Updated chicken entity with additional detail")
        else:
            # Also accept if they created a new entity (wrong but less wrong)
            has_create = any(
                p.get("t") == "entity.create" and "chicken" in p.get("id", "").lower()
                for p in parsed
            ) if parsed else False
            if has_create:
                checks["detail_added"] = 0.3
                notes.append("Created new chicken entity instead of updating existing one")
            else:
                checks["detail_added"] = 0.0
                notes.append("Expected entity.update on chicken item with quantity/note")

    # Restructuring — should create new section entities and/or move items
    if hints.get("creates_sections"):
        new_sections = [
            p for p in parsed
            if p.get("t") == "entity.create"
            and p.get("display") in ("section", "group", "checklist", "card")
        ] if parsed else []
        moves = [p for p in parsed if p.get("t") == "entity.move"] if parsed else []
        if new_sections and moves:
            checks["restructured"] = 1.0
            notes.append(f"Created {len(new_sections)} section(s) and moved {len(moves)} item(s)")
        elif new_sections:
            checks["restructured"] = 0.7
            notes.append(f"Created {len(new_sections)} section(s) but didn't move existing items into them")
        elif moves:
            checks["restructured"] = 0.7
            notes.append(f"Moved {len(moves)} item(s) but didn't create new section entities")
        else:
            checks["restructured"] = 0.0
            notes.append("Expected section creation + item moves for restructuring request")

    score = sum(checks.values()) / max(len(checks), 1) if checks else 0.5
    return DimensionScore("fidelity", score, checks, notes)


# ---------------------------------------------------------------------------
# Full scenario scorer
# ---------------------------------------------------------------------------

# Scenario-specific hints for structure/fidelity scoring
SCENARIO_HINTS: dict[str, dict] = {
    "create_graduation": {
        "expect_meta_set": True,
        "expect_page_entity": True,
        "content_markers": ["graduation", "sophie", "may", "guest", "food", "todo"],
        "expected_tokens": (400, 1200),
    },
    "create_poker": {
        "expect_meta_set": True,
        "expect_page_entity": True,
        "expect_table_not_cards": True,
        "content_markers": ["poker", "player", "thursday"],
        "expected_tokens": (400, 1200),
    },
    "create_inspo": {
        "expect_meta_set": True,
        "content_markers": ["kitchen", "renovation"],
        "expected_tokens": (200, 800),
    },
    "update_simple": {
        "max_lines": 4,
        "content_markers": ["linda", "yes"],
        "expected_tokens": (20, 80),
    },
    "update_multi": {
        "content_markers": ["linda", "potato"],
        "expected_tokens": (30, 150),
    },
    "escalation_structural": {
        "expect_escalation": True,
        "no_entity_creation": True,
        "expected_tokens": (20, 80),
    },
    "multi_intent": {
        "expect_mutation": True,
        "expect_escalation": True,
        "content_markers": ["steve"],
        "expected_tokens": (30, 120),
    },
    "query_negation": {
        "content_markers": ["bob", "james"],  # names of pending guests
        "expected_tokens": (20, 150),
    },
    "query_sufficiency": {
        "expected_tokens": (30, 200),
    },
    "inspo_reorganize": {
        "expect_batch": True,
        "content_markers": ["backsplash", "shelving"],
        "expected_tokens": (200, 800),
    },
}


def score_scenario(
    name: str,
    tier: str,
    model: str,
    prompt_version: str,
    output_text: str,
    output_tokens: int = 0,
    latency_ms: int = 0,
    cache_hit_pct: float = 0.0,
    snapshot: dict | None = None,
    user_message: str = "",
    turn_hints: dict | None = None,
) -> ScenarioScore:
    """Score a single scenario across all dimensions."""
    hints = {**SCENARIO_HINTS.get(name, {}), **(turn_hints or {})}

    result = ScenarioScore(
        name=name,
        tier=tier,
        model=model,
        prompt_version=prompt_version,
        latency_ms=latency_ms,
        output_tokens=output_tokens,
        cache_hit_pct=cache_hit_pct,
    )

    result.dimensions["validity"] = score_validity(output_text, tier)
    result.dimensions["voice"] = score_voice(output_text, tier)
    result.dimensions["structure"] = score_structure(output_text, tier, hints, snapshot)
    result.dimensions["efficiency"] = score_efficiency(output_tokens, tier, hints, output_text)
    result.dimensions["fidelity"] = score_fidelity(output_text, tier, hints, snapshot, user_message)

    result.compute_composite()
    return result


# ---------------------------------------------------------------------------
# Baseline comparison
# ---------------------------------------------------------------------------

@dataclass
class RegressionResult:
    """Comparison of current run against baseline."""
    scenario: str
    baseline_composite: float
    current_composite: float
    delta: float  # positive = improvement
    regressed_dimensions: list[str] = field(default_factory=list)
    improved_dimensions: list[str] = field(default_factory=list)
    status: str = "pass"  # pass, warn, fail

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "baseline": round(self.baseline_composite, 3),
            "current": round(self.current_composite, 3),
            "delta": round(self.delta, 3),
            "status": self.status,
            "regressed": self.regressed_dimensions,
            "improved": self.improved_dimensions,
        }


def compare_to_baseline(
    current: list[ScenarioScore],
    baseline: dict,
    regression_threshold: float = 0.05,  # 5% drop = warning
    failure_threshold: float = 0.15,     # 15% drop = failure
) -> list[RegressionResult]:
    """
    Compare current scores against a saved baseline.

    baseline format: {"scenarios": {"name": {"composite": 0.85, "dimensions": {...}}}}
    """
    results = []
    baseline_scenarios = baseline.get("scenarios", {})

    for score in current:
        base = baseline_scenarios.get(score.name)
        if not base:
            results.append(RegressionResult(
                scenario=score.name,
                baseline_composite=0.0,
                current_composite=score.composite,
                delta=score.composite,
                status="new",
            ))
            continue

        base_composite = base.get("composite", 0.0)
        delta = score.composite - base_composite

        # Check per-dimension regressions
        regressed = []
        improved = []
        base_dims = base.get("dimensions", {})
        for dim_name, dim_score in score.dimensions.items():
            base_dim = base_dims.get(dim_name, {}).get("score", 0.0)
            dim_delta = dim_score.score - base_dim
            if dim_delta < -regression_threshold:
                regressed.append(f"{dim_name} ({base_dim:.2f}→{dim_score.score:.2f})")
            elif dim_delta > regression_threshold:
                improved.append(f"{dim_name} ({base_dim:.2f}→{dim_score.score:.2f})")

        status = "pass"
        if delta < -failure_threshold:
            status = "fail"
        elif delta < -regression_threshold:
            status = "warn"

        results.append(RegressionResult(
            scenario=score.name,
            baseline_composite=base_composite,
            current_composite=score.composite,
            delta=delta,
            regressed_dimensions=regressed,
            improved_dimensions=improved,
            status=status,
        ))

    return results


def save_baseline(scores: list[ScenarioScore], path: str, metadata: dict | None = None):
    """Save current scores as a baseline for future comparison."""
    baseline = {
        "metadata": metadata or {},
        "scenarios": {},
    }
    for s in scores:
        baseline["scenarios"][s.name] = {
            "composite": s.composite,
            "dimensions": {k: {"score": v.score, "checks": v.checks} for k, v in s.dimensions.items()},
            "tier": s.tier,
            "model": s.model,
            "prompt_version": s.prompt_version,
            "latency_ms": s.latency_ms,
            "output_tokens": s.output_tokens,
        }

    with open(path, "w") as f:
        json.dump(baseline, f, indent=2)


def load_baseline(path: str) -> dict:
    """Load a baseline file."""
    with open(path) as f:
        return json.load(f)
