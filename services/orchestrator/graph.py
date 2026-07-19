"""Supervised graph for the Creator Risk pipeline.

Nodes:  collect -> grade -> trust_fit -> [GATE] -> draft -> persist
The GATE is a human-in-the-loop pause: if any RED flag exists, the run stops with
status='awaiting_human' and a review queue. Call resume(state, approve=True) to continue.

Every node runs through a retry wrapper (errors captured to state['errors']). The heavy reasoning
is rule-based; the ModelRouter is available to nodes for optional enrichment / narrative polish.

Two execution backends:
  - build_langgraph(): a native LangGraph StateGraph with interrupt_before=['draft'] + checkpointer,
    used when `langgraph` is installed.
  - FallbackRunner: a dependency-free executor with the same nodes/edges + HITL, so it runs offline.
"""
from __future__ import annotations
import os, sys, time
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, ROOT)

from services.agents.sector_watch.agent import collect
from services.agents.disclosure_claims.agent import analyze
from services.agents.trust_fit.agent import score as trust_fit
from services.agents.client_audit.agent import draft, render_markdown
from services.db.store import Store
from services.orchestrator.model_router import ModelRouter

DEFAULT_BRIEF = {"brand": "CleanGreens Co", "verticals": ["wellness"],
                 "banned_or_risky_claims": ["cured", "clinically proven", "detox", "100% safe"]}
ROUTER = ModelRouter()


# ---- retry wrapper --------------------------------------------------------
def with_retries(fn, name, state, attempts=3, base_delay=0.0):
    for i in range(1, attempts + 1):
        try:
            return fn(state)
        except Exception as e:  # noqa
            state.setdefault("errors", []).append({"node": name, "attempt": i, "error": repr(e)})
            if i == attempts:
                raise
            time.sleep(base_delay * i)


# ---- nodes (each takes state -> mutated state) ----------------------------
def node_collect(state):
    state["posts"] = collect()
    state["_log"].append(f"collect: {len(state['posts'])} posts")
    return state


def node_grade(state):
    brief = state["brief"]
    by_creator = defaultdict(list); register = []
    for p in state["posts"]:
        a = analyze(p["text"], brand_brief=brief, platform=p["platform"], creator=p["creator"], url=p["url"])
        by_creator[p["creator"]].append(a)
        for f in a["risk_flags"]:
            register.append({"severity": f["severity"], "kind": f["kind"], "detail": f["detail"],
                             "creator": p["creator"], "platform": p["platform"], "url": p["url"],
                             "confidence": a["confidence"]})
    state["by_creator"] = dict(by_creator)
    state["register"] = register
    state["reds"] = sum(1 for r in register if r["severity"] == "red")
    state["_log"].append(f"grade: {state['reds']} red / "
                         f"{sum(1 for r in register if r['severity']=='yellow')} yellow")
    return state


def node_trust_fit(state):
    state["fits"] = {c: trust_fit(c, al, state["brief"]) for c, al in state["by_creator"].items()}
    state["_log"].append("trust_fit: " + ", ".join(
        f"{c}={f['recommendation']}" for c, f in state["fits"].items()))
    return state


def gate_decision(state) -> str:
    """Returns 'pause' if human sign-off needed and not yet approved, else 'proceed'."""
    if state["reds"] > 0 and not state.get("approved"):
        return "pause"
    return "proceed"


def node_draft(state):
    audits = []
    for c, al in state["by_creator"].items():
        if state["fits"][c]["recommendation"] != "fit":
            au = draft(c, al, state["fits"][c], state["brief"])
            au["report_md"] = render_markdown(au)
            # optional narrative polish via router (local-first; safe if no model)
            if ROUTER.available():
                r = ROUTER.complete("Tighten this executive summary in one sentence: "
                                    + au["executive_summary"], complexity="high")
                if r.get("text") and not r["text"].startswith("[stub]"):
                    au["executive_summary_polished"] = r["text"].strip()
            audits.append(au)
    state["audits"] = audits
    state["_log"].append(f"draft: {len(audits)} audits ({[a['creator'] for a in audits]})")
    return state


