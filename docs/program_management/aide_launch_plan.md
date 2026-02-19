# AIde — Launch Plan

**Goal:** Ship a public product where someone can sign up, build a living page through conversation, update it via Signal, and share it.
**Starting point:** Phase 0 complete (Railway, Neon Postgres, magic link auth, domain). Kernel implemented (primitives, reducer, renderer, assembly — all passing smoke tests).
**What's left:** L2/L3 orchestrator, multi-aide management, Signal ear, rate limiting, Stripe, landing page.

---

## Phase 0: Foundation ✅ COMPLETE

### 0.1 Infrastructure
- [x] Domain & hosting (Railway, Cloudflare DNS, SSL)
- [x] Rebrand (Vibez → AIde)
- [x] Database: Neon Postgres with three-role security (aide_app, aide_readonly, aide_breakglass)
- [x] CI/CD: GitHub Actions, Railway auto-deploy from main, Alembic migrations

### 0.2 Auth
- [x] Magic links via Resend (100/day free tier)
- [x] JWT in HTTP-only, Secure, SameSite=Lax cookie (24-hour expiry)
- [x] RLS policies on all user tables
- [x] Rate limiting: 5 magic links per email/hour, 20 per IP/hour

---

## Phase 1: Core Product (3 weeks)

_Wire the kernel to users. Web chat for creation, Signal for ongoing updates._

### 1.1 Kernel ✅ COMPLETE
- [x] `types.py` — Event, Blueprint, AideFile, Warning, constants
- [x] `events.py` — make_event factory, assign_metadata
- [x] `primitives.py` — structural validation for all 22 primitives
- [x] `reducer.py` — pure `reduce(snapshot, event) → ReduceResult`, all primitive handlers
- [x] `renderer.py` — pure `render(snapshot, blueprint) → HTML`, list/table/grid views, CSS generation
- [x] `assembly.py` — IO coordinator (load, apply, save, create, publish, fork) + MemoryStorage
- [x] PostgresStorage adapter for assembly layer (Neon integration)
- [x] End-to-end smoke test: events → reducer → renderer → HTML
- [x] Engine builds:
  - [x] `engine.py` — single-file Python build (concatenated, no dependencies)
  - [x] `engine.js` — JavaScript build (transpiled from Python or hand-ported)
  - [x] `engine.ts` — TypeScript build with full type definitions
  - [x] `engine.compact.js` — minified JS for browser distribution
- [x] Test runs for all builds:
  - [x] Python tests passing (`pytest engine/kernel/tests/`) — 905 tests
  - [x] JS tests passing (same test cases, Node.js runner) — 38 tests
  - [x] TS type checking passing (`tsc --noEmit`)
  - [x] Minified JS functional test (browser smoke test)

### 1.2 Data Model ✅ COMPLETE
- [x] Neon Postgres tables (Alembic migration):
  - `aides` (id UUID, user_id, title, slug, status [draft/published/archived], state JSONB, event_log JSONB, created_at, updated_at)
  - `conversations` (id UUID, aide_id, channel [web/signal], messages JSONB, created_at, updated_at)
  - `signal_mappings` (id UUID, phone_number, user_id, aide_id, conversation_id) — maps Signal conversations to aides
- [x] RLS policies: `USING (user_id = current_setting('app.user_id')::uuid)`
- [x] Grant permissions to aide_app role
- [x] Repos in `backend/repos/` with parameterized SQL (aide_repo, conversation_repo, signal_mapping_repo)
- [x] Cross-user isolation tests for all repos

### 1.3 L2/L3 Orchestrator ✅
- [x] L3 system prompt (Sonnet): first message with no schema → `collection.create` + initial `entity.create` events
  - Handles: "we need milk, eggs, and sourdough from Whole Foods" → grocery_list collection, 3 entities, inferred fields
  - Handles: "I run a poker league, 8 guys, every other Thursday" → roster + schedule collections
  - Handles image input: screenshot of a list, receipt, whiteboard → appropriate schema + entities
  - Returns well-formed primitives that pass validation
  - Test: 10 diverse first messages, all produce valid schemas
- [x] L2 system prompt (Haiku): message + current snapshot + primitive schemas → primitives
  - Entity resolution: "Mike" → `roster/player_mike`
  - Temporal resolution: "this week" → current relevant entity
  - Multi-entity: "Mike's out, Dave's subbing" → two `entity.update` primitives
  - Negation: "got the milk" → `entity.update { checked: true }`
  - Addition: "oh and we need olive oil" → `entity.create`
  - Escalation signal when L2 can't compile (unknown field, new collection needed)
  - Test: 30 routine update messages, all produce correct primitives
