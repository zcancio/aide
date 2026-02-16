# AIde — Product Requirements Document

**Product Name:** AIde
**Author:** Zach Cancio
**Last Updated:** 2025-02-12
**Status:** Draft v1

**What is AIde?** AIde is a living system that keeps what you're running coherent over time. You describe what you're running — a league, a budget, a renovation, a team — and AIde forms a page around it. As things change, you tell AIde. The page stays current. The URL stays the same. Continuity, not creation.

---

## 1. Problem Statement

People run things. Leagues, trips, budgets, events, projects, households. The state of what they're running lives across group chats, spreadsheets, notes apps, and memory. There is no single surface that reflects how things actually stand right now.

The tools available fall into two failure modes:

**Too heavy.** Project management software (Asana, Notion, Monday) assumes organizational structure, roles, workflows, and ongoing process. For most things people actually run — a poker night, a vacation rental group, a renovation timeline — this is absurd overhead.

**Too ephemeral.** Group chats and docs capture moments but not state. The budget is somewhere in a thread from three weeks ago. Who's bringing what is in a message nobody can find. Information decays into noise.

AIde solves this by maintaining a living page — a single, shareable URL that always reflects the current state of what you're running. You tell AIde what changed. The page updates. History is preserved. Nothing gets lost.

### What This Is

AIde is infrastructure for informal coordination. It sits between "I'll just text everyone" and "let's set up a project in Notion." It's for the things that need continuity but not process.

### What This Is Not

This is not a project manager. No Gantt charts. No assignee fields. No sprint planning.
This is not a website builder. No custom domains. No SEO. No design tools.
This is not a chatbot. No personality. No encouragement. No first person.

AIde is a quiet operator. It maintains state.

| | Group chats (iMessage, WhatsApp) | AIde |
|---|---|---|
| State visibility | Buried in scroll | Always current on the page |
| History | Scattered across threads | Chronological, structured |
| Shareability | "Check the chat" | One URL, always current |
| Updates | New message in a sea of messages | Page reflects new state |

| | Project tools (Notion, Asana) | AIde |
|---|---|---|
| Setup cost | Boards, views, properties, templates | "What are you running?" |
| Mental model | Manage a project | Keep a thing coherent |
| Overhead | Ongoing maintenance of the tool itself | Say what changed |
| Audience | Teams with process | Anyone running anything |

| | Docs (Google Docs, Notes) | AIde |
|---|---|---|
| Structure | Manual, degrades over time | Formed from what you say, maintained automatically |
| Currency | Stale unless manually updated | Updated through conversation |
| Sharing | Share a doc, hope people read it | One URL, always the latest |

The coordination spectrum:

```
Ephemeral, no structure                    Heavy process, full tooling
    │                                                          │
    ▼                                                          ▼
  Texts → Group chats → Shared docs → AIde → Notion/Asana → Jira
```

AIde occupies the space where something needs more coherence than a group chat but less ceremony than a project tool.

---

## 2. Target Users

**Primary:** People who run things informally — league commissioners, trip organizers, event planners, household coordinators, club treasurers, group project leads. People whose "tool" is currently a combination of texts, spreadsheets, and memory.

**Secondary:** Small teams and organizations that need lightweight coordination surfaces — a standup page, a shared budget tracker, an onboarding reference — without adopting a full project management suite.

**Use cases:**
- Fantasy/rec league → roster, schedule, standings, who's bringing what
- Group trip → itinerary, budget splits, lodging details, packing list
- Renovation → contractor contacts, timeline, budget, decisions log
- Recurring event → next occurrence details, rotation, history
- Shared household → chores, expenses, maintenance schedule
- Club/org treasury → balance, recent transactions, dues status
- Team standup → current priorities, blockers, recent changes
- Onboarding reference → contacts, tools, access, first-week checklist

---

## 3. Core Experience

The user visits the editor, describes what they're running, and AIde forms a page around it. Only what has been explicitly stated gets structured. As the user provides updates over time, AIde maintains the page — updating state, preserving history, keeping everything coherent.

### User Flow

```
1. Sign in (Google SSO via Cloudflare Access)
2. First visit: configure AI provider (BYOK or managed)
3. White screen. Cursor. "What are you running?"
4. "I run a poker league. 8 guys, we play every other Thursday..."
5. AIde forms a page: next game, players, rotation
6. Page is live at a shareable URL
7. Two weeks later: "Mike's out this week. Dave's subbing."
8. Page updates. History preserved: "Feb 12: Mike out, Dave subbing."
```

### The First Screen

White space. Cursor.

**What are you running?**

No template picker. No onboarding wizard. No tutorial overlay. No feature tour.

