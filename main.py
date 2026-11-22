import os, re, json, html, time, calendar
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import feedparser
import requests
from openai import OpenAI

# ---------- تنظیمات ----------
MODEL = os.getenv("AI_MODEL") or "gpt-4o-mini"
BASE_URL = os.getenv("AI_BASE_URL") or "https://api.openai.com/v1"
TOP_N = int(os.getenv("TOP_N", "7"))
MAX_PER_SOURCE = int(os.getenv("MAX_PER_SOURCE", "2"))
HOURS = int(os.getenv("HOURS", "26"))
UA = {"User-Agent": "Mozilla/5.0 (compatible; IranNewsBot/1.0)"}

# هر فید که کار نکند رد می‌شود و در لاگ نوشته می‌شود
FEEDS = [
    ("BBC Persian", "https://feeds.bbci.co.uk/persian/rss.xml"),
    ("DW Persian", "https://rss.dw.com/xml/rss-per-all_volltext"),
    ("Euronews Persian", "https://parsi.euronews.com/rss"),
    ("Radio Farda", "https://www.radiofarda.com/api/zrqiteuuir"),
    ("IranWire", "https://iranwire.com/fa/feed/"),
    ("Iran International", "https://www.iranintl.com/feed"),
    ("ISNA", "https://www.isna.ir/rss"),
    ("IRNA", "https://en.irna.ir/rss"),
    ("Tehran Times", "https://www.tehrantimes.com/rss"),
    ("Al-Monitor", "https://www.al-monitor.com/rss"),
    ("Reuters", "https://news.google.com/rss/search?q=Iran+site:reuters.com+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("AP", "https://news.google.com/rss/search?q=Iran+site:apnews.com+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News (EN)", "https://news.google.com/rss/search?q=Iran+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News (FA)", "https://news.google.com/rss/search?q=%D8%A7%DB%8C%D8%B1%D8%A7%D9%86+when:1d&hl=fa&gl=IR&ceid=IR:fa"),
]
STATE_MEDIA = {"ISNA", "IRNA", "Tehran Times"}

TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT = os.environ["TELEGRAM_CHANNEL_ID"]


# ---------- جمع‌آوری اخبار ----------
def rss_image(e):
    for key in ("media_content", "media_thumbnail"):
        for m in e.get(key, []) or []:
            if m.get("url"):
                return m["url"]
    for l in e.get("links", []):
        if l.get("rel") == "enclosure" and "image" in (l.get("type") or ""):
            return l.get("href")
    return None


def collect():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS)
    seen, items = set(), []
    for feed_name, url in FEEDS:
        try:
            feed = feedparser.parse(url, request_headers=UA)
        except Exception as ex:
            print(f"[warn] {feed_name}: {ex}")
            continue
        n_before = len(items)
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
            # در فیدهای گوگل نیوز، ناشر واقعی در e.source است
            src = (e.get("source") or {}).get("title") or feed_name
            summary = re.sub(r"<[^>]+>", "", e.get("summary", ""))[:300]
            items.append({"source": src, "title": title, "url": link,
                          "summary": summary, "image": rss_image(e)})
        print(f"[info] {feed_name}: {len(items) - n_before} items")
    return items[:150]


