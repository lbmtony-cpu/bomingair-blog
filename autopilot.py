#!/usr/bin/env python3
"""
BOMING Air jobsite autopilot — runs weekly via Windows Task Scheduler, no human.

1. sync repo, hydrate+scan recent iCloud photos (jobscan)
2. find the newest (date, city) cluster NOT already published, >=3 photos
3. vision QC every photo: keep HVAC shots, DROP anything with privacy risk
   (face / house number / plate / document). Need >=2 good photos.
4. Grok writes an honest case study; photos baked with correct orientation
5. publish -> commit -> push (rebase-safe) -> IndexNow
6. append a line to autopilot_log.txt

Safe by design: if nothing new / nothing passes QC, it publishes nothing.
"""
import os, re, sys, io, json, base64, time, subprocess, datetime, pathlib
import requests
from PIL import Image, ImageOps
import pillow_heif
pillow_heif.register_heif_opener()

ROOT = pathlib.Path(__file__).parent
SITE = ROOT / "site"
POSTS_DB = ROOT / "posts.json"
LOG = ROOT / "autopilot_log.txt"
PY = sys.executable


def load_key():
    k = (os.environ.get("XAI_API_KEY") or "").strip()
    if k:
        return k
    env = pathlib.Path.home() / "thebestdoll" / ".env"
    if env.exists():
        for ln in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ln.startswith("XAI_API_KEY"):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


XAI_KEY = load_key()
MODEL = "grok-4.3"
sys.path.insert(0, str(ROOT))
import config as C
import render


def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def git(*args, check=True):
    r = subprocess.run(["git", "-c", "user.name=boming-bot",
                        "-c", "user.email=bot@bomingair.com", *args],
                       cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr[:200]}")
    return r.stdout.strip()


def grok(messages, temp=0.4, retries=6):
    for a in range(retries):
        r = requests.post("https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {XAI_KEY}"},
            json={"model": MODEL, "temperature": temp, "messages": messages}, timeout=180)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        if r.status_code in (429, 500, 502, 503):
            time.sleep(min(60, 8 * (a + 1))); continue
        raise RuntimeError(f"grok HTTP {r.status_code}: {r.text[:200]}")
    raise RuntimeError("grok retries exhausted")


def jparse(t):
    t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.MULTILINE).strip()
    return json.loads(re.search(r"\{.*\}", t, re.DOTALL).group(0))


def qc_photo(fp):
    im = ImageOps.exif_transpose(Image.open(fp)).convert("RGB")
    im.thumbnail((720, 720))
    b = io.BytesIO(); im.save(b, "JPEG", quality=72)
    b64 = base64.b64encode(b.getvalue()).decode()
    v = jparse(grok([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        {"type": "text", "text": 'Strict JSON only: {"shows":"<=14 words","is_hvac":true/false,'
         '"privacy_risk":true/false}. Set privacy_risk TRUE ONLY if EITHER (a) the photo is primarily '
         'a CLOSE-UP of a data plate / nameplate / spec sticker with a readable MODEL or SERIAL '
         'number, OR (b) it shows a person/face, house number, license plate, name, or document. '
         'Normal equipment photos with only small brand logos or warning stickers are NOT privacy.'}]}],
        temp=0.2))
    return v


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:75] or "job"


