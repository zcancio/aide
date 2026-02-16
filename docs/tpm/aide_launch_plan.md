# AIde — Launch Plan

**Goal:** Ship a public product that someone can sign up for, build a page, and share it.
**Starting point:** 94-commit Vibez codebase with working editor, chat, publishing, versioning, and 3-provider AI support.
**What's missing:** Rebrand, auth (magic links), multi-aide management, rate limiting, Stripe, landing page.

---

## Phase 0: Foundation (1 week)

_Get the house in order before anything user-facing._

### 0.1 Domain & Hosting
- [ ] Register toaide.com (Cloudflare Registrar)
- [ ] Create Railway project, connect GitHub repo
- [ ] Add `railway.toml` with start command (migrations + uvicorn)
- [ ] Set Railway custom domains: `toaide.com`, `editor.toaide.com`
- [ ] Configure Cloudflare DNS: CNAME records pointing to Railway
- [ ] Set all environment variables in Railway dashboard
- [ ] Verify SSL, deploy from main, health check passes

### 0.2 Rebrand the Codebase
- [ ] Find/replace `vibez` → `aide`, `Vibez` → `AIde` across backend, frontend, configs
- [ ] Update system prompt: "You are AIde" + new personality/instructions
- [ ] Update all URL references (`vibez.pub` → `toaide.com`)
- [ ] Update slug format: `toaide.com/s/{slug}` (namespaced under `/s/` for route safety)
- [ ] Rename repo if desired

### 0.3 Auth: Magic Links (No Google, No OAuth)
- [ ] Email sending: Resend account (free tier: 100 emails/day, 3,000/month)
- [ ] `magic_links` table: `id`, `email`, `token` (cryptographic random, 32 bytes hex), `expires_at` (15 min), `used` (boolean)
- [ ] `POST /auth/send` — validate email, generate token, store in DB, send email via Resend
- [ ] `GET /auth/verify?token=abc123` — validate token exists, not expired, not used → mark used → create/find user → issue JWT cookie
- [ ] Session management: HTTP-only, Secure, SameSite=Lax cookie with signed JWT (24-hour expiry)
- [ ] Magic link email template: clean, branded, "Sign in to AIde" button + fallback raw link
- [ ] Rate limit: max 5 magic links per email per hour, max 20 per IP per hour
- [ ] Cleanup: background task deletes expired/used tokens older than 1 hour
- [ ] Remove all Cloudflare Access JWT validation code
- [ ] Remove `Cf-Access-Jwt-Assertion` header dependencies
- [ ] Test: request link → receive email → click → land in dashboard → sign out → repeat
- [ ] **No Google dependency. No OAuth complexity. ~50 lines of auth code.**

---

## Phase 1: Multi-AIde & Core Product (2 weeks)

_Transform from "one workspace per user" to "multiple aides per user."_

### 1.1 Data Model
- [ ] SQLite schema:
  - `users` (id, email, name, tier, created_at, turn_count, turn_week_start)
  - `aides` (id, user_id, title, slug, status [draft/published/archived], created_at, updated_at)
  - `conversations` (id, aide_id, messages JSON, created_at, updated_at)
- [ ] Migrate from filesystem-per-user to aide-based storage: `/data/aides/{aide_id}/`
- [ ] Each aide has its own conversation history (not one omniscient chat)

### 1.2 AIde Dashboard
- [ ] New landing view after login: grid/list of user's aides
- [ ] Each card shows: title, thumbnail (screenshot or first 100 chars), status badge, last edited
- [ ] "New AIde" button → enters editor with blank workspace
- [ ] Click existing aide → enters editor with that aide's files + conversation
- [ ] Archive/unarchive aides
- [ ] Delete aide (with confirmation)

### 1.3 Editor Updates
- [ ] Editor layout: full-viewport preview with floating chat overlay pinned to bottom
- [ ] Chat overlay: input bar at bottom, expandable conversation history (max 60% viewport), auto-collapse after inactivity
- [ ] Chat overlay styling: backdrop blur, subtle top shadow, centered max-width 640px on desktop, full-width on mobile
- [ ] Preview is a sandboxed iframe filling the viewport below the header, refreshes per AI turn via `srcdoc`
- [ ] Subtle highlight pulse (150–250ms fade) on changed elements in preview after each update
- [ ] Same layout on all screen sizes — no split-pane, no stacking, no breakpoint-driven layout changes
- [ ] Image input: file picker + drag-and-drop, JPEG/PNG/WebP/HEIC, 10MB max, triggers L3 routing
- [ ] Voice input: microphone button in input bar, two-tier speech-to-text
  - Browser `SpeechRecognition` API as default (free, Chrome/Safari, real-time streaming into input field)
  - Server-side Whisper fallback via OpenAI API (~$0.006/min) when browser API unavailable (Firefox, older browsers)
  - Transcribed text populates input field for review before sending — never auto-sends
  - `POST /api/transcribe` endpoint: accepts WebM/Opus audio, returns `{ text: "..." }`, rate-limited same as AI turns
