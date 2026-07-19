"""rn-agent-os API skeleton (FastAPI).

Phase 0: health + agent-run endpoints. The Disclosure+Claims agent is wired in and runnable
even without a database (it returns graded JSON directly). DB persistence is optional here.
"""
from __future__ import annotations
import os, sys
from typing import Optional

try:
    from fastapi import FastAPI
    from pydantic import BaseModel
except Exception:  # pragma: no cover - allows import without fastapi installed
    FastAPI = None

# make agents importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from services.agents.disclosure_claims.agent import analyze as analyze_disclosure_claims  # noqa: E402
from services.pipeline.run_pipeline import run_pipeline  # noqa: E402


if FastAPI:
    app = FastAPI(title="rn-agent-os", version="0.1.0")

    class PostIn(BaseModel):
        platform: str = "unknown"
        creator: str = "unknown"
        url: str = ""
        text: str
        brand_brief: Optional[dict] = None

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "rn-agent-os", "version": "0.1.0"}

    @app.post("/agents/disclosure-claims/run")
    def run_disclosure_claims(post: PostIn):
        return analyze_disclosure_claims(post.text, brand_brief=post.brand_brief,
                                         platform=post.platform, creator=post.creator, url=post.url)

    class PipelineIn(BaseModel):
        brand_brief: Optional[dict] = None
        persist: bool = True

    @app.post("/pipeline/run")
    def run_full_pipeline(body: PipelineIn = PipelineIn()):
        """Sector Watch → grade → trust-fit → draft audits → persist. Driven by n8n cron."""
        return run_pipeline(brand_brief=body.brand_brief, persist=body.persist)

    # stubs — return 501 until built
    @app.post("/agents/research-scout/run")
    def _rs(): return {"error": "not_implemented", "agent": "research-scout"}

    @app.post("/agents/sector-watch/run")
    def _sw(): return {"error": "not_implemented", "agent": "sector-watch"}

    @app.get("/risk-findings")
    def _rf(): return {"items": [], "note": "connect DB to persist findings"}
