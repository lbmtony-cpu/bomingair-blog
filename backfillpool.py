#!/usr/bin/env python3
"""Give every photo-less post a real HVAC hero from the stock pool, then render."""
import json, random, pathlib, sys
ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))
import render

posts = json.loads((ROOT / "posts.json").read_text(encoding="utf-8"))
pool = json.loads((ROOT / "stock_pool.json").read_text(encoding="utf-8"))
random.shuffle(pool)
i = 0
n = 0
for p in posts:
    if p.get("photos"):
        continue
    pick = pool[i % len(pool)]; i += 1
    p["photos"] = [pick["img"]]
    p["hero_alt"] = p.get("hero_alt") or pick.get("alt", "")
    n += 1
(ROOT / "posts.json").write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
site = ROOT / "site"
for p in posts:
    render.write_article(site, p, posts)
render.write_index(site, posts); render.write_embed(site, posts)
render.write_sitemap(site, posts); render.write_static(site)
print(f"backfilled {n} photo-less posts with pool heroes")