# ---------- تحلیل با هوش مصنوعی ----------
def analyze(items):
    listing = "\n".join(
        f"[{i}] ({it['source']}{' - رسانهٔ دولتی' if it['source'] in STATE_MEDIA else ''}) "
        f"{it['title']} — {it['summary']}"
        for i, it in enumerate(items)
    )
    prompt = f"""این‌ها عناوین خبری ۲۴ ساعت اخیر دربارهٔ ایران هستند:

{listing}

وظیفه:
۱. {TOP_N + 3} خبر مهم و متمایز انتخاب کن (سیاسی، امنیتی، اقتصادی، هسته‌ای، روابط خارجی، تحولات اجتماعی مهم). خبر تکراری یا حاشیه‌ای را حذف کن. از هر منبع حداکثر {MAX_PER_SOURCE} خبر بردار و تنوع منابع را حفظ کن.
۲. برای هر خبر بنویس:
   - title: عنوان فارسی کوتاه و روان
   - summary: خلاصهٔ ۲ تا ۳ جمله‌ای فقط شامل واقعیت‌های گزارش‌شده (چه کسی، چه کاری، کجا، کی)
   - context: یک جمله دربارهٔ اهمیت یا پیشینهٔ واقعی خبر (نه پیش‌بینی، نه قضاوت)
۳. قواعد بی‌طرفی (بسیار مهم):
   - هیچ نظر، موضع‌گیری یا ارزش‌گذاری اضافه نکن و نظر یا لحن جهت‌دار منبع را وارد متن نکن (کلماتی مثل «رژیم»، «ظالمانه»، «شکست‌خورده» و مشابه ممنوع است، مگر نقل‌قول مستقیم که باید نسبت داده شود).
   - ادعاها را به گوینده نسبت بده: «به گفتهٔ …»، «به گزارش …». اگر خبر از یک منبع است و تأیید مستقل ندارد، بنویس «تأییدنشده».
   - اگر منبع رسانهٔ دولتی است، با عبارت «به گزارش رسانه‌های دولتی ایران» نسبت بده.
   - چیزی از خودت اضافه نکن؛ فقط از متن داده‌شده استفاده کن.
۴. قواعد ترجمه و نگارش:
   - ترجمهٔ طبیعی و روان فارسی، نه تحت‌اللفظی؛ جمله‌ها کوتاه و رسمی-خبری.
   - نام اشخاص و مکان‌ها به املای رایج فارسی؛ اگر مطمئن نیستی، املای لاتین را در پرانتز بیاور. نام‌ها را تغییر نده.
   - عددها، تاریخ‌ها و عنوان‌ها را دقیق منتقل کن.
۵. فقط JSON معتبر برگردان، بدون هیچ متن دیگر:
[{{"id": <شماره>, "title": "...", "summary": "...", "context": "..."}}]"""

    client = OpenAI(api_key=os.environ["AI_API_KEY"], base_url=BASE_URL)
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=5000,
        temperature=0.2,
        messages=[
            {"role": "system", "content": "تو ویراستار و مترجم خبری بی‌طرف هستی. دقیق، خنثی و بدون نظر شخصی می‌نویسی."},
            {"role": "user", "content": prompt},
        ],
    )
    text = resp.choices[0].message.content or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\[.*\]", text, re.S)
    data = json.loads(m.group(0))

    out, per_source = [], {}
    for d in data:
        i = int(d["id"])
        if not (0 <= i < len(items)):
            continue
        it = items[i]
        if per_source.get(it["source"], 0) >= MAX_PER_SOURCE:
            continue
        per_source[it["source"]] = per_source.get(it["source"], 0) + 1
        out.append({**d, "url": it["url"], "source": it["source"], "image": it["image"]})
    return out[:TOP_N]


# ---------- تصویر ----------
def find_image(r):
    if r.get("image"):
        return r["image"]
    if "news.google.com" in r["url"]:
        return None  # لینک ریدایرکت است و تصویر درستی ندارد
    try:
        resp = requests.get(r["url"], headers=UA, timeout=12)
        pats = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        ]
        for p in pats:
            m = re.search(p, resp.text, re.I)
            if m:
                return urljoin(resp.url, html.unescape(m.group(1)))
    except Exception as ex:
        print(f"[warn] image {r['url']}: {ex}")
    return None


# ---------- تلگرام ----------
def tg(method, payload):
    r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/{method}", json=payload, timeout=30)
    if not r.ok:
        print(f"[tg:{method}] {r.status_code} {r.text[:200]}")
    return r.ok


def send_text(text):
    return tg("sendMessage", {"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML",
                              "disable_web_page_preview": True})


def send_post(r, n):
    e = html.escape
    title = f"<b>{n}. {e(r['title'])}</b>"
    body = (f"{e(r['summary'])}\n\n📌 {e(r['context'])}\n\n"
            f"🔗 <a href=\"{e(r['url'], quote=True)}\">{e(r['source'])}</a>")
    full = f"{title}\n\n{body}"
    img = find_image(r)
    if img:
        if len(full) <= 1000:
            if tg("sendPhoto", {"chat_id": TG_CHAT, "photo": img, "caption": full, "parse_mode": "HTML"}):
                return
        else:
            if tg("sendPhoto", {"chat_id": TG_CHAT, "photo": img, "caption": title, "parse_mode": "HTML"}):
                send_text(body)
                return
    send_text(full)


def main():
    items = collect()
    if not items:
        print("[info] no news, exiting")
        return
    results = analyze(items)
    date = datetime.now(ZoneInfo("Asia/Tehran")).strftime("%Y-%m-%d")
    send_text(f"📰 <b>مهم‌ترین اخبار ایران — {date}</b>")
    for n, r in enumerate(results, 1):
        send_post(r, n)
        time.sleep(3)
    print("[ok] posted", len(results), "items")


if __name__ == "__main__":
    main()
