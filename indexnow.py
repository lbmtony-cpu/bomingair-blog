#!/usr/bin/env python3
"""
IndexNow submitter — instantly notify Bing/Yandex (feeds ChatGPT Search + Copilot).
No account/login needed; the key file at /<key>.txt proves ownership.

Usage:
  indexnow.py                 # submit every URL in sitemap.xml
  indexnow.py <url> [<url>..]  # submit specific URLs (used by generate.py)
"""
import sys, os, re, json, pathlib
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

HOST = C.BLOG_URL.replace("https://", "").replace("http://", "").rstrip("/")
KEY = getattr(C, "INDEXNOW_KEY", "")
SITE = pathlib.Path(__file__).parent / "site"


def all_urls():
    sm = (SITE / "sitemap.xml").read_text(encoding="utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", sm)


def submit(urls):
    if not KEY:
        print("[indexnow] no key set"); return
    urls = list(dict.fromkeys(urls))[:9000]      # dedupe, cap
    payload = {
        "host": HOST,
        "key": KEY,
        "keyLocation": f"{C.BLOG_URL}/{KEY}.txt",
        "urlList": urls,
    }
    try:
        r = requests.post("https://api.indexnow.org/indexnow",
                          json=payload, timeout=30,
                          headers={"Content-Type": "application/json"})
        print(f"[indexnow] submitted {len(urls)} urls -> HTTP {r.status_code} "
              f"{'(202/200 = accepted)' if r.status_code in (200, 202) else r.text[:200]}")
    except Exception as e:
        print(f"[indexnow][ERR] {e}")


if __name__ == "__main__":
    urls = sys.argv[1:] if len(sys.argv) > 1 else all_urls()
    submit(urls)
