-- rn-agent-os — evidence data model (Postgres + pgvector)
-- Public / permissioned data only. Every finding carries provenance, an evidence grade,
-- a confidence level, and a human review status.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  url TEXT,
  source_type TEXT,          -- regulator|platform_policy|academic|industry_report|law_firm_memo|trade_press|creator_example|brand_example
  authority_level TEXT,      -- primary|high|medium|low
  date_published DATE,
  date_ingested TIMESTAMPTZ DEFAULT now(),
  tier TEXT,                 -- Tier 1|Tier 2|Tier 3
  topic_tags TEXT[],
  summary TEXT,
  why_it_matters TEXT,
  raw_text_location TEXT,
  embedding VECTOR(768),
  status TEXT DEFAULT 'new'
);
CREATE INDEX ON sources (source_type);
CREATE INDEX ON sources (tier);
CREATE INDEX ON sources USING gin (topic_tags);

CREATE TABLE creators (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  sector TEXT,
  platforms JSONB,
  audience_notes TEXT,
  monetization_notes TEXT,
  trust_style TEXT,
  disclosure_style TEXT,
  risk_summary TEXT,
  last_reviewed TIMESTAMPTZ
);
CREATE INDEX ON creators (sector);

CREATE TABLE brands (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  sector TEXT,
  website TEXT,
  brief JSONB,               -- fit criteria, banned claims, verticals
  notes TEXT,
  risk_summary TEXT
);

CREATE TABLE content_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  url TEXT,
  platform TEXT,
  creator_id UUID REFERENCES creators(id),
  brand_id UUID REFERENCES brands(id),
  content_type TEXT,
  date_published DATE,
  captured_at TIMESTAMPTZ DEFAULT now(),
  source TEXT,               -- apify|brightdata|playwright|phyllo|brandwatch|manual
  provenance JSONB,
  transcript_location TEXT,
  text TEXT,
  summary TEXT,
  claims_json JSONB,
  disclosures_json JSONB,
  affiliate_json JSONB,
  risk_notes TEXT,
  embedding VECTOR(768)
);
CREATE INDEX ON content_items (platform);
CREATE INDEX ON content_items (creator_id);

CREATE TABLE risk_findings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_item_id UUID REFERENCES content_items(id) ON DELETE CASCADE,
  creator_id UUID REFERENCES creators(id),
  brand_id UUID REFERENCES brands(id),
  risk_type TEXT,            -- disclosure|affiliate|claim|testimonial|ai_content|platform
  severity TEXT,             -- red|yellow|green  (high|medium|low)
  evidence_grade TEXT,       -- strong|moderate|weak
  confidence TEXT,           -- high|moderate|exploratory
  explanation TEXT,
  evidence_snippets JSONB,
  recommended_action TEXT,
  review_status TEXT DEFAULT 'needs_review'  -- new|queued|agent_drafted|needs_review|approved|rejected|needs_revision|archived|client_ready
);
CREATE INDEX ON risk_findings (risk_type);
CREATE INDEX ON risk_findings (severity);
CREATE INDEX ON risk_findings (review_status);

CREATE TABLE templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT, template_type TEXT, current_version TEXT,
  last_updated TIMESTAMPTZ DEFAULT now(), affected_services TEXT[], notes TEXT
);

CREATE TABLE clients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT, sector TEXT, website TEXT, engagement_type TEXT, status TEXT
);
CREATE INDEX ON clients (status);

CREATE TABLE client_audits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID REFERENCES clients(id),
  stage TEXT,
  draft_report_location TEXT, evidence_map_location TEXT,
  risk_map_location TEXT, roadmap_location TEXT,
  reviewer_status TEXT DEFAULT 'draft'
);

CREATE TABLE agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name TEXT, run_type TEXT,
  started_at TIMESTAMPTZ DEFAULT now(), ended_at TIMESTAMPTZ,
  status TEXT, inputs_ref TEXT, outputs_ref TEXT,
  model_used TEXT, human_review_required BOOLEAN DEFAULT false
);
CREATE INDEX ON agent_runs (agent_name);

CREATE VIEW v_risk_register AS
SELECT rf.id, rf.risk_type, rf.severity, rf.confidence, rf.explanation, rf.review_status,
       ci.platform, ci.url, rf.recommended_action
FROM risk_findings rf
LEFT JOIN content_items ci ON ci.id = rf.content_item_id
WHERE rf.review_status IN ('needs_review','queued','new')
ORDER BY (rf.severity='red') DESC, (rf.severity='yellow') DESC;
