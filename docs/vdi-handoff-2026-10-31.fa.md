# تحویل ادامهٔ راه‌اندازی Kara روی VDI — ۳۱ اکتبر ۲۰۲۶

این سند را به چت جدید بدهید. وضعیت‌ها از تصاویر و گزارش کاربر در گفتگوی ۲۹ تا ۳۰ اکتبر استخراج شده‌اند؛ در زمان تحویل، VDI به‌صورت زنده دوباره بررسی نشده است. بدون دریافت نتیجهٔ جدید، اجرای آزمون‌ها یا روشن‌بودن Runner را قطعی ندانید.

## هدف و روش ادامه

Kara روی VDI لینوکسی کاربر نصب شده است. هدف فعلی، تکمیل یک آزمون واقعی مدل و سپس آزمون دسترسی برنامه به سورس آماده‌شده است؛ نصب را از ابتدا تکرار نکنید.

- به فارسی و مرحله‌به‌مرحله راهنمایی کنید: در هر پاسخ فقط یک دستور کامل قابل کپی یا یک اقدام مشخص رابط، سپس منتظر تصویر/نتیجه بمانید.
- shell محلی Codex روی مک است؛ با ترمینال VDI یکی نیست. دستورهای `$HOME/Kara` باید در خود VDI اجرا شوند. از تغییر سورس محلی مک، تغییر VDI را نتیجه نگیرید.
- فایل‌های `sources/` در پوشهٔ مادر مک مرجع فقط‌خواندنی‌اند. دستورهای AGENTS.md مخزن محلی را پیش از تغییر بخوانید.
- توکن/رمز، کل فایل env، device.json و داده‌های خصوصی را درخواست یا در سند ثبت نکنید. TLS verification، validatorها یا کنترل‌های build را برای عبور از خطا خاموش نکنید.
- «کتابخانه» تعریف قابلیت، «برنامه» آماده‌کردن اجرا، و «فلو» همکاری انسانی است. فعلاً آزمون کوچک واقعی انجام دهید؛ اجرای تیمی کلاسور یا تأیید انسانی را انجام‌شده فرض نکنید.

## دقیقاً از این نقطه ادامه دهید

کاربر در Firefox داخل VDI، برنامهٔ ساخته‌شده از قالب `Chatflow Basic: Chatbot` را در ویرایشگر workflow باز کرده است:

```text
http://127.0.0.1:8080/app/c6501f4d-79ed-4447-abf4-bb20b1cd064c/workflow
```

گرهٔ LLM باز است. کادر مدل `gpt-5.4-mini` با برچسب «ناسازگار» و خطای زیر دیده شد:

```text
Provider langgenius/openai/openai does not exist
```

آخرین راهنمایی داده‌شده: «در پنل سمت چپ، روی کادر مدل که gpt-5.4-mini و ناسازگار دارد کلیک کن و تصویر فهرست را بفرست.» هنوز تصویر فهرست مدل یا پاسخ واقعی برنامه دریافت نشده است.

قالب پیش‌فرض به افزونهٔ OpenAI اشاره می‌کند؛ افزونهٔ موجود محیط `langgenius/openai_api_compatible` نسخهٔ `0.0.73` است. هدف، تغییر انتخاب مدل گره به مدل اتصال شخصی موجود است. وجود اتصال شخصی را با موجودبودن مدل در فهرست ویرایشگر یکسان ندانید؛ اگر فهرست خالی بود، همان تصویر و تنظیمات ارائه‌دهنده/مدل پروژه را بررسی کنید.

## وضعیت تأییدشده تا آخرین تصاویر

