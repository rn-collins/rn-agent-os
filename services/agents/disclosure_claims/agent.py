"""Disclosure + Claims-Risk agent.

Reviews a single public social post for: sponsorship/affiliate/material-connection disclosure,
and express/implied claims with risk. Returns strict, graded JSON.

Design: rule-based and fully OFFLINE by default (runs with zero API keys), so the engine is
demonstrably real today. If a local LLM (Ollama) is reachable and USE_LLM=1, it refines the
result — but the rule engine is always the floor. Not legal advice; surfaces issues for human review.
"""
from __future__ import annotations
import os, re, json
from datetime import datetime, timezone

# ---- lexicons -------------------------------------------------------------
DISCLOSURE_CLEAR = [
    r"#ad\b", r"\bpaid partnership\b", r"\bsponsored\b", r"#sponsored\b",
    r"\badvertisement\b", r"\bpaid promotion\b",
]
DISCLOSURE_VAGUE = [
    r"\bthanks to\b", r"\bpartner(ed)? with\b", r"\bcollab(oration)?\b",
    r"\bbrand ambassador\b", r"#sp\b", r"#partner\b", r"\bgifted\b", r"\bpr\b",
]
AFFILIATE_SIGNALS = [
    r"\baffiliate( link)?\b", r"\bcommission\b", r"\buse (my )?code\b",
    r"\bdiscount code\b", r"\blink in bio\b", r"\bshop my\b", r"\bltk\b",
    r"\bearn(s)? (a )?commission\b",
]
GIFTED_SIGNALS = [r"\bgifted\b", r"\bpr package\b", r"\bsent me\b", r"\bfree(ly)? sent\b"]
AMBASSADOR_SIGNALS = [r"\bambassador\b", r"\bbrand partner\b", r"#partner\b", r"\bteamed up with\b"]

# claim patterns: (regex, category, risk, kind)
CLAIM_PATTERNS = [
    (r"\bcure[sd]?\b|\bcuring\b", "health", "high", "express"),
    (r"\btreat(s|ed|ment)?\b(?!.*\bnot\b)", "health", "high", "implied"),
    (r"\bheal[s]?\b|\breverse[s]?\b|\brepair[s]?\b", "health", "high", "implied"),
    (r"\bclinically proven\b|\bscientifically proven\b|\bstudies show\b", "health", "high", "express"),
    (r"\bfda[- ]approved\b|\bfda cleared\b", "safety", "high", "express"),
    (r"\bdetox(es|ify|ifies)?\b", "health", "medium", "implied"),
    (r"\bboost(s)? (your )?immune\b|\bimmunity\b", "health", "medium", "implied"),
    (r"\blose \d+\s?(lbs|pounds|kg)\b|\bweight loss\b|\bmelt(s)? fat\b", "health", "high", "express"),
    (r"\b100% (safe|effective|natural)\b|\bguaranteed\b", "performance", "high", "express"),
    (r"\bno side effects\b|\bcompletely safe\b", "safety", "high", "express"),
    (r"\bget rich\b|\bguaranteed returns?\b|\bpassive income\b|\bdouble your money\b", "finance", "high", "express"),
    (r"\banti[- ]aging\b|\byears younger\b", "health", "medium", "implied"),
    (r"\bmiracle\b|\blife[- ]changing\b|\bgame[- ]?changer\b", "performance", "medium", "implied"),
]

TESTIMONIAL_SIGNALS = [r"\bchanged my life\b", r"\bworked for me\b", r"\bmy results\b", r"\bafter using\b"]


def _find(patterns, text):
    hits = []
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            hits.append(m.group(0))
    return hits


