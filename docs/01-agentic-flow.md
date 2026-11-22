# 01 — From tool calling to an Agentic Flow

This repository started with a single Python loop and three read-only GitHub
tools. The user asks for a PR review; the LLM selects a tool and supplies JSON
arguments; **Python**, not the LLM, executes the HTTP request; the result is
passed back as a tool observation. This repeats until an answer is produced.

```text
user -> LLM(tool descriptions) -> tool call -> Python -> GitHub API
         ^                                              |
         +--------------- tool observation --------------+
                             |
                        next decision
```

## What the experiments demonstrated

1. A request to list `appium/appium` PRs triggered `list_pull_requests`.
2. A request to investigate PR #23131 triggered `get_pull_request` and then
   `get_pull_request_diff`, **even without specifying tool order**.
3. Qwen generated a security assessment, but also made confident statements
   such as "schema tests 43/43 pass" and "production-ready".

The first two show that local Ollama tool calling and a multi-step action loop
work. They **do not** establish that the PR review is reliable.

## Lessons

- **Function calling != MCP.** The local agent registers tool JSON schemas
  directly with Ollama/OpenAI. MCP adds interoperable tool discovery and
  execution with a separate client/server protocol.
- **LLM selects; code executes.** The model chooses a tool; the application
  validates arguments and holds execution permissions.
- **Agentic flow != multi-agent.** A single agent can make multiple tool calls.
- **Tool-call success != review correctness.** A plausible summary may confuse
  assertions from a PR description with independently verified evidence.
- **The API may be local.** Ollama receives POST requests at
  `127.0.0.1:11434/api/chat`; model inference occurs on the local Mac. GitHub
  requests still require the network.

Next: [02-evidence-review.md](02-evidence-review.md).
