"""
Persistence layer for the VM 2026 backend.

Two interchangeable backends behind one small interface:

  * FirestoreStore - used in Cloud Run (project credentials present).
  * LocalStore     - JSON file under ./.localdb, used for local dev/tests.

The active backend is chosen by ``get_store()``: Firestore when a project is
configured (GOOGLE_CLOUD_PROJECT / FIRESTORE_PROJECT) and the client imports
cleanly, otherwise the local file store.

Collections / shape:
  * snapshots          - dated canonical results, keyed by date (id=YYYY-MM-DD).
                         Historical snapshots are retained (DB scope = history).
  * param_experiments  - user parameter tweaks ONLY (no run outcomes), capped
                         at PARAM_CAP documents (oldest evicted).
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

PARAM_CAP = 1000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------------
# Local file store (dev / fallback)
# ----------------------------------------------------------------------
class LocalStore:
    def __init__(self, path: str | None = None):
        base = os.path.dirname(os.path.abspath(__file__))
        self.path = path or os.path.join(base, ".localdb", "db.json")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._lock = threading.Lock()
        if not os.path.exists(self.path):
            self._write({"snapshots": {}, "param_experiments": []})

    def _read(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, self.path)

    def save_canonical(self, date: str, snapshot: dict) -> None:
        with self._lock:
            db = self._read()
            db["snapshots"][date] = {"date": date, "created_at": _now_iso(),
                                     **snapshot}
            self._write(db)

    def get_latest_canonical(self) -> dict | None:
        db = self._read()
        snaps = db.get("snapshots", {})
        if not snaps:
            return None
        latest = max(snaps.values(), key=lambda s: s.get("created_at", ""))
        return latest

    def get_canonical(self, date: str) -> dict | None:
        return self._read().get("snapshots", {}).get(date)

    def list_canonical_dates(self) -> list[str]:
        db = self._read()
        return sorted(db.get("snapshots", {}).keys(), reverse=True)

    def add_param_experiment(self, params: dict) -> None:
        with self._lock:
            db = self._read()
            exps = db.setdefault("param_experiments", [])
            exps.append({"params": params, "created_at": _now_iso()})
            if len(exps) > PARAM_CAP:
                db["param_experiments"] = exps[-PARAM_CAP:]
            self._write(db)

    def param_experiment_count(self) -> int:
        return len(self._read().get("param_experiments", []))


# ----------------------------------------------------------------------
# Firestore store (production)
# ----------------------------------------------------------------------
class FirestoreStore:
    def __init__(self, project: str | None = None):
        from google.cloud import firestore  # imported lazily

        self.db = firestore.Client(project=project) if project else firestore.Client()
        self._firestore = firestore

    def save_canonical(self, date: str, snapshot: dict) -> None:
        doc = {"date": date, "created_at": self._firestore.SERVER_TIMESTAMP,
               **snapshot}
        self.db.collection("snapshots").document(date).set(doc)

    def get_latest_canonical(self) -> dict | None:
        q = (self.db.collection("snapshots")
             .order_by("created_at", direction=self._firestore.Query.DESCENDING)
             .limit(1))
        for doc in q.stream():
            return doc.to_dict()
        return None

    def get_canonical(self, date: str) -> dict | None:
        doc = self.db.collection("snapshots").document(date).get()
        return doc.to_dict() if doc.exists else None

    def list_canonical_dates(self) -> list[str]:
        q = (self.db.collection("snapshots")
             .order_by("created_at", direction=self._firestore.Query.DESCENDING))
        return [doc.id for doc in q.stream()]

    def add_param_experiment(self, params: dict) -> None:
        col = self.db.collection("param_experiments")
        col.add({"params": params, "created_at": self._firestore.SERVER_TIMESTAMP})
        # Evict oldest beyond the cap. Count is cheap via aggregation.
        try:
            count = col.count().get()[0][0].value
        except Exception:
            count = sum(1 for _ in col.stream())
        if count > PARAM_CAP:
            overflow = count - PARAM_CAP
            old = (col.order_by("created_at",
                                direction=self._firestore.Query.ASCENDING)
                   .limit(overflow).stream())
            for doc in old:
                doc.reference.delete()

    def param_experiment_count(self) -> int:
        col = self.db.collection("param_experiments")
        try:
            return col.count().get()[0][0].value
        except Exception:
            return sum(1 for _ in col.stream())


# ----------------------------------------------------------------------
# Backend selection
# ----------------------------------------------------------------------
_store = None


def get_store():
    global _store
    if _store is not None:
        return _store
    project = os.environ.get("FIRESTORE_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    # K_SERVICE is always set on Cloud Run. In any managed/explicit-project
    # context we REQUIRE Firestore and let init errors surface (a 500) rather
    # than silently using the ephemeral LocalStore, which loses data on every
    # scale-to-zero. firestore.Client() auto-detects the project from the
    # metadata server when `project` is None.
    on_cloud_run = bool(os.environ.get("K_SERVICE"))
    if project or on_cloud_run:
        _store = FirestoreStore(project)
        return _store
    _store = LocalStore()
    return _store
