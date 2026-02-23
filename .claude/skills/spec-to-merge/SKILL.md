---
name: spec-to-merge
description: Two-phase development pipeline with manual testing in between. Phase 1 (/spec-to-pr): reads a spec, creates a GitHub issue, and triggers the Claude GitHub Action to implement it asynchronously. Phase 2 (/ship-it): after you've tested the branch locally, runs lint/test checks and enables auto-merge. Use when the user says "implement this spec", "ship this", "run the pipeline", references a spec doc, says a spec was updated, or says "ship it" / "merge it" for an existing PR.
---

# Spec-to-Merge Pipeline

Two-phase pipeline with a manual testing gap in the middle.

```
PHASE 1: /spec-to-pr       GITHUB ACTION              YOU                    PHASE 2: /ship-it
─────────────────────      ─────────────              ───                    ──────────────────
Read spec
Commit spec to main
Create issue
Trigger @claude ─────────→ checkout repo
                           create branch
                           implement spec
                           push PR
                             "PR ready" ────────────→ checkout branch
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

Creates a GitHub issue and triggers the Claude GitHub Action to implement it. **No local code changes.**

### Stage 0: Read and Confirm

1. Read the spec file completely.
2. Summarize: what will change, which files, estimated scope.
3. **Ask the user to confirm.**

```
I'll create an issue to implement the engine refactor from docs/engine_refactor_instructions.md.

Scope: engine.ts, engine.js — strip renderer, promote 6 exports
Tests: existing reducer tests should pass unchanged

The Claude GitHub Action will implement this on a branch and open a PR.

Proceed?
```

**HALT if:** Spec not found. User says no.

### Stage 0.5: Commit Spec to Main

The GitHub Action needs to read the spec file from the repo. If the spec file is untracked or has uncommitted changes, commit and push it to main first.

```bash
# Check if spec file needs to be committed
git status --porcelain <spec_file>
```

If the file shows as untracked (`??`) or modified (`M`):

```bash
git add <spec_file>
git commit -m "docs: add <spec name> spec

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
git push origin main
```

**HALT if:** Push fails (e.g., branch protection on main).

### Stage 1: Create GitHub Issue

Include the **full spec content** in the issue body so the GitHub Action has everything it needs.

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

## Full Spec Content
<paste entire spec content here>

## Pipeline
Phase 1: spec-to-pr | Phase 2: ship-it" \
  --label "spec-to-merge"
```

Capture `ISSUE_NUM`.

**HALT if:** `gh issue create` fails.

### Stage 2: Trigger Claude GitHub Action

Add a comment to the issue that triggers the Claude workflow:

```bash
gh issue comment $ISSUE_NUM --body "@claude implement this spec"
```

The workflow (`.github/workflows/claude.yml`) will:
- Check out the repo
- Create branch `claude/issue-${ISSUE_NUM}`
- Run Claude Code to implement the spec
- Commit, push, and create a PR

**HALT if:** Comment fails.

### Done — Notify

```
✓ Issue created and Claude Action triggered.

Issue:   #42 — Engine refactor: strip renderer
Action:  GitHub Action is implementing...

Watch progress:
  gh run list --workflow=claude.yml

When the PR is ready, you'll see it at:
  gh pr list --state open --head claude/issue-42

After testing, run:
  /ship-it <PR_NUM>
```

Phase 1 is done. Claude Code is free. Implementation happens asynchronously in GitHub Actions.

---

## Manual Testing (You)

Once the GitHub Action completes and creates a PR, test on the branch:

```bash
git checkout claude/issue-42

# poke around, run the app, check the UI, whatever
# if you want changes, comment @claude on the PR with instructions
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
2. **Open PR exists:** Comment on the PR with `@claude the spec was updated, implement the delta` to trigger the Action again.
3. **No open PR:** Full Phase 1 from scratch.

---

## Error recovery

| User says | Action |
|---|---|
| "continue" | Resume Phase 1 from failed stage (issue creation or triggering action) |
| "CI failed on #43, fix it" | Comment on the PR with `@claude fix the CI failure` to trigger the Action |
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
