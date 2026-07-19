"""QA / Regression agent — the quality gate before findings reach a client.

Runs labeled gold-sets through the agents and reports:
  - field ACCURACY (sponsorship, disclosure clarity, overall severity)
  - high-risk-claim detection PRECISION / RECALL
  - trust-fit recommendation accuracy
  - HARD INVARIANTS that must always hold (100% or the gate fails)
  - output SCHEMA validation

Exit code is nonzero if any threshold or invariant fails, so it can gate CI / the orchestrator.

Run:  python services/agents/qa/agent.py         (human-readable + exit code)
      python services/agents/qa/agent.py --json  (machine-readable scorecard)
"""
from __future__ import annotations
import os, sys, json

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
sys.path.insert(0, ROOT)
from services.agents.disclosure_claims.agent import analyze
from services.agents.trust_fit.agent import score as trust_fit
from services.agents.client_audit.agent import draft

EVALS = os.path.join(ROOT, "evals")
THRESHOLDS = {"sponsorship_acc": 0.90, "disclosure_acc": 0.90, "severity_acc": 0.90,
              "high_claim_f1": 0.90, "trust_fit_acc": 0.90}

SEV = {"red", "yellow", "green"}
CONF = {"high", "moderate", "exploratory"}


def _has_high(a):
    return any(c["risk"] == "high" for c in a.get("claims", []))


def run_disclosure_claims():
    gold = json.load(open(os.path.join(EVALS, "gold_disclosure_claims.json")))
    n = len(gold)
    sp = dc = sv = 0
    tp = fp = fn = 0
    fails = []
    for g in gold:
        a = analyze(g["text"])
        e = g["expect"]
        if a["sponsorship"] == e["sponsorship"]: sp += 1
        else: fails.append(f"{g['id']} sponsorship: got {a['sponsorship']} exp {e['sponsorship']}")
        if a["disclosure_clarity"] == e["disclosure_clarity"]: dc += 1
        else: fails.append(f"{g['id']} disclosure: got {a['disclosure_clarity']} exp {e['disclosure_clarity']}")
        if a["overall_severity"] == e["overall_severity"]: sv += 1
        else: fails.append(f"{g['id']} severity: got {a['overall_severity']} exp {e['overall_severity']}")
        got_h, exp_h = _has_high(a), e["has_high_claim"]
        if got_h and exp_h: tp += 1
        elif got_h and not exp_h: fp += 1
        elif not got_h and exp_h: fn += 1
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 1.0
    return {"n": n, "sponsorship_acc": sp / n, "disclosure_acc": dc / n, "severity_acc": sv / n,
            "high_claim_precision": prec, "high_claim_recall": rec, "high_claim_f1": f1,
            "mismatches": fails}


def run_trust_fit():
    gold = json.load(open(os.path.join(EVALS, "gold_trust_fit.json")))
    ok = 0; fails = []
    for g in gold:
        analyses = [analyze(t, brand_brief=g["brand_brief"], creator=g["creator"]) for t in g["posts"]]
        tf = trust_fit(g["creator"], analyses, g["brand_brief"])
        if tf["recommendation"] == g["expect"]["recommendation"]: ok += 1
        else: fails.append(f"{g['id']}: got {tf['recommendation']} exp {g['expect']['recommendation']}")
    return {"n": len(gold), "trust_fit_acc": ok / len(gold), "mismatches": fails}


def check_invariants():
    """Hard rules that must ALWAYS hold. Any failure fails the gate regardless of accuracy."""
    inv = []

    def add(name, ok, detail=""):
        inv.append({"invariant": name, "pass": bool(ok), "detail": detail})

    # 1) material connection + missing disclosure -> a red disclosure flag
    a = analyze("cured my skin, use code X, link in bio")
    add("material+missing_disclosure->red_flag",
        any(f["kind"] == "disclosure" and f["severity"] == "red" for f in a["risk_flags"]))
    # 2) any high-risk claim -> overall red
    add("high_claim->overall_red", (not _has_high(a)) or a["overall_severity"] == "red")
    # 3) neutral -> green
    n = analyze("just a normal update, no links, no products")
    add("neutral->green", n["overall_severity"] == "green")
    # 4) severities + confidence in allowed sets
    add("severity_enum", a["overall_severity"] in SEV and all(f["severity"] in SEV for f in a["risk_flags"]))
    add("confidence_enum", a["confidence"] in CONF)
    # 5) audit always needs_review (never auto client_ready)
    tf = trust_fit("c", [a], {"brand": "B"})
    au = draft("c", [a], tf, {"brand": "B"})
    add("audit_needs_review", au["review_status"] == "needs_review")
    # 6) required output keys present
    req = {"sponsorship", "disclosure_clarity", "claims", "risk_flags", "overall_severity",
           "evidence_grade", "confidence", "review_status"}
    add("output_schema_keys", req.issubset(a.keys()), detail=str(sorted(req - set(a.keys()))))
    return inv


def scorecard():
    dc = run_disclosure_claims()
    tf = run_trust_fit()
    inv = check_invariants()
    metrics = {"sponsorship_acc": dc["sponsorship_acc"], "disclosure_acc": dc["disclosure_acc"],
               "severity_acc": dc["severity_acc"], "high_claim_f1": dc["high_claim_f1"],
               "trust_fit_acc": tf["trust_fit_acc"]}
    threshold_pass = {k: metrics[k] >= THRESHOLDS[k] for k in THRESHOLDS}
    invariants_pass = all(i["pass"] for i in inv)
    gate = all(threshold_pass.values()) and invariants_pass
    return {"gate_pass": gate, "metrics": metrics, "thresholds": THRESHOLDS,
            "threshold_pass": threshold_pass, "invariants": inv, "invariants_pass": invariants_pass,
            "disclosure_claims": dc, "trust_fit": tf}


def main():
    sc = scorecard()
    if "--json" in sys.argv:
        print(json.dumps(sc, indent=2)); sys.exit(0 if sc["gate_pass"] else 1)
    print("QA / REGRESSION SCORECARD")
    print("-" * 52)
    for k, v in sc["metrics"].items():
        mark = "PASS" if sc["threshold_pass"][k] else "FAIL"
        print(f"  {mark}  {k:20} {v:.2f}  (>= {sc['thresholds'][k]:.2f})")
    print("\nINVARIANTS")
    for i in sc["invariants"]:
        print(f"  {'PASS' if i['pass'] else 'FAIL'}  {i['invariant']} {i.get('detail','')}")
    for miss in sc["disclosure_claims"]["mismatches"] + sc["trust_fit"]["mismatches"]:
        print("   mismatch:", miss)
    print("\nGATE:", "PASS ✅ — safe to persist/deliver" if sc["gate_pass"] else "FAIL ❌ — block")
    sys.exit(0 if sc["gate_pass"] else 1)


if __name__ == "__main__":
    main()
