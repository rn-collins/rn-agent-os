"""Sector Watch collection agent.

Reads a watchlist and returns NORMALIZED content_items for the evidence DB. Public/permissioned
only. Offline by default: source="fixtures" reads local sample posts so the whole pipeline runs
with zero keys. source="apify" is wired but requires APIFY_TOKEN + actor ids (left as TODO).

Normalized shape (one dict per post):
  {platform, creator, url, posted_at, captured_at, source, provenance, text, metrics, sector}
"""
from __future__ import annotations
import os, json
from datetime import datetime, timezone

HERE = os.path.dirname(__file__)


def _sector_for(handle, watch):
    for c in watch.get("creators", []):
        if c["handle"] == handle:
            return c.get("sector")
    return None


def collect(watchlist_path: str | None = None) -> list[dict]:
    watch = json.load(open(watchlist_path or os.path.join(HERE, "watchlist.json")))
    source = watch.get("source", "fixtures")
    if source == "fixtures":
        raw = json.load(open(os.path.join(HERE, "fixtures", "posts.json")))
    elif source == "apify":  # pragma: no cover
        raw = _collect_apify(watch)
    else:
        raise ValueError(f"unknown source: {source}")

    now = datetime.now(timezone.utc).isoformat()
    items = []
    for r in raw:
        items.append({
            "platform": r.get("platform", "unknown"),
            "creator": r.get("creator", "unknown"),
            "url": r.get("url", ""),
            "posted_at": r.get("posted_at"),
            "captured_at": now,
            "source": source,
            "provenance": {"source": source, "raw_url": r.get("url", "")},
            "text": r.get("text", ""),
            "metrics": r.get("metrics", {}),
            "sector": _sector_for(r.get("creator"), watch),
        })
    return items


def _get(d, dotted):
    cur = d
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def normalize_apify_items(items: list[dict], platform: str, cfg: dict | None = None) -> list[dict]:
    """Map a platform's raw Apify dataset items to the normalized post shape. Pure/offline-testable."""
    cfg = cfg or json.load(open(os.path.join(HERE, "actors.json")))
    fm = cfg["field_map"].get(platform, {})

    def pick(item, keys):
        for k in keys:
            v = _get(item, k)
            if v:
                return v
        return None

    out = []
    for it in items:
        out.append({
            "platform": platform,
            "creator": pick(it, fm.get("creator", [])) or "unknown",
            "url": pick(it, fm.get("url", [])) or "",
            "posted_at": pick(it, fm.get("posted_at", [])),
            "text": pick(it, fm.get("text", [])) or "",
            "metrics": {"likes": pick(it, fm.get("likes", [])),
                        "comments": pick(it, fm.get("comments", []))},
        })
    return out


def _collect_apify(watch):  # pragma: no cover - requires keys + network
    """Run licensed Apify actors per platform, then normalize. Public/permissioned only."""
    import httpx
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN not set; use source='fixtures' for offline runs.")
    cfg = json.load(open(os.path.join(HERE, "actors.json")))
    platforms = {c["platform"] for c in watch.get("creators", [])}
    handles_by_platform = {}
    for c in watch.get("creators", []):
        handles_by_platform.setdefault(c["platform"], []).append(c["handle"])

    raw = []
    with httpx.Client(timeout=120) as client:
        for platform in platforms:
            spec = cfg.get(platform)
            if not spec:
                continue
            payload = dict(spec["input"])
            payload["_handles"] = handles_by_platform.get(platform, [])  # actor-specific: adapt to actor input schema
            r = client.post(
                f"https://api.apify.com/v2/acts/{spec['actor']}/run-sync-get-dataset-items",
                params={"token": token}, json=payload)
            r.raise_for_status()
            raw.extend(normalize_apify_items(r.json(), platform, cfg))
    return raw


if __name__ == "__main__":
    for it in collect():
        print(json.dumps(it, ensure_ascii=False))
