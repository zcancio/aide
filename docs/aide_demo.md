# AIde — A Living Object System

*2026-03-02T21:45:00Z by Showboat 0.6.1*
<!-- showboat-id: 7793b8ab-1139-4019-b4d4-dcefe43afcdc -->

AIde is a living system that keeps what you're running coherent over time. You describe what you're coordinating — a graduation party, a poker league, a group trip — and AIde brings it to life as a shareable page that stays current through natural language conversation.

**Tagline:** "For what you're living."

This demo explores AIde's core architecture and capabilities.

## Architecture Overview

AIde is a full-stack application with a Python backend (FastAPI), a JSONL-based event sourcing system, and a deterministic kernel that processes state mutations.

```bash
echo '=== Codebase Structure ===' && find . -maxdepth 2 -type d \( -name '.git' -o -name '.venv' -o -name '__pycache__' -o -name 'node_modules' -o -name '.ruff_cache' -o -name '.pytest_cache' -o -name '.obsidian' -o -name '.claude' -o -name '.github' \) -prune -o -type d -print | head -30
```

```output
=== Codebase Structure ===
.
./evals
./evals/tests
./evals/results
./evals/scripts
./evals/kernel
./docker
./frontend
./frontend/dist
./frontend/display
./frontend/src
./backend
./backend/middleware
./backend/repos
./backend/tests
./backend/utils
./backend/models
./backend/prompts
./backend/routes
./backend/services
./docs
./docs/program_management
./docs/archive
./docs/eng_design
./docs/prds
./docs/build_logs
./docs/refactors
./docs/infrastructure
./docs/strategy
./cli
```

## The Kernel — Heart of AIde

The kernel is a pure, deterministic state machine. It validates primitives and applies them to produce new state. The kernel never does I/O — it's a pure function.

```bash
source .venv/bin/activate && python3 -c "
from engine.kernel.types import PRIMITIVE_TYPES

# Server-side primitives (collections, views, blocks, fields, grid are client-side only)
server_side = [p for p in PRIMITIVE_TYPES if not any(x in p for x in ['collection', 'view', 'block', 'field', 'grid'])]

print('=== 10 Server-Side Primitive Types ===')
print()

categories = {'Entity': [], 'Relationship': [], 'Style': [], 'Meta': []}

for p in sorted(server_side):
    cat = p.split('.')[0].title()
    if cat in categories:
        categories[cat].append(p)

for cat, primitives in categories.items():
    if primitives:
        print(f'{cat}:')
        for p in primitives:
            print(f'  - {p}')
        print()
"
```

```output
=== 10 Server-Side Primitive Types ===

Entity:
  - entity.create
  - entity.remove
  - entity.update

Relationship:
  - relationship.constrain
  - relationship.set

Style:
  - style.set
  - style.set_entity

Meta:
  - meta.annotate
  - meta.constrain
  - meta.update

```

## The Reducer — Pure State Transitions

The reducer takes an event (primitive + metadata) and a current state, and produces a new state. It's a pure function — no side effects, fully deterministic.

Let's see the reducer in action by creating a graduation party planning aide:

