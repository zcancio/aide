Implement the next phase from docs/aide_launch_plan.md.

## Process

1. Read docs/aide_launch_plan.md and identify which phase to implement (the user will specify, or pick the earliest incomplete phase).

2. For each checkbox item in that phase:
   - Check if it's already implemented in the codebase
   - If not, implement it following the patterns in CLAUDE.md and docs/aide_data_access.md
   - Mark it as done when complete

3. After implementing each item, verify:
   - Code follows Hard Rules from CLAUDE.md
   - SQL is in repos/ only, parameterized, uses user_conn()
   - Pydantic models used for all request/response
   - No Google dependencies introduced
   - Security checklist items for this area are satisfied (check docs/aide_security_checklist.md)

4. Run tests after each logical group of changes.

5. At the end, summarize what was implemented and what remains.

## Important context per phase

- **Phase 0:** Domain setup is manual (Cloudflare dashboard). Auth is magic links via Resend. Read the full 0.3 section carefully.
- **Phase 1:** Data model uses Neon Postgres (not SQLite). Follow docs/aide_data_access.md patterns exactly. Published pages go to R2.
- **Phase 2:** Turn counting is per-user, weekly reset. Managed API key routing is server-side only.
- **Phase 3:** Stripe Checkout for payments. Webhook handlers must verify signatures. Idempotent.
- **Phase 4:** Landing page follows docs/aide_design_system.md. No Google Fonts — use system fonts or self-hosted.
