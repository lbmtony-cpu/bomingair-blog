#!/usr/bin/env python3
"""
Migrate BOMING Air's existing GoDaddy case studies (/f/...) into the auto blog.

For each source URL:
  1. fetch the GoDaddy page, pull the title + real uploaded photos
  2. download + compress the photos into site/img/<slug>/
  3. Grok rewrites it into a unique, honest, SEO case-study article
  4. save to posts.json + render

Usage:
  python migrate.py --pilot                 # 5 hand-picked posts (quality check)
  python migrate.py <start> <count>         # range from _gd_urls.txt
  python migrate.py <url> [<url> ...]       # specific URLs
"""
import os, re, sys, io, json, html, time, datetime, pathlib, urllib.parse
import requests
from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import render

ROOT = pathlib.Path(__file__).parent
SITE = ROOT / "site"
POSTS_DB = ROOT / "posts.json"
URLS_FILE = ROOT / "_gd_urls.txt"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
XAI_KEY = (os.environ.get("XAI_API_KEY") or "").strip()
MODEL = (os.environ.get("GROK_MODEL") or "grok-4.3").strip()

PILOT = [
    "https://bomingair.com/f/installation-of-25-ton-goodman-heat-pump-system",
    "https://bomingair.com/f/installation-of-5-ton-bosch-heat-pump-system",
    "https://bomingair.com/f/15-ton-daikin-mini-split-system-the-best-brand-in-the-world",
    "https://bomingair.com/f/installation-of-3-ton-goodman-ac-system-new-refrigerant-r32",
    "https://bomingair.com/f/install-6-mini-splits-in-two-days",
]


def load_posts():
    return json.loads(POSTS_DB.read_text(encoding="utf-8")) if POSTS_DB.exists() else []


def save_posts(p):
    POSTS_DB.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:75] or "post"


def scrape(url):
    """Return (title, image_urls[]) from a GoDaddy /f/ page."""
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    h = r.text
    # title
    m = re.search(r'<meta property="og:title" content="([^"]+)"', h)
    title = (m.group(1).strip() if m else "").strip()
    if not title or title.lower() in ("boming air", ""):
        slug = url.rstrip("/").split("/f/")[-1]
        title = urllib.parse.unquote(slug).replace("-", " ").strip().title()
    # images: decode escaped slashes; get full isteam URLs + reconstruct the rest
    dec = h.replace("\\u002f", "/").replace("\\/", "/")
    full = re.findall(r'https://img1?\.wsimg\.com/isteam/ip/[a-f0-9\-]{36}/[^\s"\'\\)]+?\.(?:jpe?g|png)', dec, re.I)
    full = [u for u in full if "gfonts" not in u]
    # base = the asset folder from og:image (or first full url), then attach every IMG_* filename
    base = None
    if full:
        base = full[0].rsplit("/", 1)[0]
    fnames = re.findall(r'(IMG_\d+\.(?:jpe?g|png))', h, re.I)
    seen, imgs = set(), []
    def add(u):
        fn = u.rsplit("/", 1)[-1].lower()
        if fn not in seen:
            seen.add(fn); imgs.append(u)
    for u in full:
        add(u)
    if base:
        for fn in fnames:
            add(f"{base}/{fn}")
    return title, imgs[:8]


def fetch_photos(imgs, slug):
    """Download + compress into site/img/<slug>/NN.jpg; return relative paths."""
    outdir = SITE / "img" / slug
    outdir.mkdir(parents=True, exist_ok=True)
    rels = []
    for i, u in enumerate(imgs, 1):
        try:
            raw = requests.get(u, headers={"User-Agent": UA}, timeout=40).content
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
            im.thumbnail((1600, 1600))
            fn = outdir / f"{i:02d}.jpg"
            im.save(fn, "JPEG", quality=82, optimize=True)
            rels.append(f"img/{slug}/{i:02d}.jpg")
        except Exception as e:
            print(f"    [img skip] {e}", file=sys.stderr)
    return rels


PROMPT = """You write case-study articles for {biz}, a licensed HVAC contractor based in {base}, \
serving homeowners and businesses across {region}.

This is a REAL completed job. Original internal title: "{title}"

Write an honest, useful case-study blog post about this specific installation/repair. Rules:
- Base it on the equipment/work in the title. Do NOT invent a customer name, exact street address, city, price, or fake statistics.
- Keep location general ("a home/business in the {region} area", "here in the {base} area"). Never claim a specific city you don't know.
- Explain: what was installed/done, why this equipment/approach is a good choice, what the process involved, and what the customer gains (comfort, efficiency, reliability). Practical and trustworthy, not salesy.
- 380-520 words. Use 3-4 <h2> sections.
- The equipment/service phrase is the SEO keyword — use it in the title and naturally in the body.
- End with a soft CTA to contact {biz}.

Return ONLY strict JSON:
{{
 "title": "clear <=68 char title built around the equipment/service (e.g. '2.5 Ton Goodman Heat Pump Installation')",
 "slug": "kebab-case-slug",
 "meta_description": "<=155 char search snippet",
 "hero_alt": "short alt text for the main install photo",
 "body_html": "article using only <h2>,<h3>,<p>,<ul>,<li>,<strong>,<em>. No <h1>, no images, no inline styles, no script.",
 "faq": [ {{"q":"...","a":"..."}}, ... 2 to 3 items ],
 "social_fb": "2-4 sentence Facebook post, friendly + emoji, ends with phone {phone}",
 "social_yelp": "2-3 sentence neighborly version, no hard sell"
}}"""


