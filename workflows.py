"""Execute an ordered selection of registered review roles on one evidence snapshot."""
import hashlib

from pydantic import BaseModel, Field, field_validator

from agent import MODEL, OLLAMA_MODEL, Provider, REPO_PATTERN
from report_writer import write_report
from review_flow import REVIEWER_PROMPT, ask_role, collect_evidence, load_skill, parse_model_json, validate_findings


# Every role accepts the same evidence and optional validated output of its predecessor.
AGENTS = {
    "changes": ("Behavior changes", "Identify changed behavior. Prefer concrete observations."),
    "compatibility": ("Compatibility", "Investigate compatibility of public APIs and existing callers."),
    "tests": ("Test coverage", "Inspect changed tests and assertions for coverage of changed behavior."),
}


class WorkflowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    steps: list[str] = Field(min_length=1, max_length=len(AGENTS))
    repo: str = Field(pattern=f"^{REPO_PATTERN.pattern}$", max_length=150)
    number: int = Field(gt=0)
    provider: Provider = "ollama"

    @field_validator("steps")
    @classmethod
    def registered_once(cls, steps):
        if any(step not in AGENTS for step in steps) or len(set(steps)) != len(steps):
            raise ValueError("Choose registered agents at most once each")
        return steps


def execute_workflow(request, on_stage):
    on_stage("evidence")
    evidence = collect_evidence(request.repo, request.number)
    if "error" in evidence:
        return {"error": evidence["error"]}
    skill = load_skill()
    result = {
        "workflow": {"name": request.name, "steps": request.steps},
        "repo": request.repo, "number": request.number, "head_sha": evidence["head_sha"],
        "title": evidence["pr_metadata"]["title"], "coverage": evidence["coverage"],
        "provider": request.provider, "model": OLLAMA_MODEL if request.provider == "ollama" else MODEL,
        "skill": skill, "skill_sha256": hashlib.sha256(skill.encode()).hexdigest(),
        "evidence": evidence, "stages": [], "status": "completed",
        "findings": [], "observations": [], "invalid_stages": [], "rejected_count": 0,
    }
    previous = None
    for step in request.steps:
        on_stage(step)
        instructions = REVIEWER_PROMPT + "\nYour focus: " + AGENTS[step][1]
        payload = {"evidence": evidence, "previous": previous}
        stage = {"agent": step, "instructions": instructions, "previous": previous}
        result["stages"].append(stage)
        try:
            raw = ask_role(request.provider, instructions, skill, payload)
        except Exception:
            stage["error"] = "Agent request failed"
            result["status"] = "incomplete"
            break
        stage["response"] = raw
        parsed = parse_model_json(raw)
        if not parsed["valid"]:
            stage["error"] = "Invalid structured response"
            result["invalid_stages"].append(step)
            result["status"] = "incomplete"
            break
        output = {}
        stage["rejected"] = {}
        for key in ("findings", "observations"):
            accepted, rejected = validate_findings(parsed, evidence, key)
            output[key] = accepted
            stage["rejected"][key] = len(rejected)
            result["rejected_count"] += len(rejected)
            for item in accepted:
                if item not in result[key]:
                    result[key].append(item)
        stage["output"] = output
        previous = {"agent": step, **output}
    on_stage("report_writer")
    result["markdown"] = write_report(result)
    if result["status"] == "incomplete":
        result["markdown"] += f"\n\nIncomplete workflow. Stopped at {step}: {stage['error']}."
    return result
