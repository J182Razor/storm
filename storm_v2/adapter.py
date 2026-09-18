"""Explicit bridges to existing STORM outputs, without eager legacy imports."""

from .contracts import text


def perspectives_from_storm(value):
    """Accept an already computed generate_persona list or a prediction.personas."""
    result = value if isinstance(value, (list, tuple)) else getattr(value, "personas", None)
    if not isinstance(result, (list, tuple)) or not 1 <= len(result) <= 12:
        raise ValueError("Supply 1–12 existing STORM perspective strings")
    return [text(item, "perspective", 1000) for item in result]


def information_records(sources):
    """Information.from_dict compatible; never substitute a model report for snippets."""
    return [{"url": s["url"], "title": s["title"], "description": "Kaizen source; see provenance metadata",
             "snippets": [e["text"] for e in s.get("excerpts", []) if e.get("text")],
             "citation_uuid": -1, "meta": {"kaizen_source_id": s["id"], "access_states": s["access_states"],
                        "requires_source_inspection": True}} for s in sources.values()]


def to_storm_information(sources, information_factory=None):
    """Import legacy dependencies only when the caller explicitly requests objects."""
    if information_factory is None:
        from knowledge_storm.interface import Information
        information_factory = Information
    return [information_factory.from_dict(record) for record in information_records(sources)]
