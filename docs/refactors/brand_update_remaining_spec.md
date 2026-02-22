# aide — Brand Update: Remaining Work

**Purpose:** Complete the brand update across the codebase. The core rendering pipeline (engine builds, react_preview.py, frontend/index.html, skill files) is already updated to the new Playfair Display + Instrument Sans + DM Sans + sage palette. This spec covers everything that's still stale.

**Prerequisite:** Read `docs/refactors/brand_design_update_instructions.md` for the full brand reference. This spec only covers _what's left to do_.

---

## Scope Rules

- **DO NOT touch** anything in `docs/archive/` — these are historical snapshots
- **DO NOT touch** `docs/refactors/brand_design_update_instructions.md` — it contains old values by design (as find→replace reference)
- **DO NOT touch** `docs/strategy/aide_living_objects.md` — uses "running" conceptually, not as tagline
- **DO NOT touch** `docs/prds/aide_prd.md` — uses "running" as product description, not tagline
- **DO NOT touch** engine builds that are already updated (`engine/builds/engine.py`, `engine/builds/engine.compact.js`, `engine/engine.min.js`, `engine/kernel/react_preview.py`)
- The `engine/builds/engine.ts` and `engine/builds/engine.js` files are reducer-only (no CSS, no rendering) — they need no brand changes

---

## Task 1: Email Template — `backend/services/email.py`

**Why:** This is the first branded touchpoint every user sees. Currently says "AIde" everywhere.

### Find → Replace (display text only, not variable names)

| Line | Old | New |
|------|-----|-----|
| 33 | `<title>Sign in to AIde</title>` | `<title>Sign in to aide</title>` |
| 114 | `<h1>AIde</h1>` | `<h1>aide</h1>` |
| 118 | `sign in to AIde. This link` | `sign in to aide. This link` |
| 119 | `Sign in to AIde</a>` | `Sign in to aide</a>` |
| 135 | `Sign in to AIde` | `Sign in to aide` |
| 137 | `sign in to AIde:` | `sign in to aide:` |
| 149 | `"subject": "Sign in to AIde"` | `"subject": "Sign in to aide"` |

**Do NOT rename** the Python file, function names, or the `params` dict keys — only display strings.

### Verification

```bash
# Should return 0 results for display-text "AIde"
grep -n "AIde" backend/services/email.py | grep -v "def \|import \|# "
```

---

## Task 2: README — `README.md`

**Why:** Public-facing repo landing page. Mixed case heading, old tagline.

### Full replacement

```markdown
# aide

**For what you're living.**

aide is a conversational web page editor. Describe what you're living — a league, a budget, a renovation — and aide forms a living page. As things change, tell aide. The page stays current. The URL stays the same.
```

The rest of the file (Stack, Development, Deploy, Docs sections) is fine. Only the top block needs updating.

---

## Task 3: Tagline Fixes — 3 docs

Simple find→replace. One line each.

### `docs/eng_design/00_overview.md`

Line 13:
```
OLD: The tagline: **For what you're running.**
NEW: The tagline: **For what you're living.**
```

### `docs/program_management/aide_launch_plan.md`

Line 196:
```
OLD: - [ ] Hero: "For what you're running." + one-line explainer
NEW: - [ ] Hero: "For what you're living." + one-line explainer
```

### `docs/strategy/aide_engine_distribution.md`

Line 218:
```
OLD: │         "description": "Build and maintain living pages for what you're running.",
NEW: │         "description": "Build and maintain living pages for what you're living.",
```

---

## Task 4: Flight Recorder — `frontend/flight-recorder.html`

**Why:** Developer-facing debugging UI. Uses old Tailwind-ish colors and says "AIde" in the title.

**Important context:** This is a dark-themed UI (`background: #0f0f17`). The colors here are for dark-mode chrome, not the published-page brand. However, the old Tailwind slate palette (`#e2e8f0`, `#64748b`, `#2d3748`) should be updated for brand consistency.

### Title

Line 6:
```
OLD: <title>Flight Recorder - AIde</title>
NEW: <title>Flight Recorder - aide</title>
```

### Color map for inline styles

| Old | New | Role |
|-----|-----|------|
| `#e2e8f0` | `#D4D1CC` | Light text on dark / borders (→ border-default) |
| `#2d3748` | `#2D2D2A` | Dark surface / assistant bubble bg (→ text-primary) |
| `#64748b` | `#6B6963` | Muted text (→ text-secondary) |

