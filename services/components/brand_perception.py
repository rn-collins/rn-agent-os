"""Brand-Perception component — callable form of Aloha's Brand-Perception Intelligence.

"Diagnose brand/creator trust by mechanism, not vibes." Scores a creator on trust mechanisms
using their collected posts + the per-post disclosure/claims analyses. Returns a 0-100 trust
profile with per-mechanism scores and rationale — the input the Trust-Fit agent needs.
"""
from __future__ import annotations


def score_creator(creator: str, analyses: list[dict]) -> dict:
    """analyses = list of Disclosure/Claims agent outputs for this creator's posts."""
    n = max(1, len(analyses))

    # --- mechanisms (0-100 each) ---
    # source credibility: penalized by high-risk claims (overclaiming erodes credibility)
    high_claims = sum(1 for a in analyses for c in a.get("claims", []) if c.get("risk") == "high")
    source_credibility = max(0, 100 - (high_claims / n) * 60)

    # disclosure hygiene: rewarded for clear disclosure, penalized for missing on material connections
    clear = sum(1 for a in analyses if a.get("disclosure_clarity") == "clear")
    missing_material = sum(1 for a in analyses
                           if a.get("sponsorship") in ("paid", "affiliate", "gifted")
                           and a.get("disclosure_clarity") == "missing")
    disclosure_hygiene = max(0, min(100, 60 + (clear / n) * 40 - (missing_material / n) * 60))

    # commercialization saturation: share of posts with a material connection (higher = more saturated)
    material = sum(1 for a in analyses if a.get("sponsorship") in ("paid", "affiliate", "gifted"))
    commercialization_saturation = round((material / n) * 100)

    # processing fluency / clarity proxy: neutral, non-hyped posts read as clearer
    hyped = sum(1 for a in analyses for c in a.get("claims", [])
                if c.get("category") in ("performance", "health") and c.get("risk") in ("high", "medium"))
    processing_fluency = max(0, 100 - (hyped / n) * 40)

    # parasocial/testimonial intensity: testimonial + health = higher intensity (a risk lever, not a virtue)
    parasocial_intensity = round(min(100, (sum(
        1 for a in analyses for f in a.get("risk_flags", []) if f.get("kind") == "testimonial") / n) * 100 + 20))

    # overall trust score: credibility + hygiene + fluency, dampened by over-commercialization
    overall = round(
        0.4 * source_credibility + 0.35 * disclosure_hygiene + 0.25 * processing_fluency
        - 0.15 * commercialization_saturation
    )
    overall = max(0, min(100, overall))

    return {
        "component": "brand_perception",
        "creator": creator,
        "posts_reviewed": len(analyses),
        "mechanisms": {
            "source_credibility": round(source_credibility),
            "disclosure_hygiene": round(disclosure_hygiene),
            "processing_fluency": round(processing_fluency),
            "commercialization_saturation": commercialization_saturation,
            "parasocial_intensity": parasocial_intensity,
        },
        "trust_score": overall,
        "rationale": _rationale(overall, source_credibility, disclosure_hygiene, commercialization_saturation),
    }


def _rationale(overall, cred, hyg, sat):
    parts = []
    if cred < 60:
        parts.append("credibility eroded by high-risk claims")
    if hyg < 60:
        parts.append("disclosure hygiene is weak (missing/late on paid content)")
    if sat > 60:
        parts.append("high commercialization saturation")
    if not parts:
        parts.append("trust mechanisms broadly intact")
    return f"Trust {overall}/100 — " + "; ".join(parts) + "."
