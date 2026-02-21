# Installing the Spec-to-Merge Skill

## File placement

```
your-repo/
├── .claude/
│   ├── commands/
│   │   ├── spec-to-pr.md             ← Phase 1: spec → PR
│   │   └── ship-it.md                ← Phase 2: test → merge
│   └── skills/
│       └── spec-to-merge/
│           ├── SKILL.md              ← full pipeline docs
│           └── scripts/
│               └── local-checks.sh   ← mirrors CI locally
```

## One-time setup

```bash
# 1. Create the label
gh label create "spec-to-merge" --color "0E8A16" --description "Automated spec-to-merge pipeline"

# 2. Enable auto-merge
#    Settings → General → Pull Requests → ✓ Allow auto-merge

# 3. Branch protection needs at least one required check
#    Settings → Branches → main → Require status checks
```

## Usage

```bash
# Phase 1: implement a spec, push PR
/spec-to-pr docs/engine_refactor_instructions.md

# ... test the branch yourself ...
git checkout feature/issue-42-engine-strip-renderer

# Phase 2: checks pass → auto-merge
/ship-it 43
```

## Flow

```
/spec-to-pr          →  you test  →  /ship-it 43
(spec→issue→code→PR)    (branch)     (checks→auto-merge)
```
