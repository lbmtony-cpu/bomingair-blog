#!/usr/bin/env python3
"""
Re-QC the existing stock pool with the strict rule (must be a REAL photo of
physical HVAC equipment/worksite — no screenshots, documents, spec sheets,
model-number lists, data-plate close-ups, faces). Remove bad ones, reassign any
post that used a removed image, re-render.
"""
import os, re, sys, io, json, base64, time, random, pathlib
import requests
from PIL import Image

ROOT = pathlib.Path(__file__).parent
SITE = ROOT / "site"
POOL_DB = ROOT / "stock_pool.json"
XAI_KEY = (os.environ.get("XAI_API_KEY") or "").strip()
sys.path.insert(0, str(ROOT))
import render


def check(imgpath):
    fp = SITE / imgpath
    if not fp.exists():
        return False
    im = Image.open(fp).convert("RGB"); im.thumbnail((900, 900))
    b = io.BytesIO(); im.save(b, "JPEG", quality=82)
    b64 = base64.b64encode(b.getvalue()).decode()
    for a in range(5):
        r = requests.post("https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {XAI_KEY}"},
            json={"model": "grok-4.3", "temperature": 0.1, "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": 'Strict JSON {"ok":true/false}. ok=true ONLY if this is an '
                 'actual PHOTOGRAPH of physical HVAC equipment or a real installation/worksite, with '
                 'NO privacy issue. ok=false for any screenshot, screen capture, document, spec sheet, '
                 'brochure, invoice, paper, diagram, text/model-number list, a close-up of a data '
                 'plate with readable model/serial, or any face/person/house number/license plate.'}]}]},
            timeout=120)
        if r.status_code == 200:
            t = r.json()["choices"][0]["message"]["content"]
            try:
                return bool(json.loads(re.search(r"\{.*\}", t, re.DOTALL).group(0)).get("ok"))
            except Exception:
                return False
        if r.status_code in (429, 500, 502, 503):
            time.sleep(8 * (a + 1)); continue
        return False
    return False


def main():
    pool = json.loads(POOL_DB.read_text(encoding="utf-8"))
    good, bad = [], []
    for x in pool:
        if check(x["img"]):
            good.append(x)
        else:
            bad.append(x["img"])
            try:
                (SITE / x["img"]).unlink()
            except Exception:
                pass
            print("[drop]", x["img"])
    POOL_DB.write_text(json.dumps(good, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"pool: kept {len(good)}, dropped {len(bad)}")

    if not good:
        print("ERROR: pool empty after clean"); return
    badset = set(bad)
    posts = json.loads((ROOT / "posts.json").read_text(encoding="utf-8"))
    reassigned = 0
    for p in posts:
        ph = p.get("photos") or []
        if any(i in badset for i in ph):
            # case studies have their own real photos; only stock-based (guide) posts
            # reference stock/. Replace removed stock imgs with a fresh good one.
            newph = [i for i in ph if i not in badset]
            if not newph:
                pick = random.choice(good)
                newph = [pick["img"]]
                p["hero_alt"] = pick.get("alt", "")
            p["photos"] = newph
            reassigned += 1
    (ROOT / "posts.json").write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"reassigned {reassigned} posts off dropped images")

    for p in posts:
        render.write_article(SITE, p, posts)
    render.write_index(SITE, posts); render.write_embed(SITE, posts)
    render.write_sitemap(SITE, posts); render.write_static(SITE)
    print("rerendered")


if __name__ == "__main__":
    main()
