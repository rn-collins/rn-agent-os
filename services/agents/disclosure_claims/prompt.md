# Disclosure + Claims-Risk agent — contract

**Job.** Review one public social post. Detect sponsorship/affiliate/material-connection and
whether disclosure is present + clear. Extract express/implied claims with category + risk.
Return strict JSON. Not legal advice; surface issues for human review.

**Engine.** Rule-based and offline by default (`agent.py`), so it runs with zero API keys.
Set `USE_LLM=1` (with a reachable Ollama at `OLLAMA_HOST`) to let a local model add nuance —
it may only ADD flags, never remove a rule-based one.

**Output keys.** sponsorship (`paid|affiliate|gifted|none|unclear`), disclosure_present (bool),
disclosure_clarity (`clear|vague|missing`), claims (`[{text,type,category,risk}]`),
risk_flags (`[{severity,kind,detail}]`, severity `red|yellow|green`), overall_severity,
evidence_grade (`strong|moderate|weak`), confidence (`high|moderate|exploratory`),
review_status, recommended_action, disclaimer.

**Severity rules.** Material connection + missing disclosure → red. Material connection +
vague/late disclosure → yellow. High-risk claim (cure/efficacy/FDA/weight-loss/guaranteed) → red.
Medium claim (detox/immunity/anti-aging/miracle) → yellow. Health testimonial → yellow.

**Run:** `python agent.py` (uses `sample_input.json`) or `python agent.py "post text..."`.
**Test:** `python tests.py`.