| بخش | نتیجه و محدودیت |
| --- | --- |
| نصب و وب | build موفق API و وب فارسی؛ حساب مدیر ساخته و ورود انجام شد |
| بانک | مهاجرت پایه با ایمیج اصلی موفق؛ سپس API و workerها شروع شدند |
| سلامت HTTP | ping داخل API و پورت 8080، هر دو `pong` |
| پروژه | کلاسور، شناسهٔ `81fc0c17-ba88-496f-a95d-ff1dc910e5d0` |
| جیرا | `https://jira.dotin.ir`؛ آزمون اتصال و احراز هویت موفق در تصویر |
| مدل | دو اتصال AIFA ثبت؛ کاربر گفت خطای آزمون با اصلاح توکن رفع شد؛ خروجی واقعی برنامه هنوز ثبت نشده |
| گیت‌لب | `https://gp.devpod.ir`؛ آزمون اتصال موفق و دریافت واقعی ۸ مخزن در آماده‌سازی نهایی |
| Runner | `Mahyar-VDI-Linux`؛ pairing و heartbeat موفق؛ backend گزارش‌شده docker؛ آزمون اجرای کد هنوز انجام نشده |
| worktree | `Clasor-Sandbox`، تعریف نسخهٔ ۶، هر ۸ بخش آماده با SHA ثبت‌شده |
| اتصال به اجرا | Runner فوق + نتیجهٔ آمادهٔ نسخهٔ ۶ ذخیره شد؛ پیام موفقیت در تصویر |
| برنامه | Chatflow Basic: Chatbot ساخته، هنوز منتشر نشده؛ مدل پیش‌فرض ناسازگار |

دو اتصال مدل: `AIFA-LLM-Sand-Assist` با نام مدل `AIFA-Sand-Assist-Model` (پیش‌فرض شخصی LLM در تصویر) و `AIFA-LLM-Sand-Dev` با نام مدل `AIFA-Sand-Dev-Model`. endpoint و توکن در این گفتگو ثبت نشده‌اند؛ آن‌ها را حدس نزنید. موفقیت اعلام‌شدهٔ آزمون اتصال، پاسخ واقعی workflow نیست.

## محیط و مسیرها

- VDI: Ubuntu 22.04.5 LTS amd64، ۵ CPU، ۲۳ GiB RAM؛ ارقام فضای آزاد ابتدای نصب‌اند و اکنون باید دوباره بررسی شوند.
- Docker 29.1.3، Compose 2.40.3؛ فرمان‌های Docker نصب با sudo انجام شدند.
- مخزن Kara روی VDI: `$HOME/Kara`، از `https://github.com/Mahyar1990/Kara.git`، شاخهٔ نصب `feat/program-team-settings`. SHA دقیق Kara روی VDI ثبت نشده است.
- مخزن محلی مک: `/Users/mahyar/Documents/Other Projects/CompanyAgentPlatform/company-agent-platform`؛ این checkout مستقل از VDI است.
- مبنای Dify: 1.17.1، commit `8387590ace4a094de812b7847fc6a4c3a27cd52b`. `.runtime/dify` را تغییر ندهید.
- Runner: `$HOME/kara-runner`، venv همان پوشه، Python میزبان ۳.۱۰؛ دادهٔ pairing خصوصی `~/.config/kara-source-runner/device.json`.
- مسیر سورس Runner: `$HOME/KaraSourceWorkspaces`؛ سورس روی VDI است، نه در filesystem مک.
- آدرس برنامه: `http://127.0.0.1:8080` داخل VDI. آدرس localhost مک و VDI را مخلوط نکنید.

اگر Runner متوقف بود، اجرای مجدد بدون pairing و بدون sudo:

```bash
cd "$HOME/kara-runner" && REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt .venv/bin/python -m kara_source_runner run
```

باید `Runner online` دیده شود؛ ترمینال را باز نگه دارید. یک‌بار Ctrl+C زده شد و Runner متوقف شد؛ بعد دوباره اجرا و آماده‌سازی نهایی موفق شد. اجرای دائمی/systemd تنظیم نشده است.

قالب فرمان Compose روی VDI:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" ps -a
```

آزمون محلی بدون پراکسی:

```bash
curl --noproxy '*' --fail --show-error --max-time 20 http://127.0.0.1:8080/console/api/ping
```

## worktree آماده و اتصال ذخیره‌شده

برنچ هر ۸ بخش `sandbox` است؛ پایهٔ URL همهٔ مخزن‌ها `https://gp.devpod.ir/pod/clasor/` است:

| مخزن | مسیر نسبی در worktree |
| --- | --- |
| `server.git` | `server/apps/server` |
| `chat.git` | `server/apps/chat` |
| `pdf-generator.git` | `server/apps/pdf-generator` |
| `client.git` | `client` |
| `clasor-main-editor.git` | `editors/clasor-main-editor` |
| `client-excel-editor.git` | `editors/client-excel-editor` |
| `clasor-office-server.git` | `office/clasor-office-server` |
| `clasor-office-client.git` | `office/clasor-office-client` |

نتیجهٔ موفق نسخهٔ ۶: `d95ed254-6dc4-4f39-acae-4f8d92439693`؛ مسیر موردانتظار بر اساس ریشهٔ گزارش‌شدهٔ Runner:

```text
/home/m.zhiani/KaraSourceWorkspaces/d95ed254-6dc4-4f39-acae-4f8d92439693
```

شناسه و SHA هر ۸ مخزن در کارت «آماده» نمایش داده شدند؛ برای SHA دقیق، همان نتیجه/manifest را بخوانید و با sandbox جاری جایگزین نکنید. در «Runnerهای شخصی ← ویرایش مقصد» دستگاه `Mahyar-VDI-Linux` و سورس `Clasor-Sandbox نسخهٔ ۶` انتخاب و «ذخیرهٔ مقصد اجرا» زده شد. تصویر آخر پیام موفقیت و انتخاب ذخیره‌شده را تأیید می‌کند. این عمل اجرای کلاسور یا دسترسی نوشتن به سورس را اثبات نمی‌کند.

تلاش ناموفق قبلی: نسخهٔ ۳، job `0a6c3ba2-3b65-4933-aa7a-dbcd64c5baba`. اشتباه مخزن `clasor-excel-editor.git` بود؛ کاربر آن را به `client-excel-editor.git` اصلاح کرد و تعریف worktree را ذخیره کرد. تاریخچهٔ ناموفق باقی می‌ماند؛ آن را خطای جاری نتیجهٔ موفق ندانید. پوشه‌های تلاش قبلی حذف نشدند.

## رفع خطاهای انجام‌شده؛ دوباره از صفر شروع نکنید

- apt/APK سازمان 403 می‌دادند؛ bootstrap با ایمیج کامل `python:3.12-bookworm` انجام شد که Git و zoneinfo دارد.
- کاتالوگ template با fetch صریح commit `fa94108ce3c39a0b96a9377a323b15db147ca88f` تأمین شد.
- Weaviate از Docker Hub رسمی دریافت و به نام رجیستری موردانتظار tag شد؛ خطای لایه‌های دانلود با pull مستقل/ترتیبی رفع شد؛ prune انجام نشد.
- ساخت وب با timezone از Python کامل، CA میزبان، نصب مستقیم `pnpm@12.3.4` و registry صریح Nexus موفق شد. فقط Dockerfile تولیدشدهٔ `.runtime/dify-web-source/.company-web` روی VDI اصلاح شد؛ setup بعدی ممکن است آن را بازنویسی کند. تنظیمات قابل‌تکرار جدید در [deployment](deployment.md) موجود است؛ اعمال یا به‌روزرسانی VDI با آن‌ها در این گفتگو تأیید نشده است.
- npm داخلی مشاهده‌شده `https://nexus3.dotin.ir/repository/Dotin-NPM/`؛ pip Runner از `https://nexus3.dotin.ir/repository/pypi-proxy/simple/` استفاده کرد.
- خطای `tenant_account_joins does not exist` با توقف api/worker/worker_beat/api_websocket، اجرای `flask db upgrade` با `langgenius/dify-api:1.17.1` و شروع مجدد رفع شد؛ این کار را بی‌علت تکرار نکنید.
- Marketplace روی میزبان ۲۰۰ ولی API خطای self-signed chain داشت. CA میزبان برای پنج سرویس runtime mount شد؛ فایل محلی `infra/compose.vdi-ca.yaml` در root compose بعد از `.runtime/compose.build.json` اضافه شد. envهای REQUESTS_CA_BUNDLE/SSL_CERT_FILE/PIP_CERT به `/etc/ssl/certs/ca-certificates.crt` اشاره می‌کنند. Compose validate و recreate شدند؛ سپس API بدون verify صریح پاسخ ۲۰۰ داد و افزونه نصب شد. این تغییر روی VDI بود؛ وجودش در checkout مک را فرض نکنید.
- خطای آزمون LLM با اصلاح توکن، طبق گزارش خود کاربر رفع شد. توکن یا endpoint در سند نیست.
- تست Git بدون token پاسخ ۴۰۱ طبیعی داشت؛ با token پاسخ smart-HTTP ۲۰۰ و ls-remote مخزن server موفق بود. مخزن Excel به علت typo پیدا نمی‌شد؛ مشکل آن حل شد. تغییرمسیر trailing slash به‌تنهایی علت قطعی نبود.

