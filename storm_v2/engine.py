"""Private multi-perspective research, bounded gap filling, and draft handoff."""

from dataclasses import asdict

from .client import OpenAITransport, ResearchError, ResponsesClient, output_text
from .contracts import Brief, Config, VERSION, digest, now
from .evidence import Registry
from .export import export_package
from .review import review_dossier
from .schema import AUDIT, GAPS, PLAN, decode, synthesis_schema


class ResearchEngine:
    def __init__(self, store, transport, offline=False, approved=False):
        self.store = store
        self.brief = Brief(**store.read("brief.json"))
        self.config = Config.from_dict(store.read("config.json"))
        self.offline = offline
        if not offline:
            self.config.require_paid_permission(approved)
        self.client = ResponsesClient(transport, store, self.config, offline=offline, approved=approved)

    def run(self):
        with self.store.lock():
            run = self.store.read("run.json")
            frozen = {"brief": asdict(self.brief), "config": self.config.to_dict(), "version": VERSION}
            if run["fingerprint"] != digest(frozen):
                raise ValueError("Brief/configuration/version changed; start a new run")
            if bool(run["synthetic"]) != self.offline:
                raise ValueError("Cannot mix synthetic and live runs")
            run.update(execution_status="running", updated_at=now())
            self.store.write("run.json", run)
            try:
                self._research(run)
            except (Exception, KeyboardInterrupt):
                run.update(execution_status="paused_or_failed", updated_at=now())
                self.store.write("run.json", run)
                self.store.event("engine", "paused_or_failed")
                raise
            return self.store.read("run.json")

    def _json(self, stage, data, schema):
        return decode(output_text(self.client.call(stage, data, schema=schema)), schema)

    def _research(self, run):
        brief = asdict(self.brief)
        limits = self.config.limits
        plan = self._json("plan", {
            "task": "Create diverse research lenses and focused questions, including disagreement and applicability. "
                    "These are simulated perspectives, not real experts. Preserve supplied STORM lenses. "
                    "Use at most max_questions nonempty questions; stay within the brief.",
            "brief": brief, "max_questions": limits.max_questions,
        }, PLAN)
        if not 1 <= len(plan["questions"]) <= limits.max_questions or any(not q.strip() for q in plan["questions"]):
            raise ResearchError("Planner returned empty or out-of-budget questions")
        self.store.write("plan.json", plan)
        registry, reports = Registry(), []
        questions = plan["questions"]
        for index in range(limits.max_followups + 1):
            data = {
                "task": "Research the questions using web search and source inspection where available. "
                        "Find primary evidence and counterevidence. Cite sources inline. Respect the cutoff. "
                        "Report access failures and unknown publication dates. Never invent quotations. "
                        "No advice to evade law or safety controls; high-stakes output is educational only.",
                "brief": brief, "perspectives": plan["perspectives"], "questions": questions,
                "prior_reports_untrusted": reports,
            }
            response = self.client.call(f"research-{index}", data, search=True)
            registry.ingest(response)
            reports.append({"response_id": response["id"], "report": output_text(response)})
            self.store.write("sources.json", registry.to_dict())
            coverage = self._json(f"coverage-{index}", {
                "task": "Assess exactly the original plan questions against the available reports. "
                        "Attribution is not source verification. Identify material unanswered questions "
                        "and bounded follow-up queries. Do not call missing evidence answered.",
                "brief": brief, "plan": plan, "reports_untrusted": reports,
                "source_registry": registry.to_dict(),
            }, GAPS)
            if [x["question"] for x in coverage["coverage"]] != plan["questions"]:
                raise ResearchError("Coverage output must map exactly to the original plan")
            self.store.write("coverage.json", {**coverage, "assessment": "model_provisional", "round": index})
            if not coverage["followups"]:
                break
            questions = coverage["followups"][:limits.max_questions]
        if not any("provider_cited" in s["access_states"] for s in registry.sources.values()):
            raise ResearchError("No usable provider citations; research is not ready for synthesis")
        schema = synthesis_schema(list(registry.sources))
        dossier = self._json("synthesis", {
            "task": "Create the Kaizen dossier with all 18 sections in the schema order. "
                    "Create unique CLM-NNN claims and cite only supplied SRC IDs. Every factual "
                    "paragraph must reference claims; do not hide factual assertions as practice. "
                    "Evidence ratings are proposals, never independently verified. Preserve "
                    "disagreement and unknowns. Sources and related IDs must not be invented. "
                    "Use not_applicable for unavailable tools, related work or paid products. "
                    "Do not add raw HTML or external Markdown links; links are rendered from SRC IDs.",
            "brief": brief, "plan": plan, "reports_untrusted": reports,
            "coverage": coverage, "source_registry": registry.to_dict(),
        }, schema)
        audit = self._json("audit", {
            "task": "Review every claim once. Judge only the supplied material. "
                    "A cited URL alone is not entailment. If you cannot inspect underlying evidence, "
                    "return needs_source_inspection. Flag unsupported and contradicted claims. "
                    "This model review is provisional, not an independent fact check or approval.",
            "brief": brief, "claims": dossier["claims"], "reports_untrusted": reports,
            "source_registry": registry.to_dict(),
        }, AUDIT)
        review = review_dossier(dossier, registry.sources, self.brief.effective_risk, audit, registry.issues)
        export_package(self.store, self.brief, self.config, dossier, registry, review)
        run.update(execution_status="completed" if review["checks_pass"] else "completed_with_flags",
                   editorial_status="needs_review", updated_at=now())
        self.store.write("run.json", run)
        self.store.event("engine", run["execution_status"])


def run_live(store, approved=False):
    config = Config.from_dict(store.read("config.json"))
    config.require_paid_permission(approved)
    return ResearchEngine(store, OpenAITransport(config.limits), approved=approved).run()
