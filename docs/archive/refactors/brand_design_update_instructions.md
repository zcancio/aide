# aide — Design System Update Instructions

**Purpose:** Update all design references across the codebase to match the finalized brand identity. The old design system used Cormorant Garamond + IBM Plex Sans with navy/forest/burgundy accents. The new system uses Playfair Display + Instrument Sans + DM Sans with warm grayscale + sage.

---

## 1. Typography — Find & Replace

### Fonts to replace

| Old | New | Role |
|-----|-----|------|
| `'Cormorant Garamond'` | `'Playfair Display'` | Display / serif / page titles / wordmark |
| `'IBM Plex Sans'` | `'DM Sans'` | Body text / UI labels / captions |
| _(none — add new)_ | `'Instrument Sans'` | Section headings / card titles / nav |

### CSS variable updates

```css
/* OLD */
--font-serif: 'Cormorant Garamond', Georgia, 'Times New Roman', serif;
--font-sans: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

/* NEW */
--font-serif: 'Playfair Display', Georgia, serif;
--font-sans: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-heading: 'Instrument Sans', -apple-system, BlinkMacSystemFont, sans-serif;
```

### Google Fonts link — replace all instances

```html
<!-- OLD -->
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">

<!-- NEW -->
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Instrument+Sans:wght@400;500;600;700&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">
```

### Type scale updates

| Level | Font | Size | Weight | Line Height | Use |
|-------|------|------|--------|-------------|-----|
| Display | `--font-serif` (Playfair) | 48–64px | 700 | 1.12 | Hero headlines |
| H1 | `--font-serif` (Playfair) | 36–42px | 700 | 1.2 | Page titles |
| H2 | `--font-serif` (Playfair) | 28–32px | 700 | 1.25 | Section headings |
| H3 | `--font-heading` (Instrument Sans) | 18–20px | 600 | 1.4 | Subsection headings |
| Body | `--font-sans` (DM Sans) | 16px | 400 | 1.65 | Paragraphs |
| Body Small | `--font-sans` (DM Sans) | 15px | 400 | 1.55 | Secondary content |
| UI Label | `--font-sans` (DM Sans) | 13–14px | 500 | 1.4 | Buttons, nav, labels |
| Caption | `--font-sans` (DM Sans) | 12px | 400 | 1.4 | Timestamps, metadata |
| Overline | `--font-sans` (DM Sans) | 11px | 600 | 1.3 | Section labels (uppercase) |

**Key change:** Old system used `font-weight: 400` for serif headings (Cormorant was decorative at 400). New system uses `font-weight: 700` for Playfair Display headings. Old system used `font-weight: 300` for body text. New system uses `font-weight: 400` — DM Sans 400 is already light enough.

### H3 now uses Instrument Sans, not the sans body font

```css
/* OLD */
.aide-heading--3 {
  font-family: var(--font-sans);
  font-weight: 500;
}

/* NEW */
.aide-heading--3 {
  font-family: var(--font-heading);
  font-weight: 600;
}
```

---

## 2. Color Palette — Full Replacement

### Old → New color mapping

```css
/* OLD PALETTE */
--bg-primary: #fafaf9;       /* cool off-white */
--bg-cream: #faf5ef;
--text-primary: #2d3748;     /* blue-gray */
--text-secondary: #4a5568;
--text-tertiary: #a0aec0;    /* cool gray */
--text-slate: #4a5568;
--border: #e2e8f0;           /* cool border */
--border-light: #edf2f7;
--accent-steel: #4a6fa5;     /* blue links */
--accent-navy: #2c5282;      /* navy buttons */
--accent-forest: #48bb78;    /* green success */
--accent-burgundy: #5A2F3B;  /* red errors */

/* NEW PALETTE */
--bg-primary: #F7F5F2;       /* warm off-white */
--bg-secondary: #EFECEA;
--bg-tertiary: #E6E3DF;
--bg-elevated: #FFFFFF;

--text-primary: #2D2D2A;     /* warm charcoal */
--text-secondary: #6B6963;   /* warm gray */
--text-tertiary: #A8A5A0;    /* light warm gray */
--text-inverse: #F7F5F2;

--border-subtle: #E0DDD8;
--border-default: #D4D1CC;
--border-strong: #A8A5A0;

/* Sage accent scale */
--sage-50: #F0F3ED;
--sage-100: #DDE4D7;
--sage-200: #C2CCB8;
--sage-300: #A3B394;
--sage-400: #8B9E7C;
--sage-500: #7C8C6E;          /* primary accent */
--sage-600: #667358;
--sage-700: #515C46;
--sage-800: #3C4534;
--sage-900: #282E23;

--accent: var(--sage-500);
--accent-hover: var(--sage-600);
--accent-subtle: var(--sage-50);
--accent-muted: var(--sage-100);
```