def rewrite(title):
    if not XAI_KEY:
        sys.exit("[ERR] XAI_API_KEY not set")
    p = PROMPT.format(biz=C.BIZ_NAME, base=C.CITY_BASE, region=C.REGION, title=title, phone=C.PHONE)
    r = None
    for attempt in range(6):
        r = requests.post("https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "temperature": 0.7,
                  "messages": [{"role": "system", "content": "Expert HVAC writer. Strict JSON only."},
                               {"role": "user", "content": p}]},
            timeout=180)
        if r.status_code == 200:
            break
        if r.status_code in (429, 503, 500, 502):     # capacity/transient → backoff
            wait = min(60, 8 * (attempt + 1))
            print(f"    [retry {attempt+1}] HTTP {r.status_code}, waiting {wait}s")
            time.sleep(wait)
            continue
        raise RuntimeError(f"Grok HTTP {r.status_code}: {r.text[:300]}")
    if not r or r.status_code != 200:
        raise RuntimeError(f"Grok failed after retries: HTTP {getattr(r,'status_code','?')}")
    txt = r.json()["choices"][0]["message"]["content"].strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.MULTILINE).strip()
    return json.loads(re.search(r"\{.*\}", txt, re.DOTALL).group(0))


def _wc(h):
    return len(re.sub(r"<[^>]+>", " ", h).split())


def migrate_one(url, posts, existing_slugs, existing_src):
    if url in existing_src:
        print(f"[skip] already migrated: {url}")
        return None
    title0, imgs = scrape(url)
    print(f"[mig] {title0!r}  ({len(imgs)} photos)")
    art = rewrite(title0)
    if _wc(art.get("body_html", "")) < 340:      # too thin → one retry for length
        print(f"    [short {_wc(art['body_html'])}w] retrying for length")
        try:
            art2 = rewrite(title0 + " — write a thorough, detailed 450-word article")
            if _wc(art2.get("body_html", "")) > _wc(art.get("body_html", "")):
                art = art2
        except Exception as e:
            print(f"    [retry failed, keeping first] {e}")
    slug = slugify(art.get("slug") or art["title"])
    while slug in existing_slugs:
        slug += "-x"
    photos = fetch_photos(imgs, slug) if imgs else []
    post = {
        "slug": slug, "title": art["title"].strip(), "meta": art["meta_description"].strip(),
        "hero_alt": art.get("hero_alt", "").strip(), "body_html": art["body_html"].strip(),
        "faq": art.get("faq", []), "social_fb": art.get("social_fb", "").strip(),
        "social_yelp": art.get("social_yelp", "").strip(),
        "kind": "case", "topic": title0, "city": C.REGION,
        "photos": photos, "source": url,
        "date": datetime.date.today().isoformat(),
    }
    existing_slugs.add(slug); existing_src.add(url)
    posts.append(post)          # case studies go after guides; sorted later
    return post


def rerender(posts):
    SITE.mkdir(exist_ok=True)
    for p in posts:
        render.write_article(SITE, p, posts)
    render.write_index(SITE, posts)
    render.write_embed(SITE, posts)
    render.write_sitemap(SITE, posts)
    render.write_static(SITE)


def main():
    args = sys.argv[1:]
    if not args:
        args = ["--pilot"]
    if args[0] == "--pilot":
        urls = PILOT
    elif args[0] == "--curated":
        urls = [u.strip() for u in (ROOT / "_curated_urls.txt").read_text().splitlines() if u.strip()]
    elif args[0].startswith("http"):
        urls = args
    else:
        start, count = int(args[0]), int(args[1])
        all_urls = [u.strip() for u in URLS_FILE.read_text().splitlines() if u.strip()]
        urls = all_urls[start:start + count]

    posts = load_posts()
    existing_slugs = {p["slug"] for p in posts}
    existing_src = {p.get("source") for p in posts if p.get("source")}
    done = 0
    for u in urls:
        try:
            if migrate_one(u, posts, existing_slugs, existing_src):
                done += 1
                save_posts(posts)          # save after each (resumable)
        except Exception as e:
            print(f"[ERR] {u}: {e}", file=sys.stderr)
    rerender(posts)
    print(f"[done] migrated {done}, total posts {len(posts)}")


if __name__ == "__main__":
    main()
