"""Draft-only Markdown and versioned JSON; preserve stable provenance IDs."""

import html
import re
from .contracts import VERSION, SECTIONS, digest, now


def escape_text(value):
    return re.sub(r"([\\`*_{}\[\]()#!|])", r"\\\1", html.escape(str(value), quote=False))


def source_link(source):
    url = source["url"].replace("<", "%3C").replace(">", "%3E")
    return f"[{source['id']}](<{url}>)"


def export_package(store, brief, config, content, registry, review):
    synthetic = store.read("run.json")["synthetic"]
    dossier = {
        "schema_version": "kaizen-dossier/1", "engine_version": VERSION,
        "research_id": brief.research_id, "business_id": brief.business_id,
        "domain": brief.domain, "audience": brief.audience, "source_cutoff": brief.source_cutoff,
        "model_requested": config.model, "reasoning_effort": config.reasoning_effort,
        "editorial_status": "needs_review", "evidence_strength": "UNKNOWN",
        "effective_risk": brief.effective_risk, "synthetic": synthetic,
        "created_at": now(), "content": content,
    }
    store.write("dossier.json", dossier)
    store.write("claims.json", {"assessment": "model_provisional", "claims": content["claims"]})
    store.write("review.json", review)
    claims = {c["id"]: c for c in content["claims"]}
    lines = ["# " + escape_text(content["title"]), "",
             "> DRAFT — human editorial review required. Not approved for publication.", ""]
    if synthetic:
        lines += ["> SYNTHETIC OFFLINE FIXTURE — NOT RESEARCH EVIDENCE.", ""]
    lines += [f"Research ID: {brief.research_id}", f"Source cutoff: {brief.source_cutoff}",
              f"Risk: {brief.effective_risk}. Evidence: UNKNOWN pending human review.", ""]
    for section in content["sections"]:
        lines += ["## " + section["heading"], ""]
        for paragraph in section["paragraphs"]:
            refs = []
            for cid in paragraph["claim_ids"]:
                for sid in claims.get(cid, {}).get("source_ids", []):
                    if sid in registry.sources and sid not in refs:
                        refs.append(sid)
            links = " ".join(source_link(registry.sources[s]) for s in refs)
            lines += [(escape_text(paragraph["text"]) + " " + links).strip(), ""]
        if section["heading"] == "Sources":
            for source in registry.sources.values():
                states = ", ".join(source["access_states"])
                lines += [f"- {source_link(source)} — {escape_text(source['title'])}. "
                          f"Access: {states}; full-text verification not established."]
            lines.append("")
    lines += ["## Review requirements", ""]
    for issue in review["errors"] + review["semantic_blockers"] + review["warnings"]:
        lines.append("- " + escape_text(issue))
    store.write_text("dossier.md", "\n".join(lines) + "\n")
    journal = store.read("requests.json")
    usage = {"request_count": len(journal), "reserved_estimate_usd": sum(
        e["reserved_estimate_usd"] for e in journal.values()), "actual_cost_usd": None,
        "cost_note": "Reservation is an operator estimate, not a billing cap; obtain actual cost from provider.",
        "web_tool_calls_observed": len(registry.tool_calls), "provider_usage": {}}
    for stage, entry in journal.items():
        usage["provider_usage"][stage] = {"response_id": entry.get("response_id"),
            "model": entry.get("response", {}).get("model"),
            "usage": entry.get("response", {}).get("usage")}
    store.write("usage.json", usage)
    manifest = {"schema_version": "kaizen-dossier/1", "synthetic": synthetic,
                "editorial_status": "needs_review", "files": {}}
    for name in ("brief.json", "plan.json", "sources.json", "claims.json", "dossier.json", "review.json", "coverage.json", "usage.json"):
        manifest["files"][name] = digest(store.read(name))
    store.write("manifest.json", manifest)