The page forms as the user speaks. Only structure what has been explicitly stated. No premature categories. No assumption scaffolding.

### What Makes This Different

| | ChatGPT / Claude Artifacts | AIde |
|---|---|---|
| Persistence | Gone when you close the chat | Permanent URL, always current |
| Continuity | New conversation, new context | Ongoing — pick up where you left off |
| Output | Sandboxed preview | Live, shareable page |
| Voice | Conversational AI personality | No personality — state reflections only |
| Provider | Single provider | BYOK — Anthropic, OpenAI, Gemini |

---

## 4. Feature Requirements

### 4.1 Authentication & Identity

| Requirement | Detail |
|---|---|
| Identity provider | Cloudflare Access with Google SSO |
| User identification | Email from `Cf-Access-Jwt-Assertion` header |
| JWT verification | Verify against Cloudflare's team domain public keys |
| Session management | Server-side session in HTTP-only cookie |
| Access control | Configurable email allowlist or domain patterns |
| Editor scope | Authentication gates editor subdomain only |
| Published pages | No authentication required — anyone with URL can view |

### 4.2 LLM Access (BYOK + Managed)

**BYOK is always available.** Users who have API keys can use them regardless of tier. No usage caps, no surcharge. Their key, their cost.

**Managed is the fallback.** For users who don't have their own API key, AIde provides managed access with a usage-based surcharge. This removes the "what's an API key?" friction.

| Requirement | Detail |
|---|---|
| BYOK providers | Anthropic, OpenAI, Gemini |
| Key storage | Browser localStorage only — never transmitted to server beyond per-request header |
| Key validation | Verify on entry with lightweight API call |
| Model selection | User picks from available models per provider |
| Provider locking | Once a conversation starts with a provider, model switching within that provider is allowed; switching providers mid-conversation is not |
| Managed access | Server-side key, usage metered, surcharge applied |

### 4.3 Conversation & State

| Requirement | Detail |
|---|---|
| Conversation model | Persistent, ongoing — not session-based |
| Storage | SQLite — messages, page state, history |
| Context management | Conversation compression at 85% context window |
| Compression method | LLM-powered summarization of older messages |
| Token counting | Provider-specific: tiktoken (OpenAI), API-based (Gemini), estimation (Anthropic) |
| History | Chronological log of state changes, human-readable |

### 4.4 Page System

The page is the core artifact. It is a living document that reflects the current state of what the user is running.

| Requirement | Detail |
|---|---|
| Format | HTML/CSS/JS — single file or multi-file workspace |
| Preview | Real-time in editor, iframe-based |
| Publishing | One click → shareable URL |
| URL structure | `aide.pub/s/{slug}` (or equivalent domain) |
| Updates | Page updates in place — URL never changes |
| Versioning | Each publish creates immutable snapshot |
| Version access | `/s/{slug}` = latest, `/s/{slug}/v3` = pinned |

### 4.5 AI Voice & Behavior

This is critical to the product identity. The AI layer must conform to the AIde voice system.

| Rule | Detail |
|---|---|
| No first person | Never "I updated..." — use state reflections |
| State over action | Show how things stand, not what was done |
| Mutation tone | Declarative, minimal, final: "Budget: $1,350." |
| Advisory tone | Structured, neutral, slightly explanatory |
| No encouragement | No "Great!", "Nice!", "Let's do this!" |
| No emojis | Never |
| No personality | AIde is infrastructure, not a character |
| Silence is valid | Not every action needs a response |

### 4.6 Tools

| Tool | Purpose |
|---|---|
| write_file | Create or overwrite page files |
| read_file | Read current page state |
| list_files | Inventory workspace contents |
| web_fetch | Pull live data for page content |

### 4.7 Update Visibility

| Requirement | Detail |
|---|---|
| Page updates | Immediate in preview |
| Animation | Subtle fade (150–250ms), highlight pulse on changed fields |
| No toast notifications | State change is visible on the page itself |
| No confetti | Ever |
| History | Accessible but not intrusive — chronological, typographic |

---

## 5. Architecture

### Domain Architecture

| Domain | Purpose | Auth |
|---|---|---|
| editor.aide.pub | Authenticated editing environment | Cloudflare Access (Google SSO) |
| aide.pub | Published pages, landing page | Public — no auth |

### Infrastructure

| Component | Detail |
|---|---|
| Server | Hetzner VPS (2GB) |
| Proxy | Cloudflare (tunneling, caching, SSL) |
| Backend | FastAPI (Python) |
| Database | SQLite |
| Real-time | WebSocket |
| AI integration | Direct API calls (not subprocess-based) |

### Key Architecture Decisions

