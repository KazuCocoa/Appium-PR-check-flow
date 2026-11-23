# Appium PR Check Flow

A minimal, read-only **AI Agentic Flow** for investigating GitHub pull requests. Supports **Ollama (local, no OpenAI API key)** and **OpenAI Responses API**, with shared tool execution, a CLI, and a local FastAPI browser UI.

## Architecture

```text
      CLI (agent.py)                  Browser UI (FastAPI)
             |                               |
             +---------- run_agent() --------+
                            |
                Choose LLM provider
                     /           \\
           Ollama /api/chat      OpenAI Responses API
                     \\           /
                   JSON tool calls
                           |
                 Common tool registry
                           |
                      GitHub REST
                           |
                Tool result -> LLM -> answer
```

Ollama uses its **native /api/chat tool-calling API**. OpenAI uses Responses API function calling. This is not MCP: both formats are adapted to a common Python tool registry.

### Tools

- `list_pull_requests(repo)`: latest 20 open PRs
- `get_pull_request(repo, number)`: description, head/base SHA and metadata
- `get_pull_request_diff(repo, number)`: bounded unified diff (up to 24,000 characters)

All GitHub actions are **read-only**.

## Setup

Use Python 3.15 for new environments. The minimum supported version is Python 3.10.

```bash
git clone https://github.com/KazuCocoa/Appium-PR-check-flow.git
cd Appium-PR-check-flow
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Option A: Local Ollama (no OpenAI API key)

Install Ollama from [ollama.com](https://ollama.com/download), then pull the default 9B model (recommended for a 24GB Apple Silicon Mac):

```bash
ollama pull qwen3.5:9b
ollama serve
```

If the Ollama desktop app already runs the server, do not start another `ollama serve` instance. The endpoint is fixed to **http://127.0.0.1:11434/api/chat** (loopback only).

CLI:

```bash
python agent.py --provider ollama "List open PRs in appium/appium"
python agent.py --provider ollama "Summarize the diff of appium/appium PR #23086"
```

Model selection:

```bash
export OLLAMA_MODEL=qwen3.5:9b
export LLM_PROVIDER=ollama
python agent.py "Show open PRs in appium/appium"
```

Use a model with **tool-calling support**. Smaller local models may hallucinate tool names, fail to invoke tools, or produce weaker code reviews. Model downloads and inference happen locally, but the GitHub tool still makes network requests to GitHub. Local does **not** mean completely offline execution.

### Option B: OpenAI API

```bash
export OPENAI_API_KEY='...'
python agent.py --provider openai "List open PRs in appium/appium"
```

Default provider is `openai` unless `LLM_PROVIDER` is set. The OpenAI model defaults to `gpt-5-mini`; override it with `OPENAI_MODEL`. OpenAI API usage is billed separately from ChatGPT subscriptions.

For private GitHub repositories or higher GitHub rate limits, optionally set `GITHUB_TOKEN`. A token is not required for public repositories under typical API rate limits.

### Evidence-based staged review (experimental)

Run the new Scout → Reviewer → Verifier workflow on a particular pull request:

```bash
python agent.py --provider ollama --review appium/appium#23131
# Or with OpenAI (requires separate API billing)
python agent.py --provider openai --review appium/appium#23131
```

This produces a structured JSON report with the exact PR head SHA, coverage,
model-generated candidate findings, and explicit `ci_checked: false` /
`tests_executed: false` flags. A deterministic evidence gate checks each
finding against an added line and an exact quoted substring in the available
patch. That validates **where a candidate points**, not whether the proposed
defect is actually real.

The Scout, Reviewer, and Verifier are distinct **role-separated model calls**
with a shared bounded evidence snapshot, not independent subprocesses or
different model weights. The original interactive CLI Agent remains unchanged.

The shared Skill is in
[`.agents/skills/appium-pr-review/SKILL.md`](.agents/skills/appium-pr-review/SKILL.md).
Both this project's staged review (via a local loader) and Codex.app (when
this repository is opened as a workspace) can use that same skill definition.
The generic natural-language CLI flow does **not** yet auto-discover skills.

**Known limitations:** the review considers at most 30 files and bounded
patch excerpts (up to 5,500 characters per file and 42,000 total). It does not
read CI status, execute tests, guarantee semantic correctness, or recommend a
merge. A truncated or missing patch is reported as incomplete. It does not
recheck the head SHA after reviewing.

### Local Web UI

```bash
python -m uvicorn web:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Choose **Ollama (local)** or **OpenAI API** and a workflow. **Single agent** accepts a question and shows the tool calls. **Staged multi-agent review** accepts a repository and PR number, then shows the rendered report, patch coverage, CI/test status, and execution trace. Expand **Structured JSON** to inspect the source result. The API accepts:

