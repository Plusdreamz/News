# Iran Daily News Bot

RSS → تحلیل با Claude API → ارسال به کانال تلگرام، همه با GitHub Actions.

## راه‌اندازی
1. در تلگرام با @BotFather بات بساز و توکن را بگیر.
2. بات را به کانال اضافه کن و ادمین (با دسترسی ارسال پیام) کن.
3. ریپو را در GitHub بساز و فایل‌ها را push کن.
4. در Settings → Secrets and variables → Actions این سه secret را بساز:
   - `ANTHROPIC_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHANNEL_ID` (مثلاً `@mychannel`)
5. از تب Actions، workflow «Daily Iran News» را با Run workflow تست کن.

## نکته‌ها
- زمان اجرا در `.github/workflows/daily.yml` است؛ GitHub ممکن است چند دقیقه تأخیر بدهد.
- در ریپوی عمومی، اگر ۶۰ روز هیچ commit نباشد، cron غیرفعال می‌شود.
- منابع در `FEEDS` داخل `main.py` قابل تغییرند.
