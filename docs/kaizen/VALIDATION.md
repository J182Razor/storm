# Validation and limitations

This branch implements the approved additive research-engine design. The name
STORM v2 refers to this fork's opt-in engine, not an upstream STORM release.

## Offline test scope

Run `python -m unittest discover -s tests/storm_v2 -v` from the repository root.
Tests use deterministic/injected transports. They cover input limits, retained
Astra parameters, citation mappings/access states, three terminal failures,
refusal/empty output, ambiguous submission, bounded polling/research, resume,
cancellation, schema failures, business-scoped paths, file permissions, locks,
export and review gates. A fixture proves serialization/control flow, not research
quality, model access, semantic accuracy or a measurable business benefit.

The local build environment could not resolve github.com for a shell clone and
had no DSPy/OpenAI SDK installed. It tested the dependency-free v2 package on
Python 3.13.5, not the complete legacy application. Repository originals were
inspected through the GitHub connector and are preserved in the remote base tree.
An offline Actions matrix covers Python 3.10–3.13 when GitHub runs it. Do not call
remote CI passed until its actual job results are available.

## Remaining live checks

- Confirm API model entitlement, actual request acceptance, latency and limits.
- Run a public-only, explicitly funded brief and reconcile provider billing.
- Verify background retrieval/expiry under the account's retention policy.
- Inspect original sources and citation entailment; model audit is provisional.
- Check the full legacy environment and optional Information-object bridge.
- Compare `kaizen-dossier/1` with the actual site's importer before importing.
- Obtain named qualified review for health and other high-risk dossiers.

## Bounded benchmark (not executed)

Compare old STORM and v2 with matched public questions, equivalent scope, and
predeclared cost/time limits. Candidate cases: AI workflow applicability, learning
methods, conflicting evidence, and a health-evidence question that tests the review
gate without producing personalized medical instructions. Count checked citations,
entailing citations, unsupported claims, and unresolved questions with denominators.
Record preparation, generation, review, correction time, API usage and actual cost.
Blind editorial comparison when feasible. No claimed improvement until measured.

Keep if total editorial effort improves without material citation/safety/cost
regression. Revise if only the draft is faster. Stop for repeated fabrication,
uncontrolled access/spend or safety failures. Insufficient samples are inconclusive.

## Boundaries

- Request/tool/output limits are explicit. Estimated dollar reservations are not
  hard billing guarantees; hosted search input and in-flight usage can exceed an
  estimate. There are no automatic unbounded retries or concurrent subagents.
- URL validation is for citations, not a network SSRF defense for a scraper. This
  engine never fetches arbitrary source URLs locally. Adding a future fetcher
  requires DNS/redirect/private-address validation and parsing limits.
- Private files use local single-writer locks and atomic replacement. This is not
  a multi-user service or hostile-local-user sandbox. Protect the host/filesystem.
- Instructions in source text cannot register local tools or trigger publication.
  Prompt instructions alone do not prove immunity to semantic prompt injection.
- Source independence, dates, study quality and evidence entailment require review.
  No full-text possession, systematic review, human panel, independent verification,
  or causal result is asserted merely because generation completed.
- Health/safety domains default to elevated review. Domain heuristics are not a
  complete risk classifier; the operator must set risk_tier=high for other cases.
- No automatic source archival, private-corpus upload, newsletter/social output,
  autonomous publishing, frontend redesign, or paid API test is in this commit.
