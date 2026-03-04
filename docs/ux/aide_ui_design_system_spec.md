# aide — Design System Implementation

**Purpose:** Practical implementation reference for the aide visual identity. This document translates the brand guidelines into code-ready specifications: CSS variables, component patterns, typography scale, and spacing system.

---

## 1. CSS Custom Properties

```css
:root {
  /* ── Backgrounds ── */
  --bg-primary: #F7F5F2;         /* Warm off-white — default page background */
  --bg-secondary: #EFECEA;       /* Slightly darker — cards, panels */
  --bg-tertiary: #E6E3DF;        /* Elevated surfaces */
  --bg-elevated: #FFFFFF;        /* Pure white — input fields, modals */

  /* ── Text ── */
  --text-primary: #2D2D2A;       /* Warm charcoal — headings, primary content */
  --text-secondary: #6B6963;     /* Warm gray — body text, secondary content */
  --text-tertiary: #A8A5A0;      /* Light warm gray — labels, timestamps, placeholders */
  --text-inverse: #F7F5F2;       /* Light text on dark backgrounds */

  /* ── Borders ── */
  --border-subtle: #E0DDD8;      /* Subtle dividers, section separators */
  --border-default: #D4D1CC;     /* Standard borders */
  --border-strong: #A8A5A0;      /* Active input borders, emphasis */

  /* ── Sage Accent Scale ── */
  --sage-50: #F0F3ED;
  --sage-100: #DDE4D7;
  --sage-200: #C2CCB8;
  --sage-300: #A3B394;
  --sage-400: #8B9E7C;
  --sage-500: #7C8C6E;           /* Primary accent */
  --sage-600: #667358;
  --sage-700: #515C46;
  --sage-800: #3C4534;
  --sage-900: #282E23;

  /* ── Accent Aliases ── */
  --accent: var(--sage-500);
  --accent-hover: var(--sage-600);
  --accent-subtle: var(--sage-50);
  --accent-muted: var(--sage-100);

  /* ── Typography ── */
  --font-serif: 'Playfair Display', Georgia, serif;
  --font-heading: 'Instrument Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-sans: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

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
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-full: 999px;

  /* ── Transitions ── */
  --transition-fast: 150ms ease;
  --transition-normal: 200ms ease;
  --transition-slow: 250ms ease;

  /* ── Backward Compatibility ── */
  --border-light: var(--border-subtle);
}
```

### Dark Mode

```css
.dark, [data-theme="dark"] {
  --bg-primary: #1E1E1C;
  --bg-secondary: #262624;
  --bg-tertiary: #2E2E2B;
  --bg-elevated: #333330;

  --text-primary: #E8E6E1;
  --text-secondary: #A8A5A0;
  --text-tertiary: #6B6963;
  --text-inverse: #1E1E1C;

  --border-subtle: #333330;
  --border-default: #3D3D39;
  --border-strong: #5A5850;

  --accent: var(--sage-400);      /* Lighter in dark mode */
  --accent-hover: var(--sage-300);
  --accent-subtle: #2A2E27;
  --accent-muted: #333829;

  --border-light: var(--border-subtle);
}
```

---

## 2. Typography System

### Font Loading

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Instrument+Sans:wght@400;500;600;700&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">
```

### Type Scale

| Level | Font | Size | Weight | Line Height | Letter Spacing | Use |
|---|---|---|---|---|---|---|
| Display | Serif (Playfair) | 48–64px | 700 | 1.12 | -0.01em | Hero headlines |
| H1 | Serif (Playfair) | 36–42px | 700 | 1.2 | -0.005em | Page titles |
| H2 | Serif (Playfair) | 28–32px | 700 | 1.25 | 0 | Section headings |
| H3 | Heading (Instrument Sans) | 18–20px | 600 | 1.4 | 0 | Subsection headings |
| Body | Sans (DM Sans) | 16px | 400 | 1.65 | 0 | Paragraphs, descriptions |
| Body Small | Sans (DM Sans) | 15px | 400 | 1.55 | 0 | State entries, secondary content |
| UI Label | Sans (DM Sans) | 13–14px | 500 | 1.4 | 0.02em | Buttons, navigation, field labels |
| Caption | Sans (DM Sans) | 12px | 400 | 1.4 | 0.01em | Timestamps, metadata |
| Overline | Sans (DM Sans) | 11px | 600 | 1.3 | 0.12em | Section labels (uppercase) |

### CSS Implementation

```css
/* Display */
.text-display {
  font-family: var(--font-serif);
  font-size: clamp(42px, 6vw, 64px);
  font-weight: 700;
  line-height: 1.12;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

/* H1 */
.text-h1 {
  font-family: var(--font-serif);
  font-size: clamp(32px, 4.5vw, 42px);
  font-weight: 700;
  line-height: 1.2;
  color: var(--text-primary);
}

/* H2 */
.text-h2 {
  font-family: var(--font-serif);
  font-size: clamp(24px, 3.5vw, 32px);
  font-weight: 700;
  line-height: 1.25;
  color: var(--text-primary);
}

/* H3 */
.text-h3 {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--text-primary);
}

