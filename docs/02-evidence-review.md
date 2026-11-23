# 02 — Evidence-based review

Our first PR #23131 experiment produced a useful summary, but the LLM treated
a PR author's statement about `schema.spec.ts (43/43)` as if it independently
verified the test results. Another output used `MERGE` / `production-ready`
despite a bounded and potentially incomplete diff.

The solution is not merely a stronger system prompt. The application needs an
**evidence contract**.

## What the staged workflow records

- PR number and head SHA to bind the analysis to a revision.
- PR description marked explicitly as `description_author_claim`.
- Changed files paginated from GitHub's `pulls/{number}/files` endpoint.
- A bounded patch per file, with explicit `patch_available`,
  `patch_truncated`, and aggregate `coverage.complete`.
- Explicit `ci_checked: false` and `tests_executed: false`.
- Candidate findings with a precise new-side diff line number and an exact
  quote that the code deterministically checks against the patch.

The local implementation rejects findings whose filename, new-side line
number, exact quote or severity are unsupported. This is **syntactic evidence
validation**, not a proof of semantic correctness or exploitability.

## Limitations

There are hard input budgets (30 files, 5,500 characters per patch, 42,000
patch characters total). Those limits prevent enormous local-LLM contexts but
may omit crucial code. A truncated/partial review must not say that the whole
PR was verified. Binary files may have no patch at all.

No CI checks are fetched, no code is executed, and no GitHub review is posted.
If a test result appears only in a PR description, it is an author's claim.

Next: [03-multi-agent-and-skills.md](03-multi-agent-and-skills.md).
