# AIde — Design System Implementation

**Purpose:** Practical implementation reference for the AIde visual identity. This document translates the brand guidelines into code-ready specifications: CSS variables, component patterns, typography scale, and spacing system.

---

## 1. CSS Custom Properties

```css
:root {
  /* ── Backgrounds ── */
  --bg-primary: #F6F5F3;         /* Warm off-white — default page background */
  --bg-cream: #FAFAF8;           /* Editorial cream — cards, panels, elevated surfaces */
  --bg-white: #FFFFFF;           /* Pure white — input fields, active states */

  /* ── Text ── */
  --text-primary: #1E1E1E;       /* Deep charcoal — headings, primary content */
  --text-slate: #2A2A2A;         /* Slate black — body text, secondary headings */
  --text-secondary: #6A6A6A;     /* Soft gray — descriptions, metadata */
  --text-tertiary: #9A9A9A;      /* Light gray — labels, timestamps, placeholders */

  /* ── Accents (use sparingly) ── */
  --accent-navy: #1F2A44;        /* Focus states, primary buttons, active elements */
  --accent-forest: #2F3E34;      /* Subtle emphasis, secondary accents */
  --accent-burgundy: #5A2F3B;    /* Sparingly — errors, critical states */
  --accent-steel: #3C506B;       /* Links, interactive elements */

  /* ── Borders ── */
  --border: #E0DFDC;             /* Standard borders */
  --border-light: #EBEAE7;       /* Subtle dividers, section separators */
  --border-focus: #1F2A44;       /* Active input borders */

  /* ── Typography ── */
  --font-serif: 'Cormorant Garamond', Georgia, 'Times New Roman', serif;
  --font-sans: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

  /* ── Spacing Scale (8px base) ── */
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
  --space-20: 80px;
  --space-24: 96px;
  --space-32: 128px;

  /* ── Radius ── */
  --radius-sm: 3px;
  --radius-md: 5px;
  --radius-lg: 8px;

  /* ── Transitions ── */
  --transition-fast: 150ms ease;
  --transition-normal: 200ms ease;
  --transition-slow: 250ms ease;
}
```

---

## 2. Typography System

### Font Loading

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">
```

### Type Scale

| Level | Font | Size | Weight | Line Height | Letter Spacing | Use |
|---|---|---|---|---|---|---|
| Display | Serif | 48–64px | 400 | 1.12 | -0.01em | Hero headlines |
| H1 | Serif | 36–42px | 400 | 1.2 | -0.005em | Page titles |
| H2 | Serif | 28–32px | 400 | 1.25 | 0 | Section headings |
| H3 | Sans | 18–20px | 500 | 1.4 | 0 | Subsection headings |
| Body | Sans | 16px | 300 or 400 | 1.65 | 0 | Paragraphs, descriptions |
| Body Small | Sans | 15px | 400 | 1.55 | 0 | State entries, secondary content |
| UI Label | Sans | 13–14px | 500 | 1.4 | 0.02em | Buttons, navigation, field labels |
| Caption | Sans | 12px | 400 | 1.4 | 0.01em | Timestamps, metadata |
| Overline | Sans | 11px | 500 | 1.3 | 0.12em | Section labels (uppercase) |

### CSS Implementation

```css
/* Display */
.text-display {
  font-family: var(--font-serif);
  font-size: clamp(42px, 6vw, 64px);
  font-weight: 400;
  line-height: 1.12;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

/* H1 */
.text-h1 {
  font-family: var(--font-serif);
  font-size: clamp(32px, 4.5vw, 42px);
  font-weight: 400;
  line-height: 1.2;
  color: var(--text-primary);
}

/* H2 */
.text-h2 {
  font-family: var(--font-serif);
  font-size: clamp(24px, 3.5vw, 32px);
  font-weight: 400;
  line-height: 1.25;
  color: var(--text-primary);
}

/* H3 */
.text-h3 {
  font-family: var(--font-sans);
  font-size: 18px;
  font-weight: 500;
  line-height: 1.4;
  color: var(--text-primary);
}

/* Body */
.text-body {
  font-family: var(--font-sans);
  font-size: 16px;
  font-weight: 300;
  line-height: 1.65;
  color: var(--text-secondary);
}

/* Overline */
.text-overline {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}
```

---

## 3. Component Specifications

### Buttons

**Primary CTA**
```css
.btn-primary {
  display: inline-block;
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: var(--bg-primary);
  background: var(--text-primary);
  padding: 13px 28px;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-normal);
  text-decoration: none;
}

.btn-primary:hover {
  background: var(--accent-navy);
}
```

CTA copy: "Start something."
No gradients. No heavy shadows. No pill shapes.

**Secondary / Text Button**
```css
.btn-secondary {
  display: inline-block;
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 400;
  color: var(--text-secondary);
  background: none;
  border: none;
  padding: 8px 0;
  cursor: pointer;
  transition: color var(--transition-fast);
  text-decoration: none;
}

