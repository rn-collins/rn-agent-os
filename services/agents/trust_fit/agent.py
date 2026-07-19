"""Trust / Brand-Fit agent.

Consumes the Brand-Perception component (trust mechanisms) + the Disclosure/Claims analyses +
an optional brand brief, and returns a creator-fit scorecard: is this creator a good, safe fit
for THIS brand — not just reach.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from services.components.brand_perception import score_creator


def score(creator: str, analyses: list[dict], brand_brief: dict | None = None) -> dict:
    brief = brand_brief or {}
    bp = score_creator(creator, analyses)
    m = bp["mechanisms"]

    # claims-risk exposure — red CLAIM flags (health/efficacy) are worse than red DISCLOSURE flags
    flags = [f for a in analyses for f in a.get("risk_flags", [])]
    red_claims = sum(1 for f in flags if f.get("severity") == "red" and f.get("kind") == "claim")
    red_other = sum(1 for f in flags if f.get("severity") == "red" and f.get("kind") != "claim")
    red = red_claims + red_other
    yellow = sum(1 for f in flags if f.get("severity") == "yellow")

    banned = [b.lower() for b in brief.get("banned_or_risky_claims", [])]
    banned_hits = sum(1 for a in analyses for c in a.get("claims", [])
                      if any(b in c.get("text", "").lower() for b in banned))
    # claims red are near-disqualifying; disclosure/affiliate reds are fixable (lighter penalty)
    fit = max(0, min(100, bp["trust_score"] - red_claims * 16 - red_other * 6
                     - yellow * 3 - banned_hits * 12))

    if red_claims > 0 or fit < 40:
        recommendation = "avoid"            # unsubstantiated claims / broadly exposed
    elif fit >= 70 and red == 0:
        recommendation = "fit"
    else:
        recommendation = "test"             # fixable disclosure gaps → pilot after remediation

    return {
        "agent": "trust_fit",
        "creator": creator,
        "uses_component": "brand_perception",
        "trust_score": bp["trust_score"],
        "mechanisms": m,
        "claims_exposure": {"red": red, "yellow": yellow, "banned_brief_hits": banned_hits},
        "fit_score": fit,
        "recommendation": recommendation,
        "rationale": bp["rationale"] + f" Fit {fit}/100 for brand "
                     f"'{brief.get('brand','(unspecified)')}' (red flags: {red}).",
        "review_status": "needs_review" if recommendation != "fit" else "agent_drafted",
    }