### Lines to update

**`#e2e8f0` → `#D4D1CC`** (9 occurrences):
- Line 15: `color: #e2e8f0;`
- Line 108: `color: isUser ? "#e2e8f0" : "#2d3748"`
- Line 112: `border: isUser ? "none" : "1px solid #e2e8f0"`
- Line 317: `color: "#e2e8f0"`
- Line 667: `borderBottom: "1px solid #e2e8f0"`
- Line 744: `color: "#e2e8f0"`
- Line 811: `color: "#e2e8f0"`
- Line 957: `color: "#e2e8f0"`
- Line 1208: `color: playSpeed === sp ? "#e2e8f0" : "#64748b"`

**`#2d3748` → `#2D2D2A`** (1 occurrence):
- Line 108: (same line as above, second value in ternary)

**`#64748b` → `#6B6963`** (many occurrences):
- Lines 25, 334, 349, 354, 371, 448, 537, 556, 584, 588, 605, 629, 747, 756, 793, 802, 821, 845, 941, 968, 1015, 1047, 1079, 1129, 1208

### Approach

Use sed for bulk replacement:
```bash
cd frontend/
sed -i 's/#e2e8f0/#D4D1CC/g' flight-recorder.html
sed -i 's/#2d3748/#2D2D2A/g' flight-recorder.html
sed -i 's/#64748b/#6B6963/g' flight-recorder.html
```

Then verify line 1208 has both new colors in the ternary.

---

## Task 5: Eval Script — `scripts/eval_0a.py`

**Why:** Default style suggestion uses old color.

Line 166:
```
OLD: "primary_color":"#2d3748"
NEW: "primary_color":"#2D2D2A"
```

---

## Task 6: Test Data — Engine kernel tests

**Why:** Test fixtures use old brand colors as example data. Updating keeps tests consistent with the brand and avoids confusion for anyone reading them.

**CRITICAL:** After making these changes, run `pytest engine/kernel/tests/ -v` and ensure all tests pass. If any test fails, the change broke an assertion — fix the assertion to match the new value.

### Color map for test data

| Old | New |
|-----|-----|
| `"#2d3748"` | `"#2D2D2A"` |
| `"#fafaf9"` | `"#F7F5F2"` |
| `"IBM Plex Sans"` | `"DM Sans"` |

### Files and lines

**`test_reducer_walkthrough.py`:**
- Line 549: `"primary_color": "#2d3748"` → `"#2D2D2A"`
- Line 608: `assert snapshot["styles"]["primary_color"] == "#2d3748"` → `"#2D2D2A"`
- Line 973: `"font_family": "IBM Plex Sans"` → `"DM Sans"`

**`test_reducer_v2_golden.py`:**
- Line 187: `assert snapshot["styles"]["global"]["primary_color"] == "#2d3748"` → `"#2D2D2A"`

**`test_reducer_determinism.py`:**
- Line 359: `"primary_color": "#2d3748"` → `"#2D2D2A"`
- Line 362: `"bg_color": "#fafaf9"` → `"#F7F5F2"`

**`test_reducer_v2_style_meta_signals.py`:**
- Line 38: `"primary_color": "#2d3748"` → `"#2D2D2A"`
- Line 42: `assert styles["primary_color"] == "#2d3748"` → `"#2D2D2A"`

**`test_reducer_round_trip.py`:**
- Line 272: `"primary_color": "#2d3748"` → `"#2D2D2A"`
- Line 699: `assert restored["styles"]["primary_color"] == "#2d3748"` → `"#2D2D2A"`

**`test_reducer_idempotency.py`:**
- Line 142: `"primary_color": "#2d3748"` → `"#2D2D2A"`
- Line 621: `payload={"primary_color": "#2d3748"` → `"#2D2D2A"`
- Line 637: `payload={"primary_color": "#2d3748"` → `"#2D2D2A"`
- Line 654: `"primary_color": "#2d3748"` → `"#2D2D2A"`
- Line 660: `assert result.snapshot["styles"]["primary_color"] == "#2d3748"` → `"#2D2D2A"`

### Approach

```bash
cd engine/kernel/tests/tests_reducer/
sed -i 's/"#2d3748"/"#2D2D2A"/g' test_reducer_walkthrough.py test_reducer_v2_golden.py test_reducer_determinism.py test_reducer_v2_style_meta_signals.py test_reducer_round_trip.py test_reducer_idempotency.py
sed -i 's/"#fafaf9"/"#F7F5F2"/g' test_reducer_determinism.py
sed -i 's/"IBM Plex Sans"/"DM Sans"/g' test_reducer_walkthrough.py
```

