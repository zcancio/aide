---
name: aide-builder
description: Build and maintain AIde living pages from natural language. Use when someone describes something they're running — a league, trip, budget, event, renovation, household — and wants a self-contained HTML page with embedded structured state. Also use when updating an existing aide.
---

# AIde Builder

## Setup

Fetch the kernel. Use whichever method is available:

- **If you have web_fetch:** `web_fetch("https://toaide.com/engine/v1/engine.min.js")`
- **If you have bash/curl:** `curl -s https://toaide.com/engine/v1/engine.min.js -o engine.js`
- **If the engine is already in project files or uploads:** use it directly

Save it as `engine.js` in your working directory. If none of these methods work, you can still build aides — the primitive catalog below is complete enough to compile events and construct the HTML output directly.

## Your Job

The user says something like "I run a poker league, 8 guys, every other Thursday at rotating houses." Your job:

1. **Design the state** — what collections, fields, entities, views, and blocks represent this thing
2. **Emit primitive events** — the structured mutations that build or update the state
3. **Run the kernel** — pass events through `reduce()`, then `render()` to get HTML
4. **Return the HTML** — a complete, self-contained aide page

You do NOT simulate the reducer or renderer. You call them.

## Two Modes

### Create Mode

User describes something new. You design everything from scratch.

```javascript
const { emptyState, reduce, render } = require("./engine")

// 1. Start empty
let snapshot = emptyState()

// 2. Apply your events
const events = [ /* your compiled events */ ]
for (const evt of events) {
  const result = reduce(snapshot, evt)
  if (!result.applied) { console.error(result.error); continue }
  snapshot = result.snapshot
}

// 3. Render
const blueprint = {
  identity: "Poker league. 8 players, biweekly Thursday.",
  voice: "No first person. State reflections only.",
  prompt: "..." // system prompt for any LLM to maintain this aide
}
const html = render(snapshot, blueprint, events)
```

### Reducer Mode

User has an existing aide (HTML with embedded JSON). They say something changed.

```javascript
const { parseAideHtml, reduce, render } = require("./engine")

// 1. Parse existing aide
const { snapshot: oldSnapshot, blueprint, events: oldEvents } = parseAideHtml(existingHtml)

// 2. Compile new events from user's message
const newEvents = [ /* your compiled events */ ]

// 3. Apply
let snapshot = oldSnapshot
const allEvents = [...oldEvents]
for (const evt of newEvents) {
  const result = reduce(snapshot, evt)
  if (!result.applied) { console.error(result.error); continue }
  snapshot = result.snapshot
  allEvents.push(evt)
}

// 4. Re-render
const html = render(snapshot, blueprint, allEvents)
```

## Event Format

Every event you emit must have this shape:

```json
{
  "id": "evt_20260215_001",
  "sequence": 1,
  "timestamp": "2026-02-15T00:00:00Z",
  "actor": "user",
  "source": "claude",
  "type": "collection.create",
  "payload": { },
  "intent": "setup",
  "message": "I run a poker league..."
}
```

Sequence numbers are monotonically increasing per aide. In create mode, start at 1. In reducer mode, continue from the last event's sequence + 1.

## Primitives

These are the events you can emit. The kernel validates and applies them.

### Entity

**entity.create** — Add an entity to a collection.
```json
{ "collection": "roster", "id": "player_mike", "fields": { "name": "Mike", "status": "active" } }
```
ID is optional (auto-generated if omitted). Fields must match collection schema. Required fields must be present.

**entity.update** — Update fields on an entity.
```json
{ "ref": "roster/player_mike", "fields": { "status": "out" } }
```
Only provided fields change. Unmentioned fields stay.

Filter variant updates multiple entities:
```json
{ "filter": { "collection": "roster", "where": { "status": "active" } }, "fields": { "notified": true } }
```

**entity.remove** — Soft-delete an entity.
```json
{ "ref": "roster/player_mike" }
```

### Collection

**collection.create** — Define a new collection with a schema.
```json
{ "id": "roster", "name": "Roster", "schema": { "name": "string", "status": "string", "snack_duty": "bool" } }
```

Field types: `string`, `int`, `float`, `bool`, `date`, `datetime`, `{"enum": ["a","b"]}`, `{"list": "string"}`. Append `?` for nullable: `"string?"`.

**collection.update** — Rename or change settings.
```json
{ "id": "roster", "name": "Players" }
```

**collection.remove** — Remove collection and all its entities.
```json
{ "id": "roster" }
```

### Field

**field.add** — Add a field to an existing collection. Backfills all entities.
```json
{ "collection": "roster", "name": "wins", "type": "int", "default": 0 }
```
Required fields (no `?`) must have a default if entities already exist.

**field.update** — Change a field's type or rename it.
```json
{ "collection": "roster", "name": "status", "type": {"enum": ["active","out","sub"]} }
```
Rename: `{ "collection": "roster", "name": "old_name", "rename": "new_name" }`

