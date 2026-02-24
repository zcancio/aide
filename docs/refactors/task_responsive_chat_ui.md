# Task: Responsive Chat UI for aide Editor

Implement the aide editor's chat interface as a single responsive component that adapts between desktop (side panel) and mobile (bottom sheet) layouts. One codebase, one component tree, breakpoint-driven behavior.

**Reference mockups:** `aide_desktop_chat.html`, `aide_mobile_chat.html`

---

## Breakpoint

```
≥ 768px  →  Desktop layout (side panel)
< 768px  →  Mobile layout (bottom sheet)
```

Use a `useIsMobile` hook:

```javascript
function useIsMobile(breakpoint = 768) {
  const [mobile, setMobile] = useState(window.innerWidth < breakpoint);
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    const handler = (e) => setMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [breakpoint]);
  return mobile;
}
```

---

## Page Layout

### Desktop (≥ 768px)

```
┌──────────────────────────────────────────────┐
│  Nav Bar (fixed, full width)                 │
├──────────────────────────┬───────────────────┤
│                          │                   │
│   Aide Page (flex: 1)    │  Chat Panel       │
│   scrollable             │  360px fixed      │
│   max-width: 600px       │  collapsible      │
│   centered               │                   │
│                          │                   │
├──────────────────────────┴───────────────────┤
```

- Root container: `display: flex`, `height: calc(100vh - 44px)`, `margin-top: 44px`
- Aide page: `flex: 1`, `overflow: auto`, `min-width: 0`
- Page content: `max-width: 600px`, `margin: 0 auto`, `padding: 28px 32px 60px`
- Chat panel: `width: 360px` (fixed), `flex-shrink: 0`, toggleable
- Panel toggle: speech bubble icon in nav bar right cluster
- When panel closed: `width: 0`, `min-width: 0`, aide page fills viewport
- Panel open/close animates: `transition: width 0.25s ease, min-width 0.25s ease`

### Mobile (< 768px)

```
┌──────────────────────┐
│  Nav Bar (fixed)     │
├──────────────────────┤
│                      │
│  Aide Page           │
│  scrollable          │
│  full width          │
│  max-width: 430px    │
│  padding-bottom: 96  │
│                      │
├──────────────────────┤
│  Bottom Sheet        │  ← 3-position drawer
└──────────────────────┘
```

- Body: `overflow: hidden`, `height: 100dvh`, `max-width: 430px`, `margin: 0 auto`
- Aide page: `padding-top: 44px`, `height: 100vh`, `overflow: auto`, `padding-bottom: 96px` (clears collapsed sheet)
- Page content: `padding: 20px 20px 20px`
- No chat toggle in nav (chat is always the bottom sheet)

---

## Nav Bar

Shared between layouts. 44px height, fixed top, z-index 200, frosted glass.

### Desktop nav

- **Left:** Back button
- **Center:** Page title (absolute centered, `max-width: 40%`)
- **Right:** Share button + Chat toggle button (speech bubble icon)
  - Chat toggle: 32×32px icon button, elevated background when panel open, secondary color when closed

### Mobile nav

- **Left:** Back button
- **Center:** Page title (absolute centered, `max-width: 55%`)
- **Right:** Share button only (no chat toggle — sheet is always present)

---

## Desktop: Chat Panel

A right-side panel that shows full conversation history.

### Structure

```
┌─────────────────────┐
│  CONVERSATION       │  ← header: 12px uppercase, tertiary, border-bottom
├─────────────────────┤
│                     │
│  message bubbles    │  ← flex: 1, overflow: auto, padding: 16px
│  (scrollable)       │
│                     │
├─────────────────────┤
│  [input bar]        │  ← fixed bottom, border-top
└─────────────────────┘
```

### Messages

- **User messages:** right-aligned, elevated background, `border-radius: 14px 14px 4px 14px`, `max-width: 85%`, 14px text
- **Aide messages:** left-aligned with aide avatar (22×22px rounded square, sage background, white "a" letter), 14px secondary text
- Margin between messages: 16px
- Auto-scroll to bottom on new messages
- New messages animate in: `fadeIn 0.2s ease-out`

### Aide avatar

```
width: 22px (desktop) / 20px (mobile)
height: same
border-radius: 6px (desktop) / 5px (mobile)
background: sage
font: 11px/10px, weight 700, color: #F7F5F2
content: "a"
```

### Typing indicator

Three dots with staggered pulse animation:

```
● ● ●   (5px circles, tertiary color)
animation: pulse 1.2s infinite
delays: 0s, 0.2s, 0.4s
```

Shown below aide avatar in same layout as aide message.

### Input bar

- Container: card background, 14px radius, 1px border, 5px padding
- Textarea: `flex: 1`, auto-growing, `max-height: 100px`, 14px font
- Send button: 32×32px circle. Elevated/tertiary when empty, sage/white when has text.
- Enter sends, Shift+Enter newline
- Reset textarea height to `"auto"` after sending

