# AIde Engine Distribution Strategy

**Date:** February 15, 2026
**Status:** Implementation plan
**Context:** AIde is a conversational web page editor that creates living pages. This doc explains how to distribute the AIde engine across every Claude surface, with a single source of truth that stays current as the engine improves through evals.

---

## Kernel vs. Engine

**The kernel** is the core of AIde: primitives, events, reducer, renderer, and validator. Pure functions, deterministic, no AI. The kernel is the same whether it runs on the AIde server or in a Claude conversation. It is the trust boundary — nothing touches state except through primitives that the kernel validates and applies.

**The engine** is the kernel packaged for distribution. It wraps the kernel in a skill — adding the L2 intent compilation instructions (SKILL.md), voice rules, examples, and evals — so that Claude can act as the brain that feeds primitives into the kernel.

```
kernel = primitives + events + reducer + renderer + validator
engine = kernel + SKILL.md + voice rules + examples + evals
```

The engine has two layers:

**L2 intent compilation (Claude's job).** Understand natural language ("Mike's out, Dave's subbing") and compile it into primitive events (`entity.update` on the roster). This is the AI part. It lives in prose instructions in SKILL.md and improves through prompt iteration and evals.

**Kernel execution (code's job).** Validate events, apply them to the snapshot, render HTML. These are the pure functions — `reducer.py`, `renderer.py`, `validator.py` — that produce identical output every time. Same code runs everywhere.

```
engine/
├── SKILL.md                  ← orchestration + L2 intent compilation instructions
├── scripts/
│   ├── reducer.py            ← reduce(snapshot, event) → snapshot  ┐
│   ├── renderer.py           ← render(snapshot, blueprint) → HTML  │ kernel
│   ├── validator.py          ← validate(event, snapshot) → pass    │
│   └── primitives.py         ← schema definitions, field types     ┘
├── references/
│   ├── voice-rules.md        ← AIde voice system (no first person, no emojis, etc.)
│   └── primitive-catalog.md  ← all 22 primitives with payload shapes
├── evals/
│   └── evals.json            ← test cases with expectations
└── examples/
    └── poker-league.html     ← reference output
```

Claude handles the fuzzy part (what did the user mean?). The kernel handles the precise part (apply it correctly, render it identically). This split means the engine gets smarter at understanding without risking correctness in execution.

---

## Single Source of Truth

The engine is hosted at a public URL:

```
https://toaide.com/engine/v1/SKILL.md
https://toaide.com/engine/v1/scripts/reducer.py
https://toaide.com/engine/v1/scripts/renderer.py
...
```

Static files served from Cloudflare R2. When evals produce an improved engine, push updated files to R2. Every surface fetches the latest on next use.

Versioned paths allow rollback:

```
/engine/v1/    ← stable, current
/engine/v2/    ← next version, testing
/engine/latest/ → symlink to current stable
```

The eval loop:

```
engine v1 → run evals → analyze failures → improve SKILL.md/scripts
    → push v2 to R2 → test against evals → promote to stable
    → every surface picks up v2 on next conversation
```

No re-deploying plugins. No updating Project files. No syncing repos. One push, everywhere updates.

---

## Distribution by Surface

### 1. claude.ai Web — Projects

**Setup:** User creates a Claude Project with one instruction line.

**Project system prompt:**
```
Before building or updating any aide, fetch the latest engine:
https://toaide.com/engine/v1/SKILL.md

Read it completely. Follow it exactly. If the skill references scripts
(reducer.py, renderer.py, etc.), fetch and execute those too.
```

**How it works:**
1. User describes what they're running, or pastes an existing aide URL
2. Claude `web_fetch`es the SKILL.md from toaide.com
3. Claude follows the skill: compile intent → run reducer script → run renderer script → produce HTML artifact
4. User sees the rendered aide in the artifact panel
5. User says "Mike's out this week" → Claude fetches engine again, reads the artifact's embedded JSON, applies the reducer, produces updated artifact

**What works:**
- Engine always current (fetched per conversation)
- Full creation and reducer mode
- Scripts execute in the computer use sandbox
- Artifact renders the aide inline — user sees the living page

**Limitations:**
- User must set up the Project themselves (one-time, one line)
- Can't publish to toaide.com — no outbound POST from sandbox
- Conversation-scoped — aide lives in the chat, not at a URL
- Can't call the AIde API

**Role in funnel:** Free tier experience. User maintains an aide through conversation in claude.ai. When they want a shareable URL, multi-user access, or Signal integration, they upgrade to toaide.com.

---

### 2. Claude Mobile — Same as Web

Identical to claude.ai web. Projects sync across devices, so a Project configured on desktop works on mobile. Same fetch-based engine sync, same artifact-based aide maintenance.

The mobile experience is actually compelling: user gets a text from their poker group ("Mike's out"), opens Claude on their phone, tells it "Mike's out, Dave's subbing," and the aide artifact updates. They see the updated roster right there.

Same limitations as web — no publishing, conversation-scoped.

---

### 3. Claude Code — Skill + MCP

**Setup:** User installs the aide-builder skill in their repo or globally.

**Repo structure:**
```
aide/
├── skills/
│   └── aide-builder/
│       ├── SKILL.md          ← thin wrapper that fetches latest engine
│       ├── evals/
│       └── examples/
├── .claude/
│   └── commands/
│       └── build-aide.md     ← /project:build-aide slash command
└── CLAUDE.md                 ← references skills/aide-builder
```

**The local SKILL.md is a thin pointer:**
```markdown
---
name: aide-builder
description: Build and maintain AIde living pages from natural language.
---
Before starting, fetch the current engine from:
https://toaide.com/engine/v1/SKILL.md
Read it. Follow it exactly.
```

**How it works:**
1. User runs `/project:build-aide I run a poker league, 8 guys...`
2. Claude Code reads the local SKILL.md, fetches the remote engine
3. Claude Code has full filesystem access — downloads scripts, executes them
4. Produces an HTML file in the working directory

**With MCP (full integration):**

An MCP server connects Claude Code to the AIde API:

```json
// .mcp.json
{
  "mcpServers": {
    "aide": {
      "type": "sse",
      "url": "https://get.toaide.com/mcp",
      "headers": {
        "Authorization": "Bearer ${AIDE_API_KEY}"
      }
    }
  }
}
```

This exposes tools:
- `aide_create(description)` — create a new aide, return URL
- `aide_apply_events(aide_id, events)` — apply primitives through the real server reducer
- `aide_get_state(aide_id)` — fetch current snapshot
- `aide_publish(aide_id)` — publish to toaide.com/p/{slug}

With MCP, Claude Code becomes a full aide management tool. User says "update my poker league — Mike's out" and it hits the real API. The aide at toaide.com updates. Other ears (Signal, web editor) see the change.

**What works:**
- Engine always current (fetched per session)
- Full filesystem and network access
- Scripts run natively (Python in terminal)
- MCP connects to real AIde API
- Can publish to toaide.com
- Evals run here via skill-creator

**Limitations:**
- Requires Claude Code (developer tool, CLI)
- MCP requires API key setup

**Role in funnel:** Power user / developer path. Also where evals run to improve the engine.

---

### 4. Cowork — Plugin + MCP

**Setup:** User installs the AIde plugin from the marketplace (or uploads it).

**Plugin structure:**
```
aide-plugin/
├── .claude-plugin/
│   └── plugin.json
│       {
│         "name": "aide",
│         "version": "1.0.0",
│         "description": "Build and maintain living pages for what you're running.",
│         "author": "Bantay LLC"
│       }
├── .mcp.json                 ← connects to toaide.com/mcp
├── commands/
│   ├── new-aide.md           ← /aide:new "I run a poker league..."
│   ├── update-aide.md        ← /aide:update "Mike's out this week"
│   └── publish-aide.md       ← /aide:publish
└── skills/
    └── aide-builder/
        └── SKILL.md          ← thin wrapper fetching remote engine
```

**How it works:**
1. User installs plugin from marketplace or `/plugin install aide`
2. User types `/aide:new I run a poker league, 8 guys, every other Thursday...`
3. Plugin's skill fetches the latest engine from toaide.com
4. Plugin's MCP connection hits the AIde API to create the aide
5. User gets back a live URL: `toaide.com/p/poker-league`
6. Later: `/aide:update Mike's out this week` → MCP pushes events to server

**Marketplace distribution:**

Plugins are discoverable at `claude.com/plugins` and installable with one click. The AIde plugin would appear alongside Anthropic's 11 official plugins (sales, legal, finance, etc.) and community submissions.

To submit: push the plugin repo to GitHub, then submit via the form at `claude.com/plugins`. Anthropic reviews submissions; verified plugins get an "Anthropic Verified" badge.

The plugin is a stable shell. It rarely changes. The engine it fetches from toaide.com changes constantly as evals improve it.

**What works:**
- Zero-friction install from marketplace
- Engine always current (fetched per task)
- MCP connects to real AIde API
- Full publish flow — user gets live URLs
- Non-technical users can manage aides from desktop
- Parallel task execution for complex operations

**Limitations:**
- Requires paid Claude plan (Pro $20/mo, Max $100/mo, Team, Enterprise)
- Desktop app must stay open during tasks
- Plugin marketplace still in research preview
- Org-wide plugin sharing not yet available (coming soon per Anthropic)

**Role in funnel:** Primary distribution channel. Non-technical users discover AIde through the plugin marketplace. They install, create an aide, get a live URL. This is the "another ear" that makes the living object thesis concrete — the aide doesn't care if input comes from Cowork, Signal, or the web editor.

---

## The Aide as a Living Artifact

On claude.ai and mobile, the aide HTML file lives as an artifact in the conversation. This is a self-contained living page the user maintains through conversation:

```
User: "I run a poker league, 8 guys..."
  → Claude fetches engine
  → Claude builds aide HTML
  → Artifact renders the page

User: "Mike's out this week. Dave's subbing."
  → Claude fetches engine
  → Claude reads artifact's embedded aide+json
  → Claude compiles intent → primitives
  → Claude runs reducer.py (via computer use)
  → Claude runs renderer.py
  → Updated artifact renders

User: "What are the current standings?"
  → Claude reads artifact's embedded aide+json
  → Responds from state (no engine fetch needed)
```

The artifact is the aide. The embedded JSON blocks (`aide+json`, `aide-events+json`, `aide-blueprint+json`) carry all state. Each conversation turn that modifies the aide produces a new artifact version with updated state and appended events.

The user can also download the HTML file at any time — it's a complete, self-contained page that works in any browser and carries its own blueprint for any LLM to continue maintaining it.

---

## MCP Server Specification

For Claude Code and Cowork, an MCP server on the AIde backend enables full integration.

**Endpoint:** `https://get.toaide.com/mcp` (SSE transport)

**Authentication:** Bearer token from magic link flow, or a dedicated API key generated in the AIde dashboard.

**Tools exposed:**

| Tool | Description | Parameters |
|------|-------------|------------|
| `aide_create` | Create a new aide from a description | `description: string` |
| `aide_get_state` | Get current snapshot for an aide | `aide_id: string` |
| `aide_apply_events` | Apply primitive events through the reducer | `aide_id: string, events: Event[]` |
| `aide_publish` | Publish aide to public URL | `aide_id: string, slug?: string` |
| `aide_list` | List user's aides | `status?: "draft" \| "published" \| "archived"` |
| `aide_fork` | Fork an existing aide | `aide_id: string` |

**Implementation:** FastAPI routes in `backend/routes/mcp.py` speaking the MCP SSE protocol. These routes call existing assembly layer methods — `load()`, `apply()`, `save()`, `publish()`. The MCP server is a thin transport layer over the existing API.

The MCP server is just another ear. Same reducer, same renderer, same storage. Different input channel.

---

## Engine Update Flow

```
1. Identify weakness
   ← eval failure, user feedback, new use case

2. Improve engine
   ← update SKILL.md prose, fix reducer.py bug, add renderer feature

3. Run evals
   ← skill-creator in Claude Code runs all test cases
   ← compare v(current) vs v(candidate)

4. Promote
   ← push updated files to R2 at /engine/v{next}/
   ← update /engine/latest/ symlink

5. Every surface picks up the new engine
   ← next claude.ai conversation fetches v{next}
   ← next Claude Code session fetches v{next}
   ← next Cowork task fetches v{next}
   ← server L2/L3 prompt updated (same content, different delivery)
```

No coordination needed across surfaces. The engine URL is the single sync point.

---

## What Gets Built When

### Now (pre-launch)
- [x] Engine skill with SKILL.md, voice rules, primitive catalog
- [x] Reference examples (poker league, renovation)
- [x] Eval suite (9 test cases covering creation and reducer modes)
- [ ] `reducer.py` — executable reducer from spec
- [ ] `renderer.py` — executable renderer from spec
- [ ] `validator.py` — event validation
- [ ] Host engine files on R2 at `toaide.com/engine/v1/`

### Phase 1 (with launch)
- [ ] Claude.ai Project template with fetch instruction (document on landing page)
- [ ] Claude Code skill in `skills/aide-builder/` pointing at remote engine
- [ ] `.claude/commands/build-aide.md` slash command

### Phase 2 (post-launch)
- [ ] MCP server endpoint on FastAPI backend (`/mcp`)
- [ ] Cowork plugin with MCP connection
- [ ] Submit plugin to marketplace
- [ ] API key generation in AIde dashboard (for MCP auth)

### Phase 3 (growth)
- [ ] Plugin customization guide (teams adapting aide-builder for their workflows)
- [ ] Engine versioning dashboard (which version is active, rollback controls)
- [ ] Eval CI pipeline (engine changes auto-run evals via GitHub Actions runner)

---

## Summary

The AIde kernel — primitives, events, reducer, renderer, validator — is the trust boundary. Nothing touches state without going through it. The engine wraps the kernel in a skill so Claude can act as the L2 compiler that feeds it. One URL syncs the engine everywhere.

| Surface | Install | Engine sync | Can publish? | API access? |
|---------|---------|-------------|--------------|-------------|
| claude.ai web | Project (1 line) | web_fetch per conversation | No | No |
| Claude mobile | Project (synced) | web_fetch per conversation | No | No |
| Claude Code | Skill in repo | fetch per session | Yes (MCP) | Yes (MCP) |
| Cowork | Plugin (1 click) | fetch per task | Yes (MCP) | Yes (MCP) |
| AIde server | System prompt | Direct (same kernel code) | Yes (native) | Yes (native) |

The living object doesn't care which ear it hears through. The kernel makes sure every mutation is valid. The engine makes sure every ear speaks the same language.
