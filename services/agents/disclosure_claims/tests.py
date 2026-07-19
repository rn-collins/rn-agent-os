"""Minimal gold-set tests for the Disclosure + Claims agent. Run: python tests.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from services.agents.disclosure_claims.agent import analyze

def check(name, cond):
    print(("PASS" if cond else "FAIL"), "-", name)
    return cond

ok = True
# 1: undisclosed affiliate + health cure = red disclosure + red claim
r = analyze("This cured my acne! use code SAVE10, link in bio, earn a commission")
ok &= check("undisclosed affiliate -> red", any(f["kind"]=="disclosure" and f["severity"]=="red" for f in r["risk_flags"]))
ok &= check("health cure claim high", any(c["risk"]=="high" and c["category"]=="health" for c in r["claims"]))
ok &= check("overall red", r["overall_severity"]=="red")

# 2: clean #ad early, no claims = green-ish, disclosure clear
r = analyze("#ad Paid partnership with Acme. Just showing my planner.")
ok &= check("clear disclosure", r["disclosure_clarity"]=="clear")
ok &= check("sponsorship paid", r["sponsorship"]=="paid")

# 3: gifted + testimonial + commission = yellow/red flags present
r = analyze("Thanks to the brand for sending this. My results were amazing after using it. I earn a commission.")
ok &= check("affiliate or disclosure flag present", any(f["kind"] in ("affiliate","disclosure") for f in r["risk_flags"]))

# 4: neutral content = green
r = analyze("New blog post on brand governance. No products, no links.")
ok &= check("neutral -> green", r["overall_severity"]=="green")

print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
