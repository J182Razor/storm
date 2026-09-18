"""python -m storm_v2: dry-run, offline fixture, explicitly funded live run, resume."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .client import OpenAITransport, ResearchError, ResponsesClient
from .contracts import Brief, Config
from .engine import ResearchEngine, run_live
from .fixture import FixtureTransport
from .state import RunStore


def load(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private Kaizen draft research; never publishes")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("run")
    start.add_argument("--brief", required=True)
    start.add_argument("--config")
    start.add_argument("--output", default=".kaizen-runs")
    mode = start.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--fixture", action="store_true")
    mode.add_argument("--live", action="store_true")
    start.add_argument("--approve-paid-api", action="store_true")
    resume = sub.add_parser("resume")
    resume.add_argument("run_dir")
    resume.add_argument("--approve-paid-api", action="store_true")
    cancel = sub.add_parser("cancel")
    cancel.add_argument("run_dir")
    cancel.add_argument("stage")
    cancel.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            brief = Brief(**load(args.brief))
            config = Config.from_dict(load(args.config)) if args.config else Config()
            if args.dry_run:
                print(json.dumps({"mode": "dry-run; no API calls", "brief": asdict(brief),
                    "effective_risk": brief.effective_risk, "config": config.to_dict()}, indent=2))
                return 0
            if args.live:
                config.require_paid_permission(args.approve_paid_api)
            store = RunStore.create(args.output, brief, config, synthetic=args.fixture)
            print("Run directory:", store.path, flush=True)
        else:
            store = RunStore(args.run_dir)
        if args.command == "cancel":
            if store.read("run.json")["synthetic"]:
                raise ValueError("Synthetic runs have no remote job to cancel")
            if not args.confirm:
                raise ValueError("Cancellation requires --confirm; incurred usage is not refunded")
            config = Config.from_dict(store.read("config.json"))
            with store.lock():
                result = ResponsesClient(OpenAITransport(config.limits), store, config).cancel(args.stage)
            print(json.dumps({"status": result["status"]}))
            return 0
        synthetic = store.read("run.json")["synthetic"]
        result = ResearchEngine(store, FixtureTransport(), offline=True).run() if synthetic else run_live(store, args.approve_paid_api)
        print(json.dumps({"run_dir": str(store.path), "status": result["execution_status"],
                          "editorial_status": "needs_review", "synthetic": synthetic}))
        return 0 if result["execution_status"] == "completed" else 2
    except ResearchError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (ValueError, TypeError, KeyError, OSError, RuntimeError):
        print("Run stopped. Inspect the local checkpoint and configuration; no automatic resubmission. "
              "Verify authorization, limits, provider access and input schema. See README_STORM_V2.md.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
