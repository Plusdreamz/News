# Iran Daily News Bot

RSS → تحلیل با هر API سازگار با OpenAI → ارسال به کانال تلگرام، همه با GitHub Actions.

## راه‌اندازی
1. در تلگرام با @BotFather بات بساز و توکن را بگیر.
2. بات را به کانال اضافه کن و ادمین (با دسترسی ارسال پیام) کن.
3. ریپو را در GitHub بساز و فایل‌ها را push کن.
4. در Settings → Secrets and variables → Actions این secretها را بساز:
   - `AI_API_KEY` : کلید API
   - `AI_BASE_URL` : مثلاً `https://api.openai.com/v1` یا `https://openrouter.ai/api/v1` یا `https://api.deepseek.com`
   - `AI_MODEL` : نام مدل، مثلاً `gpt-4o-mini`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHANNEL_ID` (مثلاً `@mychannel`)
5. از تب Actions، workflow «Daily Iran News» را با Run workflow تست کن.

## نکته‌ها
- زمان اجرا در `.github/workflows/daily.yml` است؛ GitHub ممکن است چند دقیقه تأخیر بدهد.
- در ریپوی عمومی، اگر ۶۰ روز هیچ commit نباشد، cron غیرفعال می‌شود.
- منابع در `FEEDS` داخل `main.py` قابل تغییرند.

## رفتار
- هر خبر یک پست جدا است؛ تصویر از فید یا متاتگ `og:image` صفحهٔ خبر برداشته می‌شود و اگر پیدا نشد، پست بدون تصویر می‌آید.
- منبع هر خبر با لینک زیر پست ذکر می‌شود. فیدی که کار نکند رد می‌شود.
- متغیرهای اختیاری (Variables/Secrets): `TOP_N`، `MAX_PER_SOURCE`.
