# AIde — System Architecture (v3)

**Status:** Living document
**Last Updated:** February 2026
**Audience:** Anyone who wants to understand how AIde works under the hood

---

## What AIde Is

An aide is a living object. It's not a web page you build once and publish. It's a persistent, conversational state machine: a visual artifact whose state is updated through natural language from anywhere — web chat, Signal, a screenshot, eventually any channel. The object maintains itself through conversation. The published page is its body.

**v3 introduces:** TypeScript interfaces for schema definitions, multi-channel rendering (HTML + text), and tree-sitter parsing for validation in both Python and JavaScript.

Three roles make this work:

**The Human** is the sensor network. They gather signal from the real world — group chats, emails, conversations, photos, shouts across the room — and relay it to the aide through whatever ear is available.

**The AI** is the intent compiler. It understands what the human said, compiles natural language into structured state transitions, and maintains context across the conversation history.

**The Page** is the body. A live window into the aide's current state, published at a URL, always up to date. The thing you share.

The critical insight: **most interactions with an aide are state transitions, not creative acts.** "Mike's out this week." "We need olive oil." "Contractor pushed to March." These are structured, deterministic operations. You don't need a frontier model to handle them.

---

## The Architecture in One Diagram

```
 +-------------------------------------------------------------+
 |                        User Input                           |
 |    "Mike's out this week. Dave's subbing."                  |
 |    (via web chat, Signal, screenshot, any ear)              |
 +----------------------------+--------------------------------+
                              |
                              v
 +-------------------------------------------------------------+
 |                    L2 -- Intent Compiler                    |
 |                     (Haiku-class LLM)                       |
 |                                                             |
 |  Reads: user message + current snapshot state + schema      |
 |  Outputs: one or more declarative primitives                |
 |  Or: escalates to L3 if it can't compile                    |
 |                                                             |
 |  +-------------------------------------------------------+  |
 |  | entity.update {                                       |  |
 |  |   ref: "roster/player_mike"                           |  |
 |  |   fields: { status: "out", substitute: "Dave" }       |  |
 |  | }                                                     |  |
 |  | intent: "substitution"                                |  |
 |  +-------------------------------------------------------+  |
 +----------------------------+--------------------------------+
                              |
                              v
 +-------------------------------------------------------------+
 |                     Append-Only Event Log                   |
 |              (embedded in the HTML file)                    |
 |                                                             |
 |  evt_001: collection.create { id: "roster", ... }           |
 |  evt_002: entity.create { collection: "roster", ... }       |
 |  evt_003: entity.update { ref: "player_mike", status: out } |
 |  ...                                                        |
 +----------------------------+--------------------------------+
                              |
                              v
 +-------------------------------------------------------------+
 |                         Reducer                             |
 |                                                             |
 |  (snapshot, event) -> ReduceResult                          |
 |  Applies events incrementally to produce new snapshot       |
 |  Enforces cardinality, constraints, capacity limits         |
 |  Deterministic: same events -> same snapshot, always        |
 +----------------------------+--------------------------------+
                              |
                              v
 +-------------------------------------------------------------+
 |                        Renderer                             |
 |                                                             |
 |  (snapshot, blueprint, events?) -> full HTML string         |
 |  Deterministic. No AI. A function.                          |
 |  Block tree determines document structure.                  |
 |  Views determine how collections render.                    |
 |  Style tokens -> CSS custom properties.                     |
 +----------------------------+--------------------------------+
                              |
                              v
 +-------------------------------------------------------------+
 |            Assembly: load / apply / save / publish          |
 |                                                             |
 |  Coordinates reducer + renderer + R2 storage                |
 |  Parses and reassembles the HTML file on every update       |
 |  Per-aide locking for concurrency                           |
 +----------------------------+--------------------------------+
                              |
                              v
 +-------------------------------------------------------------+
 |                 The HTML File = The Aide                    |
 |                  https://toaide.com/p/abc123                |
 |                                                             |
 |  One file. Self-contained. Downloadable. Forkable.          |
 |  Contains: rendered <body> + snapshot JSON + event log JSON |
 |  + blueprint (prompt, voice rules, identity)                |
 |  No database. No API. No JavaScript required to view.       |
 +-------------------------------------------------------------+
```