- [x] L3 schema evolution: when L2 escalates because a field doesn't exist, L3 adds it via `field.add`
- [x] Orchestrator coordinator:
  - Receives normalized message from any ear (web or Signal)
  - Loads current aide state from DB
  - Routes to L2 first; if escalation → routes to L3; if image → routes to L3
  - Applies returned primitives through reducer
  - Re-renders HTML via renderer
  - Saves state + event log to DB, uploads HTML to R2
  - Returns response text to ear
  - Test: full loop — message in, primitives emitted, state updated, HTML published
- [x] Managed API routing: server-side keys, 70% Haiku / 30% Sonnet based on message complexity
- [x] Voice rules: no first person, state reflections only, no encouragement/emojis

### 1.4 Web Chat UI ✅ COMPLETE
- [x] Dashboard (post-login landing): grid/list of user's aides
  - Each card: title, status badge, last edited timestamp
  - "New AIde" button → enters chat with blank aide
  - Click existing aide → enters chat with that aide's state + conversation
  - Archive/delete aide (with confirmation)
- [x] Chat interface: full-viewport preview (iframe, `srcdoc`) + floating chat overlay pinned to bottom
  - Chat overlay: input bar at bottom, expandable conversation history, backdrop blur
  - Image input: file picker + drag-and-drop, JPEG/PNG/WebP/HEIC, 10MB max → triggers L3 routing
  - Preview refreshes per AI turn
- [x] `POST /api/message` — accepts `{ aide_id, message, image? }`, returns `{ response_text, page_url, state }`
  - Creates new aide on first message if no aide_id
- [x] Publish flow: creates/updates aide's slug in DB, uploads to R2
  - Published URL: `toaide.com/s/{slug}` (namespaced under `/s/` for route safety)
- [x] Display components: EditableField, PageDisplay, CardDisplay, SectionDisplay, TableDisplay, ChecklistDisplay, MetricDisplay, TextDisplay, ListDisplay, ImageDisplay, GridDisplay
- [x] Direct edit pipeline: click field → inline input → WebSocket → reducer → delta broadcast (<200ms)
- [x] Telemetry for direct edits (edit_latency_ms recorded)

### 1.5 Signal Ear
- [ ] signal-cli-rest-api: Docker container on Railway alongside FastAPI
  - Dedicated phone number (Twilio or similar, ~$1/month)
  - Register number with Signal via signal-cli
  - Verify: can send/receive Signal messages programmatically
- [ ] Signal adapter:
  - Webhook: signal-cli receives message → POST to `/api/message` with normalized payload
  - Phone number → user mapping via `signal_mappings` table
  - Conversation → aide mapping: each Signal conversation (DM or group) maps to one aide
  - First message from a new number/group creates a new aide
  - Response: orchestrator returns text → adapter sends reply via signal-cli
  - Image support: Signal images forwarded as base64
  - Group chat: multiple phone numbers updating the same aide
- [ ] Linking flow: user connects their Signal number to their web account
  - Text the aide's Signal number with a link code from the dashboard
  - Or: dashboard shows "Text [number] to update this aide via Signal"

### 1.6 Published Page Serving ✅ COMPLETE
- [x] Route `toaide.com/s/{slug}` → serve HTML from R2 via Cloudflare CDN
- [x] "Made with AIde" footer injected on free tier pages (links to toaide.com)
- [x] Proper cache headers (Cache-Control, ETag)
- [x] Blueprint embedded in HTML (identity, voice rules, event log, snapshot)
- [x] Open Graph tags for link previews

### 1.7 Reliability
- [ ] Error handling: invalid primitives from AI caught by validation, not applied
- [ ] Retry logic: if L2/L3 call fails, retry once
- [ ] Signal connection: signal-cli reconnects on disconnect
- [ ] R2 upload: retry on failure (event log in DB is source of truth)

---

## Phase 2: Rate Limiting & Engine Hosting (1 week)

_Control costs and prepare for distribution._

### 2.1 Turn Counting
- [ ] Track AI turns per user in Postgres: `turn_count` + `turn_week_start` on users table
- [ ] 1 turn = 1 user message → 1 AI response (includes Signal messages)
- [ ] Weekly reset: when `now - turn_week_start > 7 days`, reset count
- [ ] Check before processing: if free user && turn_count >= 50, reject with upgrade message
- [ ] Pro users: unlimited (no check)

### 2.2 Turn Counter UI
- [ ] Show remaining turns in web chat: "37 turns left this week"
- [ ] At 45/50: yellow warning
- [ ] At 50/50: disabled input + upgrade CTA
- [ ] Signal: reply with turn count warning when approaching limit

### 2.3 Engine Hosting on R2
- [ ] Host kernel files at `toaide.com/engine/v1/` via R2 static hosting
  - `engine.js` — reducer + renderer for browser-side replay
  - `engine.py` — for Claude Code / MCP / Cowork consumption
  - `engine.ts` — TypeScript version
