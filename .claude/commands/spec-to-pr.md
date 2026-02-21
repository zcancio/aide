# Spec to PR

Read `.claude/skills/spec-to-merge/SKILL.md` and execute **Phase 1** only.

Takes a spec, creates a GitHub issue, implements it on a branch, pushes a PR, and tells the user it's ready to test. Do NOT run local checks or merge — that's Phase 2.

End by telling the user the branch name and PR number, and that they can run `/ship-it <PR_NUM>` when they've tested.

Spec reference: $ARGUMENTS
