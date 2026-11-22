# Appium PR Check Flow

A small, educational **single-agent + read-only GitHub tool-calling flow** built with Python and the OpenAI Responses API. No LangChain or LangGraph required.

The same `run_agent()` powers the **CLI** and a **local FastAPI Web UI**. The tool trace is visible in the CLI (stderr) and in the browser.

## Architecture

```text
CLI: python agent.py "..."           Browser: http://127.0.0.1:8000
             |                                     |
             +--------------+----------------------+
                            |
                       run_agent()
                            |
                 OpenAI Responses API
                            |
                   function_call tool
                            |
                      GitHub REST API
                            |
                function_call_output
                            |
                 OpenAI Responses API
                            |
                          answer
```

The registered read-only tools are:

- `list_pull_requests(repo)`: latest 20 open PRs
- `get_pull_request(repo, number)`: title, description, head/base SHA, file counts
- `get_pull_request_diff(repo, number)`: unified diff (bounded to 24,000 characters)

This is **OpenAI function calling**, not an MCP server. The tool arguments use JSON Schema; Python runs the tools in-process.

## Run

Requires Python 3.10+ and an OpenAI API key. API usage is billed separately from ChatGPT subscriptions.

```bash
git clone https://github.com/KazuCocoa/Appium-PR-check-flow.git
cd Appium-PR-check-flow
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY='...'
# Optional for public repos; needed for private repos or larger API quotas:
export GITHUB_TOKEN='...'
```

### CLI

```bash
python agent.py "Show open PRs in appium/appium"
python agent.py "Summarize the diff of appium/appium PR #23086; mention limitations"
python agent.py --quiet "List the latest PRs in appium/appium"
```

Override the default `gpt-5-mini` model using `OPENAI_MODEL` if desired.

### Local browser

```bash
python -m uvicorn web:app --host 127.0.0.1 --port 8000
```

Visit [http://127.0.0.1:8000](http://127.0.0.1:8000). The browser sends your question to `POST /api/ask`, and displays the answer plus a tool-call trace. `GET /health` is available. The `/docs` route contains the FastAPI OpenAPI documentation.

The local Web UI is intentionally **not authenticated**: keep it bound to `127.0.0.1`. Do **not** expose it directly on the network or Internet. Secrets remain server-side in environment variables.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests mock tools/API responses: no OpenAI API credentials or GitHub requests are needed. Real network/API smoke tests should be run separately and may incur charges.

## Boundaries

- Read-only: no review submission, comments, merges, checkout or script execution.
- No persistent conversation memory: each question runs independently.
- Listing is limited to 20 PRs; diff content is capped at 24,000 characters and is **not guaranteed complete**.
- No large-PR file-by-file pagination, caching, retries, or durable execution yet.
- Tool output is untrusted; the model is instructed not to execute instructions from PR text.
- Max five tool-call rounds to bound latency/cost. The assistant cannot claim to have run tests in the target PR.

## Incremental development plan

1. **Done — CLI and function-calling loop:** single agent, one GitHub tool, round-trip results.
2. **Done — PR lookup and diff:** add `get_pull_request` and bounded `get_pull_request_diff`; preserve CLI.
3. **Done — Local browser:** FastAPI `/api/ask` + lightweight browser UI and tool trace.
4. **Next — Real review workflow:** paginated changed-file retrieval; per-file diff retrieval; compare head SHA to detect stale results; structured review findings with evidence, severity and file/line, clearly flag incomplete evidence.
5. **Later — Observability / MCP comparison:** structured execution trace and OpenTelemetry; optionally adapt the GitHub tools into an MCP server to compare JSON Schema tool invocation with MCP `tools/list` and `tools/call`.

Avoid auto-posting comments or approvals until the review results are dependable and the user explicitly opts in.