```bash
source .venv/bin/activate && python3 << 'ENDSCRIPT'
from engine.kernel.reducer_v2 import empty_snapshot, reduce

print("=== Creating a Graduation Party Aide ===\n")

# Start with an empty snapshot
snap = empty_snapshot()
entity_count = len(snap["entities"])
print("Initial state: {} entities".format(entity_count))

# Step 1: Set the page title via meta.update
result = reduce(snap, {
    "t": "meta.update",
    "p": {"title": "Emmas Graduation Party", "identity": "Planning celebration for June 15th"}
})
snap = result.snapshot
print("1. Set title: {}".format(snap["meta"]["title"]))

# Step 2: Create a table container for guests
result = reduce(snap, {
    "t": "entity.create",
    "id": "guests",
    "display": "table",
    "p": {"label": "Guest List"}
})
snap = result.snapshot
print("2. Created guests table")

# Step 3: Add individual guests as children
guests_data = [
    {"id": "guest_linda", "name": "Aunt Linda", "rsvp": "yes", "bringing": "Potato salad"},
    {"id": "guest_steve", "name": "Uncle Steve", "rsvp": "yes", "bringing": "Cooler of drinks"},
    {"id": "guest_rose",  "name": "Grandma Rose", "rsvp": "yes", "bringing": "The cake"},
    {"id": "guest_jake",  "name": "Cousin Jake", "rsvp": "pending", "bringing": None},
]

for g in guests_data:
    result = reduce(snap, {
        "t": "entity.create",
        "id": g["id"],
        "parent": "guests",
        "p": {"name": g["name"], "rsvp": g["rsvp"], "bringing": g.get("bringing")}
    })
    snap = result.snapshot

print("3. Added {} guests".format(len(guests_data)))

# Step 4: Create a food items section
result = reduce(snap, {
    "t": "entity.create",
    "id": "food",
    "display": "checklist",
    "p": {"label": "Food & Drinks"}
})
snap = result.snapshot

food_items = ["Cake", "Chips", "Drinks", "Veggie Tray"]
for i, item in enumerate(food_items):
    result = reduce(snap, {
        "t": "entity.create",
        "id": "food_item_{}".format(i),
        "parent": "food",
        "p": {"label": item, "checked": False}
    })
    snap = result.snapshot

print("4. Created food checklist with {} items".format(len(food_items)))

# Step 5: Show the final state
print("\n=== Final Entity Tree ===")

# Find root entities (parent == "root")
root_entities = [e for e in snap["entities"].values() if e["parent"] == "root"]
for entity in root_entities:
    children = entity.get("_children", [])
    label = entity["props"].get("label", entity["id"])
    print("\n{}: {}".format(entity["display"], label))
    for child_id in children:
        child = snap["entities"][child_id]
        props = child["props"]
        if "name" in props:
            status = "[yes]" if props.get("rsvp") == "yes" else "[?]"
            bringing = props.get("bringing") or "---"
            print("  {} {} -- {}".format(status, props["name"], bringing))
        elif "label" in props:
            checked = "[x]" if props.get("checked") else "[ ]"
            print("  {} {}".format(checked, props["label"]))

print("\n=== Stats ===")
print("Total entities: {}".format(len(snap["entities"])))
print("Sequence: {}".format(snap["_sequence"]))
ENDSCRIPT
```

```output
=== Creating a Graduation Party Aide ===

Initial state: 0 entities
1. Set title: Emmas Graduation Party
2. Created guests table
3. Added 4 guests
4. Created food checklist with 4 items

=== Final Entity Tree ===

table: Guest List
  [yes] Aunt Linda -- Potato salad
  [yes] Uncle Steve -- Cooler of drinks
  [yes] Grandma Rose -- The cake
  [?] Cousin Jake -- ---

checklist: Food & Drinks
  [ ] Cake
  [ ] Chips
  [ ] Drinks
  [ ] Veggie Tray

=== Stats ===
Total entities: 10
Sequence: 11
```

## Intelligence Tiers — L3, L4

AIde routes user messages to the right model tier for efficiency:

- **L3 (Sonnet)**: Mutations and schema synthesis like "add Aunt Linda" or "plan my graduation party" — under 4s
- **L4 (Opus)**: Complex queries requiring reasoning like "who hasnt RSVPed?" — under 5s

Most interactions hit L3 for fast, capable responses.

```bash
source .venv/bin/activate && python3 << 'ENDSCRIPT'
# Demonstrate the classification logic from the actual classifier
import re

print("=== Intent Classification Examples ===\n")

messages = [
    "Linda RSVPed yes",
    "Add chips to the food list",
    "How many guests are coming?",
    "Add a section for decorations",
    "Jake is bringing the drinks",
    "When is the party?",
]

# Patterns from classifier.py
question_keywords = ["?", "how many", "who", "when", "where", "what is", "is there"]
structural_keywords = ["add a section", "new section", "create a new", "add table", "track"]
mutation_keywords = ["add", "update", "change", "set", "remove", "delete", "rsvp", "mark", "claim"]

print("Message -> Tier + Reason")
print("-" * 55)
for msg in messages:
    msg_lower = msg.lower()
    
    has_question = any(q in msg_lower for q in question_keywords)
    has_structural = any(k in msg_lower for k in structural_keywords)
    has_mutation = any(k in msg_lower for k in mutation_keywords)
    
    if has_question and not has_mutation:
        tier, reason = "L4", "pure_query"
    elif has_structural:
        tier, reason = "L3", "structural_change"
    else:
        tier, reason = "L3", "simple_update"
    
    print("{} | {} | {}".format(tier, reason[:15].ljust(15), msg))
ENDSCRIPT
```

