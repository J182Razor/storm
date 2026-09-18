"""Small strict schemas used both in Responses requests and offline validation."""

import json
from .contracts import EVIDENCE, SECTIONS


def string(enum=None):
    result = {"type": "string"}
    if enum is not None:
        result["enum"] = list(enum)
    return result


def array(items):
    return {"type": "array", "items": items}


def obj(**properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


PLAN = obj(perspectives=array(string()), questions=array(string()))
GAPS = obj(coverage=array(obj(question=string(), status=string(("addressed", "partial", "unresolved")),
                              reason=string())), followups=array(string()))
AUDIT = obj(checks=array(obj(claim_id=string(), status=string(("supported_by_available_material",
                "needs_source_inspection", "contradicted", "unsupported")), explanation=string())))


def synthesis_schema(source_ids):
    return obj(
        title=string(),
        claims=array(obj(id=string(), text=string(), source_ids=array(string(source_ids)),
                         evidence_strength=string(EVIDENCE), qualification=string())),
        sections=array(obj(heading=string(SECTIONS), paragraphs=array(obj(
            text=string(), claim_ids=array(string()),
            kind=string(("factual", "practice", "limitation", "not_applicable")))))),
    )


def validate(value, schema, path="$"):
    kind = schema["type"]
    expected = {"object": dict, "array": list, "string": str}[kind]
    if not isinstance(value, expected):
        raise ValueError(f"{path}: expected {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: value outside allowed enum")
    if kind == "object":
        keys = set(value)
        if not set(schema["required"]) <= keys or keys - set(schema["properties"]):
            raise ValueError(f"{path}: missing or unexpected fields")
        for key, child in schema["properties"].items():
            validate(value[key], child, path + "." + key)
    if kind == "array":
        if len(value) > 500:
            raise ValueError(f"{path}: oversized array")
        for index, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{index}]")
    if kind == "string" and len(value) > 60000:
        raise ValueError(f"{path}: oversized string")


def decode(text, schema):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    result = json.loads(text, object_pairs_hook=unique_keys)
    validate(result, schema)
    return result
