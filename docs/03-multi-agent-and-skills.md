# 03 — Multi-agent roles and reusable Skills

## Roles

The optional staged review is three independent calls to the selected model,
with separate role-specific instructions and explicit intermediate artifacts:

```text
GitHub evidence snapshot
       |
       v
Scout: identify risk areas (suggestions, not findings)
       |
       v
Reviewer: propose JSON findings with file/line/quote
       |
       v
Deterministic line/quote validation
       |
       v
Verifier: independently reject unsupported candidates
       |
       v
Deterministic validation again + subset of original candidates
       |
       v
Findings, coverage, head SHA, and limitations
```

This is a **sequential, role-separated multi-agent pattern**, not three
processes or three different models. Separate roles and prompts do not confer
independence in a statistical sense when all stages use the same model.
Agent roles themselves do not run tests or access tools directly. The Python
orchestrator collects GitHub evidence once, then passes the bounded snapshot
to each role. This is a deliberate comparison with the original agentic loop,
which dynamically selects and invokes tools.

Use `python agent.py --provider ollama --review appium/appium#23131`.
The original `python agent.py --provider ollama "question"` remains available.

## Skill sharing

The canonical Skill is at:

```text
.agents/skills/appium-pr-review/
    SKILL.md
    references/review-criteria.md
```

Codex.app can discover this repository-scoped Skill (when the repository is
opened as a workspace). The custom Python staged review loads **the same
SKILL.md** and supplies its content to each role. This demonstrates portable
review instructions, not identical capabilities or identical LLM results.

The YAML frontmatter contains `name` and `description`. Workflow guidance
avoids hardcoding Ollama, Python function names, or MCP endpoints. Codex can
use its own tools; this app uses GitHub REST.

The custom loader currently explicitly selects `appium-pr-review`; it
is **not** automatic skill discovery, semantic routing, or an Agent Skills
runtime supporting all optional metadata and resource types. The reference
file is available for Codex but is not auto-loaded by the custom agent.

## Remaining improvements

- Paginated per-file review without dropping context or cross-file interactions.
- Verify the PR head SHA again at the end; identify changed revisions.
- Read CI check results and distinguish assertion, CI pass and execution.
- Structured JSON schema enforcement with retry/recovery for malformed local
  model responses; stronger semantic verifier.
- Metrics: model latency, tool calls, context size, token estimates and
  evaluation against known seeded defects.
- Experiment with an MCP adapter without changing the Skill content.
