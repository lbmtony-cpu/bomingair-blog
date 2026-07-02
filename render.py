"""HTML rendering + SEO for the BOMING Air static blog."""
import json, html, datetime, pathlib
import config as C


def _head(title, desc, canonical, og_type="article", extra_ld=""):
    t = html.escape(title)
    d = html.escape(desc)
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t} | {C.BIZ_SHORT}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="{og_type}"><meta property="og:title" content="{t}">
<meta property="og:description" content="{d}"><meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{C.BIZ_NAME}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/style.css">
{extra_ld}
</head><body>"""


def _localbiz_ld():
    return {
        "@type": "HVACBusiness",
        "name": C.BIZ_NAME,
        "telephone": C.PHONE_TEL,
        "email": C.EMAIL,
        "url": C.MAIN_SITE,
        "areaServed": C.REGION,
        "address": {"@type": "PostalAddress", "addressLocality": C.CITY_BASE,
                    "addressRegion": C.STATE, "postalCode": C.ZIP, "addressCountry": "US"},
    }


def _header():
    return f"""<header class="site"><div class="wrap">
<a class="logo" href="/">{C.BIZ_SHORT}<span>Air Conditioning &amp; Heating</span></a>
<a class="callbtn" href="tel:{C.PHONE_TEL}">📞 {C.PHONE}</a>
</div></header>"""


def _footer():
    cities = ", ".join(C.CITIES[:10]) + " &amp; more"
    return f"""<footer class="site"><div class="wrap">
<p class="cta"><strong>Need HVAC service in {C.REGION}?</strong>
Licensed AC &amp; heating repair, maintenance &amp; installation.
Call <a href="tel:{C.PHONE_TEL}">{C.PHONE}</a> or email
<a href="mailto:{C.EMAIL}">{C.EMAIL}</a>.</p>
<p class="area"><strong>Service area:</strong> {cities}</p>
<p class="mini"><a href="{C.MAIN_SITE}">← {C.MAIN_SITE.replace('https://','')}</a> ·
© {datetime.date.today().year} {C.BIZ_NAME}</p>
</div></footer></body></html>"""


def _cta_box(city):
    return f"""<div class="ctabox">
<h3>Trusted AC &amp; heating help in {html.escape(city)}</h3>
<p>{C.BIZ_NAME} is a licensed HVAC contractor serving {html.escape(city)} and the surrounding {C.REGION} area. Whether it's a no-cool emergency, a tune-up, or a new system, we're here to help.</p>
<a class="callbtn big" href="tel:{C.PHONE_TEL}">📞 Call {C.PHONE}</a>
</div>"""


def _related_block(post, all_posts):
    if not all_posts:
        return ""
    others = [p for p in all_posts if p["slug"] != post["slug"]]
    same_city = [p for p in others if p.get("city") == post.get("city")]
    picks, seen = [], set()
    for p in same_city + others:
        if p["slug"] in seen:
            continue
        seen.add(p["slug"]); picks.append(p)
        if len(picks) == 3:
            break
    if not picks:
        return ""
    items = "".join(
        f'<li><a href="/posts/{p["slug"]}.html">{html.escape(p["title"])}</a></li>' for p in picks)
    return f'<section class="related"><h2>Related articles</h2><ul>{items}</ul></section>'


def write_article(site: pathlib.Path, post: dict, all_posts=None):
    url = f"{C.BLOG_URL}/posts/{post['slug']}.html"
    faq = post.get("faq") or []

    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BlogPosting", "headline": post["title"],
         "description": post["meta"], "datePublished": post["date"],
         "dateModified": post["date"], "mainEntityOfPage": url,
         "author": {"@type": "Organization", "name": C.BIZ_NAME},
         "publisher": {"@type": "Organization", "name": C.BIZ_NAME}},
        _localbiz_ld(),
    ]}
    if faq:
        ld["@graph"].append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"],
             "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq]})
    ld_tag = '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>"

    faq_html = ""
    if faq:
        items = "".join(
            f'<div class="faq-item"><h3>{html.escape(f["q"])}</h3><p>{html.escape(f["a"])}</p></div>'
            for f in faq)
        faq_html = f'<section class="faq"><h2>Frequently asked questions</h2>{items}</section>'

    try:
        d = datetime.date.fromisoformat(post["date"]).strftime("%B %d, %Y").replace(" 0", " ")
    except Exception:
        d = post["date"]

    body = f"""{_head(post['title'], post['meta'], url, extra_ld=ld_tag)}
{_header()}
<main class="article"><div class="wrap">
<nav class="crumb"><a href="/">Blog</a> › <span>{html.escape(post['city'])}</span></nav>
<span class="pin">{html.escape(post['city'])}, {C.STATE}</span>
<h1>{html.escape(post['title'])}</h1>
<p class="byline">By {C.BIZ_SHORT} · {d} · Serving {html.escape(post['city'])}, {C.STATE}</p>
<article class="body">{post['body_html']}</article>
{_cta_box(post['city'])}
{faq_html}
{_related_block(post, all_posts)}
</div></main>
{_footer()}"""
    outdir = site / "posts"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{post['slug']}.html").write_text(body, encoding="utf-8")


def write_index(site: pathlib.Path, posts: list):
    cards = ""
    for p in posts:
        cards += f"""<a class="card" href="/posts/{p['slug']}.html">
