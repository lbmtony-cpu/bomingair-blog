#!/usr/bin/env python3
"""
BOMING Air — auto blog generator.

1. Picks a (topic, city) combo not used recently.
2. Grok writes a genuinely useful, locally-specific, SEO-optimized HVAC post
   as strict JSON (title, meta, body_html, FAQ, social captions).
3. Renders a static article page + rebuilds index.html + sitemap.xml.

Runs headless in GitHub Actions (daily cron). Needs XAI_API_KEY.
"""
import os, re, sys, json, html, random, datetime, pathlib
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import render

ROOT = pathlib.Path(__file__).parent
SITE = ROOT / "site"
POSTS_DB = ROOT / "posts.json"

XAI_KEY = (os.environ.get("XAI_API_KEY") or "").strip()
MODEL   = (os.environ.get("GROK_MODEL") or "grok-4.3").strip()


def load_posts():
    if POSTS_DB.exists():
        return json.loads(POSTS_DB.read_text(encoding="utf-8"))
    return []


def save_posts(posts):
    POSTS_DB.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def _weighted_city():
    pool = []
    for c, w in C.CITIES_WEIGHTED:
        pool += [c] * w
    return random.choice(pool)


def pick_topic(posts):
    """Pick (kind, topic, city). Bias to high-intent service+city (winnable SEO),
    weighted toward smaller/closer cities, avoiding recently used combos."""
    used = {(p.get("topic"), p.get("city")) for p in posts}
    month = datetime.date.today().month
    for _ in range(60):
        kind = "service" if random.random() < 0.7 else "guide"
        city = _weighted_city()
        if kind == "service":
            tmpl = random.choice(C.SERVICE_TEMPLATES)
            # seasonal skip: don't push furnace pieces in peak summer
            if month in (6, 7, 8, 9) and "furnace" in tmpl.lower() and random.random() < 0.8:
                continue
            topic = tmpl.format(city=city)
        else:
            topic = random.choice(C.TOPICS)
        if (topic, city) not in used:
            return kind, topic, city
    return kind, topic, city  # give up dedup after 60 tries


PROMPT = """You are the content writer for {biz}, a licensed HVAC (air conditioning & heating) \
contractor based in {base}, serving homeowners and businesses across {region} within about a 50-mile radius.

Write ONE genuinely useful, trustworthy blog article for local customers on this topic:
TOPIC: {topic}
FEATURED CITY (weave in naturally 2-4 times, plus mention 2-3 nearby SoCal cities): {city}

Requirements:
- Audience: everyday SoCal homeowners/business owners searching Google for help. Warm, plain-English, expert but not salesy.
- PRIMARY LOCAL KEYWORD: naturally use the main "service + {city}" phrase (e.g. "AC repair in {city}") in the TITLE, in the FIRST sentence, and 2-3 more times in the body. Also mention 2-3 nearby SoCal cities once each. Never keyword-stuff or repeat robotically.
- Locally specific: reference the SoCal climate (hot dry summers, Santa Ana winds, dust, older housing stock, high summer electric bills, desert-adjacent heat).
- Genuinely helpful: real causes, real steps, honest "DIY this / call a pro for that" guidance. No fluff, no fake statistics, no invented awards.
- LENGTH IS MANDATORY: the body_html must be AT LEAST 600 words (aim 600-750). Write enough real, specific detail to hit this — do not pad with filler. Use 4-6 <h2> sections.
- End with a soft, honest call to action to contact {biz} (do NOT promise specific prices, discounts, or guarantees you weren't given).

Return ONLY strict JSON (no markdown fence) with these keys:
{{
 "title": "compelling <=65 char title, include the city",
 "slug": "kebab-case-url-slug-no-city-year",
 "meta_description": "<=155 char search snippet, includes city",
 "hero_alt": "short alt text describing a relevant HVAC scene",
 "body_html": "the article as clean HTML using only <h2>,<h3>,<p>,<ul>,<li>,<strong>,<em> tags. No <h1>. No inline styles. No script.",
 "faq": [ {{"q":"question a local customer would ask","a":"concise 1-3 sentence answer"}}, ... 3 to 4 items ],
 "social_fb": "a 2-4 sentence Facebook post promoting this article, friendly + emoji, ends with phone {phone}",
 "social_yelp": "a 2-3 sentence neighborly Yelp/Nextdoor tip version, no hard sell"
}}"""


