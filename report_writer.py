"""Write Markdown exclusively from gated statements and collector metadata."""
import re


def literal(value):
    # Keep each untrusted field inside a single Markdown code span.
    value = " ".join(str(value).splitlines()).strip() or "—"
    width = max((len(run) for run in re.findall(r"`+", value)), default=0) + 1
    fence = "`" * width
    return f"{fence} {value} {fence}"


def write_report(report):
    coverage = report["coverage"]
    lines = [f"# {literal(report['repo'])} · PR #{report['number']}", "",
             f"PR title: {literal(report['title'])}", "",
             f"Head: {literal(report['head_sha'])}"]
    for heading, key, field in [("Findings", "findings", "issue"),
                                ("Observations", "observations", "observation")]:
        lines.extend(["", f"## {heading}", ""])
        for item in report[key]:
            location = literal(f"{item['file']}:{item['line']}")
            severity = f"**{item['severity']}** · " if key == "findings" else ""
            lines.extend([f"- {severity}{location} — {literal(item[field])}",
                          f"  · Evidence: {literal(item['quote'])}"])
        if not report[key]:
            lines.append("No anchored " + heading.lower() + " retained.")
    scope = "Complete" if coverage["complete"] else "Partial"
    lines.extend(["", "## Verification", "",
                  f"- Patch coverage: {scope} · {coverage.get('files_in_context', 'unknown')} "
                  f"of {coverage.get('files_reported', 'unknown')} files in context.",
                  "- CI status: unchecked.", "- Tests: not executed by this review.",
                  "- Statements are model interpretations. Validation checks added lines and quotes.",
                  f"- Rejected candidates: {report['rejected_count']}."])
    for stage in report["invalid_stages"]:
        lines.append(f"- Incomplete analysis: {stage} returned an invalid response.")
    return "\n".join(lines)
