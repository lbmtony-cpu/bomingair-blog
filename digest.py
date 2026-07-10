#!/usr/bin/env python3
"""
Weekly BOMING Air digest — the "watchdog" that pokes the user so the plan never
stalls. Gathers status + open human-decision items, sends to Slack.

Run standalone to send now; the weekly scheduled task also calls it.
"""
import os, re, sys, json, datetime, pathlib, subprocess
import requests

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))
import config as C


def slack_url():
    u = (os.environ.get("SLACK_WEBHOOK_URL") or "").strip()
    if u:
        return u
    env = pathlib.Path.home() / "thebestdoll" / ".env"
    if env.exists():
        m = re.search(r"^SLACK_WEBHOOK_URL=(.+)$", env.read_text(encoding="utf-8", errors="ignore"), re.M)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return ""


def gather():
    posts = json.loads((ROOT / "posts.json").read_text(encoding="utf-8"))
    today = datetime.date.today()
    wk = today - datetime.timedelta(days=7)
    def d(p):
        try:
            return datetime.date.fromisoformat(p["date"])
        except Exception:
            return today
    recent = [p for p in posts if d(p) >= wk]
    cases = [p for p in posts if p.get("kind") == "case"]
    log = ROOT / "autopilot_log.txt"
    last_auto = ""
    if log.exists():
        lines = [l for l in log.read_text(encoding="utf-8").splitlines() if "PUBLISHED" in l or "no publishable" in l]
        last_auto = lines[-1] if lines else ""
    return {
        "total": len(posts), "cases": len(cases), "week": len(recent),
        "recent_titles": [p["title"] for p in recent[:6]],
        "last_auto": last_auto,
    }


def build(s):
    today = datetime.date.today().strftime("%Y-%m-%d")
    lines = [
        f"*🌀 BOMING Air 周报 · {today}*",
        "",
        f"📝 博客总数: *{s['total']}* 篇 (含 {s['cases']} 篇真图案例)",
        f"🆕 本周新增: *{s['week']}* 篇",
    ]
    if s["recent_titles"]:
        lines.append("   " + " · ".join(s["recent_titles"][:4]))
    if s["last_auto"]:
        lines.append(f"🤖 施工实录自动机: {s['last_auto'].split('] ',1)[-1]}")
    lines += [
        "",
        "🔗 " + C.BLOG_URL + "  |  作品墙 " + C.BLOG_URL + "/work.html",
        "",
        "*⚠️ 需要你拍板 (自动化搞不定的):*",
        "• Google Business Profile 优化 — 本地获客第一杠杆，还没做",
        "• (2周后) 看 Search Console 哪些词来了流量，定加文方向",
        "",
        "_自动系统在跑: 每日博客文(GitHub) + 每周施工实录(本机) + Bing/Google 自动推送_",
    ]
    return "\n".join(lines)


def main():
    url = slack_url()
    if not url:
        print("[digest] no Slack webhook"); return
    text = build(gather())
    r = requests.post(url, json={"text": text}, timeout=15)
    print(f"[digest] sent -> HTTP {r.status_code}")


if __name__ == "__main__":
    main()
