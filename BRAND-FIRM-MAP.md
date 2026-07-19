# Agentic Brand-Management Firm — Component Map

What genuinely belongs **inside** the brand firm, what already exists in Aloha AI, and what
still has to be built. Everything not on the "inside" list is an Aloha **sibling** — same
umbrella and values, not part of this firm.

Legend: ✅ **EXISTS** (shipped in Aloha) · 🟡 **PARTIAL** (a version exists, needs adapting) · 🔴 **TO BUILD**

---

## 0. The shared engine — `rn-agent-os`

One self-hosted stack. Every service below is an output of it. A human (you) signs off.

| Piece | Status | Notes |
|---|---|---|
| Docker Compose (Postgres+pgvector, n8n, Ollama, Redis, MinIO, API, Metabase) | 🔴 TO BUILD | Phase 0 scaffold in this repo |
| Evidence database (9 tables) | 🟡 PARTIAL | drafted in `creator-lurker/db/schema.sql`; formalizing here |
| FastAPI service (agent endpoints) | 🔴 TO BUILD | skeleton in Phase 0 |
| LangGraph orchestrator | 🔴 TO BUILD | Phase 2 |
| Model router (local-first, optional frontier fallback) | 🔴 TO BUILD | Phase 2 |
| Human review / sign-off states | 🔴 TO BUILD | states defined in spec; UI later |

---

## 1. The agents (internal workers — NOT products)

These feed the shared evidence DB. They are staff, not things you sell.

| Agent | Status | What already exists to reuse |
|---|---|---|
| Research Scout | 🔴 TO BUILD | — |
| Sector Watch | 🟡 PARTIAL | Aloha `monitors/*` pattern (cannabis, psychedelic, market-intel) is the same shape |
| Video Evidence (Whisper + extraction) | 🔴 TO BUILD | — |
| **Disclosure & Affiliate Risk** | 🟡 PARTIAL | overlaps Aloha **Claims Checker**; building it first in this repo |
| **Claims & Evidence Risk** | 🟡 PARTIAL | Aloha **Claims Checker** + **Citation Verifier** do adjacent work |
| Trust / Brand-Fit | 🟡 PARTIAL | Aloha **Brand-Perception Intelligence** is the diagnostic version |
| Measurement & Learning | 🔴 TO BUILD | — |
| Template Update | 🔴 TO BUILD | — |
| Client Audit Drafting | 🔴 TO BUILD | assembles the flagship deliverable |
| QA / Regression | 🔴 TO BUILD | — |

---

## 2. The products (what clients actually buy)

Each is a productized output of specific agents. The **retainer is the engine left running.**

| Product | Status | Powered by |
|---|---|---|
| **Creator + Brand Evidence Audit** (flagship) | 🟡 PARTIAL | live diagnostic page shipped (`monitors/agentic-brand-management`); the *agent-run* audit is 🔴 |
| Partnership Strategy Sprint | 🔴 TO BUILD | Trust-Fit + Sector Watch + Measurement |
| Governance + Brand Systems | 🔴 TO BUILD | Governance + Template Update + Disclosure/Claims |
| Thought-Leader / Expert System | 🔴 TO BUILD | Research Scout + Trust-Fit + content |
| Advisory Retainer (recurring) | 🔴 TO BUILD | whole OS running continuously |

---

## 3. Existing Aloha tools that plug in as COMPONENTS

These are real, shipped, and genuinely do a job the firm needs.

| Aloha tool | Status | Role inside the firm |
|---|---|---|
| Brand-Perception Intelligence | ✅ EXISTS | Trust-Fit layer (diagnostic) |
| Claims Checker | ✅ EXISTS | tool the Claims-Risk agent calls |
| Citation Verifier | ✅ EXISTS | substantiation checks for Claims-Risk |
| Content Suppression Audit (EDSA) | ✅ EXISTS | Measurement / distribution layer |
| Creator Content System | ✅ EXISTS | production arm (post-strategy) |
| Governance-Readiness / AI-Readiness Scorecard | ✅ EXISTS | Governance layer intake |
| Trust-Safe Twins | ✅ EXISTS | AI-creator governance case |
| Agentic Brand Management monitor | ✅ EXISTS | the flagship front door (just built) |

---

## 4. Aloha SIBLINGS — NOT part of the brand firm

Same umbrella, same "evidence + human sign-off" values, shared design system — but **separate
service lines.** Do not wire these into the brand firm.

- Biopharma Regulatory Intelligence
- Cannabis Rescheduling Monitor
- Psychedelic Reg Radar
- Luxury Brand / IP Protection
- Biophilic / Neuro-Architecture Intelligence
- Arts & Cultural Intelligence
- Private-AI & Data-Retention Risk
- Legal AI Workflow / Citation tools **as a legal-services line** (though it shares the same OS primitives and is the *future* self-hosted law-firm extension)

---

## 5. Honest build order

1. **`rn-agent-os` Phase 0** (this repo): Docker Compose + 9-table schema + API skeleton.
2. **First agent: Disclosure + Claims-Risk** — runnable now, offline rule-based + optional local LLM.
3. Wire in **Claims Checker / Citation Verifier / Brand-Perception** as the tools existing agents call.
4. Add Sector Watch + Video Evidence (collection).
5. Client Audit Drafting agent → assembles the flagship audit end-to-end.
6. Retainer = leave it running.

The rest of Aloha stays as-is.