- [ ] Versioned paths: `/engine/v1/`, `/engine/v2/` etc.
- [ ] CDN caching with immutable headers per version

---

## Phase 3: Payments (1 week)

_Let people give you money._

### 3.1 Stripe Integration
- [ ] Stripe account setup under Bantay LLC
- [ ] Single product: "AIde Pro" — $10/month
- [ ] Stripe Checkout session for upgrade flow
- [ ] Webhook handlers (idempotent):
  - `checkout.session.completed` → update user tier to pro
  - `customer.subscription.deleted` → downgrade to free
  - `invoice.payment_failed` → grace period logic

### 3.2 Upgrade Flow
- [ ] "Upgrade to Pro" button in dashboard header
- [ ] Upgrade CTA in rate limit message
- [ ] Post-upgrade: immediate access, footer removed, turn limit lifted
- [ ] Settings page: manage subscription, cancel

### 3.3 Pro Features
- [ ] Remove "Made with AIde" footer on published pages
- [ ] Unlimited AI turns (web + Signal)
- [ ] Custom slugs (free tier gets random slugs only)
- [ ] BYOK: always free, bypasses managed routing

---

## Phase 4: Landing Page & Launch (1 week)

_The thing people see before they sign up._

### 4.1 Landing Page (toaide.com)
- [ ] Hero: "For what you're running." + one-line explainer
- [ ] Demo: auto-playing conversation → live page building
- [ ] Use cases: 3-4 examples with screenshots (poker league, wedding, grocery list, trip)
- [ ] Signal angle: "Update your page from a text message"
- [ ] Pricing: Free (50 turns/week, "Made with AIde" footer) vs Pro ($10/mo, unlimited)
- [ ] "Sign up free" CTA → enter email → magic link → dashboard
- [ ] Mobile responsive

### 4.2 Seed Templates
- [ ] 4-6 starter templates users can remix:
  - Poker league schedule
  - Wedding logistics page
  - Freelancer pricing/services
  - Trip itinerary
  - Grocery list
- [ ] "Start from template" option on dashboard alongside "New blank aide"
- [ ] Templates are pre-built aides cloned into user's account

### 4.3 Launch Checklist
- [ ] Error monitoring (Sentry free tier)
- [ ] Rate limiting on auth endpoints (prevent brute force)
- [ ] Published page safety: basic XSS scanning, no phishing patterns
- [ ] Terms of Service + Privacy Policy (simple markdown pages)
- [ ] `robots.txt` and basic SEO meta tags
- [ ] Test full flow: sign up → create aide → chat → page appears → publish → share URL → view
- [ ] Test Signal flow: link number → text aide → page updates → share URL
- [ ] Backup verification: Neon PITR + R2 durability + Railway deploy history

---

## Phase 5: Distribution (2-4 weeks, post-launch)

_Bring the engine to every Claude surface._

### 5.1 Claude.ai Project
- [ ] Project with engine files + SKILL.md + primitive schemas
- [ ] Users paste blueprint from any aide, continue editing in Claude.ai
- [ ] Export updated state back to toaide.com

### 5.2 Claude Code Skill
- [ ] `/mnt/skills/aide-builder/SKILL.md` with engine + schemas
- [ ] Claude Code can create/modify aides from terminal

### 5.3 MCP Server
- [ ] `aide-mcp` server: tools for create_aide, update_aide, get_state, publish
- [ ] Works with any MCP-compatible client

### 5.4 Cowork Plugin
- [ ] Desktop automation for non-developers
- [ ] File-based aide management

---

## Phase 6: Post-Launch Iteration (ongoing)

### 6.1 Week 1-2
- [ ] Monitor: error rates, response times, turn usage, L2/L3 call distribution
- [ ] Watch for abuse: free tier gaming, content issues
- [ ] Gather feedback: what do first users actually make?
- [ ] Fix the top 3 bugs
- [ ] Track L3 costs — verify system gets cheaper per aide over time

### 6.2 Growth Loops
- [ ] Remix flow: "Use this as a template" button on published pages
- [ ] Share tracking: which aides get viewed most?
- [ ] Template gallery: curated community aides
- [ ] "Made with AIde" footer click-through tracking

### 6.3 Later Features (don't build until needed)
- [ ] Telegram / WhatsApp ears
- [ ] Passkey auth (WebAuthn)
- [ ] Conversation compression at context window limits
- [ ] Custom domains for published aides
- [ ] Team/collaboration features
- [ ] Analytics dashboard
- [ ] PDF export
- [ ] API for programmatic aide updates
- [ ] MacroSpec persistence (L3 synthesizes once, L2 invokes forever)

---

## Timeline

