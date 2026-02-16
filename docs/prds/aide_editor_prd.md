# AIde — Editor PRD

**Author:** Zach Cancio
**Date:** 2026-02-15
**Status:** v1 specification
**Depends on:** aide_prd.md, aide_living_objects.md, aide_renderer_spec.md

---

## What the Editor Is

The editor is the web ear. It's how users talk to their aide from a browser. It is not a page builder, not a WYSIWYG tool, not a code editor. It's a chat interface with a live preview of the aide's current state.

The conversation is the input. The preview is the output. Both are always visible.

---

## Layout

The preview is the page. It fills the entire viewport and scrolls naturally. The chat is a floating overlay pinned to the bottom — a persistent input bar with expandable conversation history. You're looking at the aide and talking to it at the same time.

### Structure

```
┌─────────────────────────────────────────────────────────────┐
│  ← Dashboard    Poker League Schedule (click to edit)   ⚙   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                                                             │
│              Rendered aide HTML (full viewport)              │
│              scrollable, the actual page                     │
│                                                             │
│                                                             │
│                                                             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ▲ conversation history (expandable)                │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │  [📎] [🎤] What are you running?                  [Send] │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Chat Overlay

The chat bar is pinned to the bottom of the viewport. It floats over the preview with a subtle backdrop blur and shadow.

**Collapsed state (default):** Just the message input bar. One line. Minimal footprint — most of the screen is the aide.

**Expanded state:** Tapping the conversation history toggle (▲) or scrolling up on the chat expands it to show recent messages. Max height: 60% of viewport. The preview remains visible behind it, dimmed slightly.

**Fully collapsed:** After sending a message and seeing the preview update, the chat can auto-minimize back to just the input bar after a few seconds of inactivity. The user is here to see the page, not to read chat history.

### Desktop vs Mobile

The layout is the same on all screen sizes. The preview is always full viewport. The chat overlay is always pinned to the bottom. No split-pane, no stacking, no breakpoint-driven layout changes.

On desktop, the chat overlay might be narrower (max-width: 640px, centered or right-aligned) to avoid spanning the full width of a wide monitor. On mobile, it spans the full width.

```
Desktop (wide):                          Mobile:
┌──────────────────────────────┐         ┌─────────────────┐
│                              │         │  ← Title     ⚙  │
│    Preview (full page)       │         ├─────────────────┤
│                              │         │                 │
│                              │         │  Preview        │
│                              │         │  (full page)    │
│       ┌──────────────┐       │         │                 │
│       │ Chat overlay  │       │         │ ┌─────────────┐│
│       │ (centered)    │       │         │ │ Chat overlay ││
│       └──────────────┘       │         │ └─────────────┘│
└──────────────────────────────┘         └─────────────────┘
```

---

## Chat Overlay

The chat overlay is the input surface. It's a floating bar at the bottom of the screen with expandable history above it.

### Input Bar

- Single-line text input that grows to multiline as needed (max 4 lines before scroll).
- Image attachment button (left of input): opens file picker. Supports drag-and-drop onto the overlay.
- Voice input button (microphone icon, between image and text input): tap to start recording, tap again to stop. Transcribed text populates the input field for review before sending.
  - Primary: browser `SpeechRecognition` API (Web Speech API). Free, real-time streaming transcription into the input field. Works in Chrome and Safari.
  - Fallback: server-side Whisper via OpenAI API (~$0.006/min). Activates automatically when `SpeechRecognition` is unavailable (Firefox, older browsers). Records audio client-side as WebM/Opus, sends to backend, returns transcript.
  - Transcribed text appears in the input field — user can review and edit before sending. Voice never auto-sends.
  - Visual: microphone icon pulses red while recording. Input field shows real-time interim transcription (browser API) or a "Transcribing..." indicator (Whisper fallback).
- Send button (right of input). Enter to send, Shift+Enter for newline.
- Input is disabled while the aide is processing. Show a subtle typing indicator (pulsing dots), not a spinner.
- Backdrop: frosted glass effect (`backdrop-filter: blur`) with a top shadow. The preview is visible but receded behind it.

### Conversation History

- Expand by tapping the ▲ toggle or swiping up on the overlay.
- Shows recent messages in reverse chronological order (newest at bottom, near the input).
- Max expanded height: 60% of viewport. The top of the preview is still visible.
- User messages: right-aligned, subtle background.
- Aide responses: left-aligned, no background. Voice rules apply — state reflections only.
- Image attachments: inline thumbnail in the message, expandable on click.
- "Page updated." indicator after each turn that mutated state — minimal, not a toast.
- Auto-collapse: after 3 seconds of inactivity following a send, the history collapses back to just the input bar. The user came to see the page.

### History Loading

- Full conversation history loads when opening an aide. Scrollable within the expanded overlay.
- No pagination — load all messages. Context window management is server-side.
- Timestamps: relative ("2 min ago", "yesterday") on hover, not always visible.

---

## Preview

The preview is the page itself, filling the entire viewport behind the chat overlay.

### Rendering

- The preview is a sandboxed `<iframe>` that fills the viewport (minus the header).
- The iframe reloads after each AI response that mutates state. Not on every keystroke — per turn.
- The rendered HTML is the same output the renderer produces for published pages. What you see is what gets published.
- The preview scrolls naturally. The user can scroll the aide while the chat overlay stays pinned at the bottom.

### Update Behavior

- After a turn that changes state, the iframe refreshes.
- Changed elements get a subtle highlight pulse: 150–250ms fade, light background highlight, then gone. This shows what changed without being intrusive.
- No toast notifications. No "Page updated!" banners. The visual change in the preview *is* the notification.
- If the aide responds but nothing changes visually (e.g., an advisory response), the preview doesn't refresh.

### Interaction

- The preview is read-only. No clicking to edit, no drag-to-reorder, no inline editing.
- Links in the preview open in a new tab (not inside the iframe).
- Scroll position in the preview is preserved across refreshes when possible. If the changed content is off-screen, auto-scroll to it.

---

## Header

Minimal. Information-dense.

```
┌─────────────────────────────────────────────────────────────┐
│  ← Dashboard    Poker League Schedule (click to edit)   ⚙   │
└─────────────────────────────────────────────────────────────┘
```

- **← Dashboard**: returns to the aide list.
- **Title**: inline editable. Click to rename. No modal, no confirmation.
- **⚙ Settings**: opens a panel/drawer with aide settings (slug, publish status, API provider, danger zone with delete/archive).

No publish button in the header. Publishing is a chat action: "publish this" or toggled in settings. The aide is the interface for its own lifecycle.

---

## Publish Flow

Publishing is controlled through conversation or settings, not through editor UI chrome.

### Via Chat

```
User: publish this
Aide: Published at toaide.com/s/poker-league
```

```
User: unpublish
Aide: Page removed from toaide.com/s/poker-league. Draft saved.
```

### Via Settings

- Toggle: Published / Draft
- Slug field (editable for Pro, random for free)
- "Copy link" button next to the published URL

### Behavior

- Publishing uploads the current rendered HTML to R2 at `aide-published/{slug}/index.html`.
- Subsequent state changes auto-republish if the aide is in published status. The user doesn't manually republish after every edit.
- Unpublishing removes the file from R2. The slug is released.

---

## Settings Panel

Drawer that slides in from the right, or a route on mobile. Not a modal.

### Sections

**Page**
- Title (same as header, editable)
- Slug (editable for Pro, read-only random for free, with upgrade CTA)
- Status: Published / Draft toggle
- Published URL (if published): copyable link

**AI Provider**
- Managed (default) — show remaining turns this week
- BYOK — API key input fields per provider (Anthropic, OpenAI, Gemini)

**Danger Zone**
- Archive aide
- Delete aide (with confirmation: type aide title to confirm)

---

## Empty State

First visit to a new aide. No messages, no content.

```
┌─────────────────────────────────────────────────────────────┐
│  ← Dashboard    Untitled                                ⚙   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                                                             │
│                                                             │
│                    This page is empty.                       │
│                                                             │
│                                                             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  [📎] [🎤] What are you running?                  [Send] │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

