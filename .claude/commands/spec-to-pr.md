# Spec to PR

Read `.claude/skills/spec-to-merge/SKILL.md` and execute **Phase 1** only.

**Important:** Do NOT implement code locally. Phase 1 only:
1. Reads the spec
2. Summarizes and confirms with user
3. Creates a GitHub issue with the full spec content
4. Adds a comment `@claude implement this spec` to trigger the Claude GitHub Action

The implementation happens asynchronously in GitHub Actions, not in this Claude Code session.

End by telling the user the issue number and how to watch progress.

Spec reference: $ARGUMENTS
