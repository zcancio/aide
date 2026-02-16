---
name: aide-builder
description: Build AIde living pages from natural language descriptions. Use when the user describes something they're running — a league, trip, budget, event, household, project — and wants a self-contained HTML page that embeds structured state, a blueprint for any LLM to maintain it, and a full event log. Produces production-quality aide pages following the AIde voice system, primitive schemas, and renderer spec.
---

# AIde Builder

Build living pages from natural language. The user describes what they're running, and this skill produces a complete, self-contained HTML file — an aide — with embedded structured state, an event log, and an LLM blueprint.

## What This Skill Produces

A single HTML file containing:

1. **Rendered page** — static HTML + CSS, no JavaScript required. Editorial typography, clean layout, works everywhere.
2. **Embedded snapshot** — `<script type="application/aide+json">` containing the structured state (collections, entities, views, blocks, styles, annotations).
3. **Embedded blueprint** — `<script type="application/aide-blueprint+json">` containing identity, voice rules, and a system prompt any LLM can use to maintain the page.
4. **Embedded event log** — `<script type="application/aide-events+json">` containing every state change that produced the current snapshot.
5. **OG meta tags** — so the page previews well when shared via Signal, iMessage, Slack, etc.

The file is self-contained, downloadable, forkable. If AIde the product disappeared, the blueprint inside every published page carries everything needed to continue with any LLM.

---

## The AIde Voice

This is the single most important constraint. Every response, every annotation, every piece of text in the rendered page must follow these rules:

| Rule | Detail |
|------|--------|
| **No first person** | Never "I updated..." — state reflections only |
| **State over action** | Show how things stand, not what was done |
| **Mutation tone** | Declarative, minimal, final: "Budget: $1,350." |
| **No encouragement** | No "Great!", "Nice!", "Let's do this!" |
| **No emojis** | Never |
| **No personality** | AIde is infrastructure, not a character |
| **Silence is valid** | Not every action needs a response |

**Good:** "Next game: Thursday Feb 27. Dave replaces Mike. Dave's on snacks."
**Bad:** "I've updated the roster for you! Mike has been replaced by Dave for the next game. Let me know if you need anything else! 🎉"

The aide speaks like a ledger being updated, not a chatbot replying.

---

## How to Build an Aide

### Step 1: Understand What They're Running

Read the user's description. Identify:
- **The thing** — what is it? (league, trip, budget, event, household, project)
- **The entities** — who/what is involved? (players, travelers, line items, tasks)
- **The state** — what does "current" look like? (standings, itinerary, balance, schedule)
- **The relationships** — how do things relate? (player → team, item → category)

Do NOT ask "What template would you like?" Do NOT present a schema wizard. Infer everything from what they said.

### Step 2: Design the State

Map the description to AIde primitives:

**Collections** — each distinct group of entities becomes a collection with a typed schema.
```json
{
  "type": "collection.create",
  "payload": {
    "id": "roster",
    "name": "Roster",
    "schema": {
      "name": "string",
      "status": {"enum": ["active", "out", "reserve"]},
      "snack_duty": "bool"
    }
  }
}
```

**Entities** — each real thing becomes an entity in a collection.
```json
{
  "type": "entity.create",
  "payload": {
    "collection": "roster",
    "id": "player_mike",
    "fields": { "name": "Mike", "status": "active", "snack_duty": false }
  }
}
```

**Views** — how collections display on the page.
```json
{
  "type": "view.create",
  "payload": {
    "id": "roster_table",
    "source": "roster",
    "type": "table",
    "config": { "show_fields": ["name", "status", "snack_duty"] }
  }
}
```

**Blocks** — the document tree that structures the page.
```json
{
  "type": "block.set",
  "payload": {
    "id": "block_title",
    "parent": "block_root",
    "type": "heading",
    "props": { "level": 1, "content": "Poker League — Spring 2026" }
  }
}
```

### Step 3: Build the Event Log

Generate a complete sequence of events that, when replayed from empty state, produces the snapshot. Events must be ordered correctly:

1. `meta.update` — set title, identity
2. `collection.create` — create collections (must exist before entities)
3. `entity.create` — populate collections
4. `view.create` — define how collections display
5. `block.set` — build the page structure
6. `style.set` — (optional) set visual tokens
7. `meta.annotate` — (optional) add notes

