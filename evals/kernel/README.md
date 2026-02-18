# Kernel Eval Scenarios

Evaluation scenarios for testing the AIde kernel (L2/L3 → primitives → reducer → snapshot).

## Scenarios

| ID | Name | Complexity | Key Primitives |
|----|------|------------|----------------|
| 01 | Grocery List | Basic | entity CRUD, check/uncheck, quantities |
| 02 | Poker League | Advanced | multi-entity (players, games), constraints, standings |
| 03 | Group Trip | Advanced | travelers, expenses, itinerary, entity styles |
| 04 | Chessboard | Advanced | positional state, move history, annotations |
| 05 | Football Squares | Advanced | 10x10 grid via Record, claims, payouts |

## Schema Format

Each scenario JSON contains:

```json
{
  "id": "scenario_id",
  "name": "Human-readable name",
  "description": "What this scenario tests",
  "complexity": "basic | intermediate | advanced",
  "primitives_exercised": ["schema.create", "entity.update", ...],
  "turns": [
    {
      "turn": 1,
      "user_message": "Natural language input",
      "expected_schemas": [...],
      "expected_entities": [...],
      "expected_blocks": [...],
      "expected_meta": [...],
      "expected_styles": [...],
      "expected_constraints": [...],
      "notes": "Optional explanation"
    }
  ],
  "final_state_assertions": {
    "entity_count": 5,
    ...
  }
}
```

## Turn Types

Each turn has an optional `type` field:

| Type | Description | Expected Output |
|------|-------------|-----------------|
| (default) | Mutation turn | `expected_*` arrays with primitives |
| `query` | Read-only question | `expected_response` with text answer |
| `error` | Invalid/ambiguous input | `expected_response` with clarification |

### Query Turns

Query turns test the system's ability to answer questions without mutating state:

```json
{
  "turn": 7,
  "type": "query",
  "user_message": "What do I still need to get?",
  "expected_primitives": [],
  "expected_response": {
    "type": "text",
    "content": "You still need: Milk, Bread, Butter...",
    "notes": "Query about unchecked items."
  }
}
```

### Error Turns

Error turns test graceful handling of invalid or ambiguous input:

```json
{
  "turn": 9,
  "type": "error",
  "user_message": "Check off the apples",
  "expected_primitives": [],
  "expected_response": {
    "type": "clarification",
    "content": "I don't see apples on your list. Did you mean...",
    "notes": "Error: referencing non-existent item."
  }
}
```

Error scenarios include:
- Referencing non-existent entities
- Ambiguous or incomplete commands
- Constraint violations
- Invalid state transitions
- Duplicate operations

## Running Evals

### Option 1: Manual Inspection

Send each `user_message` to the kernel and compare output primitives against `expected_*` arrays.

### Option 2: Automated Test Harness

```python
import json
from pathlib import Path

def load_scenario(name: str) -> dict:
    path = Path(__file__).parent / f"{name}.json"
    return json.loads(path.read_text())

def run_eval(scenario: dict):
    for turn in scenario["turns"]:
        # Send user_message to L2/L3
        primitives = kernel.process(turn["user_message"])

        # Compare against expected
        assert_primitives_match(
            primitives,
            turn.get("expected_schemas", []) +
            turn.get("expected_entities", []) +
            turn.get("expected_blocks", []) +
            turn.get("expected_meta", []) +
            turn.get("expected_styles", [])
        )
```

## Design Notes

### No Grid Primitives

Grid primitives (`grid.create`, `grid.query`) were deferred. Chessboard and Football Squares use `Record<string, T>` with positional keys:

- **Chessboard**: `squares.e4`, `squares.a1` (algebraic notation)
- **Football Squares**: `squares.sq_0_0` through `squares.sq_9_9` (row_col)

### Entity Paths

Child entities are addressed via paths: `poker_league/players/player_mike`

### Soft Deletes

`entity.update` with `child_key: null` marks child as removed (`_removed: true`).

### Fractional Indexing

`_pos` values use fractional indexing for ordering. Inserting between 1.0 and 2.0 → use 1.5.

## Adding New Scenarios

1. Create `NN_scenario_name.json`
2. Define schemas with TypeScript interfaces
3. Build out turns with user messages and expected primitives
4. Add final state assertions for validation
5. Update this README