- Preview: the renderer's empty state — "This page is empty." centered, light gray.
- Chat overlay: just the input bar. Placeholder: "What are you running?"
- No conversation history to expand. No template picker. No onboarding wizard.

---

## Responsive Behavior

The layout is the same at all screen sizes — full-viewport preview with a floating chat overlay at the bottom.

| Breakpoint | Preview | Chat overlay |
|------------|---------|-------------|
| ≥1024px | Full viewport | Centered, max-width 640px |
| 768–1023px | Full viewport | Centered, max-width 560px |
| <768px | Full viewport | Full width, edge-to-edge |

The chat overlay has consistent bottom padding to clear the input bar on mobile (accounting for iOS safe area / Android nav bar).

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Enter | Send message |
| Shift+Enter | New line in message |
| Cmd/Ctrl+K | Focus message input |
| Escape | Blur message input |

No shortcut for publish, undo, or other editor-like actions. This is a chat, not an editor.

---

## What the Editor Is Not

- **Not a page builder.** No drag-and-drop. No component palette. No property panels.
- **Not a code editor.** No HTML view, no CSS editor, no "view source."
- **Not a design tool.** Style changes happen through conversation: "make the header blue," "use a wider layout," "switch to a serif font." The preview shows the result.
- **Not a collaboration surface.** v1 is single-writer. Multi-user editing (if ever) comes through group chat ears, not through shared cursors in the editor.

