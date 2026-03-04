# aide — Brand Update Plan

**Based on:** `zcancio/aide` repo at commit `b1222fe`
**Date:** 2026-02-21

---

## Current State

The new brand system (Playfair Display + Instrument Sans + DM Sans, warm grayscale + sage palette) has been **partially applied**. The core rendering pipeline is updated, but documentation, supporting files, and a few code files still carry the old brand.

### ✅ Already Updated

| File | Status |
|------|--------|
| `engine/engine.min.js` | New fonts, sage palette, new vars |
| `engine/builds/engine.compact.js` | Matches engine.min.js |
| `engine/builds/engine.py` | New brand CSS (2788 lines) |
| `engine/kernel/react_preview.py` | Playfair + DM Sans, new palette, `--border-light` alias |
| `frontend/index.html` | New font loading, new palette for editor shell, new CSS vars for rendered pages |
| `engine/SKILL.md` | Playfair Display, DM Sans references |
| `skills/aide-builder/SKILL.md` | Correct font references |
| `skills/aide-builder/examples/poker-league.html` | New brand CSS |

### ❌ Needs Updating

Organized by priority and effort.

---

## Tier 1 — User-Facing / Shipped Code (do first)

### 1. `backend/services/email.py` — Magic link email template

**What's wrong:** "AIde" (mixed case) in 6 places — email subject, heading, body text. Should be lowercase "aide" per wordmark rules.

**Changes:**
- Line 33: `<title>Sign in to AIde</title>` → `<title>Sign in to aide</title>`
- Line 114: `<h1>AIde</h1>` → `<h1>aide</h1>`
- Line 118: `sign in to AIde` → `sign in to aide`
- Line 119: `Sign in to AIde` → `Sign in to aide`
- Line 135: `Sign in to AIde` → `Sign in to aide`
- Line 137: `sign in to AIde` → `sign in to aide`
- Line 149: `"subject": "Sign in to AIde"` → `"subject": "Sign in to aide"`
- Consider updating the email's visual design to use DM Sans and the sage palette (currently generic system font + black header)

**Effort:** Small (~15 min)

### 2. `frontend/flight-recorder.html` — Flight recorder UI

**What's wrong:** 9 references to old colors (`#e2e8f0`, `#2d3748`). This is a React-in-HTML file (1313 lines) used for session replay/debugging.

**Changes (inline JS styles):**
- `#e2e8f0` → `#E0DDD8` (border-subtle) — 7 occurrences
- `#2d3748` → `#2D2D2A` (text-primary) — 1 occurrence
- `#64748b` → `#6B6963` (text-secondary) if present
- Body background if using `#fafaf9` → `#F7F5F2`

**Effort:** Medium (~30 min, careful with JSX inline styles)

### 3. `README.md` — Public repo face

**What's wrong:** "AIde" mixed case in heading, old tagline "For what you're running."

**Changes:**
- `# AIde` → `# aide`
- `**For what you're running.**` → `**For what you're living.**`
- "AIde" in body text → "aide" (4 instances)

**Effort:** Small (~10 min)

---

## Tier 2 — Active Documentation (referenced by Claude Code)

### 4. `docs/eng_design/specs/aide_ui_design_system_spec.md` — **Full rewrite needed**

