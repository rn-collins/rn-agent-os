"""Persistence layer.

Writes pipeline output into the evidence tables. Two backends:
  - postgres (psycopg)  -> the real system; schema from db/schema.sql
  - sqlite  (built-in)  -> offline demo so the write path + dashboards are verifiable with no server

Usage:
  Store(backend="sqlite", dsn="services/db/demo.sqlite").persist_pipeline(out)
  Store(backend="postgres", dsn=os.environ["DATABASE_URL"]).persist_pipeline(out)
"""
from __future__ import annotations
import os, json, uuid
from datetime import datetime, timezone

SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS agent_runs(
  id TEXT PRIMARY KEY, agent_name TEXT, run_type TEXT, started_at TEXT, ended_at TEXT,
  status TEXT, model_used TEXT, human_review_required INTEGER);
CREATE TABLE IF NOT EXISTS content_items(
  id TEXT PRIMARY KEY, url TEXT, platform TEXT, creator TEXT, sector TEXT,
  captured_at TEXT, source TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS risk_findings(
  id TEXT PRIMARY KEY, content_item_id TEXT, creator TEXT, platform TEXT,
  risk_type TEXT, severity TEXT, confidence TEXT, explanation TEXT,
  recommended_action TEXT, review_status TEXT, url TEXT);
CREATE TABLE IF NOT EXISTS client_audits(
  id TEXT PRIMARY KEY, creator TEXT, brand TEXT, recommendation TEXT,
  reviewer_status TEXT, report_md TEXT, drafted_on TEXT);
"""


class Store:
    def __init__(self, backend="sqlite", dsn="services/db/demo.sqlite"):
        self.backend = backend
        if backend == "sqlite":
            import sqlite3
            self.con = sqlite3.connect(dsn)
            self.ph = "?"
            self.con.executescript(SQLITE_DDL)
        elif backend == "postgres":
            import psycopg  # noqa
            self.con = psycopg.connect(dsn)
            self.ph = "%s"
        else:
            raise ValueError(backend)

    def _ins(self, table, row: dict):
        cols = ",".join(row)
        marks = ",".join([self.ph] * len(row))
        cur = self.con.cursor()
        cur.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))

    def persist_pipeline(self, out: dict, audits: list[dict] | None = None) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        run_id = str(uuid.uuid4())
        self._ins("agent_runs", {"id": run_id, "agent_name": "pipeline:watch_to_risk",
                                 "run_type": "batch", "started_at": now, "ended_at": now,
                                 "status": "complete", "model_used": "rules", "human_review_required": 1})
        n_posts = n_flags = 0
        # content_items + risk_findings from the register (grouped in out['register'])
        # build a stable content id per url
        seen = {}
        for r in out["register"]:
            cid = seen.get(r["url"])
            if not cid:
                cid = str(uuid.uuid4()); seen[r["url"]] = cid
                self._ins("content_items", {"id": cid, "url": r["url"], "platform": r["platform"],
                                            "creator": r["creator"], "sector": None, "captured_at": now,
                                            "source": "fixtures", "text": None})
                n_posts += 1
            self._ins("risk_findings", {"id": str(uuid.uuid4()), "content_item_id": cid,
                                        "creator": r["creator"], "platform": r["platform"],
                                        "risk_type": r["kind"], "severity": r["severity"],
                                        "confidence": r.get("confidence"), "explanation": r["detail"],
                                        "recommended_action": None, "review_status": "needs_review",
                                        "url": r["url"]})
            n_flags += 1
        for a in (audits or []):
            self._ins("client_audits", {"id": str(uuid.uuid4()), "creator": a["creator"],
                                        "brand": a.get("brand"), "recommendation": a["recommendation"],
                                        "reviewer_status": a["review_status"],
                                        "report_md": a.get("report_md"), "drafted_on": a["drafted_on"]})
        self.con.commit()
        return {"run_id": run_id, "content_items": len(seen), "risk_findings": n_flags,
                "client_audits": len(audits or [])}

    def query(self, sql: str):
        cur = self.con.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