**field.remove** — Remove a field from schema and all entities.
```json
{ "collection": "roster", "name": "wins" }
```

### Relationship

**relationship.set** — Link two entities.
```json
{ "from": "roster/player_dave", "to": "schedule/game_feb27", "type": "hosting", "cardinality": "many_to_one" }
```
Cardinality options: `many_to_one` (default), `one_to_one`, `many_to_many`. Cardinality is set once per relationship type — subsequent events use the stored cardinality.

Many-to-one auto-removes old links from the source. One-to-one auto-removes from both sides.

**relationship.constrain** — Add a constraint on relationships.
```json
{ "id": "no_linda_steve", "rule": "exclude_pair", "entities": ["guests/linda","guests/steve"], "relationship_type": "seated_at", "message": "Keep apart" }
```

### Block

**block.set** — Create or update a block in the page tree.
```json
{ "id": "block_title", "type": "heading", "parent": "block_root", "position": 0, "props": { "level": 1, "content": "Poker League" } }
```
If the block ID exists, it's an update (merges props). If not, it's a create (type required).

Block types: `heading`, `text`, `metric`, `divider`, `callout`, `image`, `collection_view`, `column_list`, `column`.

**block.remove** — Remove a block and all its children.
```json
{ "id": "block_old_section" }
```

**block.reorder** — Reorder children of a parent block.
```json
{ "parent": "block_root", "children": ["block_title", "block_metrics", "block_roster"] }
```

### View

**view.create** — Define how a collection renders.
```json
{ "id": "roster_table", "type": "table", "source": "roster", "config": { "show_fields": ["name", "status"], "sort_by": "name" } }
```
Types: `table`, `list`. Config options: `show_fields`, `hide_fields`, `sort_by`, `sort_order`, `filter`, `group_by`.

Connect a view to the page with a `collection_view` block: `{ "type": "collection_view", "props": { "view": "roster_table", "source": "roster" } }`

**view.update** / **view.remove** — Modify or delete views.

### Style

**style.set** — Set global style tokens.
```json
{ "primary_color": "#2D2D2A", "density": "compact" }
```

**style.set_entity** — Style override on a specific entity.
```json
{ "ref": "roster/player_mike", "styles": { "highlight": true } }
```

### Meta

**meta.update** — Set aide metadata.
```json
{ "title": "Poker League — Spring 2026" }
```

**meta.annotate** — Append a note to the aide's annotation log.
```json
{ "note": "Mike rejoined the league.", "pinned": false }
```

**meta.constrain** — Add a structural constraint.
```json
{ "id": "max_players", "rule": "collection_max_entities", "collection": "roster", "value": 10, "message": "Max 10 players", "strict": true }
```

## Event Ordering

In create mode, events must be ordered so dependencies exist before references:

1. `meta.update` — title, identity
2. `collection.create` — define schemas
3. `entity.create` — populate collections
4. `field.add` / `field.update` — schema evolution (if needed)
5. `relationship.set` — link entities
6. `view.create` — define how collections render
7. `block.set` — build the page tree
8. `style.set` — visual tokens
9. `meta.annotate` — notes
10. `meta.constrain` — constraints (if needed)

## Voice

AIde pages speak in state reflections, not conversation.

- **No first person.** Never "I updated..." — state what changed: "Budget: $1,350."
- **No encouragement.** No "Great!", "Nice!", "Let's do this!"
- **No emojis.** Never.
- **No self-narration.** No "I'm going to...", "Let me..."
- **Mutations are final.** "Next game: Mike's on snacks." Not "I've updated Mike's snack duty."
- **Silence is valid.** Not every change needs narration.

Voice applies to: block text content, annotations, blueprint prompt. It does NOT apply to field values (those are raw data).

## Blueprint

Every aide embeds a blueprint — the DNA for any LLM to maintain it:

```json
{
  "identity": "Poker league. 8 players, biweekly Thursday at rotating houses.",
  "voice": "No first person. No emojis. No encouragement. State reflections only.",
  "prompt": "You maintain a living page for a poker league. The current state is embedded in the HTML as JSON. When the user tells you something changed, compile their message into primitive events and apply them through the reducer. Never simulate the reducer — call it."
}
```

The identity is a one-line description. The voice is the constraint set. The prompt is what another LLM would need to continue maintaining this aide.

## Design Typography

- H1/H2: Playfair Display (serif), 700 weight
- H3: Instrument Sans, 600 weight
- Body/labels: DM Sans, 400 weight
- Metrics: DM Sans, 500 weight
- Colors: warm grayscale (#2D2D2A primary, #6B6963 secondary, #A8A5A0 tertiary) + sage accent (#7C8C6E)
- Background: warm ivory (#F7F5F2)
- Max width: 720px, centered
- "Made with aide" footer (free tier)
