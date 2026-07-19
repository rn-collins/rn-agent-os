-- Metabase saved-query specs for rn-agent-os (Postgres).
-- These run against db/schema.sql. The offline demo (services/pipeline/persist_and_report.py)
-- runs the same shape against SQLite to prove them.

-- 1) Risk Register (open, high-severity first)
SELECT severity, risk_type, creator, platform, explanation, review_status, url
FROM risk_findings
WHERE review_status IN ('needs_review','queued','new')
ORDER BY (severity = 'red') DESC, (severity = 'yellow') DESC;

-- 2) Risk by severity (KPI cards)
SELECT severity, COUNT(*) AS n
FROM risk_findings
GROUP BY severity
ORDER BY (severity='red') DESC, (severity='yellow') DESC;

-- 3) Risk by type (bar)
SELECT risk_type, COUNT(*) AS n
FROM risk_findings
GROUP BY risk_type
ORDER BY n DESC;

-- 4) Creators by open red flags (worst offenders)
SELECT creator, COUNT(*) FILTER (WHERE severity='red') AS reds,
       COUNT(*) FILTER (WHERE severity='yellow') AS yellows
FROM risk_findings
GROUP BY creator
ORDER BY reds DESC, yellows DESC;

-- 5) Human review queue depth
SELECT COUNT(*) AS awaiting_review
FROM risk_findings
WHERE review_status = 'needs_review';

-- 6) Client audit pipeline
SELECT creator, brand, recommendation, reviewer_status, drafted_on
FROM client_audits
ORDER BY drafted_on DESC;

-- 7) Agent run health
SELECT agent_name, status, started_at, ended_at, human_review_required
FROM agent_runs
ORDER BY started_at DESC;
