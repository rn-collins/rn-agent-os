"""End-to-end pipeline: Sector Watch -> Disclosure/Claims -> Trust-Fit -> risk register.

Runs fully offline on fixtures. This is the "real stream": collect posts, grade each one,
score each creator's fit, and produce a prioritized risk register + a one-screen summary.

Run:  python services/pipeline/run_watch_to_risk.py
"""
from __future__ import annotations
import sys, os, json
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, ROOT)

from services.agents.sector_watch.agent import collect
from services.agents.disclosure_claims.agent import analyze
from services.agents.trust_fit.agent import score as trust_fit

# example brand brief the firm would attach per engagement
BRAND_BRIEF = {"brand": "CleanGreens Co", "verticals": ["wellness"],
               "banned_or_risky_claims": ["cured", "clinically proven", "detox", "100% safe"]}


def run():
    posts = collect()
    by_creator = defaultdict(list)
    register = []

    for p in posts:
        a = analyze(p["text"], brand_brief=BRAND_BRIEF, platform=p["platform"],
                    creator=p["creator"], url=p["url"])
        a["posted_at"] = p.get("posted_at")
        by_creator[p["creator"]].append(a)
        for f in a["risk_flags"]:
            register.append({"severity": f["severity"], "kind": f["kind"], "detail": f["detail"],
                             "creator": p["creator"], "platform": p["platform"], "url": p["url"],
                             "confidence": a["confidence"]})

    # trust-fit per creator (uses Brand-Perception component)
    fits = {c: trust_fit(c, al, BRAND_BRIEF) for c, al in by_creator.items()}

    # prioritize register: red first, then yellow
    order = {"red": 0, "yellow": 1, "green": 2}
    register.sort(key=lambda x: order[x["severity"]])

    return posts, register, fits


def main():
    posts, register, fits = run()
    reds = [r for r in register if r["severity"] == "red"]
    yellows = [r for r in register if r["severity"] == "yellow"]

    print("=" * 74)
    print(f"SECTOR WATCH → RISK  |  {len(posts)} posts collected  |  brand: {BRAND_BRIEF['brand']}")
    print("=" * 74)
    print(f"Risk register: {len(reds)} RED, {len(yellows)} YELLOW\n")

    print("TOP RISK FLAGS")
    for r in register[:8]:
        print(f"  [{r['severity'].upper():6}] {r['kind']:11} @{r['creator']:20} {r['detail']}")

    print("\nCREATOR TRUST-FIT (via Brand-Perception component)")
    for c, f in sorted(fits.items(), key=lambda kv: kv[1]["fit_score"]):
        print(f"  {c:22} trust {f['trust_score']:3}/100 | fit {f['fit_score']:3}/100 "
              f"| {f['recommendation'].upper():5} | reds {f['claims_exposure']['red']}")

    print("\nHuman review queue:", sum(1 for r in register if r["severity"] in ("red", "yellow")),
          "flags need sign-off before anything ships.")
    # machine-readable dump
    out = {"summary": {"posts": len(posts), "red": len(reds), "yellow": len(yellows)},
           "register": register, "trust_fit": fits}
    path = os.path.join(os.path.dirname(__file__), "last_run.json")
    json.dump(out, open(path, "w"), indent=2)
    print("Full JSON:", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
