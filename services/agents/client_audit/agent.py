"""Client Audit Drafting agent — assembles the flagship deliverable.

Takes a creator's graded stream (Disclosure/Claims analyses) + Trust-Fit + brand brief and drafts
a Creator + Brand Evidence Audit across the six layers: findings, evidence map, risk map, priority
matrix, 30/60/90 roadmap. Output is a structured dict and a rendered Markdown report, marked
needs_review. Not legal advice — human sign-off required before it reaches a client.
"""
from __future__ import annotations
from datetime import date


def draft(creator: str, analyses: list[dict], trust_fit: dict, brand_brief: dict | None = None) -> dict:
    brief = brand_brief or {}
    reds = [f for a in analyses for f in a.get("risk_flags", []) if f["severity"] == "red"]
    yellows = [f for a in analyses for f in a.get("risk_flags", []) if f["severity"] == "yellow"]
    claims = [c for a in analyses for c in a.get("claims", [])]
    material = [a for a in analyses if a.get("sponsorship") in ("paid", "affiliate", "gifted")]
    missing_disc = [a for a in material if a.get("disclosure_clarity") == "missing"]

    findings = {
        "1_brand_positioning": _f(
            f"Creator activity is {'misaligned' if trust_fit['recommendation']!='fit' else 'broadly aligned'} "
            f"with brand '{brief.get('brand','(unspecified)')}'. Trust-fit {trust_fit['fit_score']}/100.",
            "moderate", "high" if trust_fit["recommendation"] == "avoid" else "moderate"),
        "2_creator_fit": _f(
            f"Recommendation: {trust_fit['recommendation'].upper()}. "
            f"Trust {trust_fit['trust_score']}/100; disclosure hygiene "
            f"{trust_fit['mechanisms']['disclosure_hygiene']}/100.",
            "strong", "high" if trust_fit["recommendation"] == "avoid" else "moderate"),
        "3_trust_audience": _f(
            f"Commercialization saturation {trust_fit['mechanisms']['commercialization_saturation']}/100; "
            f"parasocial intensity {trust_fit['mechanisms']['parasocial_intensity']}/100. "
            "Higher saturation + testimonial language raises audience-vulnerability risk.",
            "moderate", "moderate"),
        "4_disclosure_claims": _f(
            f"{len(reds)} red and {len(yellows)} yellow flags. {len(missing_disc)} paid/affiliate/gifted "
            f"posts with MISSING disclosure. {len([c for c in claims if c['risk']=='high'])} high-risk claims "
            "need substantiation.", "strong", "high" if reds else "moderate"),
        "5_measurement": _f(
            "Engagement present but trust/compliance not currently measured. Recommend adding "
            "disclosure-compliance rate and claims-risk rate to reporting.", "moderate", "moderate"),
        "6_governance": _f(
            "No evident approval/claims-review workflow for this creator's content. "
            "Introduce briefs + a pre-publish disclosure/claims gate.", "moderate", "high" if reds else "moderate"),
    }

    evidence_map = [{"post": a["post"]["url"], "sponsorship": a["sponsorship"],
                     "disclosure": a["disclosure_clarity"], "claims": [c["text"] for c in a.get("claims", [])],
                     "evidence_grade": a["evidence_grade"], "confidence": a["confidence"]} for a in analyses]

    risk_map = ([{"severity": "red", **f} for f in reds] + [{"severity": "yellow", **f} for f in yellows])

    priority_matrix = {
        "fix_now": [f["detail"] for f in reds],
        "formalize_next": ["Creator brief + pre-publish disclosure/claims gate",
                           "Affiliate disclosure SOP"] if material else [],
        "test_before_scaling": ["Re-run trust-fit after fixes; pilot 1 post with corrected disclosure"],
        "monitor": ["Ongoing Sector Watch on this creator"],
        "stop_doing": ["Amplifying posts with unsubstantiated high-risk claims"] if reds else [],
    }

    roadmap = {
        "30": ["Remove/replace unsubstantiated high-risk claims", "Add clear, early disclosures to paid/affiliate posts"],
        "60": ["Stand up creator brief + claims/disclosure review workflow", "Define trust & compliance KPIs"],
        "90": ["Quarterly re-audit; decide continue / restructure / exit the partnership"],
    }

    exec_summary = (f"{creator} scores {trust_fit['fit_score']}/100 fit for {brief.get('brand','the brand')} "
                    f"({trust_fit['recommendation'].upper()}). {len(reds)} red-flag issues — chiefly "
                    f"{'undisclosed material connections and unsubstantiated health/performance claims' if reds else 'minor items'}. "
                    "Fixable, but not safe to amplify as-is.")

    return {
        "agent": "client_audit_drafting",
        "drafted_on": date.today().isoformat(),
        "creator": creator,
        "brand": brief.get("brand"),
        "executive_summary": exec_summary,
        "recommendation": trust_fit["recommendation"],
        "findings": findings,
        "evidence_map": evidence_map,
        "risk_map": risk_map,
        "priority_matrix": priority_matrix,
        "roadmap_30_60_90": roadmap,
        "review_status": "needs_review",
        "disclaimer": "Draft — educational risk surfacing, not legal advice. Requires human sign-off before client delivery.",
    }


def _f(text, grade, conf_map):
    conf = {"high": "high", "moderate": "moderate", "low": "exploratory"}.get(conf_map, "moderate")
    return {"finding": text, "evidence_grade": grade, "confidence": conf}


def render_markdown(audit: dict) -> str:
    L = []
    L.append(f"# Creator + Brand Evidence Audit — DRAFT")
    L.append(f"**Creator:** {audit['creator']}  ·  **Brand:** {audit['brand']}  ·  **Drafted:** {audit['drafted_on']}")
    L.append(f"\n> {audit['disclaimer']}\n")
    L.append("## Executive summary")
    L.append(audit["executive_summary"])
    L.append(f"\n**Overall recommendation: {audit['recommendation'].upper()}**\n")

    L.append("## Findings by layer")
    names = {"1_brand_positioning": "1 · Brand + Positioning", "2_creator_fit": "2 · Creator Fit",
             "3_trust_audience": "3 · Trust + Audience", "4_disclosure_claims": "4 · Disclosure + Claims Risk",
             "5_measurement": "5 · Measurement", "6_governance": "6 · Governance"}
    for k, f in audit["findings"].items():
        L.append(f"**{names[k]}** — _(evidence: {f['evidence_grade']}, confidence: {f['confidence']})_  \n{f['finding']}\n")

    L.append("## Evidence map")
    L.append("| Post | Sponsorship | Disclosure | Claims | Grade | Conf |")
    L.append("|---|---|---|---|---|---|")
    for e in audit["evidence_map"]:
        L.append(f"| {e['post']} | {e['sponsorship']} | {e['disclosure']} | "
                 f"{', '.join(e['claims']) or '—'} | {e['evidence_grade']} | {e['confidence']} |")

    L.append("\n## Risk map")
    for r in audit["risk_map"]:
        L.append(f"- **[{r['severity'].upper()}]** {r['kind']}: {r['detail']}")

    L.append("\n## Priority matrix")
    for bucket, items in audit["priority_matrix"].items():
        L.append(f"**{bucket.replace('_',' ').title()}**")
        for it in items:
            L.append(f"- {it}")
        if not items:
            L.append("- —")

    L.append("\n## 30 / 60 / 90-day roadmap")
    for d, items in audit["roadmap_30_60_90"].items():
        L.append(f"**Day {d}**")
        for it in items:
            L.append(f"- {it}")
    L.append(f"\n_Status: {audit['review_status']} — human sign-off required._")
    return "\n".join(L)