### Panel behavior

- Open by default on page load
- Toggle via nav button
- Auto-focus input when panel opens

---

## Mobile: Bottom Sheet

Three-position draggable drawer with snap points.

### Positions

| Position | Name | Height | Shows |
|----------|------|--------|-------|
| 1 | PEEK | 20px | Drag handle only. Background transparent. |
| 2 | INPUT | 96px | Handle + input bar + bottom padding |
| 3 | HISTORY | 75vh | Handle + scrollable chat history + input bar |

Default position on load: **INPUT** (position 2).

### Snap point calculation

Heights are computed from `window.innerHeight` to work with dynamic viewport units:

```javascript
function getSnapPx() {
  const vh = window.innerHeight;
  return [20, 96, Math.round(vh * 0.75)];
}
```

### Drag behavior

The sheet follows the user's finger in real-time and snaps on release:

- **Touch start:** capture `startY` and current sheet height
- **Touch move:** `newHeight = startHeight + (startY - currentY)`, clamped between 10 and `snapPx[HISTORY] + 40`. Set height directly, transitions disabled during touch.
- **Touch end:** directional intent snapping. Any upward drag > 15px from current snap commits to next position. Any downward drag > 15px commits to previous. This means a small pull-up from INPUT always goes to HISTORY, never snaps back.

```javascript
const onTouchEnd = () => {
  const dy = dragOffset - snapPx[snap];
  let next = snap;
  if (dy > 15 && snap < HISTORY) next = snap + 1;
  else if (dy < -15 && snap > PEEK) next = snap - 1;
  setSnap(next);
  setDragOffset(null);
};
```

The sheet element needs `touch-action: none` to prevent browser scroll interference.

### Snap animation

```css
transition: height 0.3s cubic-bezier(0.32, 0.72, 0, 1)
```

Disabled during finger drag (`touchDragging` flag), re-enabled on release for the snap animation. Programmatic height changes (peek bubbles) also animate — only finger tracking is instant.

### Handle

- Centered horizontal bar: 36px wide (48px in PEEK), 4px tall, `border-radius: 2px`
- Color: `border-strong` (PEEK uses `tertiary` for subtlety)
- Click cycles through positions: PEEK → INPUT → HISTORY → PEEK
- Drag surface for touch events

### Visual states by position

| Property | PEEK | INPUT | HISTORY |
|----------|------|-------|---------|
| Background | transparent | card color | card color |
| Border-top | none | 1px solid border-strong | 1px solid border-strong |
| Border-radius | 0 | 18px 18px 0 0 | 18px 18px 0 0 |
| Box-shadow | none | subtle | strong |
| Backdrop | none | none | rgba(0,0,0,0.35) overlay |

### Input bar (positions 2 and 3)

Same design as desktop but slightly different dimensions:
- Container: body background, 14px radius, 1px border, 4px padding
- Textarea: 15px font, `max-height: 80px`
- Send button: 34×34px circle
- Wrapper padding: `6px 12px 20px`

### Full history (position 3 only)

- `flex: 1`, `overflow: auto`
- Messages bottom-aligned: flex column with `flex: 1` spacer at top, messages wrapper below
- This means when there are few messages, they sit near the input bar with empty space above. As history grows, it fills upward and becomes scrollable.
- Auto-scrolls to bottom when opened and when new messages arrive
- Tap the backdrop to collapse to INPUT

### Peek bubbles (position 2 send flow)

When the user sends a message from position 2, instead of opening the full drawer, inline peek bubbles appear between the handle and input bar:

**Flow:**

1. User sends → user bubble appears in peek area → drawer grows to fit
2. Typing dots appear below user bubble → drawer grows slightly more  
3. Aide responds → aide bubble replaces dots → drawer adjusts height
4. After 2.2 seconds → drawer collapses to INPUT, peek clears, toast appears

**Implementation:**

