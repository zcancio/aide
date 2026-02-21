---
name: spec-to-merge
description: Two-phase development pipeline with manual testing in between. Phase 1 (/spec-to-pr): reads a spec, creates a GitHub issue, implements code, pushes a PR, and notifies you it's ready to test. Phase 2 (/ship-it): after you've tested the branch locally, runs lint/test checks and enables auto-merge. Use when the user says "implement this spec", "ship this", "run the pipeline", references a spec doc, says a spec was updated, or says "ship it" / "merge it" for an existing PR.
---

# Spec-to-Merge Pipeline

Two-phase pipeline with a manual testing gap in the middle.

```
PHASE 1: /spec-to-pr                YOU                    PHASE 2: /ship-it
─────────────────────               ───                    ──────────────────
Read spec                           
Create issue                        
Branch                              
Implement                           
Push PR                             
  "PR #43 ready to test" ──────→  checkout branch         
                                  poke around              
                                  manual test              
                                  "looks good" ─────────→  local checks
                                                           push any fixes
                                                           auto-merge
                                                             → CI (async)
                                                             → merge (async)
                                                             → deploy (async)
```

---

## Phase 1: `/spec-to-pr`

Takes a spec and produces a testable PR. Claude Code is free after push.

### Stage 0: Read and Confirm

1. Read the spec file completely.
2. Summarize: what will change, which files, estimated scope.
3. **Ask the user to confirm.**

```
I'll implement the engine refactor from docs/engine_refactor_instructions.md.

Branch: feature/engine-strip-renderer
Scope: engine.ts, engine.js — strip renderer, promote 6 exports
Tests: existing reducer tests should pass unchanged

Proceed?
```

**HALT if:** Spec not found. User says no.

### Stage 1: Create GitHub Issue

```bash
gh issue create \
  --title "<concise title from spec>" \
  --body "## Summary
<2-3 sentences from spec>

## Acceptance Criteria
- [ ] <criteria from spec>
- [ ] All existing tests pass
- [ ] CI green

## Spec
<path to spec file>

## Pipeline
Phase 1: spec-to-pr | Phase 2: ship-it" \
  --label "spec-to-merge"
```

Capture `ISSUE_NUM`.

**HALT if:** `gh issue create` fails.

### Stage 2: Create Branch

```bash
git checkout main
git pull origin main
BRANCH="feature/issue-${ISSUE_NUM}-<slug>"
git checkout -b "$BRANCH"
```

**HALT if:** Git fails.

### Stage 3: Implement

Follow the spec literally. Don't add scope.

- If ambiguous, **HALT and ask.**
- Commit with meaningful messages:
  ```bash
  git add -A
  git commit -m "feat: <what changed> (#${ISSUE_NUM})"
  ```
- If updating from a changed spec, implement only the delta.

**HALT if:** Contradictions or impossible requirements.

### Stage 4: Push + Create PR

```bash
git push origin "$BRANCH"

gh pr create \
  --title "$(gh issue view $ISSUE_NUM --json title -q '.title')" \
  --body "Closes #${ISSUE_NUM}

## Changes
<bulleted list from commits>

## Status
Ready for manual testing. Run \`/ship-it <PR_NUM>\` when satisfied.

Spec: <path>" \
  --head "$BRANCH" \
  --base main
```

**HALT if:** Push or PR creation fails.

### Done — Notify

```
✓ PR ready for testing.

Issue:   #42 — Engine refactor: strip renderer
Branch:  feature/issue-42-engine-strip-renderer
PR:      #43

To test locally:
  git checkout feature/issue-42-engine-strip-renderer

When ready to ship:
  /ship-it 43
```

Phase 1 is done. Claude Code is free.

---

## Manual Testing (You)

Between phases, you test on the branch however you want:

```bash
git checkout feature/issue-42-engine-strip-renderer

# poke around, run the app, check the UI, whatever
# if you want changes, just tell Claude Code on that branch
```

No time pressure. The PR sits there until you're ready.

---

## Phase 2: `/ship-it <PR_NUM>`

You've tested. Now run checks and merge.

### Stage 0: Validate PR

```bash
# Confirm the PR exists and is open
gh pr view <PR_NUM> --json state,headRefName,title
```

Check out the branch if not already on it:
```bash
git checkout <branch_from_pr>
git pull origin <branch_from_pr>
```

**HALT if:** PR not found, already merged, or closed.

### Stage 1: Local Checks

Run what CI will run:

```bash
bash .claude/skills/spec-to-merge/scripts/local-checks.sh
```

Which runs:
- `ruff check backend/`
- `ruff format --check backend/`
- `bandit -r backend/ -ll`
- `pytest backend/tests/ -v --tb=short`
- `pytest engine/kernel/tests/ -v --tb=short`

### Auto-fix loop (max 3 attempts):
If a check fails, fix and re-run. After 3 failures on the same check, **HALT and report.**

**HALT if:** Any check fails after 3 attempts.

### Stage 2: Push Fixes (if any)

If local checks required code fixes:

```bash
git add -A
git commit -m "fix: address lint/test issues (#${ISSUE_NUM})"
git push origin "$BRANCH"
```

### Stage 3: Enable Auto-Merge

```bash
gh pr merge <PR_NUM> --auto --squash --delete-branch
```

**HALT if:** `--auto` fails. Suggest enabling "Allow auto-merge" in repo settings. If no branch protection exists, merge immediately instead:
```bash
gh pr merge <PR_NUM> --squash --delete-branch
```

### Done

```
✓ Ship-it complete.

PR:     #43 — auto-merge enabled
Local:  all checks passed
Fixes:  1 commit pushed (lint fix)

GitHub will run CI and merge automatically.
If CI fails: gh pr checks 43
```

Claude Code is free.

---

## Re-running on spec updates

When the user says "I updated the spec, run it again":

1. Check for existing open PR:
   ```bash
   gh pr list --state open --label "spec-to-merge" --search "<spec keywords>"
   ```
2. **Open PR exists:** Check out that branch, implement the delta, push. Tell user to re-test and `/ship-it` again.
3. **No open PR:** Full Phase 1 from scratch.

---

## Error recovery

| User says | Action |
|---|---|
| "continue" | Resume Phase 1 from failed stage |
| "CI failed on #43, fix it" | Check out branch, read CI logs via `gh pr checks 43`, fix, push. Auto-merge retries automatically. |
| "abort" | `gh pr close <PR> --delete-branch` |
| "I made changes on the branch, re-run checks" | Jump to Phase 2 Stage 1 |

---

## What happens after `/ship-it` (async)

| CI passes | CI fails |
|---|---|
| GitHub auto-merges | PR stays open, auto-merge paused |
| Branch deleted | Push a fix → auto-merge retries |
| Railway auto-deploys from main | `gh pr checks <PR>` to see what failed |

---

## Prerequisites

- `gh` CLI authenticated
- Repo setting: **Allow auto-merge** enabled (Settings → General → Pull Requests)
- Branch protection with at least one required check
- If no branch protection, `/ship-it` merges immediately (no auto-merge needed)

## Adapting to project structure

On first use, read `.github/workflows/ci.yml` and `CLAUDE.md` to discover what checks CI runs. The local-checks script should mirror CI exactly.
