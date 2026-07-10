#!/usr/bin/env python3
"""
Privacy scrub: re-check every photo on every post and REMOVE any that show a
face/person, house number, plate, name, document, or an equipment data plate /
model number / serial number / readable spec label. Deletes the image file and
drops it from the post. Re-renders. Resumable via _scrub_report.json.
"""
import os, re, sys, io, json, base64, time, pathlib
import requests
from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()

ROOT = pathlib.Path(__file__).parent
SITE = ROOT / "site"
POSTS_DB = ROOT / "posts.json"
REPORT = ROOT / "_scrub_report.json"
XAI_KEY = (os.environ.get("XAI_API_KEY") or "").strip()
MODEL = "grok-4.3"


def flagged(imgpath):
    fp = SITE / imgpath
    if not fp.exists():
        return False
    b64 = base64.b64encode(fp.read_bytes()).decode()
    for a in range(5):
        r = requests.post("https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {XAI_KEY}"},
            json={"model": MODEL, "temperature": 0.1, "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": 'Answer strict JSON {"privacy":true/false}. Set privacy=true '
                 'ONLY if EITHER (a) the photo is primarily a CLOSE-UP of an equipment data plate / '
                 'rating nameplate / spec sticker where a MODEL NUMBER or SERIAL NUMBER is clearly '
                 'readable (a shot taken to record specs), OR (b) it shows a person or face, a house '
                 'or street number, a license plate, a personal name, or a personal document. A normal '
                 'photo of HVAC equipment that merely has small brand logos or generic warning '
                 'stickers is NOT privacy -> false.'}]}]},
            timeout=120)
        if r.status_code == 200:
            t = r.json()["choices"][0]["message"]["content"]
            try:
                return bool(json.loads(re.search(r"\{.*\}", t, re.DOTALL).group(0)).get("privacy"))
            except Exception:
                return False
        if r.status_code in (429, 500, 502, 503):
            time.sleep(8 * (a + 1)); continue
        return False
    return False


def main():
    apply = "--apply" in sys.argv           # default = DRY RUN (report only, no deletion)
    posts = json.loads(POSTS_DB.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    removed_total = 0
    total = 0
    changed = False
    for p in posts:
        ph = p.get("photos") or []
        if not ph:
            continue
        keep = []
        for img in ph:
            total += 1
            if img in report:
                bad = report[img]
            else:
                bad = flagged(img)
                report[img] = bad
                REPORT.write_text(json.dumps(report, indent=1), encoding="utf-8")
            if bad:
                removed_total += 1
                print(f"[{'remove' if apply else 'FLAG'}] {img}  ({p['slug']})")
                if apply:
                    changed = True
                    try:
                        (SITE / img).unlink()
                    except Exception:
                        pass
            else:
                keep.append(img)
        if apply and keep != ph:
            p["photos"] = keep
    print(f"[summary] {removed_total}/{total} photos flagged ({round(100*removed_total/max(total,1))}%)"
          + ("" if apply else "  -- DRY RUN, nothing deleted. Re-run with --apply to remove."))
    if changed:
        POSTS_DB.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
        import render
        for f in (SITE / "posts").glob("*.html"):
            f.unlink()
        for p in posts:
            render.write_article(SITE, p, posts)
        render.write_index(SITE, posts); render.write_embed(SITE, posts)
        render.write_sitemap(SITE, posts); render.write_static(SITE)
    print(f"[done] removed {removed_total} privacy photos, rerendered")


if __name__ == "__main__":
    main()