```output
=== Intent Classification Examples ===

Message -> Tier + Reason
-------------------------------------------------------
L3 | simple_update   | Linda RSVPed yes
L3 | simple_update   | Add chips to the food list
L4 | pure_query      | How many guests are coming?
L3 | structural_chan | Add a section for decorations
L3 | simple_update   | Jake is bringing the drinks
L4 | pure_query      | When is the party?
```

## Streaming Pipeline — Real-Time Updates

The LLM emits JSONL (one JSON line per operation). The server parses each line as it arrives, validates it, applies it to the reducer, and pushes deltas to the client via WebSocket.

The page builds itself in real-time — title first, sections next, items last.

```bash
source .venv/bin/activate && python3 << 'ENDSCRIPT'
import json

print("=== JSONL Event Stream Example ===\n")
print("When you say: \"Plan a graduation party for Emma\"")
print("The LLM emits events like:\n")

events = [
    {"t": "meta.update", "p": {"title": "Emmas Graduation Party"}},
    {"t": "entity.create", "id": "header", "display": "heading", "p": {"text": "June 15th, 2024"}},
    {"t": "entity.create", "id": "guests", "display": "table", "p": {"label": "Guest List"}},
    {"t": "entity.create", "id": "g1", "parent": "guests", "p": {"name": "Family", "count": 0}},
    {"t": "entity.create", "id": "food", "display": "checklist", "p": {"label": "Food"}},
    {"t": "voice", "p": {"text": "Party page created."}},
]

for event in events:
    print(json.dumps(event))
ENDSCRIPT
```

```output
=== JSONL Event Stream Example ===

When you say: "Plan a graduation party for Emma"
The LLM emits events like:

{"t": "meta.update", "p": {"title": "Emmas Graduation Party"}}
{"t": "entity.create", "id": "header", "display": "heading", "p": {"text": "June 15th, 2024"}}
{"t": "entity.create", "id": "guests", "display": "table", "p": {"label": "Guest List"}}
{"t": "entity.create", "id": "g1", "parent": "guests", "p": {"name": "Family", "count": 0}}
{"t": "entity.create", "id": "food", "display": "checklist", "p": {"label": "Food"}}
{"t": "voice", "p": {"text": "Party page created."}}
```

## Backend Architecture — Layered Separation

The backend follows strict layered architecture:

