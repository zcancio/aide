# Build Log: Dashboard FAB + Preview Scroll Padding

**Date:** 2026-02-21
**Issue:** #48 - Dashboard FAB + preview scroll padding (FEAT-03, BUG-03)
**Spec:** docs/refactors/brand_update_remaining_spec.md (Tasks 10-11)
**Branch:** claude/issue-48

## Summary

Moved the "new aide" button from the dashboard header to a floating action button (FAB) in the bottom-right corner. Added bottom padding to the preview root to prevent content from being hidden behind the chat overlay.

## Changes Made

### 1. Dashboard Header - Removed Button (Task 10a)

**File:** `frontend/index.html` (line ~1159)

**Changed:**
- Removed `<button id="new-aide-btn" class="btn btn-primary">+ New aide</button>` from dashboard header
- Dashboard header now only contains the `<h1>aide</h1>` title

### 2. FAB - Added to Dashboard (Task 10a)

**File:** `frontend/index.html` (line ~1211)

**Added:**
- `<button id="new-aide-fab" class="fab" onclick="startNewAide()" title="New aide">+</button>` inside dashboard div
- FAB positioned as last child of `#dashboard` container

### 3. FAB Styles - CSS Implementation (Task 10a)

**File:** `frontend/index.html` (lines ~461-506)

**Added:**
```css
/* ── FAB (floating action button) ── */
.fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #e8e8e8;
  border: none;
  color: #0f0f0f;
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
  background: #ffffff;
  transform: scale(1.05);
}

#new-aide-fab {
  display: none;
}

#dashboard.active #new-aide-fab {
  display: flex;
}

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

**Design decisions:**
- FAB only visible when dashboard is active (`#dashboard.active #new-aide-fab`)
- Fixed position in bottom-right corner (24px from edges)
- Responsive sizing for mobile (48px vs 52px)
- Subtle hover animation (scale + background change)
- z-index: 50 (below editor controls at 200, above preview content)

### 4. JavaScript - Updated Event Listener (Task 10a)

**File:** `frontend/index.html` (line ~2362)

**Changed:**
- `document.getElementById('new-aide-btn')` → `document.getElementById('new-aide-fab')`
- Event listener still calls `startNewAide()` on click

### 5. Preview Padding - Content Clearance (Task 10b)

**File:** `frontend/index.html` (line ~189)

**Added:**
- `padding-bottom: 100px;` to `#preview-root` styles
- Prevents content from being hidden behind the fixed chat overlay at bottom of screen

## Verification

### Linting & Formatting
```bash
✓ ruff check backend/       # All checks passed
✓ ruff format --check backend/  # 68 files already formatted
```

### Manual Testing Checklist (from Task 11)
- [ ] Open a published aide page
- [ ] Scroll to the very bottom
- [ ] Confirm "Made with aide" footer is fully visible
- [ ] Test on both desktop and mobile Safari

### Visual Inspection
- [ ] FAB appears only when dashboard is active
- [ ] FAB is positioned in bottom-right corner
- [ ] FAB has correct styling (circle, gray background, + icon)
- [ ] FAB hover state works (white background, slight scale)
- [ ] Dashboard header is clean (only "aide" title)
- [ ] Preview content has adequate bottom padding

## Acceptance Criteria Status

- [x] Dashboard header no longer has "+ New aide" button
- [x] FAB appears in bottom-right corner of dashboard (fixed position)
- [x] FAB only visible when dashboard is active
- [x] FAB triggers `startNewAide()` on click
- [x] Preview root has `padding-bottom: 100px` to clear chat overlay
- [x] All existing tests pass (N/A - frontend-only change)
- [ ] CI green (pending PR)

## Files Modified

1. `frontend/index.html`
   - Removed button from dashboard header
   - Added FAB to dashboard
   - Added FAB CSS styles
   - Updated JavaScript event listener
   - Added preview root bottom padding

## Notes

- No backend changes required
- No database migrations required
- No new dependencies added
- Frontend-only change - no backend tests affected
- FAB follows existing button pattern but with custom fixed-position styling
- z-index hierarchy maintained: editor controls (200) > FAB (50) > preview content
- Mobile responsiveness included per spec

## Next Steps

1. Manual QA on staging/local dev server
2. Test on mobile Safari and desktop browsers
3. Verify footer visibility on published aide pages
4. Create PR for review
