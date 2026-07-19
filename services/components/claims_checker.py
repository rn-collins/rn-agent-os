"""Claims Checker component — the callable form of Aloha's Claims Checker tool.

Reuses the SAME claim rubric the Disclosure/Claims agent uses (single source of truth), so the
self-serve browser tool and the automated agent never drift apart. Returns a compact scorecard.
"""
from __future__ import annotations
import re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from services.agents.disclosure_claims.agent import CLAIM_PATTERNS


def check(text: str) -> dict:
    low = (text or "").lower()
    found = []
    for pat, cat, risk, kind in CLAIM_PATTERNS:
        m = re.search(pat, low)
        if m:
            found.append({"text": m.group(0), "category": cat, "type": kind, "risk": risk})
    order = {"high": 3, "medium": 2, "low": 1}
    worst = max((order[c["risk"]] for c in found), default=0)
    grade = {3: "red", 2: "yellow", 1: "green", 0: "green"}[worst]
    # simple 0-100: more/higher-risk claims -> lower score
    penalty = sum({"high": 34, "medium": 15, "low": 5}[c["risk"]] for c in found)
    score = max(0, 100 - penalty)
    return {
        "component": "claims_checker",
        "claims": found,
        "worst_risk": {3: "high", 2: "medium", 1: "low", 0: "none"}[worst],
        "grade": grade,
        "substantiation_score": score,
        "needs_substantiation": [c["text"] for c in found if c["risk"] in ("high", "medium")],
        "disclaimer": "Not legal advice; flags claims needing substantiation for human review.",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(check(" ".join(sys.argv[1:]) or "clinically proven, cures acne, 100% safe"), indent=2))