```json
{"question":"List open PRs in appium/appium","provider":"ollama"}
```

The browser also exposes the **staged review** form using `POST /api/review`:

```json
{"repo":"appium/appium","number":23131,"provider":"ollama"}
```

Endpoint: `POST /api/ask`. Health: `GET /health`. Docs: `GET /docs`.

Keep the server bound to **127.0.0.1**; it has no user authentication. Never expose it directly to the Internet.

## Tests

```bash
python -m unittest discover -s tests -v
```

Unit tests use mocked model and GitHub responses, so no OpenAI key, running Ollama instance, or GitHub network access is needed. A real Ollama E2E check requires `ollama serve` or the desktop service and the downloaded model.

## Architecture and learning notes

The staged explanations are intentionally maintained in `docs/`:

1. [01 — Agentic Flow vs tool calling and MCP](docs/01-agentic-flow.md)
2. [02 — Evidence-based review and provenance](docs/02-evidence-review.md)
3. [03 — Role-separated multi-agent flow and sharing Skills](docs/03-multi-agent-and-skills.md)

## Boundaries and planned work

- One-shot questions; no persistent memory or session storage.
- Up to 5 tool-call rounds. Read-only, no GitHub commenting or PR approval.
- Diffs are capped; large PR reviews are **incomplete** without pagination.
- GitHub PR text and diffs are untrusted inputs. The agent is instructed to ignore embedded instructions; this is not a complete prompt-injection defense.
- Next: stronger semantic verification, recheck head SHA, real CI evidence, broader multi-file analysis, runtime telemetry and an optional MCP adapter.

## Troubleshooting

- **Connection refused**: make sure Ollama is running on port 11434.
- **Model missing**: run `ollama pull qwen3.5:9b`.
- **Model does not call tools**: use a model that supports tool calling; inspect CLI stderr or the browser tool trace.
- **GitHub 403**: GitHub rate limits may apply; set a read-only `GITHUB_TOKEN`.

### Review report formats

The staged CLI defaults to JSON for compatibility. Use `--format markdown`
with `--review` to print the same Markdown returned by the review API.
After the Verifier, a deterministic Report Writer formats only retained,
line-anchored findings and observations, PR metadata, and review status.
It makes no further provider call. The JSON includes the execution order in
`trace` and flags malformed specialist responses in `invalid_stages`.
The legacy JSON `summary` contains model commentary and is excluded from Markdown.

### Follow a staged review in detail

Set `REVIEW_DEBUG=1` for a CLI review or for the process serving the Web UI.
Both emit one JSON event per line to standard error. The CLI's `--quiet`
suppresses its ordinary stage messages, keeping the diagnostic file machine-readable.

```bash
REVIEW_DEBUG=1 python agent.py --quiet --provider ollama --review 'appium/appium#23131' > report.json 2> review.jsonl
REVIEW_DEBUG=1 python -m uvicorn web:app --host 127.0.0.1 --port 8000
```

Follow one `run_id` across evidence collection, the three role calls, JSON parsing,
anchor validation, the Verifier's exact-match filter, and report completion.
Each request lists the input field names. Responses record character count and
duration. A malformed JSON result appears as `json.parsed` with `valid: false`.
With `REVIEW_DEBUG=1`, the trace omits prompt text, diffs and raw responses.
Set `REVIEW_DEBUG=full` to include the role instructions and shared Skill
(`instructions`), the serialized user payload (`input`), and the returned text
before parsing or truncation (`response`). Pair events by `run_id` and `stage`.
Full logs can contain private PR descriptions, code and model output.
For the Web UI, this setting applies to every staged review in that server process.

To see the same flow offline, run this fixture. Its Verifier deliberately changes
a finding's claim while preserving its quote. Look for `new_or_changed: 1` and
`retained: 0` in the findings event.

```bash
PYTHONPATH=tests REVIEW_DEBUG=1 python -m unittest test_report.ReportTests.test_only_retained_statements_reach_markdown
```
