# Phase 1.6 — Published Page Serving

**Date:** 2026-02-17
**Branch:** `claude/issue-16`
**Status:** ✅ Phase 1.6 Complete

---

## Summary

Added public page serving at `GET /s/{slug}`. Published aide HTML is fetched from R2 and returned with proper cache headers. Free tier publishes now inject the "Made with AIde" footer. OG tags and blueprint embedding were already implemented in the renderer.

---

## What Was Built

### New Files

| File | Description |
|------|-------------|
| `backend/routes/pages.py` | `GET /s/{slug}` — fetches HTML from R2, serves with Cache-Control + ETag headers, 404 for missing slugs |

### Modified Files

| File | Change |
|------|--------|
| `backend/services/r2.py` | Added `get_published(slug)` method — fetches HTML bytes from `aide-published` bucket, returns `None` on 404 |
| `backend/routes/publish.py` | Publish now passes `RenderOptions(footer="Made with AIde")` for free tier users; pro tier gets no footer |
| `backend/main.py` | Registered `pages_routes.router` |
| `backend/tests/test_routes.py` | Added `TestPublishedPageServing` (5 tests) |

---

## API Endpoints Added

### Public Page Serving
```
GET /s/{slug}  → text/html (200) or 404
```
- No authentication required
- Fetches HTML from R2 `aide-published/{slug}/index.html`
- Returns `Cache-Control: public, max-age=300, s-maxage=3600, stale-while-revalidate=86400`
- Returns `ETag: "{md5-of-content}"` for conditional requests
- Returns `X-Content-Type-Options: nosniff`
- Returns 404 HTML page for missing slugs

---

## Cache Strategy

| Header | Value | Meaning |
|--------|-------|---------|
| `Cache-Control` | `public, max-age=300, s-maxage=3600, stale-while-revalidate=86400` | 5-min browser TTL, 1-hour CDN TTL, 24-hour stale-while-revalidate |
| `ETag` | `"{md5}"` | Content hash for conditional `If-None-Match` requests |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing |

Cloudflare CDN respects `s-maxage` and will serve from edge cache for 1 hour before revalidating with the origin. This keeps Railway load near zero for published page reads.

---

## Footer Injection

The renderer already supported `RenderOptions.footer` for injecting the "Made with AIde" link. The publish endpoint now passes the correct value based on user tier:

```python
footer_text = "Made with AIde" if user.tier == "free" else None
options = RenderOptions(footer=footer_text)
html_content = render(aide.state, blueprint=blueprint, events=[], options=options)
```

Free tier → footer rendered as `<footer class="aide-footer"><a href="https://toaide.com">Made with AIde</a></footer>`
Pro tier → no footer element.

---

## OG Tags and Blueprint (Pre-existing)

The renderer (`engine/kernel/renderer.py`) already produced:

- **OG tags:** `og:title`, `og:type`, `og:description`, `meta[name=description]`
- **Blueprint JSON:** embedded as `<script type="application/aide-blueprint+json">` in `<head>`
- **Snapshot JSON:** embedded as `<script type="application/aide+json">` in `<head>`
- **Events JSON:** embedded as `<script type="application/aide-events+json">` in `<head>` (when events present)

No changes were needed to the renderer for these features.

---

## Security Checklist

| Item | Status |
|------|--------|
| `GET /s/{slug}` is public — no auth, no session cookie | ✅ |
| HTML returned as-is from R2 — no server-side execution | ✅ |
| Slug is a path parameter — no SQL involved in page serving | ✅ |
| MD5 used with `usedforsecurity=False` (ETag only, not crypto) | ✅ |
| `X-Content-Type-Options: nosniff` to prevent MIME sniffing | ✅ |
| `botocore.ClientError` caught for R2 NoSuchKey — no unhandled exceptions | ✅ |
| `bandit -r backend/ -ll` — no medium/high issues | ✅ |

---

## File Structure

```
aide/
├── backend/
│   ├── main.py                         # MODIFIED — registered pages_routes.router
│   ├── routes/
│   │   └── pages.py                    # NEW — GET /s/{slug}
│   ├── services/
│   │   └── r2.py                       # MODIFIED — added get_published()
│   └── tests/
│       └── test_routes.py              # MODIFIED — added TestPublishedPageServing (5 tests)
└── docs/
    └── program_management/
        ├── aide_launch_plan.md         # MODIFIED — 1.6 marked complete
        └── build_log/
            └── PHASE_1_6_PUBLISHED_PAGE_SERVING.md  # this file
```

---

## Verification

### Linting
```
ruff check backend/    → All checks passed!
ruff format --check    → 41 files already formatted
bandit -r backend/ -ll → No medium/high issues
```

### Tests
```
DATABASE_URL=postgres://aide_app:test@localhost:5432/aide_test pytest backend/tests/ -v

99 passed, 0 failed, 21 warnings
```

New tests added: 5 (`TestPublishedPageServing`)
- `test_serve_published_page` — 200 with HTML, cache headers, ETag present
- `test_serve_missing_slug` — 404 for R2 miss
- `test_serve_no_auth_required` — public endpoint, no cookie needed
- `test_etag_content_hash` — ETag matches MD5 of content
- `test_publish_free_tier_includes_footer` — render called with `RenderOptions(footer="Made with AIde")`

---

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| User publishes aide with slug "my-list" | ✅ (pre-existing) |
| Visiting `toaide.com/s/my-list` shows the rendered HTML | ✅ |
| Page has proper OG tags for social sharing | ✅ (pre-existing in renderer) |
| Free tier pages show "Made with AIde" footer | ✅ |
| Cloudflare caches the page with appropriate TTL | ✅ (via Cache-Control + s-maxage headers) |

---

## Next Steps

**Phase 1.7 — Reliability**
- Retry logic for L2/L3 API failures
- R2 upload retry on failure
- Signal connection reconnect on disconnect
