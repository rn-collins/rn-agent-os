"""Demo the supervised graph: run to the human gate, show the queue, approve, resume, persist.

Run: python services/orchestrator/run.py            (auto-approve after showing the pause)
     python services/orchestrator/run.py --reject    (show the reject path)
"""
from __future__ import annotations
import os, sys
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, ROOT)
from services.orchestrator.graph import orchestrator, FallbackRunner
from services.orchestrator.model_router import ModelRouter


def main():
    approve = "--reject" not in sys.argv
    kind, app = orchestrator()
    print(f"orchestrator backend: {kind}")
    print("model router providers:", ModelRouter().providers() or ["(none → stub, rule-based agents still run)"])

    # The demo drives the dependency-free runner (same nodes/edges as the LangGraph app).
    runner = app if isinstance(app, FallbackRunner) else FallbackRunner()

    print("\n--- RUN 1: execute to the human gate ---")
    state = runner.run()
    for line in state["_log"]:
        print("  •", line)
    print("  status:", state["status"])

    if state["status"] == "awaiting_human":
        print(f"\n  HUMAN REVIEW QUEUE ({len(state['review_queue'])} flags, red first):")
        for r in state["review_queue"][:6]:
            print(f"    [{r['severity'].upper():6}] {r['kind']:11} @{r['creator']:20} {r['detail']}")

        print(f"\n--- RUN 2: human {'APPROVES' if approve else 'REJECTS'} → resume ---")
        state = runner.resume(state, approve=approve, notes="reviewed by RN")
        for line in state["_log"][-3:]:
            print("  •", line)
        print("  final status:", state["status"])
        if state["status"] == "complete":
            print("  persisted:", state["persisted"], "→", state["backend"])
            print("  audits drafted:", [a["creator"] for a in state["audits"]])
    if state.get("errors"):
        print("\n  errors captured:", state["errors"])


if __name__ == "__main__":
    main()