def publish(cluster, good):
    city, date = cluster["city"], cluster["date"]
    slug = f"hvac-{slugify(city)}-{date}"
    posts = json.loads(POSTS_DB.read_text(encoding="utf-8"))
    if any(p.get("source") == f"icloud:{date}-{slugify(city)}" for p in posts):
        log(f"already published {date} {city}"); return False
    outdir = SITE / "img" / slug
    outdir.mkdir(parents=True, exist_ok=True)
    photos = []
    for i, g in enumerate(good, 1):
        im = ImageOps.exif_transpose(Image.open(g["file"])).convert("RGB")
        im.thumbnail((1600, 1600))
        im.save(outdir / f"{i:02d}.jpg", "JPEG", quality=82, optimize=True)
        photos.append(f"img/{slug}/{i:02d}.jpg")
    shows = "; ".join(g["shows"] for g in good)
    mon = datetime.date.fromisoformat(date).strftime("%B %Y")
    prompt = (f'You write for {C.BIZ_NAME}, licensed HVAC contractor in {C.CITY_BASE} serving {C.REGION}.\n'
              f'REAL job completed in {city}, CA ({mon}). The real photos show: {shows}.\n'
              f'Write an honest 380-500 word case study of this {city} job. Do NOT invent customer '
              f'names, addresses, prices, or outcomes not visible. Explain what was done, why it '
              f'matters for {city}/SoCal homeowners, and the value delivered. 3-4 <h2> sections, '
              f'soft CTA {C.PHONE}.\nReturn ONLY strict JSON: {{"title":"<=68c with {city}",'
              f'"slug":"{slug}","meta_description":"<=155c with {city}","hero_alt":"...",'
              f'"body_html":"<h2>/<p>/<ul>/<li> only","faq":[{{"q":"...","a":"..."}},{{"q":"...","a":"..."}}],'
              f'"social_fb":"...","social_yelp":"..."}}')
    art = jparse(grok([{"role": "system", "content": "Expert HVAC writer. Strict JSON only."},
                       {"role": "user", "content": prompt}], temp=0.5))
    post = {"slug": slug, "title": art["title"].strip(), "meta": art["meta_description"].strip(),
            "hero_alt": art.get("hero_alt", ""), "body_html": art["body_html"].strip(),
            "faq": art.get("faq", []), "social_fb": art.get("social_fb", ""),
            "social_yelp": art.get("social_yelp", ""), "kind": "case",
            "topic": f"jobsite {date} {city}", "city": city, "photos": photos,
            "source": f"icloud:{date}-{slugify(city)}", "date": datetime.date.today().isoformat()}
    posts.insert(0, post)
    POSTS_DB.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    for p in posts:
        render.write_article(SITE, p, posts)
    render.write_index(SITE, posts); render.write_embed(SITE, posts)
    render.write_sitemap(SITE, posts); render.write_static(SITE)
    log(f"PUBLISHED: {post['title']} ({len(photos)} photos)")
    return post


def push_safe():
    git("add", "-A")
    if not git("status", "--porcelain"):
        return
    git("commit", "-q", "-m", f"autopilot: jobsite case study {datetime.date.today()}")
    for _ in range(4):
        r = subprocess.run(["git", "push", "origin", "main"], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode == 0:
            return
        git("pull", "--rebase", "origin", "main", check=False)
    log("WARN: push failed after retries")


def main():
    if not XAI_KEY:
        log("ABORT: no XAI key"); return
    git("pull", "--ff-only", "origin", "main", check=False)
    # hydrate + scan the recent library
    subprocess.run([PY, str(ROOT / "jobscan.py"), "150", "--hydrate"],
                   cwd=ROOT, capture_output=True, text=True)
    clusters = json.loads((ROOT / "_jobscan.json").read_text(encoding="utf-8"))
    posts = json.loads(POSTS_DB.read_text(encoding="utf-8"))
    published = {p.get("source") for p in posts if p.get("source")}
    # newest-first clusters with >=3 photos, not yet published
    cands = [c for c in clusters if c["count"] >= 3
             and f"icloud:{c['date']}-{slugify(c['city'])}" not in published]
    log(f"scan: {len(clusters)} clusters, {len(cands)} new candidates")
    for c in cands[:4]:                       # try up to 4 newest until one passes QC
        good = []
        for ph in c["photos"][:8]:
            try:
                v = qc_photo(ph["file"])
            except Exception as e:
                log(f"qc err {e}"); continue
            if v.get("is_hvac") and not v.get("privacy_risk"):
                good.append({"file": ph["file"], "shows": v.get("shows", "")})
        if len(good) >= 2:
            log(f"selected {c['date']} {c['city']} ({len(good)}/{c['count']} photos passed QC)")
            if publish(c, good[:6]):
                push_safe()
                try:
                    import indexnow
                    indexnow.submit([f"{C.BLOG_URL}/", f"{C.BLOG_URL}/sitemap.xml"])
                except Exception:
                    pass
            break
        log(f"skip {c['date']} {c['city']}: only {len(good)} usable photos")
    else:
        log("no publishable new jobsite this run")
    # keep the daily-article photo pool topped up from fresh iCloud photos
    try:
        r = subprocess.run([PY, str(ROOT / "buildpool.py"), "60", "300"],
                           cwd=ROOT, capture_output=True, text=True, timeout=1200)
        log("pool refresh: " + (r.stdout.strip().splitlines() or ["(no output)"])[-1])
        push_safe()
    except Exception as e:
        log(f"pool refresh err: {e}")


if __name__ == "__main__":
    main()