Then run tests:
```bash
pytest engine/kernel/tests/ -v
```

---

## Task 7: Design System Spec — `docs/eng_design/specs/aide_ui_design_system_spec.md`

**Why:** This is the canonical design reference Claude Code reads. It's completely stale — still has the v1 brand (Cormorant Garamond, IBM Plex Sans, accent-navy/forest/burgundy/steel, old radii).

### Rewrite the entire file

Replace the full contents with the spec below. This brings it in line with what's actually deployed in `react_preview.py`, `engine.min.js`, and `aide_brand_preview.html`.

---

```markdown
# aide — Design System

**Purpose:** Code-ready reference for the aide visual identity. CSS variables, typography, components, and layout.

---

## 1. CSS Custom Properties

```css
:root {
  /* ── Backgrounds ── */
  --bg-primary: #F7F5F2;
  --bg-secondary: #EFECEA;
  --bg-tertiary: #E6E3DF;
  --bg-elevated: #FFFFFF;

  /* ── Text ── */
  --text-primary: #2D2D2A;
  --text-secondary: #6B6963;
  --text-tertiary: #A8A5A0;
  --text-inverse: #F7F5F2;

  /* ── Sage Scale ── */
  --sage-50: #F0F3ED;
  --sage-100: #DDE4D7;
  --sage-200: #C2CCB8;
  --sage-300: #A3B394;
  --sage-400: #8B9E7C;
  --sage-500: #7C8C6E;
  --sage-600: #667358;
  --sage-700: #515C46;
  --sage-800: #3C4534;
  --sage-900: #282E23;

  /* ── Accents ── */
  --accent: var(--sage-500);
  --accent-hover: var(--sage-600);
  --accent-subtle: var(--sage-50);
  --accent-muted: var(--sage-100);

  /* ── Borders ── */
  --border-subtle: #E0DDD8;
  --border-default: #D4D1CC;
  --border-strong: #A8A5A0;

  /* ── Backward Compat Aliases ── */
  --border: var(--border-default);
  --border-light: var(--border-subtle);

  /* ── Typography ── */
  --font-serif: 'Playfair Display', Georgia, serif;
  --font-sans: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-heading: 'Instrument Sans', -apple-system, BlinkMacSystemFont, sans-serif;

  /* ── Radius ── */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-full: 999px;

  /* ── Spacing (8px base) ── */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  /* ── Transitions ── */
  --transition-fast: 150ms ease;
  --transition-normal: 200ms ease;
  --transition-slow: 250ms ease;
}
```

### Dark Mode

```css
@media (prefers-color-scheme: dark) {
  :root {
    --bg-primary: #1A1917;
    --bg-secondary: #242320;
    --bg-tertiary: #2D2C28;
    --bg-elevated: #333230;
    --text-primary: #E8E6E1;
    --text-secondary: #A8A5A0;
    --text-tertiary: #6B6963;
    --text-inverse: #1A1917;
    --border-subtle: #333230;
    --border-default: #3D3C38;
    --border-strong: #6B6963;
  }
}
```

---

## 2. Typography System

### Font Loading

```html
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Instrument+Sans:wght@400;500;600;700&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">
```

### Type Scale

| Level | Font | Size | Weight | Line Height | Use |
|-------|------|------|--------|-------------|-----|
| Display | Playfair Display | 48–64px | 700 | 1.12 | Hero headlines |
| H1 | Playfair Display | 36–42px | 700 | 1.2 | Page titles |
| H2 | Playfair Display | 28–32px | 700 | 1.25 | Section headings |
| H3 | Instrument Sans | 18–20px | 600 | 1.4 | Subsection headings |
| Body | DM Sans | 16px | 400 | 1.65 | Paragraphs |
| Body Small | DM Sans | 15px | 400 | 1.55 | Secondary content |
| UI Label | DM Sans | 13–14px | 500 | 1.4 | Buttons, nav, labels |
| Caption | DM Sans | 12px | 400 | 1.4 | Timestamps, metadata |
| Overline | DM Sans | 11px | 600 | 1.3 | Section labels (uppercase) |

### CSS Implementation

```css
body {
  font-family: var(--font-sans);
  font-weight: 400;
  color: var(--text-primary);
  background: var(--bg-primary);
  line-height: 1.65;
  font-size: 16px;
}

