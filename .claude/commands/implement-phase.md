Implement the next phase from docs/program_management/aide_launch_plan.md.

## Process

1. Read docs/program_management/aide_launch_plan.md and identify which phase to implement (the user will specify, or pick the earliest incomplete phase).

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

5. At the end, write a build log to `docs/program_management/build_log/PHASE_X_Y_<NAME>.md`:
   - Filename format: `PHASE_0_1_INFRASTRUCTURE.md`, `PHASE_1_2_DATA_MODEL.md`, etc.
   - Include:
     - **Summary**: What was implemented
     - **What Was Built**: List of files created/modified with descriptions
     - **Security Checklist Compliance**: Which items were satisfied
     - **File Structure**: Tree of new/modified files
     - **Verification**: Lint, format, test results
     - **Next Steps**: What remains in the launch plan
     - **Status**: `✅ Phase X.Y Complete` with date

6. Update the launch plan checkbox items to `[x]` for completed work.

## Important context per phase

- **Phase 0 (Foundation):** ✅ Complete. 0.1 Infrastructure (Railway, Neon, CI/CD). 0.2 Auth (magic links via Resend, JWT cookies, RLS).

- **Phase 1 (Core Product):**
  - 1.1 Kernel: ✅ Complete. Primitives, reducer, renderer, assembly.
  - 1.2 Data Model: Neon Postgres with RLS. Follow `docs/infrastructure/aide_data_access.md` patterns exactly.
  - 1.3 L2/L3 Orchestrator: L2 (Haiku) compiles intent → primitives. L3 (Sonnet) synthesizes schemas, handles images.
  - 1.4 Web Chat UI: Full-viewport preview + floating chat overlay. See `docs/prds/aide_editor_prd.md`.
  - 1.5 Signal Ear: signal-cli-rest-api on Railway. Core differentiator — "update your page from a text."
  - 1.6 Published Page Serving: R2 static hosting via Cloudflare CDN. `/s/{slug}` route.
  - 1.7 Reliability: Validation catches bad primitives. Retry logic. Event log is source of truth.

- **Phase 2 (Rate Limiting + Engine):** Turn counting per-user (50/week free), weekly reset. Host engine files on R2 for distribution.

- **Phase 3 (Payments):** Stripe Checkout for $10/mo Pro. Webhook handlers must verify signatures. Idempotent.

- **Phase 4 (Landing & Launch):** Landing page at toaide.com. Seed templates. Launch checklist (Sentry, ToS, robots.txt).

- **Phase 5 (Distribution):** Post-launch. Claude.ai Project, Claude Code skill, MCP server, Cowork plugin.
