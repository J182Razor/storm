"""Validated, dependency-free contracts for public-source research runs."""

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone

SECTIONS = (
    "Research Question", "Bottom Line", "Who This Is For", "Why This Matters",
    "What We Examined", "Evidence Quality", "What the Evidence Says",
    "Where Sources Disagree", "Practical Methods", "How to Apply It",
    "Cost / Difficulty / Time", "Risks / Failure Modes", "Kaizen Test",
    "Tools / Resources", "Sources", "Related Research", "Free Tool / Diagnostic",
    "Optional Paid Implementation",
)
EVIDENCE = ("HIGH", "MODERATE", "LOW", "ANECDOTAL", "UNKNOWN")
VERSION = "2.0.0a1"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", value):
        raise ValueError("Unsafe or empty identifier")
    return value


def text(value, name, maximum=6000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be nonempty text of at most {maximum} characters")
    return value


def positive(value, name, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive number")
    if not math.isfinite(value) or value <= 0 or (integer and not isinstance(value, int)):
        raise ValueError(f"{name} must be a positive {'integer' if integer else 'number'}")


@dataclass(frozen=True)
class Brief:
    research_id: str
    question: str
    domain: str
    audience: str
    business_id: str = "KAIZEN-RESEARCH"
    language: str = "English"
    geography: str = "Not specified; report jurisdiction limits"
    source_cutoff: str = field(default_factory=lambda: date.today().isoformat())
    exclusions: tuple = ()
    perspectives: tuple = ()
    risk_tier: str = "general"

    def __post_init__(self):
        identifier(self.research_id)
        if not re.fullmatch(r"KR-[A-Z0-9]+-RES-[0-9]{3,}", self.research_id):
            raise ValueError("research_id must be KR-<DOMAIN>-RES-<NNN>")
        if self.business_id != "KAIZEN-RESEARCH":
            raise ValueError("This runner is scoped to KAIZEN-RESEARCH")
        for name in ("question", "domain", "audience", "language", "geography"):
            text(getattr(self, name), name)
        date.fromisoformat(self.source_cutoff)
        if self.risk_tier not in ("general", "high"):
            raise ValueError("risk_tier must be general or high")
        for name in ("exclusions", "perspectives"):
            values = getattr(self, name)
            if not isinstance(values, (list, tuple)) or len(values) > 12:
                raise ValueError(f"{name} must contain at most 12 strings")
            for value in values:
                text(value, name, 1000)
            object.__setattr__(self, name, tuple(values))

    @property
    def effective_risk(self):
        domain = self.domain.lower()
        high = ("health", "medical", "clinical", "nutrition", "fitness", "legal",
                "finance", "housing", "living", "resilience", "prepping", "survival",
                "homestead", "water", "food", "electric", "structural", "safety")
        return "high" if self.risk_tier == "high" or any(x in domain for x in high) else "general"


@dataclass(frozen=True)
class Limits:
    max_requests: int = 10
    max_tool_calls: int = 8
    max_output_tokens: int = 12000
    max_input_chars: int = 180000
    max_response_bytes: int = 8_000_000
    max_polls: int = 180
    request_timeout_seconds: float = 120
    poll_interval_seconds: float = 5
    max_questions: int = 4
    max_followups: int = 1
    max_estimated_cost_usd: float = 0
    estimated_cost_per_request_usd: float = 0

    def __post_init__(self):
        for name in ("max_requests", "max_tool_calls", "max_output_tokens", "max_input_chars",
                     "max_response_bytes", "max_polls", "max_questions"):
            positive(getattr(self, name), name, integer=True)
        for name in ("request_timeout_seconds", "poll_interval_seconds"):
            positive(getattr(self, name), name)
        if type(self.max_followups) is not int or not 0 <= self.max_followups <= 5:
            raise ValueError("max_followups must be between 0 and 5")
        for name in ("max_estimated_cost_usd", "estimated_cost_per_request_usd"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.max_output_tokens > 128000 or self.max_questions > 12:
            raise ValueError("Output or question limit exceeds this adapter's supported envelope")


@dataclass(frozen=True)
class Config:
    model: str = "gpt-6-astra"
    reasoning_effort: str = "xhigh"
    background: bool = True
    store: bool = True
    limits: Limits = field(default_factory=Limits)
    allowed_domains: tuple = ()

    def __post_init__(self):
        if not re.fullmatch(r"gpt-6-astra(?:-[0-9-]+)?", self.model):
            raise ValueError("Use gpt-6-astra or an explicitly verified dated snapshot; no fallback")
        if self.reasoning_effort not in ("low", "medium", "high", "xhigh", "max"):
            raise ValueError("Unsupported reasoning effort")
        if type(self.background) is not bool or type(self.store) is not bool:
            raise ValueError("background and store must be booleans")
        if self.background and not self.store:
            raise ValueError("Resumable background mode in this runner requires explicit store=True")
        if not isinstance(self.limits, Limits):
            raise ValueError("limits must be Limits")
        if not isinstance(self.allowed_domains, (list, tuple)) or len(self.allowed_domains) > 100:
            raise ValueError("allowed_domains must contain at most 100 hostnames")
        for domain in self.allowed_domains:
            if not isinstance(domain, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,}", domain):
                raise ValueError("Domain filters must be bare hostnames")
        object.__setattr__(self, "allowed_domains", tuple(self.allowed_domains))

    def require_paid_permission(self, approved):
        if approved is not True:
            raise ValueError("Live requests require explicit paid API authorization")
        positive(self.limits.max_estimated_cost_usd, "max_estimated_cost_usd")
        positive(self.limits.estimated_cost_per_request_usd, "estimated_cost_per_request_usd")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        data["limits"] = Limits(**data.get("limits", {}))
        return cls(**data)
