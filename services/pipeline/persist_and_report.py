"""Full standing-system demo: pipeline -> draft audits -> persist -> dashboard queries.

Runnable offline with SQLite (proves the write path + dashboards). Point at Postgres by setting
DATABASE_URL and BACKEND=postgres to write into the real schema for Metabase.

Run: python services/pipeline/persist_and_report.py
"""
from __future__ import annotations
import os, sys, json
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, ROOT)

from services.pipeline.run_watch_to_risk import run, BRAND_BRIEF
from services.agents.client_audit.agent import draft, render_markdown
from services.db.store import Store

BACKEND = os.getenv("BACKEND", "sqlite")
# SQLite demo writes to local tmp (mounted folders can block sqlite file locks); Postgres is the real target.
DSN = os.getenv("DATABASE_URL") if BACKEND == "postgres" else os.path.join(
    os.getenv("TMPDIR", "/tmp"), "agentos_demo.sqlite")

# SQLite-compatible dashboard queries (CASE instead of FILTER)
Q = {
    "risk_by_severity": "SELECT severity, COUNT(*) n FROM risk_findings GROUP BY severity",
    "risk_by_type": "SELECT risk_type, COUNT(*) n FROM risk_findings GROUP BY risk_type ORDER BY n DESC",
    "worst_creators": ("SELECT creator, "
                       "SUM(CASE WHEN severity='red' THEN 1 ELSE 0 END) reds, "
                       "SUM(CASE WHEN severity='yellow' THEN 1 ELSE 0 END) yellows "
                       "FROM risk_findings GROUP BY creator ORDER BY reds DESC, yellows DESC"),
    "review_queue": "SELECT COUNT(*) awaiting_review FROM risk_findings WHERE review_status='needs_review'",
    "audit_pipeline": "SELECT creator, brand, recommendation, reviewer_status FROM client_audits",
}


def main():
    posts, register, fits = run()
    out = {"register": register}

    # group analyses back per creator to draft audits (re-run grading is cheap; reuse register mapping)
    # rebuild per-creator analyses from run() by re-collecting:
    from services.agents.sector_watch.agent import collect
    from services.agents.disclosure_claims.agent import analyze
    by_creator = defaultdict(list)
    for p in collect():
        by_creator[p["creator"]].append(
            analyze(p["text"], brand_brief=BRAND_BRIEF, platform=p["platform"], creator=p["creator"], url=p["url"]))

    # draft audits for creators that need review (AVOID/TEST)
    deliv_dir = os.path.join(ROOT, "deliverables")
    os.makedirs(deliv_dir, exist_ok=True)
    audits = []
    for creator, analyses in by_creator.items():
        tf = fits[creator]
        if tf["recommendation"] == "fit":
            continue
        a = draft(creator, analyses, tf, BRAND_BRIEF)
        md = render_markdown(a)
        a["report_md"] = md
        path = os.path.join(deliv_dir, f"audit_{creator}.md")
        open(path, "w").write(md)
        audits.append(a)
        print(f"drafted audit -> {os.path.relpath(path, ROOT)}  ({a['recommendation'].upper()})")

    # persist
    if BACKEND == "sqlite" and os.path.exists(DSN):
        os.remove(DSN)  # fresh demo each run
    store = Store(backend=BACKEND, dsn=DSN)
    stats = store.persist_pipeline(out, audits)
    print(f"\npersisted to {BACKEND}: {stats}")

    print("\n=== DASHBOARD QUERIES (what Metabase would show) ===")
    for name, sql in Q.items():
        print(f"\n[{name}]")
        for row in store.query(sql):
            print("  ", row)


if __name__ == "__main__":
    main()