| Phase | Duration | What ships |
|-------|----------|------------|
| **Phase 0** — Foundation | ✅ complete | Domain, rebrand, magic link auth, Railway + Neon |
| **Phase 1** — Core Product | 3 weeks | Kernel ✅, Data Model ✅, L2/L3 orchestrator, dashboard, web chat, Signal ear, publishing |
| **Phase 2** — Rate Limiting + Engine | 1 week | 50 turns/week, turn counter UI, engine on R2 |
| **Phase 3** — Payments | 1 week | Stripe, $10/mo Pro, upgrade flow |
| **Phase 4** — Landing & Launch | 1 week | Landing page, templates, launch checklist |
| **Total to launch** | **~6 weeks remaining** | **Public launch** |
| **Phase 5** — Distribution | 2-4 weeks post-launch | Claude.ai, Claude Code, MCP, Cowork |

---

## Cost Model

| Model Tier | Role | Cost per Call | When Used |
|------------|------|---------------|-----------|
| L2 (Haiku) | Intent compiler | ~$0.001 | ~90% of interactions |
| L3 (Sonnet) | Schema synthesis, evolution, vision | ~$0.02–0.05 | ~10% of interactions |
| Renderer | State → HTML | $0.00 | Every state change (pure code) |

### Per-Aide Lifecycle Costs

| Aide Type | Events | L2 Calls | L3 Calls | Estimated Cost |
|-----------|--------|----------|----------|----------------|
| Grocery list (weekly) | ~50/week | ~45 | ~5 (first week) | ~$0.15 first week, ~$0.05/week after |
| Poker league (full season) | ~130 | ~125 | ~5 | ~$0.23 |
| Wedding seating (96 guests) | ~56 | ~54 | ~2 | ~$0.10 |
| Trip itinerary | ~40 | ~35 | ~5 | ~$0.12 |

System gets cheaper over time per aide: L3 calls are front-loaded (schema synthesis), L2 handles the long tail.

---

## What's NOT in v1

Explicitly descoped to avoid scope creep:

- **Team tier** — Solo users first. Teams come after PMF.
- **Custom domains** — Nice but not blocking anyone.
- **Analytics dashboard** — Later. Ship first.
- **Real-time collaboration** — Signal group chat handles multi-user for now.
- **Template marketplace with payments** — Free remixes only at launch.
- **Conversation compression** — Build when someone hits context limits.
- **Mobile app** — Web-responsive + Signal is enough.
- **MacroSpec persistence** — L3 synthesizes inline for now. Persistence is a cost optimization, not a launch requirement.
- **Telegram / WhatsApp** — Signal + web is enough to prove the model.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| L2 produces invalid primitives | Medium | Medium | Validation layer catches before reducer. Retry with L3 on failure. |
| Signal container reliability | Medium | Medium | Reconnect logic. Web chat always available as fallback. |
| AI costs higher than modeled | Low | Medium | 50 turns/week cap bounds worst case. Monitor weekly. |
| Nobody signs up | Medium | High | Ship fast. ~6 weeks, not 6 months. Signal demo is compelling. |
| Abuse (free tier gaming) | Medium | Low | Turn cap + footer discourages commercial abuse. |
| Published pages used for phishing | Low | High | XSS scanner. Report button. Monitor. |
| Stripe webhook issues | Low | Medium | Idempotent handlers. Manual override in DB if needed. |

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Signal in v1 (not post-launch) | Core differentiator. "Update your page from a text" is the demo moment. |
| $10/mo Pro (not $16) | Under "lunch money" threshold. Notion Plus pricing. |
| 50 turns/week (not per-aide) | Simple, predictable, prevents abuse. Covers both web + Signal turns. |
| Magic link auth (not Google OAuth) | No Google dependency. ~50 lines of code. Works for any email. |
| Neon Postgres (not SQLite) | RLS, managed, scale-to-zero. Supports multi-user patterns later. |
| Railway (not Hetzner DIY) | Zero ops. Git-push deploys. $5/mo. |
| `/s/{slug}` prefix (not clean URLs) | Route safety — avoids collisions with `/auth`, `/api`, `/dashboard`. |
| Event sourcing + declarative primitives | Deterministic replay, cheaper over time, distributable engine. |
| L2/L3 tiering (not single model) | 90% of calls at $0.001 vs $0.02-0.05. Cost-effective at scale. |
| No team tier at launch | Solo operators first. Don't build for users you don't have. |
| "Made with AIde" footer on free | The billboard. Every published page is marketing. |
| Python/FastAPI | 94 commits of working code. Bottleneck is LLM API, not server. |

---

## Supersedes

This document replaces both `aide_launch_plan.md` (v1) and `aide_mvp_checklist.md`. The MVP checklist was written for a dogfood-only, Signal-first scope. This plan targets a public product with Signal as a v1 feature rather than a deferred post-launch addition.