def call_grok(topic, city):
    if not XAI_KEY:
        sys.exit("[ERR] XAI_API_KEY not set")
    prompt = PROMPT.format(biz=C.BIZ_NAME, base=C.CITY_BASE, region=C.REGION,
                           topic=topic, city=city, phone=C.PHONE)
    r = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": "You are an expert HVAC content writer. Output strict JSON only."},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=180,
    )
    if r.status_code != 200:
        sys.exit(f"[ERR] Grok HTTP {r.status_code}: {r.text[:600]}")
    txt = r.json()["choices"][0]["message"]["content"].strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.MULTILINE).strip()
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        sys.exit(f"[ERR] no JSON in Grok reply:\n{txt[:600]}")
    return json.loads(m.group(0))


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:70] or "post"


def post_to_facebook(link, message):
    """Auto-post the new article to the FB Page, if creds are configured.
    Needs env FB_PAGE_ID + FB_PAGE_TOKEN (a long-lived Page access token)."""
    page_id = (os.environ.get("FB_PAGE_ID") or "").strip()
    token = (os.environ.get("FB_PAGE_TOKEN") or "").strip()
    if not (page_id and token):
        print("[fb] no FB creds set — skipping Facebook post")
        return
    try:
        r = requests.post(
            f"https://graph.facebook.com/v21.0/{page_id}/feed",
            data={"message": message, "link": link, "access_token": token},
            timeout=30,
        )
        if r.status_code == 200:
            print(f"[fb] posted: {r.json().get('id','?')}")
        else:
            print(f"[fb][ERR] HTTP {r.status_code}: {r.text[:300]}", file=sys.stderr)
    except Exception as e:
        print(f"[fb][ERR] {e}", file=sys.stderr)


def _wc(html_str):
    return len(re.sub(r"<[^>]+>", " ", html_str).split())


def main():
    posts = load_posts()
    kind, topic, city = pick_topic(posts)
    print(f"[gen] kind={kind} topic={topic!r} city={city!r} model={MODEL}")
    art = call_grok(topic, city)
    if _wc(art.get("body_html", "")) < 520:      # one retry if too short for SEO
        print(f"[gen] short ({_wc(art['body_html'])}w), retrying for length")
        art2 = call_grok(topic + " (write a thorough 650-word article)", city)
        if _wc(art2.get("body_html", "")) > _wc(art.get("body_html", "")):
            art = art2

    today = datetime.date.today().isoformat()
    base_slug = slugify(art.get("slug") or art["title"])
    slug = f"{base_slug}-{slugify(city)}"
    # ensure unique
    existing = {p["slug"] for p in posts}
    if slug in existing:
        slug = f"{slug}-{today}"

    post = {
        "slug": slug,
        "title": art["title"].strip(),
        "meta": art["meta_description"].strip(),
        "hero_alt": art.get("hero_alt", "").strip(),
        "body_html": art["body_html"].strip(),
        "faq": art.get("faq", []),
        "social_fb": art.get("social_fb", "").strip(),
        "social_yelp": art.get("social_yelp", "").strip(),
        "kind": kind,
        "topic": topic,
        "city": city,
        "date": today,
    }
    posts.insert(0, post)          # newest first
    save_posts(posts)

    SITE.mkdir(exist_ok=True)
    render.write_article(SITE, post, posts)
    render.write_index(SITE, posts)
    render.write_embed(SITE, posts)
    render.write_sitemap(SITE, posts)
    render.write_static(SITE)

    # stash social captions for the (manual) Yelp/Nextdoor + (auto) FB steps
    (ROOT / "latest_social.json").write_text(
        json.dumps({"url": f"{C.BLOG_URL}/posts/{slug}.html",
                    "title": post["title"],
                    "fb": post["social_fb"],
                    "yelp": post["social_yelp"]}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"[ok] published: {C.BLOG_URL}/posts/{slug}.html")

    fb_msg = post["social_fb"] or f"{post['title']} — {post['meta']}"
    post_to_facebook(f"{C.BLOG_URL}/posts/{slug}.html", fb_msg)

    try:                        # ping Bing/Yandex (ChatGPT Search, Copilot) — no login
        import indexnow
        indexnow.submit([f"{C.BLOG_URL}/posts/{slug}.html", f"{C.BLOG_URL}/"])
    except Exception as e:
        print(f"[indexnow] skipped: {e}")


if __name__ == "__main__":
    main()