The editor is a full-page preview with a chat overlay at the bottom. You're looking at the aide and talking to it. The conversation floats. The page is primary. But both are always present because some things — football squares, styled grids, event pages with specific aesthetics — need a visual feedback loop.

---

## Technical Notes

### Preview Iframe

- Use `srcdoc` attribute to inject rendered HTML directly — no network round-trip.
- Iframe fills the viewport below the header: `position: absolute; top: header-height; bottom: 0; width: 100%;`
- Sandbox: `sandbox="allow-same-origin"` — no scripts, no forms, no popups. The preview is a pure visual render.
- CSP on the iframe should block all external resources except fonts (Google Fonts).

### Chat Overlay

- `position: fixed; bottom: 0;` with `z-index` above the iframe.
- Backdrop: `backdrop-filter: blur(12px); background: rgba(255,255,255,0.85);` with a subtle `box-shadow` on top edge.
- Expanded history scrolls internally. Max-height transition for smooth expand/collapse.
- Safe area padding: `padding-bottom: env(safe-area-inset-bottom);` for iOS.

### State Flow

```
User sends message
  → Chat overlay shows typing indicator
  → Backend processes (L2/L3 → primitives → reducer → renderer)
  → Response returns: { message: "...", html: "...", mutated: true/false }
  → Chat overlay appends aide message in expanded history
  → If mutated: preview iframe updates via srcdoc
  → If published: R2 upload happens async (user doesn't wait)
  → After 3s inactivity: chat history auto-collapses to input bar
```

### Image Input

- Accept: JPEG, PNG, WebP, HEIC (convert HEIC server-side).
- Max size: 10MB.
- Images are sent as base64 in the message payload to the AI provider.
- Thumbnail shown in chat immediately (client-side preview before upload).
- Images trigger L3 routing (vision-capable model).

### Voice Input

Two-tier speech-to-text: browser API as default, server-side Whisper as fallback.

**Browser SpeechRecognition API (primary)**
- Check `window.SpeechRecognition || window.webkitSpeechRecognition` on load.
- `continuous: false`, `interimResults: true`, `lang: 'en-US'` (detect from browser locale).
- Stream interim results into the input field in real time. Replace with final result on `onresult` with `isFinal: true`.
- Handle `onerror` gracefully — if `not-allowed`, show a one-time permissions prompt. If `network` or `no-speech`, fall back to Whisper.
- No audio leaves the device. Free. No server cost.

**Whisper fallback (server-side)**
- When `SpeechRecognition` is unavailable, record audio client-side using `MediaRecorder` API.
- Format: WebM/Opus (smallest size, Whisper supports natively).
- Max recording duration: 120 seconds. Show a countdown timer.
- On stop: upload audio to `POST /api/transcribe` → server sends to OpenAI Whisper API → returns `{ text: "..." }`.
- Cost: ~$0.006/minute. At 30s average recording, ~$0.003 per voice message. Counts toward the user's turn budget — the transcription is the input, not an extra turn.
- Server endpoint is rate-limited: same as managed AI turns (free tier budget applies).

**Input field behavior**
- While recording (either method): microphone icon pulses red, input field placeholder shows "Listening..."
- Browser API: interim text streams into input field live. User sees words appearing.
- Whisper: after recording stops, input shows "Transcribing..." then populates with result.
- In both cases: text lands in the input field. User can edit, append, or delete before hitting Send. Voice is a text input method, not a separate message type.

---

## Design Principles

1. **The page is primary.** The preview fills the viewport. The chat floats on top. You're looking at the aide, not at a chat window with a preview attached.
2. **The chat is a whisper.** The input bar is minimal. History expands on demand and collapses after use. The chat gets out of the way so you can see what you're building.
3. **Refresh, don't stream.** The preview updates once per turn. No partial renders, no flickering, no streaming HTML. The user sees the stable result.
4. **Show what changed.** A brief highlight on mutated elements is the only feedback. No toasts, no modals, no "successfully updated" messages.
5. **Same layout everywhere.** Desktop and mobile are the same model — full-page preview, floating chat overlay. No breakpoint-driven layout shifts.
6. **Infrastructure aesthetic.** The editor should feel like a utility — clean, fast, invisible. The chrome disappears. The aide is what you see.