---

## Ears — How Input Arrives

The architecture described above doesn't care where messages come from. An ear is a channel adapter that normalizes input into a common shape: user identity, aide identity, message content (text, image, or both). The brain never knows which ear a message came from.

### v1 Ears

**Web chat** — browser-based chat at toaide.com. Text and image input. Universal fallback.

**Signal** — via signal-cli-rest-api running as a container on Railway. Dedicated phone number. Users text it directly or add it to a Signal group chat. The first channel ear. The dogfood ear.

**Image input** — available through both web chat and Signal. Screenshots of conversations, photos of receipts, handwritten notes, scoreboards. The human integration layer. When the aide receives an image, the message routes to a vision-capable model (Sonnet) for the L2 step instead of Haiku.

### Adding new ears

Each ear is a thin adapter: receive platform-specific input → normalize → POST to the brain's API → receive response → send back through platform. Adding Telegram, WhatsApp, a share sheet, or voice is writing a new adapter. The brain, reducer, renderer, and HTML file don't change.

---

## Starting in the Middle

Traditional tools require a creation step: pick a template, define a schema, name the thing. AIde doesn't. You just start talking.

"We need milk, eggs, and that sourdough from Whole Foods."

The first message hits L3 (the slow path), which synthesizes the initial schema: a collection called "grocery_list" with fields `{name, store, checked}`. The aide comes alive from that first utterance. No setup, no blank page.

Over time, the schema grows. By the tenth message, L3 has added `{category, requested_by}` fields because the conversation revealed those patterns. The aide reshapes as it learns more about what it's maintaining.

This means L3 handles more calls early in an aide's life (schema synthesis, structural decisions) and fewer over time as L2 takes over for routine updates. The cost curve is front-loaded.

---

## Layer 1: State — The Kernel

At the core of every aide is structured state. Not HTML. Not a database. A typed JSON document that the AI reads, the reducer maintains, and the renderer turns into a page.

### What State Looks Like

The snapshot state is embedded in the HTML file's `<script type="application/aide+json">` tag:

```
AideState {
  version: 3

  meta: {
    title: "Poker League"
    identity: "Poker league. 8 players, biweekly Thursday, rotating hosts."
  }

  schemas: {
    Player: {
      interface: "interface Player { name: string; status: 'active' | 'out' | 'sub'; wins: number; }"
      render_html: "<div class=\"player {{status}}\">{{name}} ({{wins}}W)</div>"
      render_text: "{{name}} — {{status}} ({{wins}}W)"
      styles: ".player { padding: 8px; } .player.out { opacity: 0.5; }"
    }
    Game: {
      interface: "interface Game { date: string; host: string; winner?: string; }"
      render_html: "<div class=\"game\">{{date}} @ {{host}}{{#winner}} → {{winner}}{{/winner}}</div>"
      render_text: "{{date}} @ {{host}}{{#winner}} → {{winner}}{{/winner}}"
    }
    League: {
      interface: "interface League { name: string; season: string; players: Record<string, Player>; games: Record<string, Game>; }"
      render_html: "<div class=\"league\"><h1>{{name}}</h1><p>{{season}}</p>{{>players}}{{>games}}</div>"
      render_text: "{{name}} — {{season}}\n\nPlayers:\n{{>players}}\n\nGames:\n{{>games}}"
    }
  }

  entities: {
    poker_league: {
      _schema: "League"
      name: "Poker League"
      season: "Spring 2026"
      players: {
        player_mike: { name: "Mike", status: "active", wins: 3, _pos: 1.0 }
        player_dave: { name: "Dave", status: "active", wins: 2, _pos: 2.0 }
      }
      games: {
        game_feb27: { date: "2026-02-27", host: "Dave", _pos: 1.0 }
      }
    }
  }

  blocks: {
    block_root: {
      children: ["block_league"]
    }
    block_league: { type: "entity_view", props: { source: "poker_league" } }
  }

  styles: {
    primary_color: "#2d3748"
    font_family: "Inter"
    density: "comfortable"
  }

  constraints: []
  annotations: []
}
```

**v3 structure:** Schemas define entity types using TypeScript interfaces. Each schema includes `render_html` and `render_text` templates for multi-channel output. Entities reference their schema via `_schema` and can contain nested children in `Record<string, T>` fields. Full schema details are in `unified_entity_model.md` and `aide_primitive_schemas_spec.md`.