.aide-heading--1, .aide-heading--2 {
  font-family: var(--font-serif);
  font-weight: 700;
  color: var(--text-primary);
}

.aide-heading--3 {
  font-family: var(--font-heading);
  font-weight: 600;
  color: var(--text-primary);
}
```

---

## 3. Component Specifications

### Buttons

```css
.btn-primary {
  background: var(--accent);
  color: var(--text-inverse);
  border: none;
  border-radius: var(--radius-sm);
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 500;
  padding: var(--space-2) var(--space-4);
  transition: background var(--transition-fast);
}

.btn-primary:hover {
  background: var(--accent-hover);
}
```

### Input Fields

```css
.input {
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  font-family: var(--font-sans);
  font-size: 16px;
  color: var(--text-primary);
  transition: border-color var(--transition-fast);
}

.input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-muted);
}
```

### Cards / Panels

```css
.card {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--space-5);
}

.card-title {
  font-family: var(--font-heading);
  font-weight: 600;
  font-size: 16px;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}
```

### Status Indicators

```css
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.active {
  background: var(--sage-400);
  box-shadow: 0 0 0 3px var(--accent-muted);
}

.status-dot.idle { background: var(--border-strong); }
.status-dot.thinking {
  background: var(--sage-300);
  animation: pulse 1.5s ease-in-out infinite;
}
```

---

## 4. Motion System

```css
transition: property 200ms ease;  /* default */
transition: property 150ms ease;  /* hover states, small elements */
transition: property 250ms ease;  /* panels, overlays */
```

No spring animations. No bounces. No celebration animations. Purposeful transitions only.

---

## 5. Layout System

### Max Widths

| Context | Width |
|---------|-------|
| Published page content | 720px |
| Editor chrome | 100% (responsive) |
| Chat input | 640px |

### Container

```css
.container {
  max-width: 720px;
  margin: 0 auto;
  padding: 0 var(--space-5);
}
```

### Section Spacing

Sections separated by `var(--space-10)` (40px). Within a section, elements use `var(--space-4)` to `var(--space-6)`.

---

## 6. Iconography

Tabler Icons, `stroke-width="1.0"`. Muted by default (`var(--text-tertiary)`), darken to `var(--text-secondary)` on hover.

---

## 7. Design Litmus Test

Before shipping any component, screen, or interaction:

**Does this feel like infrastructure?** Or does it feel like software trying to impress?

**If it performs, remove it. If it stabilizes, keep it.**

- No bright gradients
- No celebration animations
- No emoji
- No novelty fonts
- No dashboard density
- No widget grids
- No toast notifications
- No mascots or illustrations
- Generous white space
- Strong typographic hierarchy
- Muted, neutral color palette
- Subtle, purposeful motion only
- Publication feel, not SaaS feel
```

---

## Execution Order

Run tasks in this order. Each task is independent and can be committed separately.

```
1. backend/services/email.py          (~5 min, string replacements)
2. README.md                          (~5 min, rewrite top block)
3. docs/eng_design/00_overview.md     (~1 min, one line)
4. docs/program_management/aide_launch_plan.md  (~1 min, one line)
5. docs/strategy/aide_engine_distribution.md    (~1 min, one line)
6. frontend/flight-recorder.html      (~5 min, sed replacements + verify)
7. scripts/eval_0a.py                 (~1 min, one value)
8. engine/kernel/tests/**             (~10 min, sed + run tests)
9. docs/eng_design/specs/aide_ui_design_system_spec.md  (~15 min, full rewrite)
```

Commit message: `chore: complete brand update — lowercase aide, new tagline, updated colors`

---

## Task 10: Dashboard FAB — FEAT-03 + BUG-03 scroll fix

**Issues:** FEAT-03 (Move "new aide" to floating action button), BUG-03 (Chat input bubble covers bottom of page)

These are linked. The FAB is the dashboard-side fix. The scroll padding is the editor-side fix. Both involve the bottom of the viewport.

### 10a. Dashboard — Replace header button with FAB

**Current state:** `frontend/index.html` line 1159 has `<button id="new-aide-btn" class="btn btn-primary">+ New aide</button>` in the `.dashboard-header` div next to the `<h1>aide</h1>`.

**Target:** Remove the button from the header. Add a fixed-position FAB in the bottom-right corner of the dashboard view. The FAB is always visible while scrolling the aide grid.

#### HTML change