def analyze(text: str, brand_brief: dict | None = None,
            platform: str = "unknown", creator: str = "unknown", url: str = "") -> dict:
    t = text or ""
    low = t.lower()

    clear = _find(DISCLOSURE_CLEAR, low)
    vague = _find(DISCLOSURE_VAGUE, low)
    affiliate = _find(AFFILIATE_SIGNALS, low)
    gifted = _find(GIFTED_SIGNALS, low)
    ambassador = _find(AMBASSADOR_SIGNALS, low)

    # sponsorship classification
    if clear and not affiliate:
        sponsorship = "paid"
    elif affiliate:
        sponsorship = "affiliate"
    elif gifted:
        sponsorship = "gifted"
    elif ambassador:
        sponsorship = "paid"        # ambassador / brand-partner = a paid material connection
    elif vague:
        sponsorship = "unclear"
    else:
        sponsorship = "none"

    disclosure_present = bool(clear)
    if clear:
        # clear if the marker appears in the first 120 chars (early/visible), else vague
        early = any(re.search(p, low[:120], flags=re.I) for p in DISCLOSURE_CLEAR)
        disclosure_clarity = "clear" if early else "vague"
    elif vague:
        disclosure_clarity = "vague"
    else:
        disclosure_clarity = "missing"

    # claims
    claims = []
    for pat, cat, risk, kind in CLAIM_PATTERNS:
        m = re.search(pat, low)
        if m:
            claims.append({"text": m.group(0), "type": kind, "category": cat, "risk": risk})

    # risk flags
    flags = []
    material_connection = sponsorship in ("paid", "affiliate", "gifted")
    if material_connection and disclosure_clarity == "missing":
        flags.append({"severity": "red", "kind": "disclosure",
                      "detail": f"Material connection ({sponsorship}) with no disclosure."})
    elif material_connection and disclosure_clarity == "vague":
        flags.append({"severity": "yellow", "kind": "disclosure",
                      "detail": f"Material connection ({sponsorship}); disclosure vague or not early/visible."})
    if affiliate and disclosure_clarity != "clear":
        flags.append({"severity": "yellow", "kind": "affiliate",
                      "detail": "Affiliate signals present without a clear affiliate disclosure."})
    for c in claims:
        sev = "red" if c["risk"] == "high" else ("yellow" if c["risk"] == "medium" else "green")
        flags.append({"severity": sev, "kind": "claim",
                      "detail": f"{c['category']} {c['type']} claim: \"{c['text']}\" — substantiation needed."})
    if _find(TESTIMONIAL_SIGNALS, low) and any(c["category"] == "health" for c in claims):
        flags.append({"severity": "yellow", "kind": "testimonial",
                      "detail": "Health-outcome testimonial language; atypical-results/disclaimer risk."})

    # overall severity + confidence/grade
    order = {"red": 3, "yellow": 2, "green": 1}
    top = max((order[f["severity"]] for f in flags), default=1)
    overall = {3: "red", 2: "yellow", 1: "green"}[top]
    # evidence grade: rule matches are direct textual evidence
    evidence_grade = "strong" if flags else "moderate"
    # confidence: high when both a material connection and explicit markers are unambiguous
    if overall == "green":
        confidence = "high"
    elif disclosure_clarity == "missing" and material_connection:
        confidence = "high"
    else:
        confidence = "moderate"

    result = {
        "agent": "disclosure_claims",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "engine": "rules",
        "post": {"platform": platform, "creator": creator, "url": url},
        "sponsorship": sponsorship,
        "disclosure_present": disclosure_present,
        "disclosure_clarity": disclosure_clarity,
        "claims": claims,
        "risk_flags": flags,
        "overall_severity": overall,
        "evidence_grade": evidence_grade,
        "confidence": confidence,
        "review_status": "needs_review" if overall in ("red", "yellow") else "agent_drafted",
        "recommended_action": _recommend(overall, sponsorship, disclosure_clarity, claims),
        "disclaimer": "Educational risk surfacing, not legal advice. High/medium flags require human review.",
    }

    if os.getenv("USE_LLM") == "1":
        result = _maybe_refine_with_llm(t, result)
    return result


def _recommend(overall, sponsorship, clarity, claims):
    if overall == "red":
        return "Hold from amplification; route to human review before publishing/partnering."
    if overall == "yellow":
        return "Review before scaling; fix disclosure placement/clarity and substantiate flagged claims."
    return "No blocking issues detected by rules; log and monitor."


def _maybe_refine_with_llm(text, result):
    """Optional: ask a local Ollama model to add nuance. Never lowers a rule-based flag."""
    try:
        import httpx  # noqa
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        prompt = (
            "You are a creator-marketing disclosure/claims analyst. Return ONLY JSON with keys "
            "extra_flags (list of {severity,kind,detail}) and notes (string). Post:\n" + text
        )
        r = httpx.post(f"{host}/api/generate",
                       json={"model": model, "prompt": prompt, "format": "json", "stream": False},
                       timeout=30)
        data = json.loads(r.json()["response"])
        result["engine"] = "rules+llm"
        if isinstance(data.get("extra_flags"), list):
            result["risk_flags"].extend(data["extra_flags"])
        if data.get("notes"):
            result["llm_notes"] = data["notes"]
    except Exception as e:  # offline / model missing → keep rule result
        result["llm_note"] = f"llm_unavailable: {e.__class__.__name__}"
    return result


if __name__ == "__main__":
    import sys
    here = os.path.dirname(__file__)
    samples = json.load(open(os.path.join(here, "sample_input.json")))
    if len(sys.argv) > 1:
        samples = [{"text": " ".join(sys.argv[1:]), "platform": "cli", "creator": "cli"}]
    for s in samples:
        out = analyze(s["text"], platform=s.get("platform", "unknown"), creator=s.get("creator", "unknown"))
        print(json.dumps(out, indent=2))
        print("-" * 70)