### The Block Tree

The page structure is a tree of blocks. Blocks flow top-to-bottom and can contain children. Layout is achieved through nesting — column containers, not pixel coordinates.

Block types include headings, text, images, dividers, collection views (live data from a collection), metrics (single values), callouts, embeds, and layout containers. Novel block types can be synthesized by L3.

### Collections, Entities, Relationships

**Collections** are named groups of entities with a shared schema: "roster", "schedule", "grocery_list", "budget_items". Each collection defines what fields its entities can have.

**Entities** are the atoms of state: a player in a roster, a game on a schedule, an item on a grocery list. They live in exactly one collection and have fields defined by the collection's schema.

**Relationships** are typed links between entities, within or across collections. "player_dave is hosting game_feb27." Every relationship type has a cardinality — `one_to_one`, `many_to_one`, or `many_to_many` — and the reducer enforces it automatically.

**Constraints** are persistent rules. "Host rotation cycles through the roster." The system validates constraints on every state change and warns on violations.

### Views

Views define how a collection renders inside a collection_view block. A view says: show these fields, hide those, sort by this, group by that, color cells based on these conditions.

Multiple views of the same collection can coexist. The organizer sees payment status. The group sees the schedule. Same data, different presentations.

View types include grid, list, table, dashboard, calendar, and kanban. Novel view types are synthesized by L3 and persisted as ViewPresets.

### Styles

Style tokens control visual appearance: colors, fonts, spacing, density. They're separated from structure — changing the style never changes the data or the block tree.

---

## Layer 2: Events — The Log

Every state change is an event in an append-only log, embedded in the HTML file's `<script type="application/aide-events+json">` tag. Events are the source of truth. The snapshot state is derived — it can always be reconstructed by replaying the log.

### Event Structure

```
Event {
  id: "evt_20260227_003"
  timestamp: "2026-02-27T14:30:00Z"
  actor: "organizer"
  source: "signal"           // which ear this came from
  sequence: 3

  // Declarative payload (what the reducer reads)
  type: "entity.update"
  payload: {
    ref: "roster/player_mike"
    fields: { status: "out" }
  }

  // Semantic metadata (what humans read)
  intent: "substitution"
  message: "Mike's out this week"
  message_id: "msg_abc123"
}
```

The event carries two layers: the **declarative payload** (what changed) and the **semantic metadata** (why it changed, who said it, which ear it came through). The reducer only reads the payload. The event log preserves the full story.

### Why Event Sourcing

Event sourcing means user says something → AI emits an event → event is appended to the log → state is derived by replaying all events.

What this gives you:

**Time travel.** Reconstruct the state at any point. "What did the schedule look like before we moved the game?"

**Undo for free.** Replay all events except the last one.

**Audit trail.** Every event is traceable to a user message and a source ear. "Who said Mike was out?" Check the event log.

**Multi-device consistency.** Any client can reconstruct the full state from the event log.

**Multi-ear coherence.** Events from web chat and Signal interleave in the same log. The reducer doesn't care where they came from.

---

## Layer 3: The AI — Intent Compiler

The AI is not the brain. It's the compiler. It translates natural language into structured events. This is the key insight: treating the AI as a translation layer rather than a creative agent.

### L2: The Fast Path (Haiku-class)

L2 handles ~90% of interactions. It reads the user's message alongside the current snapshot state and schema, then emits one or more declarative primitives.

```
Input:  "Mike's out this week. Dave's subbing."
        + snapshot state (mike exists, status is active, dave exists)

Output: entity.update {
          ref: "roster/player_mike"
          fields: { status: "out" }
        }
        entity.update {
          ref: "roster/player_dave"
          fields: { status: "subbing", snack_duty: true }
        }
        intent: "substitution"
```

L2 does entity resolution ("Mike" → `roster/player_mike`), temporal resolution ("this week" → current game), and disambiguation. It emits structured events against the known primitive vocabulary. It does not generate HTML. It does not call tools.

