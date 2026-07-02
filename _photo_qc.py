#!/usr/bin/env python3
"""
Vision QC for migrated case studies: does each post's hero photo actually match
its title? Mismatches get REWRITTEN honestly from (photo content + original title).

Phase 1: Grok vision describes each hero photo + verdict -> _qc_report.json
Phase 2: rewrite mismatched posts (no invented installs), fix title/slug/body
Phase 3: rerender everything (clears site/posts first to drop stale slugs)
"""
import os, re, sys, io, json, base64, time, datetime, pathlib
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import render

ROOT = pathlib.Path(__file__).parent
SITE = ROOT / "site"
POSTS_DB = ROOT / "posts.json"
REPORT = ROOT / "_qc_report.json"
XAI_KEY = (os.environ.get("XAI_API_KEY") or "").strip()
MODEL = (os.environ.get("GROK_MODEL") or "grok-4.3").strip()


def grok(messages, retries=6):
    for a in range(retries):
        r = requests.post("https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "temperature": 0.3, "messages": messages}, timeout=180)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        if r.status_code in (429, 500, 502, 503):
            w = min(60, 8 * (a + 1)); print(f"    [retry] {r.status_code}, {w}s"); time.sleep(w); continue
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    raise RuntimeError("retries exhausted")


def jparse(txt):
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.MULTILINE).strip()
    return json.loads(re.search(r"\{.*\}", txt, re.DOTALL).group(0))


def qc_one(post):
    img = SITE / post["photos"][0]
    b64 = base64.b64encode(img.read_bytes()).decode()
    txt = grok([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        {"type": "text", "text":
         f'This photo is the hero image of an HVAC blog post titled: "{post["title"]}".\n'
         'Return ONLY strict JSON: {"shows": "<=15 word literal description of what the photo shows", '
         '"is_hvac_equipment": true/false, "matches_title": true/false}'}]}])
    return jparse(txt)


REWRITE = """You write for {biz}, a licensed HVAC contractor in {base} serving {region}.

A blog post needs fixing. The ORIGINAL internal note title was: "{orig}"
Its real photo shows: "{shows}"

Write an honest post consistent with BOTH the original note and the photo. Rules:
- Do NOT claim a specific equipment installation happened unless the photo/original title shows it.
- If the source is a tip/advice note, write it as a practical advice article for SoCal homeowners.
- No invented customers, cities, prices, or stats. 380-500 words, 3-4 <h2> sections. Soft CTA to {biz} ({phone}).

Return ONLY strict JSON:
{{"title":"<=68 chars honest title","slug":"kebab-case","meta_description":"<=155 chars",
"hero_alt":"alt text matching the photo","body_html":"<h2>/<h3>/<p>/<ul>/<li> only",
"faq":[{{"q":"...","a":"..."}},...2-3],"social_fb":"...","social_yelp":"..."}}"""


def main():
    posts = json.loads(POSTS_DB.read_text(encoding="utf-8"))
    cases = [p for p in posts if p.get("kind") == "case" and p.get("photos")]
    report = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}

    print(f"=== QC {len(cases)} case heroes ===")
    for p in cases:
        if p["slug"] in report:
            continue
        try:
            v = qc_one(p)
            report[p["slug"]] = v
            REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
            flag = "" if v.get("matches_title") else "  <-- MISMATCH"
            print(f"[qc] {p['slug'][:52]:54s} {v.get('shows','?')[:40]}{flag}")
        except Exception as e:
            print(f"[ERR qc] {p['slug']}: {e}", file=sys.stderr)

    bad = [s for s, v in report.items() if not v.get("matches_title")]
    print(f"\n=== {len(bad)} mismatches -> rewriting ===")
    slugs = {p["slug"] for p in posts}
    for p in posts:
        if p["slug"] not in bad or p.get("kind") != "case":
            continue
        v = report[p["slug"]]
        try:
            art = jparse(grok([
                {"role": "system", "content": "Expert HVAC writer. Strict JSON only."},
                {"role": "user", "content": REWRITE.format(
                    biz=C.BIZ_NAME, base=C.CITY_BASE, region=C.REGION,
                    orig=p["topic"], shows=v.get("shows", ""), phone=C.PHONE)}]))
            old = p["slug"]
            ns = re.sub(r"[^a-z0-9]+", "-", (art.get("slug") or art["title"]).lower()).strip("-")[:75]
            while ns in slugs:
                ns += "-x"
            slugs.discard(old); slugs.add(ns)
            p.update(slug=ns, title=art["title"].strip(), meta=art["meta_description"].strip(),
                     hero_alt=art.get("hero_alt", "").strip(), body_html=art["body_html"].strip(),
                     faq=art.get("faq", []), social_fb=art.get("social_fb", ""),
                     social_yelp=art.get("social_yelp", ""))
            print(f"[fix] {old} -> {ns}: {p['title']}")
            POSTS_DB.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[ERR fix] {p['slug']}: {e}", file=sys.stderr)

    # phase 3: clean rerender (drop stale slug html files)
    pd = SITE / "posts"
    if pd.exists():
        for f in pd.glob("*.html"):
            f.unlink()
    for p in posts:
        render.write_article(SITE, p, posts)
    render.write_index(SITE, posts)
    render.write_embed(SITE, posts)
    render.write_sitemap(SITE, posts)
    render.write_static(SITE)
    print(f"[done] QC {len(report)} | fixed {len(bad)}")


if __name__ == "__main__":
    main()
