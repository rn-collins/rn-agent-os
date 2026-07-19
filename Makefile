# rn-agent-os — turnkey commands.
.PHONY: up down logs demo pipeline dashboard psql

up:            ## bring up the whole stack (db, ollama, n8n, metabase, api)
	docker compose up -d --build
	@echo "waiting for services..." && sleep 20
	@echo "API:      http://localhost:8000/health"
	@echo "Metabase: http://localhost:3000  (finish the 1-time setup, then: make dashboard)"
	@echo "n8n:      http://localhost:5678"

down:
	docker compose down

logs:
	docker compose logs -f api

eval:          ## QA quality gate — accuracy + invariants; nonzero exit blocks delivery
	python3 services/agents/qa/agent.py

demo:          ## offline demo: pipeline -> sqlite -> dashboard queries (no docker)
	python3 services/pipeline/persist_and_report.py

pipeline:      ## run the full pipeline against the running API
	curl -s localhost:8000/pipeline/run -H 'content-type: application/json' -d '{}' | python3 -m json.tool

dashboard:     ## auto-build the Metabase DB connection + cards + dashboard
	python3 dashboards/provision_metabase.py

psql:
	docker compose exec db psql -U agentos -d agentos