def node_persist(state):
    # QA quality gate — block delivery if agents regress below thresholds/invariants
    if os.getenv("QA_GATE", "1") == "1":
        from services.agents.qa.agent import scorecard
        sc = scorecard()
        state["qa"] = {"gate_pass": sc["gate_pass"], "metrics": sc["metrics"]}
        state["_log"].append(f"qa_gate: {'PASS' if sc['gate_pass'] else 'FAIL'}")
        if not sc["gate_pass"]:
            state["status"] = "blocked_by_qa"
            raise RuntimeError("QA gate failed — refusing to persist/deliver. See state['qa'].")
    backend = os.getenv("BACKEND", "postgres" if os.getenv("DATABASE_URL") else "sqlite")
    dsn = os.getenv("DATABASE_URL") if backend == "postgres" else os.path.join(
        os.getenv("TMPDIR", "/tmp"), "agentos_demo.sqlite")
    if backend == "sqlite" and os.path.exists(dsn):
        os.remove(dsn)
    store = Store(backend=backend, dsn=dsn)
    state["persisted"] = store.persist_pipeline({"register": state["register"]}, state["audits"])
    state["backend"] = backend
    state["_log"].append(f"persist: {backend} {state['persisted']}")
    return state


# ---- fallback executor (no langgraph needed) ------------------------------
class FallbackRunner:
    def _fresh(self, brief):
        return {"brief": brief or DEFAULT_BRIEF, "_log": [], "errors": [],
                "status": "running", "approved": False}

    def run(self, brief=None):
        s = self._fresh(brief)
        with_retries(node_collect, "collect", s)
        with_retries(node_grade, "grade", s)
        with_retries(node_trust_fit, "trust_fit", s)
        if gate_decision(s) == "pause":
            s["status"] = "awaiting_human"
            s["review_queue"] = sorted(s["register"], key=lambda r: {"red": 0, "yellow": 1, "green": 2}[r["severity"]])
            s["_log"].append(f"GATE: paused — {s['reds']} red flags need sign-off")
            return s
        return self._finish(s)

    def resume(self, state, approve: bool, notes: str = ""):
        state["approved"] = bool(approve)
        state["approval_notes"] = notes
        if not approve:
            state["status"] = "rejected"
            state["_log"].append("GATE: rejected by human — stopping")
            return state
        state["_log"].append("GATE: approved by human — resuming")
        return self._finish(state)

    def _finish(self, s):
        with_retries(node_draft, "draft", s)
        with_retries(node_persist, "persist", s)
        s["status"] = "complete"
        return s


# ---- native LangGraph builder (used when installed) -----------------------
def build_langgraph():  # pragma: no cover - requires langgraph
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    from typing import TypedDict, Any

    class S(TypedDict, total=False):
        brief: dict; posts: list; by_creator: dict; register: list; reds: int
        fits: dict; audits: list; persisted: dict; approved: bool; _log: list; errors: list

    g = StateGraph(S)
    g.add_node("collect", node_collect)
    g.add_node("grade", node_grade)
    g.add_node("trust_fit", node_trust_fit)
    g.add_node("draft", node_draft)
    g.add_node("persist", node_persist)
    g.set_entry_point("collect")
    g.add_edge("collect", "grade")
    g.add_edge("grade", "trust_fit")
    # conditional edge = the gate; interrupt_before draft gives the human pause
    g.add_conditional_edges("trust_fit", lambda s: gate_decision(s),
                            {"pause": "draft", "proceed": "draft"})
    g.add_edge("draft", "persist")
    g.add_edge("persist", END)
    return g.compile(checkpointer=MemorySaver(), interrupt_before=["draft"])


def orchestrator():
    """Return the native LangGraph app if available, else the FallbackRunner."""
    try:
        import langgraph  # noqa
        return ("langgraph", build_langgraph())
    except Exception:
        return ("fallback", FallbackRunner())
