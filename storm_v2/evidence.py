"""Conservative source normalization; citation presence is not entailment."""

import hashlib
import ipaddress
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .contracts import now


def normalize_url(url):
    if not isinstance(url, str) or len(url) > 4096 or re.search(r"[\x00-\x20\x7f\\]", url):
        raise ValueError("Unsafe source URL")
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme.lower() not in ("http", "https") or not host or parts.username or parts.password:
        raise ValueError("Source URL must be public HTTP(S) without credentials")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")) or "." not in host:
        raise ValueError("Non-public source host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Non-public source address")
    if parts.port not in (None, 80, 443):
        raise ValueError("Nonstandard source port")
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if re.search(r"token|api.?key|password|secret|signature|credential", key, re.I):
            raise ValueError("Source URL contains a sensitive query key")
        if not key.lower().startswith("utm_") and key.lower() not in ("fbclid", "gclid"):
            query.append((key, value))
    netloc = "[" + host + "]" if ":" in host else host
    if parts.port and parts.port != (443 if parts.scheme.lower() == "https" else 80):
        netloc += ":" + str(parts.port)
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", urlencode(query), ""))


class Registry:
    def __init__(self):
        self.sources, self.citations, self.issues, self.tool_calls = {}, [], [], []
        self.observed_at = now()

    def add(self, url, title, state, response_id):
        try:
            canonical = normalize_url(url)
        except (ValueError, TypeError):
            self.issues.append({"code": "unsafe_source_url", "response_id": response_id})
            return None
        source_id = "SRC-" + hashlib.sha256(canonical.encode()).hexdigest()[:16]
        source = self.sources.setdefault(source_id, {
            "id": source_id, "url": canonical, "title": title or canonical,
            "original_urls": [], "access_states": [], "response_ids": [],
            "published_at": None, "retrieved_at": self.observed_at, "excerpts": [],
            "source_type": "unclassified", "human_verified": False,
        })
        if title:
            source["title"] = title
        for key, value in (("original_urls", url), ("access_states", state), ("response_ids", response_id)):
            if value not in source[key]:
                source[key].append(value)
        return source_id

    def ingest(self, response):
        response_id = response["id"]
        self.observed_at = response.get("received_at") or now()
        for item_index, item in enumerate(response.get("output", [])):
            if item.get("type") == "web_search_call":
                action = item.get("action") or {}
                kind = action.get("type", "unknown")
                self.tool_calls.append({"response_id": response_id, "id": item.get("id"),
                                        "type": kind, "status": item.get("status")})
                if item.get("status") != "completed":
                    self.issues.append({"code": "incomplete_search", "response_id": response_id})
                    continue
                for source in action.get("sources", []) or []:
                    if isinstance(source, dict):
                        self.add(source.get("url"), source.get("title"), "search_listed", response_id)
                if kind in ("open_page", "find_in_page") and action.get("url"):
                    self.add(action["url"], None, "provider_opened", response_id)
            if item.get("type") != "message":
                continue
            for part_index, part in enumerate(item.get("content", [])):
                if part.get("type") != "output_text":
                    continue
                content = part.get("text", "")
                for annotation in part.get("annotations", []) or []:
                    if annotation.get("type") != "url_citation":
                        continue
                    citation = annotation.get("url_citation", annotation)
                    source_id = self.add(citation.get("url"), citation.get("title"), "provider_cited", response_id)
                    start, end = citation.get("start_index"), citation.get("end_index")
                    valid = type(start) is int and type(end) is int and 0 <= start <= end <= len(content)
                    if not valid:
                        self.issues.append({"code": "invalid_citation_offsets", "response_id": response_id})
                    if source_id:
                        self.citations.append({"source_id": source_id, "response_id": response_id,
                            "output_item": item_index, "content_part": part_index,
                            "start_index": start, "end_index": end, "offsets_valid": valid})

    def to_dict(self):
        return {"sources": self.sources, "citations": self.citations,
                "issues": self.issues, "tool_calls": self.tool_calls}
