# Task: Add Top Toolbar and Sticky Section Pill

Add two fixed UI elements to the aide page viewer: a frosted glass nav bar and a scroll-tracking section pill.

---

## 1. Nav Bar

Fixed to top of viewport. 44px tall. z-index 200.

### Visual

- Frosted glass: `background: rgba(26,26,24,0.9)` + `backdrop-filter: blur(14px)`
- Bottom border: `1px solid` border color
- Three zones: left (back), center (title), right (share)

### Left — Back Button

```html
<button>
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M19 12H5" /><path d="M12 19l-7-7 7-7" />
  </svg>
  Back
</button>
```

- `fontSize: 14, fontWeight: 500`, secondary text color
- Hover: primary text color
- No background, no border

### Center — Page Title

- `position: absolute, left: 50%, transform: translateX(-50%)`
- `fontSize: 14, fontWeight: 600`, primary text color
- `whiteSpace: nowrap, overflow: hidden, textOverflow: ellipsis, maxWidth: 55%`
- Reads from page entity title or hardcoded page title

### Right — Share Button

```html
<button>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
    <polyline points="16 6 12 2 8 6" />
    <line x1="12" y1="2" x2="12" y2="15" />
  </svg>
  Share
</button>
```

- Same text style as Back
- Hover: elevated background color, rounded 6px

### Body Offset

Add `padding-top: 44px` to the scrollable content wrapper so nothing hides behind the nav.

---

## 2. Sticky Section Pill

As the user scrolls into a section, its title appears as a centered pill below the nav bar.

### Registration

Each Section component registers itself on mount:

```javascript
const SectionRegistry = createContext({ register: () => {}, unregister: () => {} })

// In Section component:
const ref = useRef(null)
const { register, unregister } = useContext(SectionRegistry)
useEffect(() => {
  if (ref.current) register(entityId, title, ref.current)
  return () => unregister(entityId)
}, [entityId, title])
// Attach ref to the section's outermost div
```

### Scroll Tracking

In the root App component:

```javascript
const sectionsRef = useRef({})        // { [id]: { title, el } }
const [activeTitle, setActiveTitle] = useState(null)
const prevTitleRef = useRef(null)      // avoid unnecessary re-renders
const rafRef = useRef(null)           // rAF handle

const register = useCallback((id, title, el) => {
  sectionsRef.current[id] = { title, el }
}, [])
const unregister = useCallback((id) => {
  delete sectionsRef.current[id]
}, [])

useEffect(() => {
  const onScroll = () => {
    if (rafRef.current) return
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null
      const threshold = NAV_HEIGHT + 10
      let current = null

      for (const { title, el } of Object.values(sectionsRef.current)) {
        const rect = el.getBoundingClientRect()
        // Section header has scrolled past nav AND section bottom still visible
        if (rect.top < threshold && rect.bottom > threshold + 24) {
          current = title
        }
      }

      if (current !== prevTitleRef.current) {
        prevTitleRef.current = current
        setActiveTitle(current)
      }
    })
  }

  window.addEventListener("scroll", onScroll, { passive: true })
  return () => {
    window.removeEventListener("scroll", onScroll)
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
  }
}, [])
```

Key details:
- `requestAnimationFrame` throttle — never run layout reads more than once per frame
- Compare with `prevTitleRef` before calling `setActiveTitle` to avoid re-renders when nothing changed
- `{ passive: true }` on scroll listener for performance
- Last matching section wins if multiple overlap

### Pill Component

```javascript
function StickyPill({ title }) {
  if (!title) return null
  return (
    <div style={{
      position: "fixed",
      top: NAV_HEIGHT + 6,
      left: 0, right: 0,          // NOT left: 50% — that misaligns with scrollbar
      zIndex: 190,
      display: "flex",
      justifyContent: "center",
      pointerEvents: "none",       // clicks pass through container
      animation: "pillIn 0.15s ease-out",
    }}>
      <div style={{
        background: "rgba(36,36,34,0.94)",
        backdropFilter: "blur(10px)",
        border: "1px solid <border-strong>",
        borderRadius: 999,
        padding: "3px 14px",
        fontSize: 13,
        fontWeight: 600,
        color: "<text-primary>",
        boxShadow: "0 1px 8px rgba(0,0,0,0.2)",
        whiteSpace: "nowrap",
        pointerEvents: "auto",      // pill itself is interactive
      }}>
        {title}
      </div>
    </div>
  )
}
```

### Animation Keyframe

Add to CSS:

```css
@keyframes pillIn {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
```

The animation replays each time the pill title changes because the component unmounts/remounts when `title` goes null → string or changes value.

---

## Centering Gotcha

Do NOT center the pill with `left: 50%; transform: translateX(-50%)`. Fixed positioning calculates from the full viewport including the scrollbar gutter, which shifts the pill right of the visible content center. Use `left: 0; right: 0; display: flex; justify-content: center` instead.

---

## Wiring

```jsx
<SectionRegistry.Provider value={{ register, unregister }}>
  <NavBar />
  <StickyPill title={activeTitle} />
  <div style={{ paddingTop: NAV_HEIGHT }}>
    {/* page content with Section components */}
  </div>
</SectionRegistry.Provider>
```

---

## Acceptance Criteria

- [ ] Nav bar stays fixed on scroll, content scrolls behind with blur visible
- [ ] Page title truncates with ellipsis on narrow screens
- [ ] Pill appears when scrolling past a section header
- [ ] Pill swaps to next section title when scrolling into a new section
- [ ] Pill disappears when scrolling back above all sections
- [ ] Pill disappears when scrolling past the bottom of the last visible section
- [ ] No layout thrashing — scroll handler uses rAF throttle
- [ ] Works on mobile (touch scroll, no hover states on nav assumed)
