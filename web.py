"""Local-only FastAPI browser interface for the same CLI agent."""
import json
from pathlib import Path

import anyio

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from markdown_it import MarkdownIt
from pydantic import BaseModel, Field

from agent import Provider, run_agent
from review_flow import review_pr
from workflows import AGENTS, WorkflowRequest, execute_workflow

app = FastAPI(title="Appium PR Check Flow", docs_url="/docs")
INDEX = Path(__file__).parent / "static" / "index.html"


app.mount("/static", StaticFiles(directory=INDEX.parent), name="static")
# Both model text and repository content are untrusted. Disable raw HTML
# and remote images; markdown-it also rejects unsafe link protocols.
renderer = MarkdownIt("commonmark", {"html": False}).enable("table").disable("image")


class AgentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    provider: Provider = "openai"


class AgentResponse(BaseModel):
    answer: str
    html: str
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
    return AgentResponse(answer=answer, html=renderer.render(answer), tools=events)


class ReviewRequest(BaseModel):
    repo: str = Field(min_length=3, max_length=150)
    number: int = Field(gt=0)
    provider: Provider = "ollama"


def render_report(report):
    if "markdown" in report:
        return {**report, "html": renderer.render(report["markdown"])}
    return report


@app.post("/api/review")
def staged_review(request: ReviewRequest):
    """Bounded read-only review; returns coverage and evidence metadata."""
    try:
        report = review_pr(request.repo, request.number, provider=request.provider)
        return render_report(report)
    except Exception:
        raise HTTPException(status_code=502, detail="Review execution failed; check server logs") from None

@app.post("/api/review/stream")
async def stream_review(request: ReviewRequest):
    """Send newline-delimited stage events and one terminal result per request."""
    return stream_events(lambda notify: review_pr(request.repo, request.number, provider=request.provider,
                                                 on_stage=notify))


@app.get("/api/workflows/agents")
def registered_agents():
    return [{"id": key, "label": label} for key, (label, _) in AGENTS.items()]


@app.post("/api/workflows/run")
def run_workflow(request: WorkflowRequest):
    return stream_events(lambda notify: execute_workflow(request, notify))


def stream_events(execute):
    async def events():
        send, receive = anyio.create_memory_object_stream(1)

        def run():
            def publish(event):
                anyio.from_thread.run(send.send, event)

            try:
                report = execute(lambda stage: publish({"stage": stage}))
                if "error" in report:
                    publish({"error": report["error"]})
                else:
                    publish({"result": render_report(report)})
            except (anyio.BrokenResourceError, anyio.ClosedResourceError):
                return
            except Exception:
                publish({"error": "Review execution failed"})

        async def produce():
            async with send:
                await anyio.to_thread.run_sync(run)

        async with anyio.create_task_group() as group:
            group.start_soon(produce)
            async with receive:
                async for event in receive:
                    yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
