"""Offline test: prove the Apify normalizer maps real-shaped payloads correctly. No network."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from services.agents.sector_watch.agent import normalize_apify_items

# minimal payloads shaped like the real Apify actors
IG = [{"caption": "cured my gut, use code HEAL20, link in bio", "url": "https://ig/p/1",
       "timestamp": "2026-07-08", "ownerUsername": "wellness_creator_a",
       "likesCount": 4200, "commentsCount": 310}]
TT = [{"text": "#ad paid partnership with Acme", "webVideoUrl": "https://tt/v/2",
       "createTimeISO": "2026-07-09", "authorMeta": {"name": "founder_b"},
       "diggCount": 1200, "commentCount": 44}]

ig = normalize_apify_items(IG, "instagram")[0]
tt = normalize_apify_items(TT, "tiktok")[0]

ok = True
def chk(n, c):
    global ok; ok &= c; print(("PASS" if c else "FAIL"), "-", n)

chk("ig creator", ig["creator"] == "wellness_creator_a")
chk("ig text",    "cured" in ig["text"])
chk("ig url",     ig["url"] == "https://ig/p/1")
chk("ig likes",   ig["metrics"]["likes"] == 4200)
chk("tt creator (nested)", tt["creator"] == "founder_b")
chk("tt url",     tt["url"] == "https://tt/v/2")
chk("tt platform tag", tt["platform"] == "tiktok")

print("\nALL PASS" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
