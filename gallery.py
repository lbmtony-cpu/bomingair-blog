#!/usr/bin/env python3
"""
Build the "Our Work" portfolio wall from the repetitive GoDaddy install posts
(the ones NOT worth individual articles). One photo + cleaned caption each.

No LLM needed. Resumable via gallery.json.
"""
import os, re, sys, io, json, html, pathlib, urllib.parse
import requests
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

ROOT = pathlib.Path(__file__).parent
SITE = ROOT / "site"
GAL_DB = ROOT / "gallery.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def clean_title(t):
    t = re.sub(r"\s*(lol|LOL)\.?\s*$", "", t).strip()
    t = re.sub(r"[一-鿿，。！？]+", "", t).strip(" -,.")   # drop Chinese dup text
    return t[:80]


def scrape_first_image(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    h = r.text
    m = re.search(r'<meta property="og:image" content="([^"]+)"', h)
    img = m.group(1) if m else ""
    if "isteam/ip/" not in img:
        return None, None
    m2 = re.search(r'<meta property="og:title" content="([^"]+)"', h)
    title = m2.group(1).strip() if m2 else urllib.parse.unquote(
        url.rstrip("/").split("/f/")[-1]).replace("-", " ").title()
    return title, img


def main():
    all_urls = [u.strip() for u in (ROOT / "_gd_urls.txt").read_text().splitlines() if u.strip()]
    curated = {u.strip() for u in (ROOT / "_curated_urls.txt").read_text().splitlines() if u.strip()}
    posts = json.loads((ROOT / "posts.json").read_text(encoding="utf-8"))
    migrated = {p.get("source") for p in posts if p.get("source")}
    todo = [u for u in all_urls if u not in curated and u not in migrated]

    items = json.loads(GAL_DB.read_text(encoding="utf-8")) if GAL_DB.exists() else []
    done_urls = {i["source"] for i in items}
    outdir = SITE / "img" / "work"
    outdir.mkdir(parents=True, exist_ok=True)

    for u in todo:
        if u in done_urls:
            continue
        try:
            title, img = scrape_first_image(u)
            if not img:
                print(f"[skip no-img] {u}")
                continue
            raw = requests.get(img, headers={"User-Agent": UA}, timeout=40).content
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            im.thumbnail((640, 640))
            n = len(items) + 1
            fn = f"{n:03d}.jpg"
            im.save(outdir / fn, "JPEG", quality=78, optimize=True)
            items.append({"source": u, "title": clean_title(title), "img": f"img/work/{fn}"})
            done_urls.add(u)
            GAL_DB.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[{len(items)}] {clean_title(title)}")
        except Exception as e:
            print(f"[ERR] {u}: {e}", file=sys.stderr)

    render_page(items)
    print(f"[done] gallery items: {len(items)}")


def render_page(items):
    tiles = "".join(
        f'<figure class="wt"><img src="/{i["img"]}" alt="{html.escape(i["title"])}" loading="lazy">'
        f'<figcaption>{html.escape(i["title"])}</figcaption></figure>'
        for i in items)
    desc = (f"{len(items)}+ real AC & heating installations completed by {C.BIZ_NAME} "
            f"across {C.REGION}. Licensed, warrantied work.")
    doc = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Our Work — {len(items)}+ Real Installations | {C.BIZ_SHORT}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{C.BLOG_URL}/work.html">
<link rel="stylesheet" href="/style.css">
<style>
.wgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;margin:24px 0}}
.wt{{margin:0;background:#fff;border:1px solid #e6ebf2;border-radius:10px;overflow:hidden}}
.wt img{{width:100%;height:190px;object-fit:cover;display:block}}
.wt figcaption{{padding:10px 12px;font-size:13px;color:#3a4658;line-height:1.4}}
</style></head><body>
<header class="site"><div class="wrap">
<a class="logo" href="{C.MAIN_SITE}">{C.BIZ_SHORT}<span>Air Conditioning &amp; Heating</span></a>
<a class="callbtn" href="tel:{C.PHONE_TEL}">&#128222; {C.PHONE}</a>
</div></header>
<main><div class="wrap">
<nav class="crumb"><a href="/">Blog</a> &#8250; <span>Our Work</span></nav>
<h1>Our Work: {len(items)}+ Real Installations</h1>
<p style="color:#4a5a70;font-size:17px">Every photo below is a real job completed by our team across {C.REGION} —
central AC systems, heat pumps, mini-splits, roof package units and more. Licensed and warrantied.</p>
<div class="wgrid">{tiles}</div>
</div></main>
<footer class="site"><div class="wrap">
<p class="cta"><strong>Want yours done next?</strong> Call <a href="tel:{C.PHONE_TEL}">{C.PHONE}</a>
or email <a href="mailto:{C.EMAIL}">{C.EMAIL}</a>.</p>
<p class="mini"><a href="/">&#8592; Back to blog</a> · © {C.BIZ_NAME}</p>
</div></footer></body></html>"""
    (SITE / "work.html").write_text(doc, encoding="utf-8")


if __name__ == "__main__":
    main()
