# AIde — MVP Checklist

**Goal:** Prove a living object works. Text an aide, watch a page form, share the URL, have someone else text it, watch the page update coherently.

**Test:** Can you and your partner manage groceries through a Signal group chat with an aide, and share the live page URL with anyone?

---

## Phase 1: The Kernel (pure code, no AI, fully testable)

_Build the state machine. No LLM calls. Just primitives in, HTML out._

### 1.1 Primitive Schemas
- [ ] Define JSON schemas for all 25 primitives (entity, collection, field, relationship, block, view, style, meta) — see `aide_primitive_schemas.md` for full spec
- [ ] Validation layer: given a primitive + payload, confirm it's well-formed
- [ ] Test: hand-write 10 primitives in JSON, all validate

### 1.2 Reducer
- [ ] Pure function: `events[] → snapshot state`
- [ ] Field application: `entity.update` merges fields into existing entity
- [ ] Entity lifecycle: `entity.create`, `entity.remove` (soft-delete)
- [ ] Collection lifecycle: `collection.create`, `collection.update`, `collection.remove`
- [ ] Schema evolution: `field.add`, `field.update`, `field.remove`
- [ ] Relationship handling: `relationship.set` with cardinality enforcement (many_to_one auto-unlinks)
- [ ] Constraint validation: `relationship.constrain`, `meta.constrain` — warn on violations
- [ ] Block tree: `block.set`, `block.remove`, `block.reorder`
- [ ] View management: `view.create`, `view.update`, `view.remove`
- [ ] Style tokens: `style.set`, `style.set_entity`
- [ ] Meta: `meta.update`, `meta.annotate`, `meta.constrain`
- [ ] Determinism test: same events replayed → identical snapshot every time
- [ ] Test: hand-craft a 20-event grocery list, reducer produces correct snapshot

### 1.3 Renderer
- [ ] Pure function: `snapshot state → HTML body`
- [ ] Walk block tree top-to-bottom, render each block by type
- [ ] Block types for v1: heading, text, metric, collection_view, divider
- [ ] Collection view renders: list view (default), table view
- [ ] Style tokens → CSS variables
- [ ] Clean, readable output — editorial feel, not dashboard
- [ ] Test: feed grocery list snapshot, get valid HTML page

### 1.4 HTML File Assembly
- [ ] Combine: `<body>` (rendered) + `aide-state` (snapshot JSON) + `aide-events` (event log) + `aide-blueprint` (identity/voice/prompt)
- [ ] Single file, self-contained, viewable without JavaScript
- [ ] Test: open the assembled HTML in a browser, looks correct
- [ ] Test: extract `aide-state` from file, feed to reducer, get same snapshot

---

## Phase 2: The AI Compiler (prompt engineering)

_Teach the AI to emit primitives instead of HTML._

### 2.1 L3 — Schema Synthesis (Sonnet)
- [ ] System prompt: given a first message with no existing schema, emit `collection.create` + initial `entity.create` events
- [ ] Handles: "we need milk, eggs, and sourdough from Whole Foods" → grocery_list collection, 3 entities, inferred fields
- [ ] Handles: "I run a poker league, 8 guys, every other Thursday" → roster + schedule collections
- [ ] Handles image input: screenshot of a list, receipt, whiteboard → appropriate schema + entities
- [ ] Returns well-formed primitives that pass validation
- [ ] Test: 10 diverse first messages, all produce valid schemas

### 2.2 L2 — Intent Compiler (Haiku)
- [ ] System prompt: given a message + current snapshot + primitive schemas, emit one or more primitives
- [ ] Entity resolution: "Mike" → `roster/player_mike`
- [ ] Temporal resolution: "this week" → current relevant entity
- [ ] Multi-entity: "Mike's out, Dave's subbing" → two `entity.update` primitives
- [ ] Negation: "got the milk" → `entity.update { checked: true }`
- [ ] Addition: "oh and we need olive oil" → `entity.create`
- [ ] Returns well-formed primitives that pass validation
- [ ] Escalation: when L2 can't compile (unknown field, new collection needed), returns escalation signal
- [ ] Test: 30 routine update messages against existing schemas, all produce correct primitives

### 2.3 L3 — Schema Evolution
- [ ] When L2 escalates because a field doesn't exist, L3 adds it: `field.add`
- [ ] When conversation reveals a new pattern (categories, stores), L3 evolves the schema
- [ ] Test: start with minimal grocery schema, 20 messages later the schema has grown to include category, store, requested_by

### 2.4 Orchestrator
- [ ] Receives normalized message from any ear
- [ ] Loads current aide state from HTML file (or creates new aide if none)
- [ ] Routes to L2 first
- [ ] If L2 returns escalation → routes to L3
- [ ] If image attached → routes to L3 (vision-capable model)
- [ ] Applies returned primitives through reducer
- [ ] Re-renders HTML
- [ ] Uploads to R2
- [ ] Returns response text to ear
- [ ] Test: full loop — message in, primitives emitted, state updated, HTML published

---

## Phase 3: Web Chat Ear

