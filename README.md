# rn-agent-os

The self-hosted engine behind Aloha AI's **Agentic Brand Management** service line. A coordinated
system of AI agents that monitors public/permissioned content, grades evidence, checks disclosure
and claims risk, and assembles brand-management deliverables — with a human sign-off gate.

> **Boundary.** Public / permissioned data only. Not a private-account bypass tool. Surfaces
> disclosure/claims risk for human and counsel review — **not legal advice.**

See **`BRAND-FIRM-MAP.md`** for what belongs inside the firm vs. Aloha siblings.

## Status (Phase 0 — shipped in this repo)

- ✅ `db/schema.sql` — 9-table evidence model (Postgres + pgvector)
- ✅ `docker-compose.yml` — Postgres/pgvector, n8n, Ollama, Redis, MinIO, Metabase, API
- ✅ `services/api` — FastAPI skeleton (`/health`, `/agents/disclosure-claims/run`, stubs)
- ✅ **`services/agents/disclosure_claims`** — first agent, **runnable offline today**

## Live API (free tier, no database)

The Disclosure + Claims agent needs no database, no model key and no Ollama, so that
much runs as a hosted endpoint:

- `GET /health`
- `POST /agents/disclosure-claims/run` — `{"text": "...", "platform": "...", "creator": "..."}`

**https://agentos-blue-rho.vercel.app**

What is *not* deployed there: Postgres/pgvector, Redis, MinIO, Ollama, n8n and Metabase.
Anything needing evidence storage, retrieval, the local model, workflows or dashboards
still requires the self-hosted stack in `docker-compose.yml`. The hosted endpoint is the
part that can run honestly without them, not a hosted version of the engine.

## Try the first agent right now (no keys, no Docker)

```bash
python3 services/agents/disclosure_claims/tests.py      # gold-set tests
python3 services/agents/disclosure_claims/agent.py      # runs on sample_input.json
python3 services/agents/disclosure_claims/agent.py "cured my acne, use code SAVE10, link in bio"
```

It returns graded JSON: sponsorship type, disclosure presence/clarity, claims (category+risk),
red/yellow/green risk flags, evidence grade, confidence, and a review status. Rule-based floor;
set `USE_LLM=1` with a local Ollama to add nuance (never lowers a rule flag).

## Full local stack

```bash
cp .env.example .env
docker compose up -d          # db(+pgvector), ollama, n8n, redis, minio, metabase, api
# schema auto-loads; API at http://localhost:8000/health
curl -s localhost:8000/agents/disclosure-claims/run \
  -H 'content-type: application/json' \
  -d '{"text":"this cured my gut, use code HEAL20, link in bio","platform":"ig"}'
```

## Orchestrator (Phase 2 — supervised graph + model router)

Replaces the hardcoded pipeline order with a supervised graph:
`collect → grade → trust_fit → [HUMAN GATE] → draft → persist`, with per-node **retries** and a
**human-in-the-loop pause**: if any RED flag exists, the run stops (`awaiting_human`) and only
resumes on approval.

```bash
python3 services/orchestrator/run.py            # run → pause at gate → auto-approve → resume → persist
python3 services/orchestrator/run.py --reject   # show the reject path
```

- **Model router** (`model_router.py`): local Ollama first; optional Anthropic/OpenAI fallback for
  high-stakes narrative; deterministic **stub** when nothing is configured (rule-based agents still
  run, so it never hard-fails offline). Set `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` + `ALLOW_FRONTIER=1`.
- **Two backends, same graph**: `pip install langgraph` and the native `build_langgraph()` StateGraph
  (with `interrupt_before=['draft']` + MemorySaver checkpointer) is used automatically; otherwise the
  dependency-free `FallbackRunner` runs the identical nodes/edges + HITL.

## Go live (on your machine — needs Docker + your keys)

```bash
make up                 # docker compose up: db(+pgvector), ollama, n8n, metabase, api
# 1) finish Metabase's one-time setup wizard at http://localhost:3000
make dashboard          # auto-builds the "Creator Risk" dashboard (7 cards) via Metabase API
#    (MB_USER / MB_PASS = the admin you just created)
make pipeline           # POST /pipeline/run — grades + persists into Postgres; dashboard lights up
```

**Weekly automation (n8n):** import `workflows/weekly_pipeline.json` at http://localhost:5678.
It crons Monday 07:00 → `POST api:8000/pipeline/run` → alerts you if any RED flags. Swap the
final node for your Email/Slack creds.

**Real collection (Apify):** set `APIFY_TOKEN` in `.env`, set `"source": "apify"` in
`services/agents/sector_watch/watchlist.json`, and put your licensed actor ids in
`services/agents/sector_watch/actors.json`. The normalizer maps IG/TikTok/YouTube payloads to the
evidence shape (offline-tested in `test_apify_normalizer.py`). Public/permissioned only.

## Build order (from the spec)

1. **Phase 0** ✅ — Compose + schema + API + Disclosure/Claims agent (done).
2. Wire existing Aloha tools as components (Claims Checker, Citation Verifier, Brand-Perception).
3. Collection agents (Sector Watch, Video Evidence) → populate the evidence DB.
4. Trust-Fit + Measurement + Governance agents.
5. Client Audit Drafting agent → assembles the flagship audit end-to-end.
6. LangGraph orchestrator + model router + review UI.
7. Retainer = leave the OS running.

## Human review is mandatory for

legal/compliance interpretation · claims review · client-facing recommendations · public
compliance content · anything flagged **red**.
