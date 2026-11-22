# Appium PR Check Flow

A minimal, educational **single-agent + GitHub tool-calling** loop implemented in Python with OpenAI's Responses API. The LLM chooses when to invoke a read-only GitHub API tool; Python executes it and returns its result to the model. No agent framework required.

## Setup

Requires Python 3.10+ and an OpenAI API key.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY='...'
# Optional: higher GitHub API rate limits; required for private repos
export GITHUB_TOKEN='...'
python agent.py 'appium/appium のOpen PRを一覧にして'
```

The default model is `gpt-5-mini`. You may select another Responses API function-calling model via `OPENAI_MODEL`.

## Agent flow

1. A user asks about a GitHub repository.
2. The model either answers or requests `list_pull_requests`.
3. The Python tool validates `owner/repo` and reads open PR metadata from the GitHub REST API.
4. Tool results are sent back to the model via `function_call_output`.
5. The loop continues up to five tool-call rounds, then returns an answer.

## Limitations

- Read-only; it does not inspect PR diffs, post comments, or create reviews.
- At most 20 open PRs, sorted by last update; not an exhaustive listing.
- Treat PR titles and other tool data as untrusted content.
- OpenAI API charges are separate from ChatGPT subscriptions.
- CLI only in this first stage; FastAPI/Web UI can be added later.

## Tests

```bash
python -m unittest discover -s tests -v
```