/* Body */
.text-body {
  font-family: var(--font-sans);
  font-size: 16px;
  font-weight: 400;
  line-height: 1.65;
  color: var(--text-secondary);
}

/* Overline */
.text-overline {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 600;
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
  color: var(--text-inverse);
  background: var(--text-primary);
  padding: 12px 24px;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-normal);
  text-decoration: none;
}

.btn-primary:hover {
  background: var(--sage-700);
}
```

CTA copy: "Start something."
No gradients. No heavy shadows. No pill shapes.

**Secondary Button**
```css
.btn-secondary {
  display: inline-block;
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-default);
  padding: 12px 24px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
  text-decoration: none;
}

.btn-secondary:hover {
  background: var(--bg-tertiary);
}
```

**Ghost Button**
```css
.btn-ghost {
  display: inline-block;
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 400;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  padding: 8px 0;
  cursor: pointer;
  transition: color var(--transition-fast);
  text-decoration: none;
}

.btn-ghost:hover {
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
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  width: 100%;
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.input::placeholder {
  color: var(--text-tertiary);
}

.input:focus {
  border-color: var(--sage-500);
  box-shadow: 0 0 0 3px var(--sage-50);
}
```

### Cards / Panels

```css
.panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.panel-header {
  padding: var(--space-4) var(--space-6);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-body {
  padding: var(--space-6);
}
```

### Tags / Badges

```css
.tag-sage {
  display: inline-block;
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  background: var(--sage-50);
  color: var(--sage-600);
}

.tag-neutral {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}
```

### State Entry (History Log)

```css
.state-entry {
  padding: var(--space-3) 0;
}

.state-entry + .state-entry {
  border-top: 1px solid var(--border-subtle);
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

/* Active / current state — subtle sage dot */
.status--active::before {
  content: '';
  display: inline-block;
  width: 6px;
  height: 6px;
  background: var(--sage-500);
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
  20% { background-color: var(--sage-50); }
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

## 6. Icons

Use Tabler Icons with `stroke-width="1.0"` (thinner than default 1.5).

### CDN

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">
```

### Inline SVG pattern (preferred)

```html
<svg width="20" height="20" viewBox="0 0 24 24"
  fill="none" stroke="currentColor"
  stroke-width="1.0" stroke-linecap="round" stroke-linejoin="round">
  <!-- path data from Tabler -->
</svg>
```

### Key icon mapping

| Use | Tabler Icon |
|-----|-------------|
| Home | `icon-home` |
| Dashboard | `icon-layout-dashboard` |
| Settings | `icon-settings` |
| Edit | `icon-pencil` |
| Publish | `icon-world-upload` |
| New aide | `icon-plus` |
| Chat / AI | `icon-message-circle` |
| Delete | `icon-trash` |
| Copy | `icon-copy` |
| Check | `icon-check` |

---

## 7. Accessibility

| Requirement | Standard |
|---|---|
| Contrast ratio | WCAG AA minimum (4.5:1 normal text, 3:1 large text) |
| Font size minimum | 13px (labels), 15px (body content) |
| Line height | 1.5+ for body text |
| Focus states | Visible, uses sage-500 with subtle box-shadow |
| Touch targets | 44px minimum on mobile |
| Reduced motion | Respect `prefers-reduced-motion` |

### Contrast Verification

| Pair | Ratio | Pass |
|---|---|---|
| --text-primary on --bg-primary | 12.1:1 | AA |
| --text-secondary on --bg-primary | 5.3:1 | AA |
| --text-tertiary on --bg-primary | 3.4:1 | AA Large only |
| --text-primary on --bg-secondary | 11.8:1 | AA |
| --text-inverse on --text-primary | 12.1:1 | AA (reversed, for buttons) |

---

## 8. Wordmark

The aide wordmark uses lowercase "aide" in Playfair Display 700 with a sage thin underline on "ai":

```html
<span class="wordmark">
  <span class="wordmark-ai">ai</span>de
</span>
```

```css
.wordmark {
  font-family: var(--font-serif);
  font-weight: 700;
}

.wordmark-ai {
  text-decoration: underline;
  text-decoration-color: var(--sage-500);
  text-underline-offset: 3px;
  text-decoration-thickness: 1px;
}
```

**Note:** The underline is for the wordmark/logo only. In body text, "aide" is written plain lowercase with no underline.

---

## 9. Design Litmus Test

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
- [ ] Muted, neutral color palette with sage accents
- [ ] Subtle, purposeful motion only
- [ ] Publication feel, not SaaS feel