- **Direct API over subprocess**: Agent SDK subprocess approach showed 8–15s response times due to memory contention on VPS. Direct API calls achieve ~1.3s.
- **Provider abstraction**: Frontend is agnostic to which AI engine is running. WebSocket event layer abstracts provider differences.
- **File I/O tools only**: No Docker sandbox. AI edits files directly through tool calls.

---

## 6. Information Architecture

### Status Indicators

Prefer: "Updated Feb 12" / "3 changes" / "Current as of..."
Avoid: "Success!" / "Completed!" / "You're all set!"

### History Log

Human-readable state summaries:

```
Feb 12
Next game: Mike's on snacks.

Feb 10
Budget: $1,350.

Feb 8
Airbnb confirmed. 4 nights.
```

No system jargon. No "Record updated successfully."

### Confirmations

Confirm through state, not dialogue.

Instead of: "Just to confirm, you want me to update the snack assignment to Mike?"
Prefer: "Next game: Mike's on snacks."

---

## 7. Growth & Distribution

### Natural Loop

Every AIde page gets shared — that's the point. The URL is the distribution.

```
User creates/updates a page → shares the link
    → Recipient sees current state + "Maintained with AIde"
    → Recipient starts their own
    → Shares their link → ...
```

### Growth Mechanics

- **"Maintained with AIde" footer** on free-tier pages. Removed on paid tier.
- **Remix**: Any published page can be forked as a starting point.
- **Embed mode**: iframe embed for Slack, Notion, internal tools.

### High-Value Early Use Cases

- Rec leagues (commissioners share with all members)
- Group trips (organizer shares with travelers)
- Recurring events (host shares with regulars)
- Small team coordination (lead shares with team)

### Distribution Channels

- Product Hunt / Show HN
- Reddit communities (fantasy sports, group travel, event planning)
- Word of mouth through shared pages
- The pages themselves are the marketing

---

## 8. Monetization

| Tier | Price | Includes |
|---|---|---|
| Free | $0 | BYOK only, "Maintained with AIde" footer, 3 active pages |
| Pro | $12/month | Managed AI access, no footer, unlimited pages, version history, custom slugs |
| Team | $8/seat/month | Shared pages, team-level defaults, admin controls |

BYOK is always free. Managed AI access is the primary revenue driver.

---

## 9. Planned Features

### 9.1 Conversation Compression

| Requirement | Detail |
|---|---|
| Trigger | 85% of context window capacity |
| Method | LLM-powered summarization of older messages |
| Token counting | Provider-specific methods |
| Preservation | Recent messages kept verbatim, older messages summarized |
| Transparency | User can view full history even after compression |

### 9.2 Collaborative Pages

Multiple users can update the same page. Each user's conversation with AIde is independent, but mutations apply to the shared page state.

### 9.3 Scheduled Updates

"Remind me to update the rotation after each game." AIde can prompt for updates on a schedule.

### 9.4 Data Import

Pull structured data from external sources — a Google Sheet for the budget, a URL for scores — and keep the page current.

---

## 10. Milestones

### M0: Prototype (Complete)
Single-user, Anthropic-only, basic chat-to-page loop. Proves the mechanic works.

### M1: AIde MVP
- Rebrand from Vibez to AIde
- Voice system implementation (no first person, state reflections)
- Provider abstraction (Anthropic, OpenAI, Gemini)
- Cloudflare Access auth + per-user workspaces
- BYOK setup flow
- Publishing: update page → URL stays current
- Landing page at aide.pub (or equivalent domain)
- Deploy to Hetzner VPS behind Cloudflare Tunnel

### M2: Continuity
- Conversation persistence (SQLite)
- Conversation compression
- Page versioning / snapshots
- History log (human-readable state changes)
- Page management (list, rename, unpublish, delete)

### M3: Growth
- Custom slugs
- Remix / fork published pages
- Embed mode
- "Maintained with AIde" footer with link
- Opt-in view count on published pages

---

## 11. Success Criteria

**M1 launch:**
- A non-technical user can describe what they're running and get a live, shareable URL in under 3 minutes
- The AI voice never uses first person, never encourages, never emotes
- Published pages load fast (<2s) and feel composed — editorial, not "default HTML"
- Three providers work interchangeably
- API keys are never stored server-side
- Total server cost under $10/month
- At least 3 people besides Zach are actively maintaining a page

**Brand test:**
- If someone says "I run everything through AIde" — the product has succeeded
- If the landing page feels like infrastructure, not software trying to impress — the design has succeeded
- If the AI responses feel like a ledger being updated, not a chatbot replying — the voice has succeeded

---

## 12. Design Litmus Test

Before shipping any UI, copy, or feature:

Does this feel like infrastructure?
Or does it feel like software trying to impress?

If it performs, remove it.
If it stabilizes, keep it.
