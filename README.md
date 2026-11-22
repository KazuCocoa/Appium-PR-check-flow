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

Python 3.10+:

```bash
git clone https://github.com/KazuCocoa/Appium-PR-check-flow.git
cd Appium-PR-check-flow
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Option A: Local Ollama (no OpenAI API key)

Install Ollama from [ollama.com](https://ollama.com/download), then in another terminal:

```bash
ollama pull qwen3:4b
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
export OLLAMA_MODEL=qwen3:4b
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

### Local Web UI

```bash
python -m uvicorn web:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Choose **Ollama (local)** or **OpenAI API** from the dropdown, ask a question, and inspect the tool execution trace. The API accepts:

```json
{"question":"List open PRs in appium/appium","provider":"ollama"}
```

Endpoint: `POST /api/ask`. Health: `GET /health`. Docs: `GET /docs`.

Keep the server bound to **127.0.0.1**; it has no user authentication. Never expose it directly to the Internet.

## Tests

```bash
python -m unittest discover -s tests -v
```

Unit tests use mocked model and GitHub responses, so no OpenAI key, running Ollama instance, or GitHub network access is needed. A real Ollama E2E check requires `ollama serve` or the desktop service and the downloaded model.

## Boundaries and planned work

- One-shot questions; no persistent memory or session storage.
- Up to 5 tool-call rounds. Read-only, no GitHub commenting or PR approval.
- Diffs are capped; large PR reviews are **incomplete** without pagination.
- GitHub PR text and diffs are untrusted inputs. The agent is instructed to ignore embedded instructions; this is not a complete prompt-injection defense.
- Next: paginated diff per file, structured findings with line-level evidence, SHA consistency checks, runtime telemetry, then a comparison adapter for MCP `tools/list` and `tools/call`.

## Troubleshooting

- **Connection refused**: make sure Ollama is running on port 11434.
- **Model missing**: run `ollama pull qwen3:4b`.
- **Model does not call tools**: use a model that supports tool calling; inspect CLI stderr or the browser tool trace.
- **GitHub 403**: GitHub rate limits may apply; set a read-only `GITHUB_TOKEN`.
