"""Mechanical gates and clearly provisional semantic assessments. No publisher."""

import re
from .contracts import SECTIONS, digest, now, text


def review_dossier(dossier, sources, risk, audit=None, registry_issues=()):
    errors, warnings, semantic_blockers = [], [], []
    claims = dossier.get("claims", [])
    ids = [claim["id"] for claim in claims]
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r"CLM-[0-9]{3,}", x) for x in ids):
        errors.append("Claim identifiers must be unique CLM-NNN values")
    headings = [section["heading"] for section in dossier.get("sections", [])]
    if headings != list(SECTIONS):
        errors.append("Dossier must preserve all 18 sections in order")
    for claim in claims:
        if not claim["text"].strip():
            errors.append(f"{claim['id']}: empty claim")
        if not claim["source_ids"] or any(s not in sources for s in claim["source_ids"]):
            errors.append(f"{claim['id']}: missing or unknown sources")
        if claim.get("evidence_strength") in ("HIGH", "MODERATE"):
            warnings.append(f"{claim['id']}: model-proposed evidence rating requires human confirmation")
        if any(not sources[s].get("excerpts") for s in claim["source_ids"] if s in sources):
            warnings.append(f"{claim['id']}: underlying source text not held locally; inspect original sources")
    for section in dossier.get("sections", []):
        for paragraph in section["paragraphs"]:
            refs = paragraph["claim_ids"]
            if any(c not in ids for c in refs):
                errors.append(f"{section['heading']}: unknown claim reference")
            if paragraph["kind"] == "factual" and paragraph["text"].strip() and not refs:
                errors.append(f"{section['heading']}: factual paragraph has no claim references")
    checks = [] if audit is None else audit.get("checks", [])
    checked = [check["claim_id"] for check in checks]
    if audit is not None and (set(checked) != set(ids) or len(set(checked)) != len(checked)):
        errors.append("Semantic audit must cover exactly the known claims once")
    for check in checks:
        if check["status"] in ("contradicted", "unsupported"):
            semantic_blockers.append(f"{check['claim_id']}: {check['status']} by provisional model assessment")
    errors.extend("Registry: " + issue["code"] for issue in registry_issues)
    warnings.append("Citation presence and model review are not independent source verification")
    if risk == "high":
        warnings.append("Qualified human review required for high-stakes subject matter")
    return {"mechanical_pass": not errors, "checks_pass": not errors and not semantic_blockers,
            "semantic_blockers": semantic_blockers, "editorial_status": "needs_review",
            "errors": errors, "warnings": warnings, "semantic_checks": checks,
            "semantic_assessor": "model; provisional, not independent verification",
            "required_reviewer": "qualified_specialist" if risk == "high" else "editor",
            "dossier_hash": digest(dossier), "reviewed_at": now()}


def record_human_decision(store, reviewer, notes, approve=False, qualified=False):
    """Local audit record only; never publishes. Invalidated by any dossier edit."""
    text(reviewer, "reviewer", 200)
    text(notes, "notes", 6000)
    report, dossier = store.read("review.json"), store.read("dossier.json")
    if report["dossier_hash"] != digest(dossier["content"]):
        raise ValueError("Dossier changed after checks; rerun review")
    manifest = store.read("manifest.json")
    for name, expected in manifest["files"].items():
        if digest(store.read(name)) != expected:
            raise ValueError("Research artifacts changed after export; rerun review")
    if approve and (not report["checks_pass"] or dossier["synthetic"]):
        raise ValueError("Cannot approve failed checks or synthetic fixture research")
    if approve and report["required_reviewer"] == "qualified_specialist" and qualified is not True:
        raise ValueError("High-stakes approval requires an explicitly identified qualified reviewer")
    store.write("human-review.json", {"reviewer": reviewer, "notes": notes,
                "qualified_attestation": qualified, "dossier_hash": digest(dossier),
                "decision": "approved" if approve else "changes_requested", "at": now(),
                "scope": "editorial decision only; no automatic publication"})
