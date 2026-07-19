"""One callable that runs the whole pipeline and persists — used by the API and n8n cron.

run_pipeline() -> collect (Sector Watch) → grade (Disclosure/Claims) → trust-fit → draft audits
→ persist to the configured backend. Returns a summary dict.
"""
from __future__ import annotations
import os, sys
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, ROOT)

from services.agents.sector_watch.agent import collect
from services.agents.disclosure_claims.agent import analyze
from services.agents.trust_fit.agent import score as trust_fit
from services.agents.client_audit.agent import draft, render_markdown
from services.db.store import Store

DEFAULT_BRIEF = {"brand": "CleanGreens Co", "verticals": ["wellness"],
                 "banned_or_risky_claims": ["cured", "clinically proven", "detox", "100% safe"]}


def run_pipeline(brand_brief: dict | None = None, persist: bool = True) -> dict:
    brief = brand_brief or DEFAULT_BRIEF
    posts = collect()
    by_creator = defaultdict(list)
    register = []
    for p in posts:
        a = analyze(p["text"], brand_brief=brief, platform=p["platform"], creator=p["creator"], url=p["url"])
        by_creator[p["creator"]].append(a)
        for f in a["risk_flags"]:
            register.append({"severity": f["severity"], "kind": f["kind"], "detail": f["detail"],
                             "creator": p["creator"], "platform": p["platform"], "url": p["url"],
                             "confidence": a["confidence"]})
    fits = {c: trust_fit(c, al, brief) for c, al in by_creator.items()}

    audits = []
    for c, al in by_creator.items():
        if fits[c]["recommendation"] != "fit":
            au = draft(c, al, fits[c], brief)
            au["report_md"] = render_markdown(au)
            audits.append(au)

    result = {"posts": len(posts),
              "red": sum(1 for r in register if r["severity"] == "red"),
              "yellow": sum(1 for r in register if r["severity"] == "yellow"),
              "creators": {c: {"fit": f["fit_score"], "rec": f["recommendation"]} for c, f in fits.items()},
              "audits_drafted": [a["creator"] for a in audits]}

    if persist:
        backend = os.getenv("BACKEND", "postgres" if os.getenv("DATABASE_URL") else "sqlite")
        dsn = os.getenv("DATABASE_URL") if backend == "postgres" else os.path.join(
            os.getenv("TMPDIR", "/tmp"), "agentos_demo.sqlite")
        store = Store(backend=backend, dsn=dsn)
        result["persisted"] = store.persist_pipeline({"register": register}, audits)
        result["backend"] = backend
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(run_pipeline(persist=False), indent=2))