### Dark mode

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

  --accent: var(--sage-400);      /* #8B9E7C — lighter in dark mode */
  --accent-hover: var(--sage-300);
  --accent-subtle: #2A2E27;
  --accent-muted: #333829;
}
```

### Specific color find-and-replace

Run these across the entire codebase:

```
#fafaf9  →  #F7F5F2    (bg-primary)
#faf5ef  →  #EFECEA    (bg-cream → bg-secondary)
#2d3748  →  #2D2D2A    (text-primary)
#4a5568  →  #6B6963    (text-secondary/slate)
#a0aec0  →  #A8A5A0    (text-tertiary)
#e2e8f0  →  #E0DDD8    (border)
#edf2f7  →  #E0DDD8    (border-light → border-subtle)
#4a6fa5  →  #7C8C6E    (accent-steel → sage-500)
#2c5282  →  #667358    (accent-navy → sage-600)
#48bb78  →  #7C8C6E    (accent-forest → sage-500)
```

### Remove these variables (no longer used)

```
--accent-steel
--accent-navy
--accent-forest
--accent-burgundy
--bg-cream
--text-slate
```

---

## 3. Border Radius

```css
/* OLD */
--radius-sm: 3px;    /* was 4px in some files */
--radius-md: 5px;
--radius-lg: 8px;

/* NEW */
--radius-sm: 6px;
--radius-md: 10px;
--radius-lg: 16px;
--radius-full: 999px;
```

---

## 4. Wordmark & Tagline

### Wordmark

- **Old:** `AIde` (mixed case)
- **New:** `aide` (all lowercase)
- Find all instances of `AIde` in display/heading contexts and replace with `aide`
- The wordmark uses Playfair Display 700 with a sage thin underline on "ai":

```html
<span class="wordmark">
  <span style="text-decoration:underline;text-decoration-color:#7C8C6E;text-underline-offset:3px;text-decoration-thickness:1px">ai</span>de
</span>
```

Or as a CSS class:

```css
.wordmark-ai {
  text-decoration: underline;
  text-decoration-color: var(--sage-500);
  text-underline-offset: 3px;
  text-decoration-thickness: 1px;
}
```

```html
<span class="wordmark"><span class="wordmark-ai">ai</span>de</span>
```

**Note:** The underline is for the wordmark/logo only. In body text, "aide" is written plain lowercase with no underline.

### Tagline

- **Old:** `For what you're running.`
- **New:** `For what you're living.`
- Find and replace all instances across docs, HTML, config, and copy.

### CLAUDE.md update

```markdown
**Tagline:** "For what you're living."
```

---

## 5. Icons — Tabler at 1.0px

### Old → New