- Separate `peekMsgs` state array (not the main `messages` history)
- `peekRef` on the peek container to measure rendered height
- `useEffect` watches `peekMsgs` and `sending` → measures `peekRef.getBoundingClientRect().height` → sets `dragOffset = snapPx[INPUT] + peekH + 4`
- This means the drawer auto-sizes to exactly fit the bubbles regardless of text length
- Peek area uses `flexShrink: 0` (not scrollable — it's a fixed preview)
- Peek is hidden when full history is visible (`showPeek = peekMsgs.length > 0 && !showHistory`)
- Peek clears on any snap change or handle click

### Toast

After peek collapses, aide's response floats as a temporary card above the sheet:

```
┌─ aide avatar ─ response text ─┐
└───────────────────────────────┘
```

- Position: `fixed`, `bottom: 84px` (above INPUT sheet), `left/right: 16px`
- Card background, 12px radius, 1px border, shadow
- Animates in: `translateY(20px) → 0` with opacity, 0.25s
- Holds for 2.8s, then fades out over 0.7s
- `pointer-events: none`
- Only shows when at INPUT or PEEK position

---

## Chat Messages (shared)

Both layouts share the same message rendering. Extract a `ChatMessage` component:

```javascript
function ChatMessage({ message, isNew, avatarSize = 22 }) {
  const isUser = message.role === "user";
  // ... render user bubble or aide bubble with avatar
}
```

### Message bubble styles

| Property | User | Aide |
|----------|------|------|
| Alignment | right | left with avatar |
| Background | elevated color | none |
| Border radius | 14px 14px 4px 14px | none |
| Padding | 9-10px 13-14px | none |
| Max width | 85% | 100% minus avatar |
| Text color | primary | secondary |
| Font size | 14px | 14px |

---

## Send Flow Summary

| Context | Behavior |
|---------|----------|
| Desktop panel | Append user msg → show typing dots → append aide response → auto-scroll |
| Mobile position 3 | Same as desktop — append inline, stay in position 3 |
| Mobile position 2 | Show peek bubbles → auto-size drawer → after response, collapse + toast |
| Mobile position 1 | N/A (no input visible) |

The key distinction: check `wasHistory = (snap === SNAP.HISTORY)` before any state changes. If true, append inline. If false, use the peek flow.

---

## Scroll Behavior

### Aide page scroll

Both layouts scroll the aide page in a container div (not the body):

- Desktop: `#aide-page-scroll` div with `flex: 1, overflow: auto`
- Mobile: `#aide-page-scroll` div with `height: 100vh, overflow: auto`

The sticky section pill tracks scroll on this element (not `window`).

### Chat scroll

- Desktop: messages container `overflow: auto`, auto-scroll to `bottomRef` on message change
- Mobile position 3: same, but only when `showHistory` is true
- Mobile peek: no scrolling needed (fixed height, 1-2 messages)

### Hidden scrollbars

All scrollable areas hide their scrollbar:

```css
::-webkit-scrollbar { display: none }
* { scrollbar-width: none }
```

---

## Component Tree

```
App
├── Nav
│   ├── BackButton
│   ├── PageTitle
│   ├── ShareButton
│   └── ChatToggle (desktop only)
├── StickyPill
├── PageContainer (flex row on desktop, stacked on mobile)
│   ├── AidePageScroll
│   │   └── AidePageContent
│   │       ├── PageTitle (h1)
│   │       ├── AideEntity (recursive)
│   │       └── Footer
│   ├── ChatPanel (desktop only, ≥768px)
│   │   ├── PanelHeader
│   │   ├── MessageList
│   │   │   └── ChatMessage (repeated)
│   │   └── ChatInput
│   └── BottomSheet (mobile only, <768px)
│       ├── DragHandle
│       ├── PeekBubbles (position 2 send only)
│       ├── MessageList (position 3 only)
│       │   └── ChatMessage (repeated)
│       └── ChatInput (positions 2+3)
└── Toast (mobile only)
```

---

## State Management

Chat state should be lifted to the App level so both desktop and mobile layouts share it:

```javascript
// In App:
const [messages, setMessages] = useState(initialHistory);
const [sending, setSending] = useState(false);

const sendMessage = (text) => {
  setMessages(prev => [...prev, { role: "user", text }]);
  setSending(true);
  // ... AI call, then:
  // setMessages(prev => [...prev, { role: "aide", text: response }]);
  // setSending(false);
};

// Pass to whichever chat component is active:
isMobile
  ? <BottomSheet messages={messages} sending={sending} onSend={sendMessage} />
  : <ChatPanel messages={messages} sending={sending} onSend={sendMessage} />
```

Layout-specific state (snap position, dragOffset, peekMsgs, panelOpen) stays local to each component.

---

## Acceptance Criteria

### Desktop
- [ ] Chat panel opens on right, 360px wide, with toggle in nav
- [ ] Panel open/close animates width
- [ ] Aide page reflows when panel toggles (flex layout)
- [ ] Messages auto-scroll to bottom
- [ ] Typing indicator shows during AI response
- [ ] Textarea auto-grows and resets after send

### Mobile
- [ ] Three sheet positions: peek (handle only), input (bar visible), history (scrollable)
- [ ] Sheet follows finger during drag, snaps on release with spring curve
- [ ] Upward drag from INPUT always commits to HISTORY (directional intent)
- [ ] Sending from INPUT shows peek bubbles that auto-size the drawer
- [ ] Peek bubbles handle variable-length user messages
- [ ] After aide responds, sheet collapses and toast appears
- [ ] Sending from HISTORY appends inline, stays open
- [ ] Full history is bottom-aligned (space at top, messages at bottom)
- [ ] Handle click cycles through all three positions
- [ ] Backdrop appears in HISTORY, tap to collapse

### Responsive
- [ ] Crossing 768px breakpoint switches layout without page reload
- [ ] Chat history is preserved when switching layouts
- [ ] No scrollbar visible on any scrollable area
- [ ] Sticky section pill works on both layouts (tracks aide page scroll container)
