Review the codebase against docs/aide_security_checklist.md.

Go through every section and every checkbox item. For each item, determine:
- ✅ **Done** — implementation exists and is correct
- ⚠️ **Partial** — some implementation exists but incomplete or has issues
- ❌ **Missing** — not implemented at all
- ➖ **N/A** — not applicable yet (e.g., Stripe items before Phase 3)

## Priority order

Check these sections first (highest risk):
1. Authentication (Magic Links) — token randomness, expiry, single-use, rate limiting
2. SQL Injection — grep for f-strings near SQL keywords, verify all queries use $1/$2
3. Authorization — RLS policies exist on all tables, user_conn() used in all route handlers
4. Input Validation — Pydantic models on all endpoints, max_length constraints
5. Secrets Management — no hardcoded secrets, .env not in git

Then check remaining sections.

## Also check Hard Rules from CLAUDE.md

Flag any violations of the Hard Rules:
- ORM usage
- SQL outside repos/ directory
- Raw dicts instead of Pydantic models in routes
- system_conn() used in route handlers that return user data
- f-strings in SQL
- Google/OAuth code
- Secrets in code or Docker layers

## Output format

For each section, list every checkbox with its status and a one-line explanation if partial or missing. End with a summary count: X done, Y partial, Z missing.