<span class="card-city">{html.escape(p['city'])}, {C.STATE}</span>
<h2>{html.escape(p['title'])}</h2>
<p>{html.escape(p['meta'])}</p>
<span class="card-read">Read article &#8594;</span></a>"""
    if not cards:
        cards = "<p>New articles coming soon.</p>"
    desc = f"Practical AC & heating tips for {C.REGION} homeowners from {C.BIZ_NAME}."
    body = f"""{_head(f"HVAC Tips & Advice for {C.REGION}", desc, C.BLOG_URL + "/", og_type="website")}
{_header()}
<main class="index"><div class="wrap">
<div class="intro"><h1>AC &amp; Heating Tips for {C.REGION}</h1>
<p>Straight, useful advice from the licensed team at {C.BIZ_NAME} — serving {C.CITY_BASE} and nearby cities.</p></div>
<div class="grid">{cards}</div>
</div></main>
{_footer()}"""
    (site / "index.html").write_text(body, encoding="utf-8")


def write_sitemap(site: pathlib.Path, posts: list):
    urls = [f"<url><loc>{C.BLOG_URL}/</loc></url>"]
    for p in posts:
        urls.append(f"<url><loc>{C.BLOG_URL}/posts/{p['slug']}.html</loc>"
                    f"<lastmod>{p['date']}</lastmod></url>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join(urls) + "</urlset>")
    (site / "sitemap.xml").write_text(xml, encoding="utf-8")
    (site / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {C.BLOG_URL}/sitemap.xml\n", encoding="utf-8")


def write_embed(site: pathlib.Path, posts: list, n: int = 8):
    """Standalone cards strip to iframe-embed on bomingair.com (auto-updates)."""
    cards = ""
    for p in posts[:n]:
        cards += f"""<a class="ec" href="{C.BLOG_URL}/posts/{p['slug']}.html" target="_blank" rel="noopener">
<span class="ecity">{html.escape(p['city'])}, {C.STATE}</span>
<h3>{html.escape(p['title'])}</h3>
<p>{html.escape(p['meta'])}</p>
<span class="eread">Read article &#8594;</span></a>"""
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{{--blue:{C.BRAND_BLUE};--dark:{C.BRAND_DARK};--accent:{C.BRAND_ACCENT}}}
*{{box-sizing:border-box}}html,body{{margin:0;background:transparent}}
body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1a2233}}
.eh{{font-size:23px;font-weight:800;color:var(--dark);margin:4px 0 4px}}
.esub{{color:#5a6b82;font-size:15px;margin:0 0 18px}}
.eg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px}}
.ec{{display:flex;flex-direction:column;background:#fff;border:1px solid #e6ebf2;
border-top:3px solid var(--accent);border-radius:10px;padding:16px 18px 14px;
text-decoration:none;color:inherit;transition:.15s}}
.ec:hover{{box-shadow:0 8px 22px rgba(10,60,120,.10);border-color:#cfe0f5;transform:translateY(-2px)}}
.ecity{{display:inline-block;align-self:flex-start;background:#eaf1fb;color:var(--blue);
font-size:12px;font-weight:600;padding:3px 9px;border-radius:20px;margin-bottom:10px}}
.ec h3{{margin:0 0 8px;font-size:16px;line-height:1.35;color:var(--dark)}}
.ec p{{margin:0 0 14px;font-size:13.5px;color:#5a6b82;line-height:1.5;flex:1}}
.eread{{font-size:13.5px;font-weight:700;color:var(--blue)}}
.eall{{display:inline-block;margin-top:18px;color:var(--blue);font-weight:700;text-decoration:none;font-size:15px}}
</style></head><body>
<div class="eh">HVAC Tips &amp; Advice for {C.REGION}</div>
<p class="esub">Straight, useful advice from the licensed team at {C.BIZ_NAME}.</p>
<div class="eg">{cards}</div>
<a class="eall" href="{C.BLOG_URL}/" target="_blank" rel="noopener">View all articles &#8594;</a>
<script>
function ph(){{var h=document.body.scrollHeight;parent.postMessage({{bomingBlogHeight:h}},"*");}}
window.addEventListener("load",ph);setInterval(ph,1000);
</script></body></html>"""
    (site / "embed.html").write_text(doc, encoding="utf-8")


def write_static(site: pathlib.Path):
    # custom domain for GitHub Pages
    (site / "CNAME").write_text("blog.bomingair.com\n", encoding="utf-8")
    (site / "style.css").write_text(CSS, encoding="utf-8")


CSS = f""":root{{--blue:{C.BRAND_BLUE};--dark:{C.BRAND_DARK};--accent:{C.BRAND_ACCENT}}}
*{{box-sizing:border-box}}body{{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
color:#1a2233;line-height:1.65;background:#f4f7fb}}
.wrap{{max-width:820px;margin:0 auto;padding:0 20px}}
a{{color:var(--blue);text-decoration:none}}a:hover{{text-decoration:underline}}
header.site{{background:var(--dark);position:sticky;top:0;z-index:10}}
header.site .wrap{{display:flex;align-items:center;justify-content:space-between;padding:14px 20px}}
.logo{{color:#fff;font-weight:800;font-size:20px;line-height:1}}
.logo span{{display:block;font-weight:500;font-size:11px;letter-spacing:.5px;color:#9db8d8;margin-top:3px}}
.callbtn{{background:var(--accent);color:#1a2233!important;font-weight:700;padding:9px 14px;border-radius:8px;white-space:nowrap}}
.callbtn:hover{{text-decoration:none;filter:brightness(1.05)}}
.callbtn.big{{display:inline-block;font-size:18px;padding:14px 22px;margin-top:6px}}
main{{padding:26px 0 10px}}
.crumb{{font-size:13px;color:#6b7a90;margin-bottom:14px}}
.pin{{display:inline-block;background:#eaf1fb;color:var(--blue);font-size:13px;font-weight:600;
padding:4px 12px;border-radius:20px;margin-bottom:12px}}
h1{{font-size:30px;line-height:1.25;margin:6px 0 8px}}
.byline{{color:#6b7a90;font-size:14px;margin:0 0 22px}}
.body h2{{font-size:22px;margin:28px 0 10px}}.body h3{{font-size:18px;margin:20px 0 8px}}
.body p,.body li{{font-size:17px}}.body ul{{padding-left:22px}}
.ctabox{{background:#fff;border:1px solid #e2eaf3;border-left:5px solid var(--accent);
border-radius:12px;padding:22px;margin:32px 0}}
.ctabox h3{{margin:0 0 8px;font-size:20px}}
.faq{{margin:34px 0}}.faq h2{{font-size:22px}}
.faq-item{{background:#fff;border:1px solid #e2eaf3;border-radius:10px;padding:16px 18px;margin:12px 0}}
.faq-item h3{{margin:0 0 6px;font-size:17px}}.faq-item p{{margin:0;color:#3a4658}}
.related{{margin:34px 0}}.related h2{{font-size:20px}}
.related ul{{list-style:none;padding:0;margin:0}}
.related li{{padding:10px 0;border-bottom:1px solid #e2eaf3;font-size:17px}}
.intro h1{{margin-bottom:6px}}.intro p{{color:#4a5a70;font-size:17px;margin-top:0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px;margin:24px 0}}
.card{{display:flex;flex-direction:column;background:#fff;border:1px solid #e6ebf2;
border-top:3px solid var(--accent);border-radius:10px;padding:16px 18px 14px;color:inherit;transition:.15s}}
.card:hover{{text-decoration:none;box-shadow:0 8px 22px rgba(10,60,120,.10);border-color:#cfe0f5;transform:translateY(-2px)}}
.card-city{{display:inline-block;align-self:flex-start;background:#eaf1fb;color:var(--blue);
font-size:12px;font-weight:600;padding:3px 9px;border-radius:20px;margin-bottom:10px}}
.card h2{{margin:0 0 8px;font-size:17px;line-height:1.35;color:var(--dark)}}
.card p{{margin:0 0 14px;color:#5a6b82;font-size:14px;line-height:1.5;flex:1}}
.card-read{{font-size:13.5px;font-weight:700;color:var(--blue)}}
footer.site{{background:var(--dark);color:#c7d6e8;margin-top:40px;padding:26px 0}}
footer .cta{{font-size:16px}}footer a{{color:#8fc0ff}}
footer .area{{font-size:14px;color:#9db8d8}}footer .mini{{font-size:13px;color:#7a93b3;margin-bottom:0}}
@media(max-width:600px){{h1{{font-size:25px}}}}
"""