- [ ] Editor header shows aide title (editable inline)
- [ ] "Back to Dashboard" button
- [ ] Publish flow now creates/updates the aide's slug in DB
- [ ] Published URL: `toaide.com/s/{slug}` (namespaced for route safety)

### 1.4 Published Page Serving
- [ ] Route `toaide.com/s/{slug}` → serve from `/data/aides/{aide_id}/published/`
- [ ] "Made with AIde" footer injected on free tier pages
- [ ] Footer links to `toaide.com` (the billboard)
- [ ] Published pages served with proper cache headers

---

## Phase 2: Rate Limiting & Managed API (1 week)

_Control costs and enable the free tier to actually work._

### 2.1 Turn Counting
- [ ] Track AI turns per user in SQLite: `turn_count` + `turn_week_start`
- [ ] 1 turn = 1 user message → 1 AI response (tool calls don't count extra)
- [ ] Weekly reset: when `now - turn_week_start > 7 days`, reset count
- [ ] Check before processing: if free user && turn_count >= 50, reject with upgrade message
- [ ] Pro users: unlimited (no check)

### 2.2 Turn Counter UI
- [ ] Show remaining turns in editor: "37 turns left this week"
- [ ] Update after each turn
- [ ] At 45/50: yellow warning
- [ ] At 50/50: disabled input + upgrade CTA
- [ ] Weekly reset display: "Resets Sunday at midnight"

### 2.3 Managed API Keys
- [ ] Server-side API keys for managed users (stored in env vars, not user-facing)
- [ ] Blended routing: 70% Haiku, 30% Sonnet (based on message complexity)
- [ ] Simple heuristic for routing: short messages / simple edits → Haiku, longer / complex → Sonnet
- [ ] BYOK users bypass managed routing entirely (existing behavior)

---

## Phase 3: Payments (1 week)

_Let people give you money._

### 3.1 Stripe Integration
- [ ] Stripe account setup
- [ ] Single product: "AIde Pro" — $10/month
- [ ] Stripe Checkout session for upgrade flow
- [ ] Webhook handler: `checkout.session.completed` → update user tier to pro
- [ ] Webhook handler: `customer.subscription.deleted` → downgrade to free
- [ ] Webhook handler: `invoice.payment_failed` → grace period logic

### 3.2 Upgrade Flow
- [ ] "Upgrade to Pro" button in dashboard header
- [ ] Upgrade CTA in rate limit message (when hitting 50 turns)
- [ ] Upgrade CTA on aide creation when at free limit (if you add aide limits later)
- [ ] Post-upgrade: immediate access, "Made with AIde" footer removed, turn limit lifted
- [ ] Settings page: manage subscription, see billing history, cancel

### 3.3 Pro Features
- [ ] Remove "Made with AIde" footer on published pages
- [ ] Unlimited AI turns
- [ ] Custom slugs (free tier gets random slugs only)
- [ ] Later: password-protected pages, analytics, PDF export

---

## Phase 4: Landing Page & Launch (1 week)

_The thing people see before they sign up._

### 4.1 Landing Page (toaide.com)
- [ ] Hero: "For what you're running." + one-line explainer
- [ ] Demo: auto-playing conversation → live page building (from existing vibe demos)
- [ ] Use cases: 3-4 examples with screenshots (poker league, wedding, pricing page, trip)
- [ ] Pricing: Free (50 turns/week, "Made with AIde" footer) vs Pro ($10/mo, unlimited)
- [ ] "Sign up free" CTA → enter email → magic link → dashboard
- [ ] Mobile responsive

### 4.2 Seed Templates
- [ ] 4-6 starter templates users can remix on first visit:
  - Poker league schedule
  - Wedding logistics page
  - Freelancer pricing/services
  - Trip itinerary
  - QBR / team update
- [ ] "Start from template" option on dashboard alongside "New blank aide"
- [ ] Templates are just pre-built aides that get cloned into user's account

### 4.3 Launch Checklist
- [ ] Error monitoring (Sentry free tier)
- [ ] Backup: Neon PITR (automatic) + R2 durability (automatic) + Railway deploy history
- [ ] Rate limiting on auth endpoints (prevent brute force)
- [ ] Published page safety: basic XSS scanning, no phishing patterns
- [ ] Terms of Service + Privacy Policy (can be simple markdown pages)
- [ ] `robots.txt` and basic SEO meta tags on landing + published pages
- [ ] Open Graph tags on published aides (so they preview nicely when shared)
- [ ] Test full flow: sign up → create aide → edit → publish → share → view

---

## Phase 5: Post-Launch (ongoing)

_Ship, then iterate based on what actually happens._

### 5.1 Week 1-2 After Launch
- [ ] Monitor: error rates, response times, turn usage patterns
- [ ] Watch for abuse: free tier gaming, content issues
- [ ] Gather feedback: what do first users actually make?
- [ ] Fix the top 3 bugs

### 5.2 Growth Loops
- [ ] Remix flow: "Use this as a template" button on published pages
- [ ] Share tracking: which aides get viewed most?
- [ ] Template gallery: curated page of best community aides
- [ ] "Made with AIde" footer click-through tracking

### 5.3 Later Features (don't build until needed)
- [ ] Passkey auth (WebAuthn) as faster sign-in alongside magic links
- [ ] Conversation compression at context window limits
- [ ] Provider locking (prevent mid-convo provider switching)
- [ ] Custom domains for published aides
- [ ] Team/collaboration features
- [ ] Analytics dashboard for published aides
- [ ] PDF export
- [ ] API for programmatic aide updates

---

## Timeline

| Phase | Duration | What ships |
|-------|----------|------------|
| **Phase 0** — Foundation | 1 week | New domain, rebrand, magic link auth |
| **Phase 1** — Multi-AIde | 2 weeks | Dashboard, per-aide workspaces, clean URLs |
| **Phase 2** — Rate Limiting | 1 week | 50 turns/week, managed API routing, turn counter UI |
| **Phase 3** — Payments | 1 week | Stripe, $10/mo Pro, upgrade flow |
| **Phase 4** — Landing & Launch | 1 week | Landing page, templates, launch checklist |
| **Total** | **~6 weeks** | **Public launch** |

---

## What's NOT in v1

Explicitly descoped to avoid scope creep:

- **Team tier** — Solo users first. Teams come after PMF.
- **Custom domains** — Nice but not blocking anyone from using the product.
- **Analytics** — Know how many views? Later. Ship first.
- **PPTX export** — Stretch goal from original PRD. Cut.
- **Real-time collaboration** — Not needed for solo operators.
- **Template marketplace with payments** — Level 0 (free remixes) only at launch.
- **Conversation compression** — Only matters at scale. Build when someone hits the context limit.
- **Mobile app** — Web-first. Mobile-responsive editor is enough.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Auth implementation has a bug | Low | High | Magic links are ~50 lines of code. Simple to audit. Test the full flow. |
| AI costs higher than modeled | Low | Medium | 50 turns/week cap bounds worst case. Monitor weekly. |
| Nobody signs up | Medium | High | Ship fast. 6 weeks, not 6 months. Iterate on what you learn. |
| Abuse (free tier gaming) | Medium | Low | Turn cap + "Made with AIde" footer discourages commercial abuse. |
| Published pages used for phishing | Low | High | Existing safety scanner. Add report button. Monitor. |
| Stripe webhook issues | Low | Medium | Idempotent handlers. Manual override in DB if needed. |

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| $10/mo Pro (not $16) | Notion Plus pricing. Under "lunch money" threshold. |
| 50 turns/week (not per-aide) | Simple, predictable, prevents abuse at $3.28 worst case. |
| Magic link auth (not Google OAuth) | No Google dependency. Simpler code (~50 lines). Works for any email. Resend free tier covers launch. |
| No Google infrastructure | Avoid dependency on Google for auth, analytics, or email. Resend for email, Neon for DB, R2 for storage. |
| SQLite (not Postgres) | ~~Single server. No ops overhead.~~ **Changed: Neon Postgres.** RLS, managed, scale-to-zero. |
| Railway (not Hetzner DIY) | Zero ops. Git-push deploys. No SSH, no Docker, no systemd. $5/mo. |
| No team tier at launch | Solo operators first. Don't build for users you don't have. |
| Random slugs for free, custom for Pro | Upgrade trigger. Free pages still shareable. |
| "Made with AIde" footer on free | The billboard. Every published page is marketing. |
| Python/FastAPI (not Go/Rust) | 94 commits of working code. Bottleneck is LLM API, not server. |
| `/s/{slug}` prefix (not bare `/{slug}`) | Namespace safety. Avoids slug collisions with future routes. Nobody types URLs — they copy-paste. |
| Full-viewport preview with chat overlay (not split-pane) | The page is primary. Chat floats at the bottom, expands on demand, auto-collapses. Same layout on all screen sizes. Visual aides need a feedback loop; the overlay provides it without splitting attention. |
| Voice input in v1 (browser API + Whisper fallback) | "Tell the aide what changed" should mean literally telling it. Browser SpeechRecognition is free for Chrome/Safari; Whisper fallback covers Firefox at ~$0.003/message. Text lands in input field for review, never auto-sends. |