**What's wrong:** This is the canonical design system spec and it's completely stale. It has:
- Cormorant Garamond + IBM Plex Sans
- Old accent vars (navy, forest, burgundy, steel)
- Old palette (#F6F5F3 bg, #1E1E1E text — close but not matching the finalized brand)
- Old radius values (3/5/8)
- No dark mode
- No sage scale
- No `--font-heading` variable

**What to do:** Rewrite the entire CSS Custom Properties section and all component specs to match the finalized brand from `design_update_instructions.md`. This is the file Claude Code reads to understand the design system, so accuracy matters.

**Effort:** Large (~1–2 hours, but critical)

### 5. `CLAUDE.md` — Claude Code instructions

**What's wrong:** No explicit tagline line. Title says `# AIde — Claude Code Guardrails`. The name "AIde" is used throughout in code-identifier context which is fine for class names/variables, but the title of the doc itself is display text.

**Changes:**
- Check if a tagline line should be added (the project-level CLAUDE.md in this claude.ai project has `**Tagline:** "For what you're running."`)
- The repo CLAUDE.md doesn't have a tagline field at all — consider adding `**Tagline:** "For what you're living."` near the top

**Effort:** Small (~10 min)

### 6. `docs/eng_design/00_overview.md` — Overview doc

**What's wrong:** Line 13: `The tagline: **For what you're running.**`

**Changes:** → `The tagline: **For what you're living.**`

**Effort:** Trivial

---

## Tier 3 — Strategy & Planning Docs

### 7. `docs/prds/aide_prd.md`

**What's wrong:** "what you're running" appears as product description throughout. This is tricky — "running" is used conceptually (you "run" a league, a budget), not just as the tagline.

**Recommendation:** Only update the explicit tagline instance if it appears verbatim. Leave conceptual uses of "running" — they describe user activity, not the tagline. The PRD is a historical document.

**Effort:** Small (~10 min)

### 8. `docs/program_management/aide_launch_plan.md`

**What's wrong:** Line 196: `Hero: "For what you're running."` — this is in the landing page task.

**Changes:** → `Hero: "For what you're living."`

**Effort:** Trivial

### 9. `docs/strategy/aide_engine_distribution.md`

**What's wrong:** Line 218: `"description": "Build and maintain living pages for what you're running."`

**Changes:** → `"Build and maintain living pages for what you're living."`

**Effort:** Trivial

### 10. `docs/strategy/aide_living_objects.md`

**What's wrong:** "what you're running" in ~4 places, used as conceptual description.

**Recommendation:** Leave as-is. This is a strategy doc describing the concept. The phrase "what you're running" is used descriptively, not as the tagline. Updating it would change the meaning.

**Effort:** Skip

---

## Tier 4 — Test Data (handle carefully)

### 11. Engine test files — Old color values as test data

**Files affected:**
- `engine/kernel/tests/tests_reducer/test_reducer_walkthrough.py`
- `engine/kernel/tests/tests_reducer/test_reducer_v2_golden.py`
- `engine/kernel/tests/tests_reducer/test_reducer_determinism.py`
- `engine/kernel/tests/tests_reducer/test_reducer_v2_style_meta_signals.py`
- `engine/kernel/tests/tests_reducer/test_reducer_round_trip.py`
- `engine/kernel/tests/tests_reducer/test_reducer_idempotency.py`

**What's there:** `#2d3748` and `#fafaf9` used as test input values for `style.set` payloads and assertions. Also `"IBM Plex Sans"` in one walkthrough test.

**Recommendation:** Update test values to new brand colors (`#2D2D2A`, `#F7F5F2`, `DM Sans`) so they don't suggest the old brand to anyone reading the tests. But these are arbitrary color values in test data — they don't affect rendering. **Run tests after changing to ensure nothing breaks.**

**Effort:** Medium (~30 min, must run full test suite)

### 12. `scripts/eval_0a.py`

**What's wrong:** Line 166: Default style suggestion uses `#2d3748`.

**Changes:** → `#2D2D2A`

**Effort:** Trivial

---

## Tier 5 — Archive (leave alone)

### 13. `docs/archive/v1.3_eng_design/specs/*`

Old renderer and primitive specs reference Cormorant Garamond. These are explicitly archived. **Do not update.**

### 14. `docs/refactors/brand_design_update_instructions.md`

This is the instructions document itself — it contains old values by design (as "find this → replace with that"). **Do not update.**

---

## Compatibility Note: `--border-light` Alias

The updated engine files use `--border-light: var(--border-subtle)` as a backward-compatibility alias. This is intentional and correct — it lets CSS that still references `border-light` work while the canonical variable is now `border-subtle`. The same pattern is used in `react_preview.py`, `engine.min.js`, `engine.compact.js`, and `frontend/index.html`.

**Do not remove these aliases** until all references to `--border-light` are cleaned up.

---

## Execution Order

```
1. backend/services/email.py          (user-facing, quick win)
2. README.md                          (public-facing, quick win)
3. CLAUDE.md                          (add tagline)
4. docs/eng_design/00_overview.md     (tagline fix)
5. docs/program_management/aide_launch_plan.md  (tagline fix)
6. docs/strategy/aide_engine_distribution.md    (tagline fix)
7. frontend/flight-recorder.html      (old colors → new)
8. scripts/eval_0a.py                 (old color → new)
9. engine/kernel/tests/**             (test data colors → new, run tests)
10. docs/eng_design/specs/aide_ui_design_system_spec.md  (full rewrite — biggest item)
```

**Estimated total effort:** 3–4 hours

---

## Validation After All Changes

```bash
# No old fonts anywhere in non-archive, non-instructions code
grep -rn "Cormorant\|IBM Plex" --include="*.py" --include="*.ts" --include="*.js" --include="*.html" --include="*.css" \
  | grep -v docs/archive | grep -v docs/refactors/brand_design | grep -v node_modules

# No old colors in non-archive, non-instructions, non-test code
grep -rn "#fafaf9\|#2d3748\|#4a5568\|#a0aec0" --include="*.py" --include="*.ts" --include="*.js" --include="*.html" \
  | grep -v docs/archive | grep -v docs/refactors/brand_design | grep -v node_modules

# No old accent vars
grep -rn "accent-steel\|accent-navy\|accent-forest\|accent-burgundy" --include="*.py" --include="*.ts" --include="*.js" --include="*.html" \
  | grep -v docs/archive | grep -v docs/refactors/brand_design | grep -v node_modules

# Old tagline only in non-tagline contexts
grep -rn "what you're running" --include="*.md" | grep -v docs/archive | grep -v docs/refactors/brand_design

# Tests still pass
pytest engine/kernel/tests/ -x
```
