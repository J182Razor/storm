# STORM v2 implementation record

Goal: implement the approved additive Kaizen Research engine on `storm-v2`.
Base: fb951af7744dab086e34962e9bc6fe878e145f83.
Architecture: dependency-free Python 3.10+ core; documented OpenAI Responses REST
adapter; read-only hosted web search; private checkpoints; review-only exports.

Placement adjustment: use top-level `storm_v2/` rather than importing through
`knowledge_storm/__init__.py`, which eagerly loads the legacy stack/cache. Existing
STORM files remain byte-for-byte unchanged. The optional adapter accepts existing
STORM perspective results and produces `Information`-compatible records.

- [x] Contracts/configuration and fail-closed validation; offline unit tests.
- [x] Responses transport, resumable request journal, bounded usage controls.
- [x] Source/citation registry, structured output validation, claim review.
- [x] Perspective planning, iterative research, gap follow-up, synthesis/export.
- [x] CLI and fixture demonstration. Streamlit UI deferred: no redesign is required
  for the research-engine milestone; the legacy UI remains unchanged.
- [x] Fresh tests, syntax checks, and local diff review.
- [ ] Remote commit/reference verification (performed after this document is saved).

Scope: no merge, deployment, website changes, private corpus upload, or paid calls.
Network limitation: shell DNS cannot resolve GitHub. Connector reads/writes are
available. Local workspace contains the new files, not a full repository clone.
Legacy dependency integration cannot be claimed tested from this workspace.

Local verification: 43 offline unittest cases pass on Python 3.13.5; compileall,
dry-run and a complete synthetic fixture run pass. No live API calls were made.
The optional legacy adapter was tested at its record boundary, not with DSPy.