_The quickest way to test the full loop in a browser._

### 3.1 Chat Interface
- [ ] Minimal page at toaide.com: text input, send button, conversation history
- [ ] Image upload: drag-and-drop or file picker
- [ ] Link to published page (opens in new tab)
- [ ] No split-pane editor, no dashboard, no sidebar
- [ ] No auth required for first session (anonymous, session cookie)
- [ ] Email gate: prompt to save after 10 turns

### 3.2 API Endpoint
- [ ] `POST /api/message` — accepts `{ aide_id, message, image? }`
- [ ] Returns `{ response_text, page_url }`
- [ ] Creates new aide on first message if no aide_id
- [ ] WebSocket or SSE for streaming responses (nice to have, not blocking)

### 3.3 Publishing
- [ ] On every state change: upload updated HTML file to R2
- [ ] Serve from `toaide.com/p/{aide_id}` via Cloudflare CDN
- [ ] Test: send a message, open the URL, see the updated page

---

## Phase 4: Signal Ear

_The ear that makes it real for daily use._

### 4.1 signal-cli-rest-api Setup
- [ ] Docker container running on Railway alongside FastAPI
- [ ] Dedicated phone number (Twilio or similar, ~$1/month)
- [ ] Register number with Signal via signal-cli
- [ ] QR code link to authenticate the Signal session
- [ ] Verify: can send/receive Signal messages programmatically

### 4.2 Signal Adapter
- [ ] Webhook: signal-cli receives message → POST to `/api/message` with normalized payload
- [ ] Phone number → user identity mapping (simple lookup table in Postgres)
- [ ] Conversation → aide mapping: each Signal conversation (DM or group) maps to one aide
- [ ] First message from a new conversation creates a new aide
- [ ] Response: orchestrator returns text → Signal adapter sends reply via signal-cli
- [ ] Image support: Signal images forwarded to orchestrator as base64 or URL
- [ ] Group chat: multiple phone numbers updating the same aide, each identified by their number

### 4.3 Test the Full Loop
- [ ] Text the aide's Signal number: "we need milk and eggs"
- [ ] Receive reply with page URL
- [ ] Open URL — see grocery list
- [ ] Add aide to Signal group with partner
- [ ] Partner texts: "add stuff for tacos"
- [ ] Aide replies in group, page updates
- [ ] Partner texts: "chicken. and olive oil"
- [ ] Page reflects all changes from both people

---

## Phase 5: Polish & Dogfood

_Use it daily. Fix what breaks._

### 5.1 Voice System
- [ ] No first person in any aide response
- [ ] State reflections only: "Milk, eggs, sourdough. 3 items."
- [ ] No encouragement, no emojis, no "I updated the list for you"
- [ ] Verify voice rules hold across L2 and L3 responses

### 5.2 Reliability
- [ ] Error handling: bad primitives from AI get caught by validation, not applied
- [ ] Retry logic: if L2/L3 call fails, retry once
- [ ] Signal connection: signal-cli reconnects on disconnect
- [ ] R2 upload: retry on failure, don't lose state (event log is the source of truth)

### 5.3 Blueprint
- [ ] Every published page embeds `aide-blueprint` with identity, voice rules, and prompt
- [ ] Test: copy the blueprint, paste into Claude.ai, describe an update — get a coherent response

### 5.4 Dogfood for 2 weeks
- [ ] Use grocery aide daily with partner via Signal
- [ ] Create at least 3 other aides (poker, a trip, something else)
- [ ] Note every failure, friction point, and surprise
- [ ] Fix the top 5 issues

---

## What's Explicitly Cut

These are not in the MVP. They come later.

- [ ] ~~Auth (magic links)~~ — anonymous + email-to-save is enough
- [ ] ~~Multi-aide dashboard~~ — one aide per Signal conversation, manage by scrolling chat history
- [ ] ~~Rate limiting~~ — you're the only user
- [ ] ~~Stripe / payments~~ — no one is paying yet
- [ ] ~~BYOK~~ — managed keys only
- [ ] ~~MacroSpec persistence~~ — L3 synthesizes inline, doesn't persist reusable macros yet
- [ ] ~~Telegram / WhatsApp ears~~ — Signal + web is enough to prove the model
- [ ] ~~Landing page~~ — toaide.com is just the chat interface
- [ ] ~~Custom slugs~~ — random IDs are fine
- [ ] ~~"Made with AIde" footer~~ — add when there are users to convert
- [ ] ~~CRDT multi-writer~~ — Signal group chat handles multi-user for now
- [ ] ~~Conversation compression~~ — context windows are big enough for MVP-length conversations
- [ ] ~~View types beyond list and table~~ — grid, calendar, kanban come when someone needs them

---

## Success Criteria

The MVP works when:

1. You text the aide from Signal and a page appears at a URL
2. Your partner texts the same aide and the page updates coherently
3. The page makes sense to someone who wasn't in the conversation
4. You use it for real groceries for two weeks without switching back to Apple Notes
5. The aide starts in the middle — no setup, no templates, just talk
6. It feels alive