In the dashboard section (~line 1155–1166), remove the button from the header and add a FAB element:

```html
<!-- Dashboard -->
<div id="dashboard">
  <div class="dashboard-header">
    <h1>aide</h1>
  </div>
  <div id="aide-grid" class="aide-grid"></div>
  <div id="empty-state" class="empty-state" style="display:none;">
    <p>Nothing yet.</p>
    <button class="btn btn-ghost" onclick="startNewAide()">Create your first aide</button>
  </div>
  <button id="new-aide-fab" class="fab" onclick="startNewAide()" title="New aide">+</button>
</div>
```

#### CSS

Add FAB styles. Reference: `aide_brand_preview.html` already has the canonical FAB design using the sage accent.

```css
/* ── FAB (floating action button) ── */
.fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #7C8C6E;          /* sage-500 */
  border: none;
  color: #F7F5F2;               /* text-inverse (warm white) */
  font-size: 24px;
  font-weight: 300;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  transition: background 0.15s ease, transform 0.15s ease;
  z-index: 50;
}

.fab:hover {
  background: #667358;          /* sage-600 */
  transform: scale(1.05);
}

/* Only show FAB when dashboard is active */
#new-aide-fab {
  display: none;
}

#dashboard.active #new-aide-fab {
  display: flex;
}

/* Mobile: tighter inset */
@media (max-width: 767px) {
  .fab {
    bottom: 20px;
    right: 16px;
    width: 48px;
    height: 48px;
    font-size: 22px;
  }
}
```

**Note on color:** Both the FAB and send button use sage-500 (`#7C8C6E`) as the brand accent, even on the dark dashboard. This provides a consistent brand color anchor across all surfaces.

### 10c. Chat send button — sage accent

**Current state:** `frontend/index.html` lines 371–377. The send button uses `var(--accent)` which resolves to `#fff` (white) in the dark editor theme. Hover is hardcoded `#ddd`.

**Target:** Sage-500 background with warm white text, sage-600 on hover. Same color as the FAB.

#### CSS change

Replace lines 371–377:

```css
/* OLD */
#send-btn {
  background: var(--accent);
  color: #000;
  border-radius: 8px;
}

#send-btn:hover:not(:disabled) { background: #ddd; }

/* NEW */
#send-btn {
  background: #7C8C6E;         /* sage-500 */
  color: #F7F5F2;              /* warm white */
  border-radius: 8px;
}

#send-btn:hover:not(:disabled) { background: #667358; }  /* sage-600 */
```

Also update the auth screen "Send magic link" button to match. Line 1146 has:
```html
<button id="send-link-btn" class="btn btn-primary" style="width:100%;justify-content:center;">Send magic link</button>
```

The `.btn-primary` class (line ~69) is currently `background: var(--accent); color: #000;`. Update it:

```css
/* OLD */
.btn-primary { background: var(--accent); color: #000; }
.btn-primary:hover:not(:disabled) { background: #ddd; }

/* NEW */
.btn-primary { background: #7C8C6E; color: #F7F5F2; }
.btn-primary:hover:not(:disabled) { background: #667358; }
```

This makes the magic link "Send" button, the chat send button, and the FAB all sage. Consistent brand accent throughout.

#### JS change

Update the `new-aide-btn` event listener (~line 2356 area) to bind to `new-aide-fab` instead. Search for `getElementById('new-aide-btn')` and replace with `getElementById('new-aide-fab')`.

Also remove any references to the old `new-aide-btn` ID.

### 10b. Editor — Preview bottom padding to clear chat overlay

**Current state:** The preview (`#preview-root`) fills `width: 100%; height: 100%` with `overflow-y: auto`. The chat overlay is `position: fixed; bottom: 20px`. Content at the bottom of the aide page is hidden behind the chat overlay because there's no bottom padding on the preview content.

**Fix:** Add bottom padding to the preview root so the user can scroll past the chat overlay to see all content.

#### CSS change

```css
#preview-root {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  background: #fff;
  position: relative;
  padding-bottom: 100px;  /* Clear chat overlay + breathing room */
}
```

The 100px accounts for:
- Chat input bar height (~52px)
- Bottom offset of overlay (20px)
- Breathing room (~28px)

If the history panel is expanded (max-height 160px), the user may need to scroll further, but the input bar is what permanently occludes content. 100px handles the collapsed state which is the common case.

#### Alternative: dynamic padding via CSS custom property

If the chat overlay height varies (e.g., thinking indicator adds height), a more robust approach uses a CSS variable set by JS:

