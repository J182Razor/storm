"""Private, atomic run storage. A run is a single-writer local workflow."""

import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from .contracts import VERSION, digest, identifier, now


def no_symlinks(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Symlink paths are not permitted for run storage")
    return path


class RunStore:
    def __init__(self, path):
        self.path = no_symlinks(path)
        if not self.path.is_dir():
            raise ValueError("Run directory does not exist")

    @classmethod
    def create(cls, root, brief, config, run_id=None, synthetic=False):
        run_id = identifier(run_id or uuid4().hex)
        path = no_symlinks(Path(root) / brief.business_id / brief.research_id / run_id)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.mkdir(mode=0o700)
        store = cls(path)
        frozen = {"brief": asdict(brief), "config": config.to_dict(), "version": VERSION}
        store.write("brief.json", frozen["brief"])
        store.write("config.json", frozen["config"])
        store.write("run.json", {
            "run_id": run_id, "version": VERSION, "fingerprint": digest(frozen),
            "created_at": now(), "execution_status": "created",
            "editorial_status": "needs_review", "synthetic": synthetic,
        })
        store.write("requests.json", {})
        return store

    def file(self, name):
        if not isinstance(name, str) or Path(name).name != name or name in (".", ".."):
            raise ValueError("Only direct run artifact filenames are allowed")
        identifier(name.rsplit('.', 1)[0])
        return no_symlinks(self.path / name)

    def read(self, name):
        with self.file(name).open(encoding="utf-8") as handle:
            return json.load(handle)

    def write(self, name, data):
        self.write_text(name, json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")

    def write_text(self, name, content):
        dest = self.file(name)
        fd, temp = tempfile.mkstemp(prefix=".writing-", dir=self.path)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, dest)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def event(self, stage, status):
        identifier(stage)
        identifier(status)
        path = self.file("events.jsonl")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now(), "stage": stage, "status": status}) + "\n")

    @contextmanager
    def lock(self):
        path = self.file("run.lock")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise RuntimeError("Run is locked; inspect the recorded PID before manual recovery") from None
        with os.fdopen(fd, "w") as handle:
            handle.write(str(os.getpid()))
        try:
            yield
        finally:
            path.unlink()
