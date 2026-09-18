"""Deterministic transport for offline smoke tests. Not a research model."""

import json
from .contracts import SECTIONS


class FixtureTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, path, payload=None):
        if method != "POST" or path != "responses":
            raise ValueError("Fixture supports completed synchronous responses only")
        stage = payload["metadata"]["stage"]
        self.calls.append(stage)
        data = json.loads(payload["input"][0]["content"])
        annotations, tools = [], []
        if stage == "plan":
            value = {"perspectives": ["Synthetic skeptic lens"], "questions": ["What does this fixture demonstrate?"]}
        elif stage.startswith("research-"):
            value = "This is synthetic fixture material, not research evidence. [1]"
            annotations = [{"type": "url_citation", "url": "https://example.com/kaizen-fixture",
                            "title": "Synthetic fixture only", "start_index": len(value)-3, "end_index": len(value)}]
            tools = [{"type": "web_search_call", "id": "ws_fixture", "status": "completed", "action": {
                "type": "search", "sources": [{"url": "https://example.com/kaizen-fixture"}]}}]
        elif stage.startswith("coverage-"):
            value = {"coverage": [{"question": q, "status": "addressed", "reason": "Synthetic fixture only"}
                                   for q in data["plan"]["questions"]], "followups": []}
        elif stage == "synthesis":
            sid = next(iter(data["source_registry"]["sources"]))
            value = {"title": "Synthetic Kaizen dossier demonstration",
                "claims": [{"id": "CLM-001", "text": "This fixture demonstrates artifact generation.",
                            "source_ids": [sid], "evidence_strength": "UNKNOWN", "qualification": "Synthetic only"}],
                "sections": [{"heading": heading, "paragraphs": [{
                    "text": "Synthetic fixture; no real-world research conclusion is asserted.",
                    "claim_ids": ["CLM-001"] if heading == "Bottom Line" else [],
                    "kind": "factual" if heading == "Bottom Line" else "not_applicable"}]} for heading in SECTIONS]}
        elif stage == "audit":
            value = {"checks": [{"claim_id": "CLM-001", "status": "needs_source_inspection", "explanation": "Synthetic fixture only"}]}
        else:
            raise ValueError("Unknown fixture stage")
        return {"id": "resp_fixture_" + stage, "status": "completed", "model": "offline-fixture",
                "output": [{"type": "reasoning", "summary": ["DO NOT SAVE"]}] + tools + [{"type": "message", "content": [
                    {"type": "output_text", "text": value if isinstance(value, str) else json.dumps(value), "annotations": annotations}]}],
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}