- **Old:** No icon library specified (or Lucide in some places)
- **New:** Tabler Icons with `stroke-width="1.0"` (thinner than Tabler's default 1.5)

### CDN

```html
<!-- Tabler Icons CSS (if using icon font) -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">
```

### Inline SVG pattern (preferred for control over stroke width)

All Tabler SVGs should use these attributes:

```html
<svg width="20" height="20" viewBox="0 0 24 24"
  fill="none" stroke="currentColor"
  stroke-width="1.0" stroke-linecap="round" stroke-linejoin="round">
  <!-- path data from Tabler -->
</svg>
```

### Key icon mapping

| Use | Tabler Icon | Notes |
|-----|-------------|-------|
| Home | `icon-home` | |
| Dashboard | `icon-layout-dashboard` | |
| Settings | `icon-settings` | |
| Edit / Compose | `icon-pencil` | |
| Publish | `icon-world-upload` | |
| New aide | `icon-plus` | |
| Chat / AI | `icon-message-circle` | |
| Delete | `icon-trash` | |
| Copy | `icon-copy` | |
| Check | `icon-check` | |
| Status active | `icon-circle-filled` | 8px, sage |
| Status thinking | `icon-circle-filled` | 8px, amber, pulsing |
| Status idle | `icon-circle` | 8px, gray |

---

## 6. Component Updates

### Buttons

```css
/* Primary */
.btn-primary {
  font-family: var(--font-sans);    /* DM Sans */
  font-size: 14px;
  font-weight: 500;
  color: var(--text-inverse);        /* #F7F5F2 */
  background: var(--text-primary);   /* #2D2D2A */
  padding: 12px 24px;
  border: none;
  border-radius: var(--radius-md);   /* 10px */
  cursor: pointer;
  transition: background 0.2s ease;
}
.btn-primary:hover {
  background: var(--sage-700);       /* #515C46 */
}

/* Secondary */
.btn-secondary {
  color: var(--text-primary);
  background: var(--bg-secondary);   /* #EFECEA */
  border: 1px solid var(--border-default);
}
.btn-secondary:hover {
  background: var(--bg-tertiary);
}

/* Ghost */
.btn-ghost {
  color: var(--text-secondary);
  background: transparent;
  border: none;
}
.btn-ghost:hover {
  color: var(--text-primary);
  background: var(--bg-secondary);
}
```

### Tags / Badges

```css
.tag-sage {
  background: var(--sage-50);
  color: var(--sage-600);
}
.tag-neutral {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}
```

### Input fields

```css
.input-field {
  font-family: var(--font-sans);
  font-size: 15px;
  padding: 12px 16px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  color: var(--text-primary);
}
.input-field:focus {
  border-color: var(--sage-500);
  outline: none;
  box-shadow: 0 0 0 3px var(--sage-50);
}
```

---

## 7. Files to Update

Search the entire codebase. Priority files:

| File | What to change |
|------|---------------|
| `CLAUDE.md` | Tagline, font references |
| `engine.py` | CSS string (has full embedded stylesheet) |
| `engine.ts` | CSS string (has full embedded stylesheet) |
| `engine.js` | CSS string (has full embedded stylesheet) |
| `docs/eng_design/specs/aide_ui_design_system_spec.md` | Full rewrite of CSS vars, type scale, font loading |
| `docs/eng_design/specs/aide_renderer_spec.md` | CSS generation section, style token table |
| `frontend/index.html` | Google Fonts link, any inline styles |
| Any `.css` files | Color values, font-family declarations |
| Any `.html` templates | Font loading links, inline styles |

### Grep commands to find all instances

```bash
# Typography
grep -rn "Cormorant" --include="*.py" --include="*.ts" --include="*.js" --include="*.html" --include="*.css" --include="*.md"
grep -rn "IBM Plex" --include="*.py" --include="*.ts" --include="*.js" --include="*.html" --include="*.css" --include="*.md"

# Colors
grep -rn "#fafaf9\|#faf5ef\|#2d3748\|#4a5568\|#a0aec0\|#e2e8f0\|#edf2f7\|#4a6fa5\|#2c5282\|#48bb78" --include="*.py" --include="*.ts" --include="*.js" --include="*.html" --include="*.css" --include="*.md"

# Wordmark case
grep -rn "AIde" --include="*.py" --include="*.ts" --include="*.js" --include="*.html" --include="*.css" --include="*.md"

# Old tagline
grep -rn "what you're running" --include="*.py" --include="*.ts" --include="*.js" --include="*.html" --include="*.css" --include="*.md"

# Old accent variables
grep -rn "accent-steel\|accent-navy\|accent-forest\|accent-burgundy" --include="*.py" --include="*.ts" --include="*.js" --include="*.html" --include="*.css" --include="*.md"

# Old radius values
grep -rn "radius-sm\|radius-md\|radius-lg" --include="*.py" --include="*.ts" --include="*.js" --include="*.html" --include="*.css" --include="*.md"
```

---

## 8. Engine CSS String — Critical

The `engine.py`, `engine.ts`, and `engine.js` files each contain a full CSS string that gets embedded into rendered aide pages. This is the highest-impact change — every published aide page uses this CSS.

The embedded CSS string must be updated with all of the above: new fonts, new colors, new variables, new radius values. The Google Fonts `@import` or `<link>` within the rendered HTML `<head>` must also point to the new font families.

---

## 9. Validation Checklist

After making changes, verify:

- [ ] All three engine files (`.py`, `.ts`, `.js`) have identical CSS output
- [ ] No references to Cormorant Garamond, IBM Plex Sans anywhere
- [ ] No references to old color hex values (#fafaf9, #2d3748, #4a5568, etc.)
- [ ] No references to accent-steel, accent-navy, accent-forest, accent-burgundy
- [ ] "AIde" only appears in code identifiers (class names, variables) — never in display text
- [ ] All display text uses lowercase "aide"
- [ ] Tagline reads "For what you're living." everywhere
- [ ] Google Fonts loads Playfair Display, Instrument Sans, DM Sans
- [ ] All icon SVGs use `stroke-width="1.0"`
- [ ] Border radius uses 6/10/16/999 not 3/5/8
- [ ] Dark mode variables are present and use the warm dark palette
- [ ] Existing tests still pass