.btn-secondary:hover {
  color: var(--text-primary);
}
```

### Input Fields

```css
.input {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 400;
  color: var(--text-primary);
  background: var(--bg-white);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  width: 100%;
  outline: none;
  transition: border-color var(--transition-fast);
}

.input::placeholder {
  color: var(--text-tertiary);
}

.input:focus {
  border-color: var(--border-focus);
  border-bottom-width: 2px;
  padding-bottom: 9px; /* compensate for border width */
}
```

No glowing focus theatrics. Accent underline on active.

### Cards / Panels

```css
.panel {
  background: var(--bg-cream);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.panel-header {
  padding: var(--space-4) var(--space-6);
  border-bottom: 1px solid var(--border-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-body {
  padding: var(--space-6);
}
```

### State Entry (History Log)

```css
.state-entry {
  padding: var(--space-3) 0;
}

.state-entry + .state-entry {
  border-top: 1px solid var(--border-light);
}

.state-entry-date {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: var(--space-1);
}

.state-entry-content {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 400;
  color: var(--text-primary);
  line-height: 1.5;
}
```

### Status Indicators

```css
.status {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--text-tertiary);
}

/* Active / current state — subtle dot */
.status--active::before {
  content: '';
  display: inline-block;
  width: 6px;
  height: 6px;
  background: var(--accent-forest);
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
```

Copy format: "Updated Feb 12" / "Current as of 4:30 PM" / "3 changes"

---

## 4. Motion System

All motion communicates state change, then returns to stillness.

```css
/* Fade in — for new content appearing */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-in {
  animation: fadeIn 200ms ease forwards;
}

/* Highlight pulse — for updated fields */
@keyframes highlightPulse {
  0% { background-color: transparent; }
  20% { background-color: rgba(31, 42, 68, 0.06); }
  100% { background-color: transparent; }
}

.animate-update {
  animation: highlightPulse 1.2s ease;
}

/* Respect reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

**Allowed:**
- 150–250ms fade transitions
- Subtle highlight pulse on updated fields
- Smooth height transitions for expanding content

**Prohibited:**
- Bounce easing
- Elastic transitions
- Toast notifications
- Confetti
- Slide-in panels
- Loading spinners with personality ("Almost there!")

---

## 5. Layout System

### Max Widths

| Context | Max Width |
|---|---|
| Content (reading) | 720px |
| Page (wider context) | 960px |
| Full bleed | 100% with padding |

### Container

```css
.container {
  max-width: 720px;
  margin: 0 auto;
  padding: 0 var(--space-8);
}

.container--wide {
  max-width: 960px;
}

@media (max-width: 640px) {
  .container {
    padding: 0 var(--space-5);
  }
}
```

### Section Spacing

| Section type | Padding |
|---|---|
| Major section | 80px top/bottom |
| Sub-section | 48px top/bottom |
| Compact | 32px top/bottom |
| Mobile (major) | 56px top/bottom |

### Grid

Use CSS Grid sparingly. Prefer single-column layouts for content. Grid for use-case cards and comparison layouts only.

```css
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px;
}

@media (max-width: 640px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }
}
```

---

## 6. Accessibility

| Requirement | Standard |
|---|---|
| Contrast ratio | WCAG AA minimum (4.5:1 normal text, 3:1 large text) |
| Font size minimum | 13px (labels), 15px (body content) |
| Line height | 1.5+ for body text |
| Focus states | Visible, uses `--border-focus` color |
| Touch targets | 44px minimum on mobile |
| Reduced motion | Respect `prefers-reduced-motion` |

### Contrast Verification

| Pair | Ratio | Pass |
|---|---|---|
| --text-primary on --bg-primary | 13.5:1 | AA |
| --text-secondary on --bg-primary | 5.1:1 | AA |
| --text-tertiary on --bg-primary | 3.2:1 | AA Large only |
| --text-primary on --bg-cream | 13.2:1 | AA |
| --bg-primary on --text-primary | 13.5:1 | AA (reversed, for buttons) |

---

## 7. Design Litmus Test

Before shipping any component, screen, or interaction:

**Does this feel like infrastructure?**
Or does it feel like software trying to impress?

**If it performs, remove it.**
**If it stabilizes, keep it.**

### Checklist

- [ ] No bright gradients
- [ ] No celebration animations
- [ ] No emoji
- [ ] No novelty fonts
- [ ] No dashboard density
- [ ] No widget grids
- [ ] No toast notifications
- [ ] No mascots or illustrations
- [ ] Generous white space
- [ ] Strong typographic hierarchy
- [ ] Muted, neutral color palette
- [ ] Subtle, purposeful motion only
- [ ] Publication feel, not SaaS feel
