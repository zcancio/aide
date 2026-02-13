# Claude Code Setup for AIde

## How this works

Claude Code reads `CLAUDE.md` in your project root on every session. It contains the project architecture, hard rules, and conventions that Claude Code must follow.

Custom slash commands live in `.claude/commands/`. They're available as `/project:command-name` in Claude Code.

Architecture docs live in `docs/`. Claude Code references them when implementing features.

## Available commands

| Command | What it does |
|---------|-------------|
| `/project:security-review` | Audit codebase against docs/aide_security_checklist.md |
| `/project:new-endpoint` | Implement a new API endpoint following data access patterns |
| `/project:new-table` | Add a database table with RLS, migration, repo, models, and tests |
| `/project:implement-phase` | Implement the next launch plan phase from docs/aide_launch_plan.md |
| `/project:pre-commit` | Run quality and security checks before committing |
| `/project:audit-architecture` | Audit codebase structure against architecture docs |

## Setup

1. Copy `CLAUDE.md` to your project root
2. Copy `.claude/` directory to your project root
3. Copy all `aide_*.md` files to `docs/` in your project
4. Start Claude Code in your project directory

Claude Code will automatically pick up the instructions and commands.

## Updating docs

When decisions change in Claude.ai conversations, download updated docs and replace the files in `docs/`. Claude Code will use the latest version on its next session.

The workflow:
```
Claude.ai (decisions, planning, docs)
    ↓ download updated .md files
docs/ in your repo (committed to git)
    ↓ read by Claude Code on every session
Claude Code (implementation, following the docs)
```
