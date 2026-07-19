"""Auto-build the Metabase dashboard for rn-agent-os.

After `docker compose up` and finishing Metabase's one-time setup wizard, run:
    MB_USER=you@example.com MB_PASS=yourpass python3 dashboards/provision_metabase.py

It logs in, ensures a Postgres connection to the agentos DB, creates one card per query in
dashboards/queries.sql, and assembles a "Creator Risk" dashboard (KPI cards + risk register table).

Offline self-check (no Metabase needed):  python3 dashboards/provision_metabase.py --dry-run
"""
from __future__ import annotations
import os, re, sys, json

HERE = os.path.dirname(__file__)
QUERIES = os.path.join(HERE, "queries.sql")

# card display per query title keyword
DISPLAY = {
    "risk register": "table", "risk by severity": "bar", "risk by type": "bar",
    "creators by open red": "table", "human review queue": "scalar",
    "client audit pipeline": "table", "agent run health": "table",
}


def parse_queries(path=QUERIES):
    """Return [(title, sql), ...] from '-- N) Title' delimited blocks."""
    text = open(path).read()
    blocks = re.split(r"(?m)^--\s*\d+\)\s*", text)
    out = []
    for b in blocks[1:]:
        lines = b.strip().splitlines()
        title = lines[0].strip()
        sql = "\n".join(l for l in lines[1:] if not l.strip().startswith("--")).strip()
        if sql:
            out.append((title, sql))
    return out


def _display_for(title):
    t = title.lower()
    for k, v in DISPLAY.items():
        if k in t:
            return v
    return "table"


def provision():
    import httpx
    host = os.getenv("MB_HOST", "http://localhost:3000").rstrip("/")
    user, pw = os.getenv("MB_USER"), os.getenv("MB_PASS")
    if not (user and pw):
        sys.exit("Set MB_USER and MB_PASS (the Metabase admin you created in the setup wizard).")

    c = httpx.Client(base_url=host, timeout=30)
    token = c.post("/api/session", json={"username": user, "password": pw}).json()["id"]
    h = {"X-Metabase-Session": token}

    # ensure DB connection
    dbs = c.get("/api/database", headers=h).json().get("data", [])
    db = next((d for d in dbs if d.get("name") == "agentos"), None)
    if not db:
        db = c.post("/api/database", headers=h, json={
            "name": "agentos", "engine": "postgres",
            "details": {"host": os.getenv("PG_HOST", "db"), "port": 5432,
                        "dbname": os.getenv("POSTGRES_DB", "agentos"),
                        "user": os.getenv("POSTGRES_USER", "agentos"),
                        "password": os.getenv("POSTGRES_PASSWORD", "agentos")}}).json()
    db_id = db["id"]

    dash = c.post("/api/dashboard", headers=h,
                  json={"name": "Creator Risk — rn-agent-os"}).json()
    dash_id = dash["id"]

    for title, sql in parse_queries():
        card = c.post("/api/card", headers=h, json={
            "name": title, "display": _display_for(title),
            "dataset_query": {"type": "native", "native": {"query": sql}, "database": db_id},
            "visualization_settings": {}}).json()
        c.post(f"/api/dashboard/{dash_id}/cards", headers=h,
               json={"cardId": card["id"], "row": 0, "col": 0, "sizeX": 6, "sizeY": 4})
        print("card:", title)
    print(f"\nDashboard ready: {host}/dashboard/{dash_id}")


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        for title, sql in parse_queries():
            print(f"[{_display_for(title):6}] {title}")
            print("   " + sql.replace("\n", "\n   "))
            print()
    else:
        provision()
