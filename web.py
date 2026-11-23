"""Local-only FastAPI browser interface for the same CLI agent."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Literal

from agent import run_agent
from review_flow import review_pr

app = FastAPI(title="Appium PR Check Flow", docs_url="/docs")
INDEX = Path(__file__).parent / "static" / "index.html"


class AgentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    provider: Literal['openai', 'ollama'] = 'openai'


class AgentResponse(BaseModel):
    answer: str
    tools: list[dict]


@app.get("/")
def index():
    return FileResponse(INDEX)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/ask", response_model=AgentResponse)
def ask(request: AgentRequest):
    events = []

    def on_tool(name, arguments, result):
        events.append({
            "tool": name,
            "arguments": arguments,
            "error": result.get("error") if isinstance(result, dict) else None,
        })

    try:
        answer = run_agent(request.question, on_tool=on_tool, provider=request.provider)
    except Exception as exc:
        # Do not leak tokens, request headers, or upstream error bodies to web clients.
        raise HTTPException(status_code=502, detail="Agent execution failed; check server logs") from None
    return AgentResponse(answer=answer, tools=events)


class ReviewRequest(BaseModel):
    repo: str = Field(min_length=3, max_length=150)
    number: int = Field(gt=0)
    provider: Literal["ollama", "openai"] = "ollama"


@app.post("/api/review")
def staged_review(request: ReviewRequest):
    """Bounded read-only review; returns coverage and evidence metadata."""
    try:
        return review_pr(request.repo, request.number, provider=request.provider)
    except Exception:
        raise HTTPException(status_code=502, detail="Review execution failed; check server logs") from None
