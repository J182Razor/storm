# STORM v2: Kaizen Research

Opt-in GPT-6 Astra research engine for **Kaizen Research**. It leaves the existing
STORM and Co-STORM implementation and defaults unchanged. This is an API workflow,
not a copy of ChatGPT's internal Deep Research implementation.

**Status:** alpha implementation with offline tests. No live paid-model benchmark
has been run. Generated research always requires editorial review.

## Quick start: no API key, no installation, no network

From this repository's `storm-v2` branch, with Python 3.10 or newer:

```sh
python -m unittest discover -s tests/storm_v2 -v
python -m storm_v2 run --brief examples/kaizen/brief.json --dry-run
python -m storm_v2 run --brief examples/kaizen/brief.json --fixture
```

The fixture generates a **synthetic demonstration**, not publishable research.
The command prints its private output directory under `.kaizen-runs/`.
The v2 core uses the Python standard library and the documented Responses REST
API; it does not require an OpenAI SDK or import the legacy DSPy/LiteLLM stack.
Existing STORM users can still install the full project normally; `find_packages`
also discovers `storm_v2`. A source checkout is sufficient for the v2 CLI.

## Live research: explicit authorization required

1. Review `examples/kaizen/brief.json`: question, audience, geography, language,
   cutoff, exclusions and risk. Use public information only.
2. Copy `examples/kaizen/config.json` outside the tracked example directory.
3. Set a nonzero approved `max_estimated_cost_usd` and an operator-supplied
   `estimated_cost_per_request_usd`. The shipped zeros intentionally prevent paid
   execution. These are planning estimates, **not a guaranteed billing cap**.
4. Configure `OPENAI_API_KEY` in your environment or secret manager. Never commit
   it, paste it into research input, or add it to a browser application.
5. Confirm that the API project can use `gpt-6-astra` and Responses web search.
6. After approving the spend and brief, run:

```sh
python -m storm_v2 run --brief examples/kaizen/brief.json \
  --config /path/to/approved-config.json --live --approve-paid-api
```

A missing model, permission or unsupported parameter fails explicitly. There is
no silent fallback to another model. `xhigh` is the configurable preset;
`low`, `medium`, `high`, `xhigh`, and `max` are accepted. Background mode defaults
on with explicit `store=true` for recovery. Review OpenAI retention policies and
your organization's requirements; this mode is not suitable for a zero-retention
requirement. Foreground requests can use `background=false, store=false`, but an
interrupted foreground submission may require manual provider reconciliation.

## What the pipeline does

1. Validate and freeze the Kaizen brief, limits and configuration fingerprint.
2. Produce multi-perspective questions. Existing STORM perspective strings can be
   supplied in `brief.perspectives`; simulated lenses are not actual experts.
3. Research with read-only hosted web search and preserve citation/tool metadata.
4. Assess question coverage and perform a bounded number of gap-filling rounds.
5. Synthesize a structured 18-section dossier using only registered source IDs.
6. Run a separate **provisional model assessment**, mechanical checks and a human
   review gate. A second call to the same model is not independent verification.
7. Export Markdown, JSON, source/claim records, coverage, review flags and usage.

No function tools, shell, unrestricted MCP, private-drive access, automated
publishing, billing, email or website credentials are exposed to the model.
Web search is not a guarantee of Google search-engine execution or direct access
to Reddit, TikTok, Instagram, Facebook, restricted groups or paywalled full texts.

## Output contract

Each run has its own directory:
`.kaizen-runs/KAIZEN-RESEARCH/<research-id>/<run-id>/`

- `brief.json`, `config.json`, `plan.json`: frozen scope and plan.
- `sources.json`: normalized URLs, original URLs, citation offsets, access states,
  tool observations and retrieval issues. Publication dates remain null when not
  verified; source types start unclassified for editorial assessment.
- `claims.json`: claims, source IDs, qualifications and proposed evidence ratings.
- `dossier.json`, `dossier.md`: structured and readable drafts.
- `review.json`: mechanical errors, separate semantic blockers and review needs.
- `coverage.json`: model-reported coverage and unresolved follow-up questions.
- `usage.json`: request reservations and provider-reported token usage. Actual
  dollar cost is null until reconciled with provider billing.
- `run.json`, `requests.json`, `events.jsonl`: status, resumable request journal,
  and sanitized stage events. Reasoning items and raw provider error bodies are
  excluded; private run text is still sensitive and must not be committed.
- `manifest.json`: artifact hashes for review/change detection.

Every generated dossier has `editorial_status=needs_review` and an overall
`evidence_strength=UNKNOWN`. Claim ratings are **model proposals**, not validated
ratings. Citation annotations establish attribution, not source entailment.
`provider_opened` means the provider reported a page action, not that the engine
has the page's full text. This version does not scrape original pages or invent
excerpts. Inspect originals before publication, especially for high-stakes topics.

## Recovery and review

```sh
python -m storm_v2 resume /path/to/run --approve-paid-api
python -m storm_v2 cancel /path/to/run research-0 --confirm
```

For synthetic runs, resume needs no paid approval. A queued/in-progress response
is retrieved by its saved provider ID, never automatically submitted again.
Network failures on submission are ambiguous; inspect provider records manually.
The tool deliberately does not retry POSTs. HTTP rejection records include only a
safe status code. Correct configuration and start a new run after resolving the
rejection. A changed brief/configuration/version requires a new run.

Polling is bounded across resumes. Exhausting the polling cap does not cancel a
job or refund charges: inspect/cancel it explicitly. Interrupt the foreground
runner first to release its lock before using the cancellation command. After a
hard process crash, inspect the PID in `run.lock` and confirm no writer remains
before manually removing that lock. Do not remove another active process's lock.

`storm_v2.review.record_human_decision` records a named editorial decision, notes,
artifact hash, and a qualified-reviewer attestation for high-risk work. It refuses
synthetic material, changed artifacts, failed checks, or missing required
qualification. The attestation is an operator record, not credential verification.
It **never publishes**. A website importer must verify hashes and the human
review record and must safely render text. Importer compatibility with the actual
Kaizen site schema remains unverified; `kaizen-dossier/1` is this engine's contract.

## STORM interoperability

`storm_v2.adapter.perspectives_from_storm` accepts already computed persona lists
or a prediction with `.personas`. This avoids hidden, unbudgeted legacy model
calls. `information_records` returns `Information.from_dict`-compatible records.
`to_storm_information` optionally creates legacy objects, importing STORM only on
that explicit path. A provider-generated report is never relabeled an original
source snippet; records without real excerpts have empty `snippets`.

See [docs/kaizen/VALIDATION.md](docs/kaizen/VALIDATION.md) for test scope, remaining
live checks and the bounded baseline comparison. No main-site, Labs, DNS, social
or commerce configuration is changed by this engine.

## Primary API references (checked 2026-09-18)

- https://developers.openai.com/api/docs/models/gpt-6-astra
- https://developers.openai.com/api/docs/guides/tools-web-search
- https://developers.openai.com/api/docs/guides/background
- https://developers.openai.com/api/docs/guides/structured-outputs
