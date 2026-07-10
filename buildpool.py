#!/usr/bin/env python3
"""
Build a curated photo pool (site/stock/) from the iCloud library so EVERY daily
guide article can get a real HVAC hero image (cloud generate.py picks from it).

Vision-QC every candidate: keep clear HVAC-equipment shots, DROP anything with a
privacy risk (face, house number, plate, person, document). Orient + compress.
Writes stock_pool.json (committed) = [{img, alt}]. Resumable.

Usage: buildpool.py [target_count=50] [scan_files=500]
"""
import os, re, sys, io, json, base64, time, pathlib
import requests
from PIL import Image, ImageOps
import pillow_heif
pillow_heif.register_heif_opener()

ROOT = pathlib.Path(__file__).parent
SITE = ROOT / "site"
POOL_DIR = SITE / "stock"
POOL_DB = ROOT / "stock_pool.json"
LIB = pathlib.Path(r"E:\iCloudPhotos\Photos")
XAI_KEY = (os.environ.get("XAI_API_KEY") or "").strip()
MODEL = "grok-4.3"


def grok_vision(fp):
    im = ImageOps.exif_transpose(Image.open(fp)).convert("RGB")
    im.thumbnail((720, 720))
    b = io.BytesIO(); im.save(b, "JPEG", quality=72)
    b64 = base64.b64encode(b.getvalue()).decode()
    for a in range(5):
        r = requests.post("https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {XAI_KEY}"},
            json={"model": MODEL, "temperature": 0.2, "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": 'Strict JSON only: {"alt":"<=12 word alt text of the HVAC '
                 'equipment shown","is_hvac":true/false,"privacy_risk":true/false}. Set privacy_risk '
                 'TRUE ONLY if EITHER (a) the photo is primarily a CLOSE-UP of a data plate / '
                 'nameplate / spec sticker with a readable MODEL or SERIAL number, OR (b) it shows a '
                 'person/face, house number, license plate, name, or document. Normal equipment '
                 'photos with only small brand logos or warning stickers are NOT privacy.'}]}]},
            timeout=120)
        if r.status_code == 200:
            t = r.json()["choices"][0]["message"]["content"]
            t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.MULTILINE).strip()
            return json.loads(re.search(r"\{.*\}", t, re.DOTALL).group(0))
        if r.status_code in (429, 500, 502, 503):
            time.sleep(8 * (a + 1)); continue
        break
    return {"is_hvac": False}


def is_placeholder(p):
    a = p.stat().st_file_attributes
    return bool(a & 0x400000) or bool(a & 0x1000)


def main():
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    scan = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    POOL_DIR.mkdir(parents=True, exist_ok=True)
    pool = json.loads(POOL_DB.read_text(encoding="utf-8")) if POOL_DB.exists() else []
    done_src = {x["src"] for x in pool}

    files = [p for p in LIB.iterdir()
             if p.suffix.lower() in (".jpg", ".jpeg", ".heic")]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    checked = 0
    for p in files:
        if len(pool) >= target:
            break
        if str(p) in done_src:
            continue
        try:
            if is_placeholder(p):
                continue
        except Exception:
            continue
        if checked >= scan:
            break
        checked += 1
        try:
            v = grok_vision(p)
        except Exception as e:
            print("qc err", e); continue
        if not v.get("is_hvac") or v.get("privacy_risk"):
            continue
        n = len(pool) + 1
        fn = f"{n:03d}.jpg"
        im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
        im.thumbnail((1400, 1400))
        im.save(POOL_DIR / fn, "JPEG", quality=82, optimize=True)
        pool.append({"img": f"stock/{fn}", "alt": v.get("alt", "HVAC equipment"), "src": str(p)})
        POOL_DB.write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{len(pool)}/{target}] {v.get('alt','')[:40]}")

    print(f"pool size: {len(pool)} (checked {checked})")


if __name__ == "__main__":
    main()