- **routes/** — HTTP handlers, thin, no SQL
- **services/** — Business logic, external integrations
- **repos/** — Data access, all SQL lives here

```bash
echo "=== Backend Structure ===" && find backend -type f -name "*.py" | grep -v __pycache__ | grep -v tests | sort | head -35
```

```output
=== Backend Structure ===
backend/__init__.py
backend/auth.py
backend/config.py
backend/db.py
backend/main.py
backend/middleware/__init__.py
backend/middleware/rate_limit.py
backend/models/__init__.py
backend/models/aide.py
backend/models/api_token.py
backend/models/auth.py
backend/models/cli_auth.py
backend/models/conversation.py
backend/models/flight_recorder.py
backend/models/signal_mapping.py
backend/models/telemetry.py
backend/models/user.py
backend/repos/__init__.py
backend/repos/aide_repo.py
backend/repos/api_token_repo.py
backend/repos/cli_auth_repo.py
backend/repos/conversation_repo.py
backend/repos/magic_link_repo.py
backend/repos/signal_mapping_repo.py
backend/repos/telemetry_repo.py
backend/repos/user_repo.py
backend/routes/__init__.py
backend/routes/aides.py
backend/routes/api_tokens.py
backend/routes/auth_routes.py
backend/routes/cli_auth.py
backend/routes/conversations.py
backend/routes/engine.py
backend/routes/flight_recorder.py
backend/routes/pages.py
```

## Data Access — PostgreSQL with Row-Level Security

AIde uses Neon Postgres with RLS for multi-tenant isolation:

- **user_conn(user_id)**: Sets app.current_user_id for RLS filtering
- **system_conn()**: Background tasks only, bypasses RLS
- All SQL uses parameterized queries (, ) — never f-strings

```bash
echo "=== Sample Repo Pattern (aide_repo.py) ===" && head -60 backend/repos/aide_repo.py | tail -35
```

```output
=== Sample Repo Pattern (aide_repo.py) ===
        updated_at=row["updated_at"],
    )


class AideRepo:
    """All aide-related database operations."""

    async def create(self, user_id: UUID, req: CreateAideRequest) -> Aide:
        """
        Create a new aide for a user.

        Args:
            user_id: User UUID
            req: CreateAideRequest with aide details

        Returns:
            Newly created Aide
        """
        aide_id = uuid4()
        now = datetime.now(UTC)

        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO aides (id, user_id, title, r2_prefix, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $5)
                RETURNING *
                """,
                aide_id,
                user_id,
                req.title,
                f"aides/{aide_id}",
                now,
            )
            return _row_to_aide(row)
```

## Test Suite

AIde maintains comprehensive tests for the kernel and backend:

```bash
source .venv/bin/activate && python -m pytest engine/kernel/tests/ -v --tb=no -q 2>&1 | head -30
```

```output
============================= test session starts ==============================
platform darwin -- Python 3.12.12, pytest-8.3.4, pluggy-1.6.0
rootdir: /Users/zacharycancio/Projects/aide
configfile: pyproject.toml
plugins: anyio-4.12.1, asyncio-0.25.2
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=session
collected 148 items

engine/kernel/tests/test_mock_llm.py ......                              [  4%]
engine/kernel/tests/test_primitives_validation.py ..............         [ 13%]
engine/kernel/tests/tests_reducer/test_reducer_v2_entity.py ............ [ 21%]
.............................                                            [ 41%]
engine/kernel/tests/tests_reducer/test_reducer_v2_golden.py ............ [ 49%]
.......................                                                  [ 64%]
engine/kernel/tests/tests_reducer/test_reducer_v2_relationship.py ...... [ 68%]
............                                                             [ 77%]
engine/kernel/tests/tests_reducer/test_reducer_v2_style_meta_signals.py . [ 77%]
.................................                                        [100%]

============================= 148 passed in 1.14s ==============================
```

## Frontend

The frontend renders entities based on their display hint. Display types (table, checklist, heading, etc.) are handled client-side in React components.

```bash
echo "=== Frontend Structure ===" && find frontend -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.html" -o -name "*.css" \) | grep -v node_modules | sort
```

```output
=== Frontend Structure ===
frontend/cli-auth.html
frontend/display/__tests__/snapshots/empty-document.html
frontend/display/__tests__/snapshots/empty.html
frontend/display/__tests__/snapshots/nested-document.html
frontend/display/__tests__/snapshots/nested.html
frontend/display/__tests__/snapshots/poker-league-document.html
frontend/display/__tests__/snapshots/poker-league.html
frontend/display/__tests__/snapshots/simple-text-document.html
frontend/display/__tests__/snapshots/simple-text.html
frontend/display/tokens.css
frontend/dist/assets/spa-93GJXdpo.css
frontend/dist/spa.html
frontend/flight-recorder.html
frontend/spa.html
frontend/src/styles/chat.css
frontend/src/styles/dashboard.css
frontend/src/styles/editor.css
frontend/src/styles/theme.css
```

## AI Voice — Infrastructure, Not Personality

AIde maintains a distinctive non-conversational voice:

- No first person ("I updated...")
- No encouragement ("Great!", "Nice!")  
- No emojis — ever
- State over action: "Budget: $1,350" not "I updated the budget"
- Silence is valid — not every action needs a response

## Summary

AIde is a living object system with:

- **10 server-side primitive types** for structured mutations
- **Pure reducer** for deterministic state transitions  
- **JSONL streaming** for real-time page building
- **Two speeds**: AI (1-5s) and spreadsheet (<200ms direct edits)
- **L3/L4 routing** for efficient model selection
- **RLS-backed multi-tenancy** for secure isolation

**Tagline:** For what you're living.