```css
#preview-root {
  padding-bottom: var(--chat-clearance, 100px);
}
```

```javascript
// In the resize/layout observer:
function updateChatClearance() {
  const overlay = document.getElementById('chat-overlay');
  if (overlay) {
    const height = overlay.offsetHeight + 40; // 40px breathing room
    document.getElementById('preview-root').style.setProperty('--chat-clearance', height + 'px');
  }
}
```

**Recommendation:** Start with the static 100px. Only add the dynamic approach if testing reveals edge cases.

---

## Task 11: Published page scroll — BUG-03 adjacent

Published pages at `/s/{slug}` are static HTML served from R2. They don't have the chat overlay, but they do have the `aide-footer` at the very bottom. Verify that the footer is visible and not clipped.

The engine CSS already includes:
```css
.aide-footer {
  margin-top: var(--space-16);  /* 64px */
  padding-top: var(--space-6);  /* 24px */
}
```

This should be fine. **No code change needed** — just add to the manual QA checklist:
- Open a published aide page
- Scroll to the very bottom
- Confirm the "Made with aide" footer is fully visible
- Test on both desktop and mobile Safari (iOS has the dynamic address bar that affects bottom content)

---

## Updated Execution Order

```
1.  backend/services/email.py          (~5 min)
2.  README.md                          (~5 min)
3.  docs/eng_design/00_overview.md     (~1 min)
4.  docs/program_management/aide_launch_plan.md  (~1 min)
5.  docs/strategy/aide_engine_distribution.md    (~1 min)
6.  frontend/flight-recorder.html      (~5 min)
7.  scripts/eval_0a.py                 (~1 min)
8.  engine/kernel/tests/**             (~10 min)
9.  docs/eng_design/specs/aide_ui_design_system_spec.md  (~15 min)
10. frontend/index.html — FAB + scroll padding  (~20 min)
11. QA: published page footer visibility (~5 min)
```

Commit messages:
- Tasks 1–9: `chore: complete brand update — lowercase aide, new tagline, updated colors`
- Task 10: `feat: dashboard FAB + preview scroll padding (FEAT-03, BUG-03)`

---

## Final Validation

After all changes, run these checks. All should return 0 relevant results:

```bash
# Old fonts (exclude archive + instructions doc)
grep -rn "Cormorant\|IBM Plex" --include="*.py" --include="*.ts" --include="*.js" --include="*.html" --include="*.css" \
  | grep -v docs/archive | grep -v brand_design_update | grep -v node_modules

# Old colors in code files (exclude archive + instructions)
grep -rn "#fafaf9\|#2d3748\|#4a5568\|#a0aec0\|#e2e8f0\|#edf2f7\|#64748b" \
  --include="*.py" --include="*.ts" --include="*.js" --include="*.html" --include="*.css" \
  | grep -v docs/archive | grep -v brand_design_update | grep -v node_modules

# Old accent variables
grep -rn "accent-steel\|accent-navy\|accent-forest\|accent-burgundy\|bg-cream\|text-slate" \
  --include="*.py" --include="*.ts" --include="*.js" --include="*.html" --include="*.css" \
  | grep -v docs/archive | grep -v brand_design_update | grep -v node_modules

# "AIde" in display text (email, README, HTML titles — NOT code identifiers like class names)
grep -rn '"AIde"\|>AIde<\|Sign in to AIde\|title>.*AIde' \
  --include="*.py" --include="*.html" --include="*.md" \
  | grep -v docs/archive | grep -v brand_design_update | grep -v CLAUDE.md

# Old tagline as tagline (not conceptual usage)
grep -rn 'For what you.re running\.' --include="*.md" --include="*.html" \
  | grep -v docs/archive | grep -v brand_design_update | grep -v aide_prd.md | grep -v aide_living_objects.md

# Tests pass
pytest engine/kernel/tests/ -v
ruff check backend/ engine/

# FAB: old button removed, new FAB exists
grep -n "new-aide-btn" frontend/index.html  # should return 0
grep -n "new-aide-fab" frontend/index.html  # should return 2+ (HTML + JS)

# Sage accent on FAB, send button, and btn-primary
grep -n "7C8C6E\|667358" frontend/index.html  # should return 4+ (FAB, send-btn, btn-primary, hovers)

# Scroll padding: preview-root has padding-bottom
grep "padding-bottom" frontend/index.html | grep "preview-root\|100px"
```