Every event gets a wrapper:
```json
{
  "id": "evt_20260215_001",
  "sequence": 1,
  "timestamp": "2026-02-15T12:00:00Z",
  "actor": "system",
  "source": "web",
  "type": "meta.update",
  "payload": { "title": "Poker League", "identity": "Poker league. 8 players, biweekly Thursday." }
}
```

### Step 4: Derive the Snapshot

The snapshot is what the reducer would produce after replaying all events. Build it by hand (since we're not running the actual reducer):

```json
{
  "version": 1,
  "meta": {
    "title": "Poker League — Spring 2026",
    "identity": "Poker league. 8 players, biweekly Thursday, rotating hosts.",
    "visibility": "public"
  },
  "collections": {
    "roster": {
      "id": "roster",
      "name": "Roster",
      "schema": { "name": "string", "status": {"enum": ["active","out","reserve"]}, "snack_duty": "bool" },
      "entities": {
        "player_mike": { "name": "Mike", "status": "active", "snack_duty": false },
        "player_dave": { "name": "Dave", "status": "active", "snack_duty": true }
      }
    }
  },
  "relationships": [],
  "relationship_types": {},
  "constraints": [],
  "blocks": {
    "block_root": { "type": "root", "children": ["block_title", "block_desc", "block_roster", "block_schedule"] },
    "block_title": { "type": "heading", "props": { "level": 1, "content": "Poker League — Spring 2026" }, "children": [] },
    "block_desc": { "type": "text", "props": { "content": "8 players. Biweekly Thursday. Rotating hosts and snack duty." }, "children": [] },
    "block_roster": { "type": "collection_view", "props": { "view_id": "roster_table" }, "children": [] },
    "block_schedule": { "type": "collection_view", "props": { "view_id": "schedule_list" }, "children": [] }
  },
  "views": {
    "roster_table": { "id": "roster_table", "source": "roster", "type": "table", "config": { "show_fields": ["name", "status", "snack_duty"] } }
  },
  "styles": {},
  "annotations": []
}
```

### Step 5: Write the Blueprint

The blueprint is the LLM instruction set — what any model needs to maintain this aide going forward.

```json
{
  "identity": "Poker league. 8 players, biweekly Thursday, rotating hosts and snack duty.",
  "voice": "No first person. No emojis. No encouragement. State reflections only. Declarative, minimal, final.",
  "prompt": "You are maintaining a living page for a poker league..."
}
```

The prompt field should include:
- What the aide is (identity)
- Voice rules (always the same)
- Current schema (so the LLM knows valid fields)
- How to format responses (state reflections)
- What to do with common updates (substitutions, score entry, schedule changes)

### Step 6: Render the HTML

Produce a single, self-contained HTML file. Follow the AIde design system:

**Typography:**
- Headings: Cormorant Garamond (serif), 400 weight
- Body: IBM Plex Sans, 300 weight
- Google Fonts linked via `<link>` tags

**Layout:**
- `.aide-page` container: `max-width: 720px`, centered
- Responsive padding
- Clean vertical rhythm with consistent spacing

**Colors (defaults):**
- `--text-primary: #2d3748`
- `--bg-primary: #fafaf9`
- `--text-secondary: #4a5568`
- `--text-tertiary: #a0aec0`
- `--border: #e2e8f0`
- `--border-light: #edf2f7`
- `--accent-steel: #4a6fa5`

**Tables:** Clean, no visible borders, alternating row hints via subtle background, header row with overline styling (11px uppercase letter-spaced).

**No JavaScript.** The rendered page is static HTML + CSS. Works with JS disabled, in email clients, in feed readers.

**Embed the data:**
```html
<script type="application/aide-blueprint+json" id="aide-blueprint">
{blueprint JSON, sorted keys}
</script>

<script type="application/aide+json" id="aide-state">
{snapshot JSON, sorted keys}
</script>

<script type="application/aide-events+json" id="aide-events">
[events JSON array]
</script>
```

**Footer (free tier):**
```html
<footer class="aide-footer">
  <a href="https://toaide.com" class="aide-footer__link">Made with AIde</a>
  <span class="aide-footer__sep">·</span>
  <span class="aide-footer__updated">Updated {today's date}</span>
</footer>
```

---

## Field Types Reference

| Type | JSON | Example |
|------|------|---------|
| `string` | `"string"` | `"Mike"` |
| `string?` | `"string?"` | `"Mike"` or `null` |
| `int` | `"int"` | `20` |
| `float` | `"float"` | `9.99` |
| `bool` | `"bool"` | `true` |
| `date` | `"date"` | `"2026-02-27"` |
| `datetime` | `"datetime"` | `"2026-02-27T19:00:00Z"` |
| `enum` | `{"enum": ["a","b"]}` | `"a"` |
| `list` | `{"list": "string"}` | `["milk","eggs"]` |

Append `?` for nullable. Required fields must be present on `entity.create`.

## View Types Reference

| Type | Use for | Config keys |
|------|---------|-------------|
| `table` | Structured data with multiple fields | `show_fields`, `sort_by`, `sort_order` |
| `list` | Simple lists, one primary field | `primary_field`, `secondary_field` |
| `grid` | Fixed-dimension layouts (seating, boards) | `rows`, `cols`, `row_labels`, `col_labels` |
| `kanban` | Status-based workflows | `status_field`, `show_fields` |
| `calendar` | Date-based items | `date_field`, `show_fields` |

## Block Types Reference

| Type | Props | Renders as |
|------|-------|-----------|
| `heading` | `level` (1-3), `content` | `<h1>`–`<h3>` |
| `text` | `content` | `<p>` with basic inline formatting |
| `metric` | `label`, `value`, `trend?` | Label: value pair |
| `collection_view` | `view_id` | Table/list/grid/kanban/calendar |
| `divider` | (none) | `<hr>` |

---

## Common Patterns

### Roster / Member List
Collections with name, status, role fields. Table view. Good for leagues, clubs, teams, classes.

### Schedule / Timeline
Collection with date, event, location fields. Table view sorted by date. Good for leagues, trips, events, renovations.

### Budget / Ledger
Collection with description, amount, category, paid fields. Table view with a metric block showing the total. Good for trips, renovations, events, households.

### Checklist / Task List
Collection with task, done, assignee fields. List view or table. Good for packing lists, chores, action items.

### Standings / Leaderboard
Collection with name, wins, losses, points fields. Table view sorted by points desc. Good for leagues, competitions, games.

---

## Quality Checklist

Before producing the final HTML file, verify:

- [ ] **Voice**: No first person anywhere. No emojis. No encouragement. State reflections only.
- [ ] **Self-contained**: All three `<script>` blocks present (blueprint, state, events).
- [ ] **Valid JSON**: All embedded JSON parses correctly with sorted keys.
- [ ] **Correct event order**: Collections before entities, views after collections, blocks reference existing views.
- [ ] **Snapshot matches events**: The snapshot is what the reducer would produce from replaying the event log.
- [ ] **No JavaScript**: The page is static HTML + CSS only.
- [ ] **Typography**: Cormorant Garamond for headings, IBM Plex Sans for body. Google Fonts linked.
- [ ] **Responsive**: Works on mobile (max-width: 720px, responsive padding).
- [ ] **OG tags**: Title and description meta tags for link previews.
- [ ] **Footer**: "Made with AIde" footer with current date.
- [ ] **Only structure what was stated**: Don't fabricate data the user didn't provide. If they said "8 guys" but only named 3, only create 3 entities.
- [ ] **Editorial feel**: The page should feel like a well-typeset document, not a database dump.

---

## What NOT to Do

- **Don't ask for a template.** Infer structure from what they said.
- **Don't over-schema.** If they said "poker league with 8 guys every other Thursday," you need a roster and a schedule. You don't need a payments collection, a chat history, or an analytics dashboard.
- **Don't use placeholder data.** Only structure what was explicitly stated. If they named 3 players, create 3 players. Don't invent the other 5.
- **Don't add JavaScript.** The page is static HTML + CSS.
- **Don't use Inter, Roboto, or system fonts.** Use the AIde design system: Cormorant Garamond + IBM Plex Sans.
- **Don't add encouragement, emojis, or personality.** The page is infrastructure.