**What L2 sees in its system prompt:**
- The 25 kernel primitives with their schemas
- The current aide's collection schemas and entity names
- The current snapshot state (or a summary if it's large)
- Any active constraints
- Recently synthesized macros

**Cost:** ~$0.001 per call. A tenth of a cent per interaction.

### L3: The Slow Path (Sonnet-class)

L3 handles the ~10% of interactions that L2 can't compile. These are novel requests — things that don't map to existing primitives, require structural changes, or need the aide to form itself from nothing.

**Escalation triggers:**

| Signal | Example | What L3 Does |
|--------|---------|--------------|
| First message (no schema) | "We need milk and eggs" | Synthesize initial collection schema |
| Unknown entity shape | "Track who drove and who carpooled" | Synthesize new collection schema |
| Novel view type | "Show this as a calendar" | Synthesize a ViewPreset |
| Complex conditional | "Rotate hosts automatically" | Synthesize a MacroSpec |
| Structural refactor | "Put the schedule next to the roster" | Plan a block tree restructure |
| Ambiguous intent | "Make this cleaner" | Interpret, plan, decompose into primitives |
| Image input | Screenshot of a WhatsApp conversation | Extract state changes via vision, emit primitives |

L3 never touches state directly. It outputs a **MacroSpec** — a validated sequence of primitives that gets applied through the same event pipeline as everything else.

```
MacroSpec {
  id: "macro_host_rotation"
  name: "Host Rotation"
  trigger: "manual"
  steps: [
    { primitive: "entity.update", args: {
        ref: "schedule/game_feb27", fields: { host: "Dave" }
    }},
    { primitive: "entity.update", args: {
        ref: "roster/player_dave", fields: { snack_duty: true }
    }},
    { primitive: "meta.annotate", args: {
        note: "Host rotation advanced. Dave hosting Feb 27."
    }}
  ]
}
```

Once synthesized, a MacroSpec is persisted. L2 can invoke it by name in future interactions. The system grows its own vocabulary — L3 creates a capability once, and L2 uses it forever after. This means the system gets cheaper over time as common patterns accumulate.

**Cost:** ~$0.02–0.05 per call. A typical aide lifecycle has 3–5 L3 calls (initial schema synthesis + a few novel requests), so ~$0.10–0.25 total for L3.

### The L2→L3 Boundary

L2 tries to compile the utterance against the known primitive set and current schema. If it can't produce a valid primitive — the entity doesn't exist, the field doesn't exist, the operation doesn't map — it returns an escalation signal.

```
Escalation {
  reason: "no_schema"
  user_message: "we need milk, eggs, and sourdough"
  context: "No collections exist. This is a new aide."
}
```

The orchestrator receives the escalation and routes to L3 with the full context.

---

## Layer 4: The Primitives — Declarative Operations

The kernel has primitives across several categories. Every state change goes through one of these. They are declarative — they describe desired state, not actions.

### The Primitive Set (v3)

| # | Category | Primitive | What It Does |
|---|----------|-----------|-------------|
| 1 | Schema | `schema.create` | Declare a new schema with TypeScript interface + templates |
| 2 | Schema | `schema.update` | Update schema interface or templates |
| 3 | Schema | `schema.remove` | Remove a schema (fails if entities reference it) |
| 4 | Entity | `entity.create` | Declare a new entity with `_schema` reference |
| 5 | Entity | `entity.update` | Update entity fields or nested children |
| 6 | Entity | `entity.remove` | Soft-delete an entity and its children |
| 7 | Block | `block.set` | Declare a block's existence, type, and position |
| 8 | Block | `block.remove` | Remove a block from the tree |
| 9 | Block | `block.reorder` | Reorder children within a parent block |
| 10 | Style | `style.set` | Declare global visual tokens |
| 11 | Style | `style.set_entity` | Declare per-entity visual overrides |
| 12 | Meta | `meta.update` | Declare aide-level properties |
| 13 | Meta | `meta.annotate` | Append a note |
| 14 | Meta | `meta.constrain` | Declare aide-level rules |
| 15 | Grid | `grid.create` | Batch-create grid cells using tensor shape |
| 16 | Grid | `grid.query` | Query a grid cell by label |
| 17–20 | *(reserved)* | — | Future primitives (triggers, computed, relationships) |

### Why Declarative

"Seat Linda at table 5" is just `relationship.set { from: linda, to: table_5, type: seated_at }`. If Linda was at table 3, the reducer auto-unlinks her because `seated_at` is `many_to_one`. The reducer enforces cardinality. You never explicitly unlink — you just declare the new state.

"Mike's out" is just `entity.update { ref: player_mike, fields: { status: "out" } }`. No special primitive for substitutions. The semantic meaning — "this was a substitution" — lives in the event's `intent` metadata, not in the primitive type.

### What the Reducer Does

The reducer is a pure function: `(snapshot, event) -> ReduceResult`. It takes the current state and one event, returns the new state plus any warnings or errors. In production, the reducer runs incrementally -- 1-5 events per user message. Full replay (all events from empty state) is used for undo, time travel, and integrity checks.

```python
@dataclass
class ReduceResult:
    snapshot: AideState        # The new state
    applied: bool              # Whether the event was applied
    warnings: list[Warning]    # Constraint violations, type coercions
    error: str | None          # If applied is False, why
```

The reducer handles: field merging, cardinality enforcement (many_to_one auto-unlinks), constraint validation (warn by default, reject only if strict), soft-delete cascades, schema backfill on field.add, bulk updates via filter, and type compatibility checks on field.update. It does not do rendering, AI calls, or side effects. Boring by design.

Events either apply cleanly, apply with warnings, or reject with a structured error code. Partial application is supported -- if event 2 of 5 is rejected, events 1, 3, 4, 5 still apply. The full reducer contract is in `aide_reducer_spec.md`.

---

## Layer 5: Rendering — The HTML File Is the Aide

An aide is a single HTML file. Not a database. Not an API endpoint. An HTML file that contains its rendered presentation, its structured state, its event history, and its blueprint. This is the core promise: a URL, not an app.

### The HTML File Structure

```html
<!DOCTYPE html>
<html>
<head>
  <title>Poker League</title>

  <!-- The blueprint: identity + voice + prompt for any LLM -->
  <script type="application/aide-blueprint+json" id="aide-blueprint">
  {
    "identity": "Poker league. 8 players, biweekly Thursday, rotating hosts.",
    "voice": "No first person. State reflections only. No encouragement.",
    "prompt": "You are maintaining a living page for a poker league..."
  }
  </script>

  <!-- The snapshot: current state of the aide -->
  <script type="application/aide+json" id="aide-state">
  {
    "version": 1,
    "meta": { "title": "Poker League" },
    "collections": { ... },
    "relationships": [],
    "constraints": [],
    "blocks": { ... },
    "views": { ... },
    "styles": { ... }
  }
  </script>

  <!-- The event log: full history -->
  <script type="application/aide-events+json" id="aide-events">
  [
    {"seq":1,"type":"collection.create","payload":{"id":"roster","schema":{...}},"ts":"2026-02-01T14:00:00Z"},
    {"seq":2,"type":"entity.create","payload":{"collection":"roster","id":"player_mike",...},"ts":"2026-02-01T14:00:01Z"},
    ...
  ]
  </script>

  <style>/* Rendered styles from style tokens */</style>
</head>
<body>
  <!-- Rendered HTML from the block tree — what browsers display -->
  <h1>Poker League</h1>
  <div class="metric">Next game: Thu Feb 27 at Dave's</div>
  <div class="roster-list">...</div>
  <div class="schedule-table">...</div>
</body>
</html>
```

Four layers in one file:

**The `<body>`** is the rendered page. What browsers display, what search engines index. No JavaScript required to view it.

**The blueprint (`aide-blueprint`)** is the aide's DNA. Its identity, voice rules, and a prompt that any LLM can use to become the aide's brain. Download the file, paste the prompt into any model, and the aide comes back to life.

**The snapshot (`aide-state`)** is the current structured state. What the editor reads when you reopen the aide. What a remixer gets when they fork.

**The event log (`aide-events`)** is the complete history of every state change. Enables time travel, undo, and audit trails. Optional in the published file — can be stripped for a smaller download.

### The Renderer

The renderer is a pure function that produces output for different channels: `(snapshot, blueprint, channel, events?, options?) -> string`. For HTML, it produces a complete, self-contained web page. For text, it produces unicode suitable for SMS, terminal, or Slack. No AI involved. Deterministic: same input, same output, always.

```python
def render(snapshot, blueprint, channel="html", events=None, options=None) -> str:
    # 1. For HTML: Generate CSS from design system + schema styles + token overrides
    # 2. Walk block tree depth-first
    # 3. For entity_view blocks: render entity using its schema's template
    #    - render_html for HTML channel
    #    - render_text for text channel
    # 4. For HTML: Assemble full document with embedded JSON
    # 5. For text: Assemble unicode output with box-drawing characters
    return output_string
```

Entities are rendered using Mustache templates defined in their schemas. The `render_html` template produces HTML with CSS classes; the `render_text` template produces unicode text. Child collections (e.g., `Record<string, T>` fields) are rendered via `{{>fieldname}}` syntax.

Block types: heading, text, metric, entity_view, divider, image, callout, column_list, column. The `entity_view` block is the bridge between the block tree and entity data — it renders an entity using its schema's template.

The full rendering contract, multi-channel output, and Mustache templating are in `aide_renderer_spec.md`.

### The Assembly Layer

The assembly layer sits between the pure functions (reducer, renderer) and the outside world (R2 storage, the orchestrator). It coordinates the lifecycle of an aide's HTML file:

- **load** -- fetch from R2, parse HTML, extract snapshot + events + blueprint
- **apply** -- validate primitives, reduce events into snapshot, re-render the full HTML
- **save** -- upload updated HTML to R2 workspace bucket
- **create** -- initialize a new aide from a blueprint with empty state
- **publish** -- copy workspace file to published bucket (optionally with footer, compacted events)
- **fork** -- deep clone an aide's state and blueprint, clear events and history

R2 uses two buckets: `aide-workspaces` (private, mutable, keyed by aide_id) and `aide-published` (public via CDN, keyed by slug). The workspace file is updated on every event. Publishing copies it to the public bucket. For v1, publish happens automatically on every save.

Concurrency is handled via per-aide asyncio locks (single instance). The event-sourced architecture makes conflict resolution straightforward if multiple writes collide -- reload, re-apply. The assembly also supports integrity checks (replay all events, compare to stored snapshot) and self-healing repair.

The full assembly contract is in `aide_assembly_spec.md`.

### Why the HTML File Is the Artifact

**Self-contained.** An aide is one file. Download it, email it, host it anywhere. No database dependency. No backend required to *view* it. The backend is only needed to *edit* it (because editing requires the AI compiler).

**Portable.** The blueprint means any LLM can become the aide's brain. The objects are yours, not ours.

**Remixable.** Fork an aide and you get the state, the schema, the block tree. Start fresh with your own data but the same structure.

**Inspectable.** View source and you can read the structured state. No opaque database. JSON in a script tag.

---

## The Cost Model

| Model Tier | Role | Cost per Call | When Used |
|------------|------|---------------|-----------|
| L2 (Haiku-class) | Intent compiler | ~$0.001 | 90% of interactions |
| L3 (Sonnet-class) | Schema synthesis, macros | ~$0.02–0.05 | 10% of interactions |
| L3 (Sonnet-class, vision) | Image/screenshot input | ~$0.03–0.08 | When images arrive |
| Renderer | State → HTML | $0.00 | Every state change |

### Per-Aide Lifecycle Costs

| Aide Type | Events | L2 Calls | L3 Calls | Estimated Cost |
|-----------|--------|----------|----------|----------------|
| Grocery list (ongoing, weekly) | ~50/week | ~45 | ~5 (first week) | ~$0.15 first week, ~$0.05/week after |
| Poker league (full season) | ~130 | ~125 | ~5 | ~$0.23 |
| Wedding seating (96 guests) | ~56 | ~54 | ~2 | ~$0.10 |
| Trip itinerary | ~40 | ~35 | ~5 | ~$0.12 |

The system gets cheaper over time within an aide because L3 calls are front-loaded (schema synthesis, first novel request) and L2 handles the long tail of routine updates. Macros compound the effect — once L3 synthesizes a capability, L2 invokes it by name forever after.

---

## Data Flow: End to End

Here's what happens when someone texts the aide's Signal number "Mike's out this week. Dave's subbing." -- every step, using the assembly layer.

**1. Message arrives at an ear.** Signal delivers the message to the signal-cli-rest-api container. The Signal ear normalizes it: user phone number, aide ID (mapped from the Signal conversation), message text.

**2. Ear posts to the brain.** The normalized message hits the FastAPI endpoint. The message is stored in server-side conversation history for AI context.

**3. Orchestrator acquires aide lock.** Per-aide asyncio lock prevents concurrent writes to the same aide.

**4. Assembly loads the aide.** `assembly.load(aide_id)` fetches the HTML file from R2 (workspace bucket), parses it, extracts the snapshot, events, and blueprint into an AideFile.

**5. L2 compiles to primitives.** The orchestrator sends the user message + snapshot + primitive schemas to L2 (Haiku). L2 resolves "Mike" to `roster/player_mike`, determines this is a substitution pattern, and emits primitives. If L2 can't compile (new schema needed, novel request), it escalates to L3 (Sonnet).

**6. Assembly applies events.** `assembly.apply(aide_file, events)` validates each primitive, reduces it into the snapshot (collecting any warnings or rejections), then re-renders the full HTML file from the new snapshot.

**7. Assembly saves.** `assembly.save(aide_file)` uploads the updated HTML to R2 (workspace bucket). One atomic PutObject.

**8. Assembly publishes.** `assembly.publish(aide_file)` copies the HTML to R2 (published bucket) at `aide-published/{slug}/index.html`. For free tier, injects the "Made with AIde" footer. Cloudflare CDN serves it at `toaide.com/p/{slug}`.

**9. Orchestrator releases aide lock.**

**10. Aide responds through the ear.** The Signal ear sends back: "Next game: Thu Feb 27 at Dave's. Dave replaces Mike. Dave's on snacks." with the page URL.

Total time: under 2 seconds. The L2 call dominates. Reduce + render + upload is milliseconds.

**New aide flow** (first message, no aide_id):

1. `assembly.create(default_blueprint)` -- empty AideFile
2. Orchestrator sends to L3 (schema synthesis from first message)
3. L3 returns: `collection.create` + `entity.create` + `block.set` + `view.create` + `meta.update`
4. `assembly.apply(aide_file, L3_events)`
5. `assembly.save(aide_file)` + `assembly.publish(aide_file)`
6. Record aide_id in Postgres, return page URL to user

---

## Persistence: Two Tiers

### Tier 1: The HTML File (the artifact)

The aide's HTML file is the source of truth. It contains:

| What | Where in the HTML | Purpose |
|------|-------------------|---------|
| Rendered page | `<body>` | What browsers display |
| Blueprint | `<script type="application/aide-blueprint+json">` | Identity, voice, prompt for any LLM |
| Current state | `<script type="application/aide+json">` | Structured snapshot (7 sections: meta, collections, relationships, relationship_types, constraints, blocks, views, styles, annotations) |
| Event history | `<script type="application/aide-events+json">` | Audit trail, undo, time travel |
| Styles | `<style>` | CSS from design system + style token overrides |

Self-contained, viewable without JavaScript, forkable, downloadable. If you lose everything else but keep this file, you have the aide.

**Storage:** Two Cloudflare R2 buckets.

| Bucket | Key | Access | Purpose |
|--------|-----|--------|---------|
| `aide-workspaces` | `{aide_id}/index.html` | Private (app only) | The living file, updated on every event |
| `aide-published` | `{slug}/index.html` | Public (via CDN) | The published snapshot, served at `toaide.com/p/{slug}` |

For v1, every save auto-publishes (workspace and published are always in sync). For v2, publishing can be gated (draft mode, scheduled publish).

**Size budget:** Grocery list ~15KB. Poker league ~25KB. Wedding with 500+ events ~100-200KB. Event log compaction (strip old events, keep snapshot) available when files grow large.

### Tier 2: Server-Side Working State (the editor's context)

The server maintains working state in Neon Postgres that supports the editing experience but is *not* part of the aide artifact:

- **Conversation history** -- the chat between the user and the AI. Context for the AI, not part of the aide. Fork an aide and you get the state, not someone else's conversation.
- **Synthesized macros** -- when L3 creates a capability, it's stored server-side so L2 can invoke it. The macro's *output* (the events it produces) goes into the HTML. The macro *definition* stays on the server.
- **User/session metadata** -- auth, tier, Signal phone mapping, ear preferences.

**Backup priority:**
1. The HTML files -- these are the aides. Everything else is reconstructible.
2. The server databases -- nice for conversation continuity, but losing them just means the AI loses context. The aide state (in the HTML) is unaffected.

---

## Multi-User: Group Chat as Collaboration

The current architecture is single-writer for the primary organizer via web chat, and multi-writer via Signal group chats. Events from multiple users interleave in the event log. The reducer applies them deterministically.

For the claiming/RSVP pattern (multiple people updating the same aide through a group chat), the event log handles conflicts naturally:

```
// User A (via Signal): "I'm bringing salad"
evt_012: entity.create { collection: "potluck", fields: { item: "salad", brought_by: "Mike" } }

// User B (via Signal): "I'll do salad too" 
evt_013: entity.create { collection: "potluck", fields: { item: "salad", brought_by: "Dave" } }

// Both events apply. Two salads. The aide can reflect: 
// "Two salads — Mike and Dave. Want one of you to switch?"
```

Future multi-writer capabilities (two organizers editing simultaneously from web chat) would upgrade the reducer to use CRDT merge rules. The event-sourced, declarative primitive architecture makes this a reducer upgrade, not a rewrite.

---

## Infrastructure

| Component | Technology | Notes |
|-----------|-----------|-------|
| Backend | FastAPI (Python) | WebSocket + REST |
| Aide storage | HTML files on Cloudflare R2 | One file per aide, self-contained |
| Server state | Neon Postgres | Conversations, macros, users, sessions |
| Hosting | Railway | Backend + signal-cli container |
| CDN | Cloudflare | Published pages served from edge |
| Signal ear | signal-cli-rest-api (Docker) | Runs alongside FastAPI on Railway |
| Auth | Magic links via Resend | JWT in HTTP-only cookies |
| AI | Managed (Haiku/Sonnet) + BYOK | L2/L3 routing via orchestrator |

---

## What This Architecture Doesn't Do

**No external integrations (v1).** AIde doesn't connect to Venmo, Google Calendar, or Slack. The human is the integration point. They relay information through whatever ear is available. Channel ears (Signal, eventually WhatsApp/Telegram) let the aide listen directly to group conversations, but AIde never reaches out to other services.

**No computed fields in the kernel.** "Total paid = count where paid=true" is not a primitive. The renderer computes derived values during snapshot materialization. Keeping computation out of the kernel keeps the reducer simple.

**No conditional triggers (yet).** "Notify me when all items are checked off" requires a trigger system. Future layer, not a kernel feature.

---

## Summary

AIde is an event-sourced system where natural language is compiled into structured state transitions by a tiered AI. A small model handles routine updates cheaply and fast. A large model synthesizes new capabilities when needed -- including the initial schema when the aide first comes alive from a single message. The aide is a single HTML file containing its rendered page, its structured state, its event history, and its blueprint. Rendering is deterministic. The architecture accepts input from any ear without caring which one. The system grows its own vocabulary through macros, getting cheaper over time.

The human is the sensor. The AI is the compiler. The HTML file is the aide. The event log is the truth. The published page is the body. The ears don't matter -- the object is alive regardless of how you reach it.

---

## Detailed Specs

The kernel has implementation specs covering each layer in full detail:

| Spec                             | What it covers                                                                                                                                          |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `unified_entity_model.md`        | v3 data model: TypeScript interfaces, multi-channel rendering, tree-sitter parsing, entity structure, fractional indexing                              |
| `aide_primitive_schemas_spec.md` | JSON schemas for all primitives, TypeScript type mappings, validation rules, event wrapper, escalation signals                                          |
| `aide_reducer_spec.md`           | Reduction rules per primitive, tree-sitter parsing, ReduceResult contract, constraint checking, type validation, error catalog, testing strategy        |
| `aide_renderer_spec.md`          | Multi-channel rendering (HTML + text), Mustache templating, CSS generation, block rendering, entity templates, value formatting, sanitization           |
| `aide_assembly_spec.md`          | Load/apply/save/create/publish/fork operations, R2 layout, parsing, integrity checks, concurrency, compaction, error recovery                           |