## کارهای باقی‌مانده، به ترتیب

1. تصویر فعلی/فهرست مدل گرهٔ LLM را بگیرید و مدل قالب را به ارائه‌دهنده و مدل سازگار با اتصال شخصی موجود تغییر دهید؛ انتخاب موفق هنوز رخ نداده است.
2. یک پیام ساده در «اشکال‌زدایی و پیش‌نمایش» اجرا و پاسخ واقعی مدل و وضعیت اجرا را ثبت کنید. آزمون اتصال قبلی را جای این آزمون نگذارید. خطای جدید را با نتیجهٔ Runner و لاگ مرتبط بررسی کنید.
3. آزمون مستقل خواندن فایل‌های سورس متصل را با ابزار/مرحلهٔ مناسب Runner انجام دهید؛ Chatbot ساده خودبه‌خود فایل‌ها را نمی‌خواند. مسیر نسبی، یک شاهد واقعی و commit منبع را ثبت کنید؛ ادعای دسترسی از روی ذخیرهٔ تنظیم نکنید.
4. اجرای واقعی حداقلی کد با backend Docker و مجوز socket کاربر Runner را بررسی کنید. فقط پیام backend docker دیده شده؛ این پذیرش باقی است. برای آزمون خواندن، نوشتن روی worktree را فعال نکنید؛ نیاز نوشتن باید جداگانه مشخص شود.
5. پس از موفقیت smoke، برنامهٔ متناسب با کار واقعی کاربر را انتخاب/آماده کنید؛ انتشار، اجرای تیمی، تحلیل اختصاصی کلاسور، push/merge هنوز انجام نشده‌اند. تأیید PO و merge TL انسانی می‌مانند.
6. پایداری Runner پس از بستن ترمینال، logout و reboot: هنوز تنظیم/آزمایش نشده؛ در صورت نیاز سرویس کاربری با CA و همان هویت دستگاه طراحی شود.
7. موجودی و backup قابل‌بازیابی از DB، داده‌ها و تنظیم خصوصی + آزمون restore؛ انجام نشده است. پاک‌کردن volume یا runtime مجاز نشده است.
8. ثبت SHA واقعی Kara در VDI و وضعیت تغییرات محلی قبل از هر update؛ بررسی سازگاری راهنمای استقرار جدید، حفظ CA runtime و اصلاحات generated build. نصب مجدد کامل یا update خودکار لازم نیست.
9. `make doctor` روی VDI، پذیرش تمام سرویس‌ها و در صورت نیاز تست جیرا با درخواست واقعی، GitLab فراتر از خواندن، اجرای چندحسابی و VDI دوم؛ هنوز تأیید نشده‌اند. دامنهٔ بعدی را مطابق هدف کاربر محدود نگه دارید.

## مراجع چت جدید

- [نصب VDI و رفع خطاهای واقعی](vdi-installation.fa.md)
- [استقرار قابل‌تکرار و تنظیمات جدید](deployment.md)
- [سورس کد و Runner](source-code-runner.md)
- [اجرای محلی](local-execution.md)
- [اتصال‌های شخصی مدل](personal-model-connections.md)
- [انتخاب مدل هنگام اجرای برنامه](program-runtime-model.md)

پیشنهاد پیام شروع چت جدید: «سند تحویل VDI را بخوان؛ از تغییر مدل گرهٔ LLM در Chatflow Basic: Chatbot ادامه بده. در هر قدم فقط یک دستور یا اقدام بده و منتظر تصویر من بمان. نصب، Jira، GitLab و worktree نسخهٔ ۶ قبلاً انجام شده‌اند؛ اکنون پاسخ واقعی برنامه و خواندن سورس را می‌خواهیم ثابت کنیم.»
