import os, re, json, html, calendar
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import feedparser
import requests
from anthropic import Anthropic

# ---------- تنظیمات ----------
MODEL = os.getenv("AI_MODEL", "claude-sonnet-5-5")
TOP_N = int(os.getenv("TOP_N", "7"))
HOURS = int(os.getenv("HOURS", "26"))

FEEDS = [
    ("BBC Persian", "https://feeds.bbci.co.uk/persian/rss.xml"),
    ("Radio Farda", "https://www.radiofarda.com/api/zrqiteuuir"),
    ("IranWire", "https://iranwire.com/fa/feed/"),
    ("Iran International", "https://www.iranintl.com/feed"),
    ("Google News (EN)", "https://news.google.com/rss/search?q=Iran+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News (FA)", "https://news.google.com/rss/search?q=%D8%A7%DB%8C%D8%B1%D8%A7%D9%86+when:1d&hl=fa&gl=IR&ceid=IR:fa"),
]

TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT = os.environ["TELEGRAM_CHANNEL_ID"]  # مثل @mychannel یا -100xxxxxxxxxx


# ---------- جمع‌آوری اخبار ----------
def collect():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS)
    seen, items = set(), []
    for source, url in FEEDS:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        except Exception as e:
            print(f"[warn] {source}: {e}")
            continue
        for e in feed.entries[:40]:
            title = (e.get("title") or "").strip()
            link = e.get("link")
            if not title or not link:
                continue
            ts = e.get("published_parsed") or e.get("updated_parsed")
            if ts:
                dt = datetime.fromtimestamp(calendar.timegm(ts), timezone.utc)
                if dt < cutoff:
                    continue
            key = re.sub(r"\W+", "", title.lower())[:60]
            if key in seen:
                continue
            seen.add(key)
            summary = re.sub(r"<[^>]+>", "", e.get("summary", ""))[:300]
            items.append({"source": source, "title": title, "url": link, "summary": summary})
    print(f"[info] {len(items)} items collected")
    return items[:120]


# ---------- تحلیل با هوش مصنوعی ----------
def analyze(items):
    listing = "\n".join(
        f"[{i}] ({it['source']}) {it['title']} — {it['summary']}" for i, it in enumerate(items)
    )
    prompt = f"""این‌ها عناوین خبری ۲۴ ساعت اخیر مرتبط با ایران هستند:

{listing}

وظیفه:
1. {TOP_N} خبر مهم‌تر و متمایز را انتخاب کن (خبرهای تکراری یا حاشیه‌ای را حذف کن؛ مهم‌ترین‌ها: سیاسی، امنیتی، اقتصادی، هسته‌ای، روابط خارجی، تحولات اجتماعی بزرگ).
2. برای هر کدام خلاصهٔ دو جمله‌ای بی‌طرف و یک تحلیل کوتاه (۲ تا ۳ جمله: چرا مهم است و چه پیامدی دارد) به فارسی روان بنویس.
3. تفاوت واقعیت و ادعا را حفظ کن؛ اگر خبری از یک منبع و تأییدنشده است، صریح بگو.
4. فقط JSON معتبر برگردان، بدون هیچ متن اضافه:
[{{"id": <شماره خبر>, "title": "...", "summary": "...", "analysis": "..."}}]"""

    client = Anthropic()  # ANTHROPIC_API_KEY از محیط خوانده می‌شود
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system="تو تحلیلگر ارشد اخبار خاورمیانه هستی. دقیق، بی‌طرف و مختصر می‌نویسی.",
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"\[.*\]", text, re.S)
    data = json.loads(m.group(0))
    out = []
    for d in data:
        i = int(d["id"])
        if 0 <= i < len(items):
            out.append({**d, "url": items[i]["url"], "source": items[i]["source"]})
    return out


# ---------- قالب‌بندی و ارسال ----------
def build_messages(results):
    now = datetime.now(ZoneInfo("Asia/Tehran")).strftime("%Y-%m-%d")
    header = f"📰 <b>مهم‌ترین اخبار ایران — {now}</b>\n\n"
    blocks = []
    for n, r in enumerate(results, 1):
        e = html.escape
        blocks.append(
            f"<b>{n}. {e(r['title'])}</b>\n{e(r['summary'])}\n\n"
            f"🔎 <i>{e(r['analysis'])}</i>\n"
            f"🔗 <a href=\"{e(r['url'], quote=True)}\">{e(r['source'])}</a>\n"
        )
    msgs, cur = [], header
    for b in blocks:
        if len(cur) + len(b) > 3800:
            msgs.append(cur)
            cur = ""
        cur += b + "\n"
    msgs.append(cur)
    return msgs


def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={
            "chat_id": TG_CHAT,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    r.raise_for_status()


def main():
    items = collect()
    if not items:
        print("[info] no news, exiting")
        return
    results = analyze(items)
    for msg in build_messages(results):
        send(msg)
    print("[ok] posted", len(results), "items")


if __name__ == "__main__":
    main()
