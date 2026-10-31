# تحویل ادامهٔ راه‌اندازی Kara روی VDI — ۳۱ اکتبر ۲۰۲۶

سند زندهٔ تحویل برای ادامهٔ کار است؛ این نسخه نصب اولیه و ادامهٔ رفع خطا/ارتقای ۳۰ تا ۳۱ اکتبر ۲۰۲۶ را پوشش می‌دهد. شواهد VDI از تصاویر و گزارش کاربرند؛ ویرایش این سند به معنی بررسی زندهٔ دوبارهٔ VDI نیست. هر ترد، کارهای انجام‌شده و پیگیری‌ها را با حفظ مرز شواهد به‌روز کند.

## هدف و روش ادامه

Kara روی VDI لینوکسی کاربر نصب شده است. آزمون اولیهٔ واقعی مدل در Workflow موفق شد؛ هدف بعدی آزمون اجرای کد و دسترسی برنامه به سورس آماده‌شده است. نصب را از ابتدا تکرار نکنید.

- به فارسی و مرحله‌به‌مرحله راهنمایی کنید: در هر پاسخ فقط یک دستور کامل قابل کپی یا یک اقدام مشخص رابط، سپس منتظر تصویر/نتیجه بمانید.
- shell محلی Codex روی مک است؛ با ترمینال VDI یکی نیست. دستورهای `$HOME/Kara` باید در خود VDI اجرا شوند. از تغییر سورس محلی مک، تغییر VDI را نتیجه نگیرید.
- فایل‌های `sources/` در پوشهٔ مادر مک مرجع فقط‌خواندنی‌اند. دستورهای AGENTS.md مخزن محلی را پیش از تغییر بخوانید.
- توکن/رمز، کل فایل env، device.json و داده‌های خصوصی را درخواست یا در سند ثبت نکنید. TLS verification و validatorهای امنیت/خروجی را برای عبور از خطا خاموش نکنید. تست کلاینتی فعلاً به درخواست کاربر اجرا نشود؛ در build ارتقای اخیر، فقط با درخواست صریح کاربر `KARA_WEB_SKIP_CHECKS=true` استفاده شد. build وب با آزمون رابط یا اجرای مدل یکی نیست.
- «کتابخانه» تعریف قابلیت، «برنامه» آماده‌کردن اجرا، و «فلو» همکاری انسانی است. فعلاً آزمون کوچک واقعی انجام دهید؛ اجرای تیمی کلاسور یا تأیید انسانی را انجام‌شده فرض نکنید.

## نقطهٔ فعلی و اولویت ادامه

نصب مجدد لازم نیست. در ادامهٔ ۳۱ اکتبر، شش کامیت تا `9e88cc4` با درخواست کاربر منتشر و با fast-forward روی VDI دریافت شدند. دو اصلاح دستی CA و migration در stash جدا حفظ و با سورس رسمی جایگزین شدند. CA سرویس‌های runtime دوباره تنظیم شد؛ درخواست Marketplace از API پاسخ ۲۰۰ داد. API پس از زمان راه‌اندازی، مستقیم و از Nginx پاسخ `pong` داد و `doctor --server-only` روی VDI موفق شد.

Runner با همان pairing قبلی و آدرس loopback دوباره online شد. مسیر HTTPS مدل روی همان IP قبلی پاسخ ۲۰۰ داد؛ اعتبارسنجی Assist در پروژهٔ کلاسور موفق شد. Workflow جدید «آزمون مدل روی VDI» خروجی واقعی `{"answer":"12"}` داد: ۳ گام، ۳۷٫۰۸۸ ثانیه و ۱۰۸۵ توکن گزارش‌شده. اولویت بعدی، بررسی دسترسی Docker بدون sudo و آزمون مستقل خواندن سورس است؛ انتخاب سورس هنگام اجرای مدل، خواندن واقعی فایل‌ها را ثابت نمی‌کند.

## وضعیت تأییدشده و حدود

| بخش | نتیجه و محدودیت |
| --- | --- |
| ارتقای Kara | سورس VDI روی `9e88cc4`؛ تنظیمات محلی CA و loopback در Compose؛ تصاویر API طبق doctor جاری |
| بانک و API | migration و init_permissions با کد صفر؛ API و PostgreSQL healthy؛ ping شبکه pong |
| شبکه و همکاری | آدرس canonical شبکه تنظیم شد؛ ایراد token ناشی از اختلاف host و خطای application context رفع شدند؛ کاربر رفع همگام‌سازی دو طرف را تأیید کرد |
| پروژه | کلاسور، `81fc0c17-ba88-496f-a95d-ff1dc910e5d0` |
| جیرا | آزمون احراز هویت تاریخی موفق؛ درخواست واقعی گسترده تأیید نشده |
| گیت‌لب و سورس | آزمون تاریخی موفق؛ هر ۸ مخزن نسخهٔ ۶ آماده و به مقصد متصل شدند |
| Runner | `Mahyar-VDI-Linux` دوباره online؛ همان pairing و URL قبلی؛ اجرای Workflow مدل موفق؛ مجوز و اجرای واقعی Docker هنوز بررسی نشده |
| مدل در ویرایشگر | هر دو مدل شخصی نمایش داده شدند؛ Assist انتخاب شد و هشدار کاذب ناسازگار به CHAT تغییر کرد |
| آزمون واقعی مدل | Workflow با Assist، temperature صفر و max_tokens برابر ۱۲۸ موفق؛ خروجی answer برابر 12؛ علت شکست قبلی با ۰٫۷ قطعی نیست |
| برنامهٔ فعلی | Workflow «آزمون مدل روی VDI»، شناسهٔ `607685e4-3657-46c6-a853-f58669341ec7`؛ پیش‌نویس، منتشر نشده؛ Chatflow قبلی همچنان پشتیبانی نمی‌شود |
| پشتیبان | dump بانک و تنظیمات تهیه و pg_restore --list موفق؛ restore واقعی و پشتیبان کامل داده‌های جانبی باقی است |

Workflow موفق فعلی:

```text
http://10.20.168.117:8080/app/607685e4-3657-46c6-a853-f58669341ec7/workflow
```

برنامهٔ Chatflow قبلی، با محدودیت اجرای محلی:

```text
http://10.20.168.117:8080/app/c6501f4d-79ed-4447-abf4-bb20b1cd064c/workflow
```

پیش‌فرض قالب `gpt-5.4-mini` با provider غایب `langgenius/openai/openai` بود. اکنون `AIFA-Sand-Assist` انتخاب شده است. دو اتصال `AIFA-LLM-Sand-Assist` و `AIFA-LLM-Sand-Dev` به provider `langgenius/openai_api_compatible/openai_api_compatible` مربوط‌اند. نام مدل ذخیره‌شده Assist برابر `AIFA-Sand-Assist-Model` و نام واقعی آن در سرویس `assistance-model` است؛ نام نمایشی را با شناسهٔ فراخوانی یکسان نگیرید.

## محیط و مسیرها

- VDI: Ubuntu 22.04.5 LTS amd64، ۵ CPU، ۲۳ GiB RAM؛ ارقام فضای آزاد ابتدای نصب‌اند و اکنون باید دوباره بررسی شوند.
- Docker 29.1.3، Compose 2.40.3؛ فرمان‌های Docker نصب با sudo انجام شدند.
- مخزن Kara روی VDI: `$HOME/Kara`، از `https://github.com/Mahyar1990/Kara.git`، شاخهٔ نصب `feat/program-team-settings`. آخرین SHA کوتاه دریافت‌شده `9e88cc4` است؛ تغییرات محلی Compose نیز جداگانه حفظ شوند.
- مخزن محلی مک: `/Users/mahyar/Documents/Other Projects/CompanyAgentPlatform/company-agent-platform`؛ این checkout مستقل از VDI است.
- مبنای Dify: 1.17.1، commit `8387590ace4a094de812b7847fc6a4c3a27cd52b`. `.runtime/dify` را تغییر ندهید.
- Runner: `$HOME/kara-runner`، venv همان پوشه، Python میزبان ۳.۱۰؛ دادهٔ pairing خصوصی `~/.config/kara-source-runner/device.json`.
- مسیر سورس Runner: `$HOME/KaraSourceWorkspaces`؛ سورس روی VDI است، نه در filesystem مک.
- آدرس canonical برنامه: `http://10.20.168.117:8080` برای مدیر و همکاران. در ادامهٔ همین روز، binding اضافی `127.0.0.1:8080` برای Runner همان VDI تنظیم و ping آن موفق شد؛ پورت ۸۴۴۳ همچنان روی IP شبکه است. کوکی میزبان‌ها مستقل است؛ localhost مک به VDI اشاره نمی‌کند.

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
curl --noproxy '*' --fail --show-error --max-time 20 http://10.20.168.117:8080/console/api/ping
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
- ساخت وب با timezone از Python کامل، CA میزبان، نصب مستقیم `pnpm@12.3.4` و registry صریح Nexus موفق شد. این‌ها اصلاحات تاریخی generated Dockerfile بودند؛ در ارتقای اخیر با تنظیمات رسمی `.env.local` و setup جدید جایگزین شدند. اصلاح دستی قدیمی را پس از setup تکرار نکنید؛ مسیر جاری در [deployment](deployment.md) است.
- npm داخلی مشاهده‌شده `https://nexus3.dotin.ir/repository/Dotin-NPM/`؛ pip Runner از `https://nexus3.dotin.ir/repository/pypi-proxy/simple/` استفاده کرد.
- خطای `tenant_account_joins does not exist` با توقف api/worker/worker_beat/api_websocket، اجرای `flask db upgrade` با `langgenius/dify-api:1.17.1` و شروع مجدد رفع شد؛ این کار را بی‌علت تکرار نکنید.
- Marketplace روی میزبان ۲۰۰ ولی API خطای self-signed chain داشت. CA میزبان برای پنج سرویس runtime mount شد؛ فایل محلی `infra/compose.vdi-ca.yaml` در root compose بعد از `.runtime/compose.build.json` اضافه شد. envهای REQUESTS_CA_BUNDLE/SSL_CERT_FILE/PIP_CERT به `/etc/ssl/certs/ca-certificates.crt` اشاره می‌کنند. Compose validate و recreate شدند؛ سپس API بدون verify صریح پاسخ ۲۰۰ داد و افزونه نصب شد. این تنظیم تاریخی در stash محفوظ شد؛ در ارتقای جدید compose اصلی از ریموت جایگزین شد و این overlay یکجا برگردانده نشد. حفظ trust runtime برای درخواست‌های آیندهٔ Marketplace/API باید جداگانه بررسی شود؛ موفقیت build با CA، اثبات حفظ mount runtime نیست.
- رفع خطای توکن مربوط به گزارش تاریخی کاربر بود؛ آزمون‌های جدید اتصال مدل شکست خوردند. اطلاعات شبکهٔ بعدی در بخش تشخیص مدل آمده است؛ توکن در سند نیست.
- تست Git بدون token پاسخ ۴۰۱ طبیعی داشت؛ با token پاسخ smart-HTTP ۲۰۰ و ls-remote مخزن server موفق بود. مخزن Excel به علت typo پیدا نمی‌شد؛ مشکل آن حل شد. تغییرمسیر trailing slash به‌تنهایی علت قطعی نبود.

## ارتقای انجام‌شده، تنظیمات خصوصی و وضعیت انتشار

شاخهٔ همهٔ کارها `feat/program-team-settings` است. انتشار و pull اولیه تا `9a40d78` بود؛ در ادامهٔ ۳۱ اکتبر، چهار کامیت اصلاحی زیر به‌همراه دو کامیت مستندات `6024f34` و `9e88cc4` منتشر و روی VDI دریافت شدند. وضعیت ریموت در زمان ادامه دوباره خوانده شود:

| کامیت | تغییر |
| --- | --- |
| `5335cc9` | خواندن CA با cafile در OpenSSL به جای decode اجباری ASCII |
| `bf8f6cd` | اصلاح اولیهٔ دریافت محیط بانک در migration |
| `81d793b` | تست رد PEM خراب/ناقص یا کلید خصوصی پس از گواهی معتبر |
| `bcd6651` | تکمیل migration با ارث‌بری صریح API upstream و فایل‌های اختیاری محیط |

کامیت `6024f34` سند تحویل ترد قدیمی‌تر و `9e88cc4` تطبیق دو سند را ثبت کرده‌اند؛ آمار ahead را ثابت فرض نکنید. اصلاح WebSocket در `5055d7b` و انتخابگر در `d499489` و `9a40d78` قبلاً منتشر شده‌اند. انتخابگر به summary مشترک وابسته نیست؛ مسیرهای مشترک اعتبارنامه در backend باز نشده‌اند.

قبل از pull، تغییرات tracked/untracked VDI با نام زیر stash شدند:

```text
vdi-before-remote-update-2026-10-30
```

**stash را یکجا apply/pop نکنید.** شامل compose قدیمی، CA runtime، اصلاح install.py و overlay دستی انتخابگر است. overlay می‌تواند patch رسمی را بازنویسی کند. فایل‌های ignored `.runtime` در stash جابه‌جا نشدند.

تنظیمات خصوصی `$HOME/Kara/.env.local` ساخته شدند؛ برای مقادیر همین VDI و دستورهای بازتولید به [راهنمای نصب](vdi-installation.fa.md#تنظیمات-پایدار-همین-vdi) مراجعه کنید. IP، registry داخلی و CA به سورس عمومی hardcode نشوند.

دو تغییر دستی قبلی که اکنون در stash جدید `vdi-manual-ca-migration-before-update-2026-10-31` حفظ و با نسخهٔ رسمی جایگزین شده‌اند:

- `scripts/build_environment.py`: استفاده از `context.load_verify_locations(cafile=str(source))`. فایل سیستم ۱۲۵ marker و بایت غیر ASCII داشت؛ OpenSSL آن را با ۱۲۳ گواهی بارگذاری کرد. عدد marker معیار تعداد گواهی یکتا نیست و علت اختلاف تعداد جداگانه بررسی نشده است. TLS غیرفعال نشد.
- `infra/compose.local.yaml`: افزودن env_file مطلق `/home/m.zhiani/Kara/.runtime/compose.env` به migration. پیش از آن تمام DB متغیرها غایب بودند و localhost:5432 رد می‌شد؛ پس از اصلاح مقصد db_postgres:5432 و اجرای migration موفق بود. نسخهٔ عمومی نهایی در `bcd6651` به‌جای مسیر مطلق از `extends.file: docker-compose.yaml` استفاده می‌کند تا `.env` و فایل‌های اختیاری upstream را بگیرد.

پشتیبان پیش از ارتقا:

```text
/home/m.zhiani/Kara/.runtime/update-backups/20261030-234607
```

فایل‌های `env.local`، `compose.env`، `compose.build.json`، `database.dump` و `database-list.txt` نگهداری شدند. dump با `pg_dump -Fc` ساخته و فهرست با `pg_restore --list` خوانده شد؛ restore واقعی تست نشده و این پشتیبان، snapshot کامل فایل‌های آپلود/دانش/worktree نیست. نسخه‌های اصلی دو فایل اصلاح‌شده هم در زیرپوشه‌های زمان‌دار همین update-backups محفوظ‌اند.

## تشخیص مدل و چت‌فلو؛ دو مسئلهٔ مستقل

موارد زیر تشخیص تاریخی پیش از اجرای موفق Workflow هستند. وضعیت جدید در بخش «ادامهٔ تأییدشدهٔ ۳۱ اکتبر» ثبت شده: مسیر HTTPS و اعتبارسنجی Assist اکنون موفق‌اند و Workflow پاسخ واقعی داده است؛ محدودیت advanced-chat باقی است.

1. پیش‌نمایش برنامه در `local_dispatch.submit` پیش از تماس با مدل رد شد؛ شرط فعلی فقط `app.mode == 'workflow'` را می‌پذیرد. برنامهٔ فعلی `advanced-chat` است. خطای BadRequest به 500 تبدیل شد. پشتیبانی چت‌فلو پیاده‌سازی نشده؛ حذف شرط به‌تنهایی راه‌حل نیست.
2. آزمون مستقل اتصال شخصی روی Runner انجام شد. ردیف‌های جدید `local_rpc` با `model_request_failed` failed بودند و یک ردیف قدیمی‌تر succeeded بود. مسیر خطا `model_client_boundary → local_rpc.model_call → local_rpc.wait` است؛ خطای generic، HTTP/TLS دقیق را ثابت نمی‌کند.
3. Base URL مشاهده‌شدهٔ Assist: `https://aifa-chatbot.sandpod.ir/v1`؛ DNS در VDI برابر `79.132.215.248`. درخواست بدون توکن به `/v1/models` با curl هم با noproxy و هم بدون آن، Connection refused روی 443 و HTTP=000 داد. اتصال هنوز به بررسی توکن/TLS نرسیده است؛ صحت DNS یا وضعیت سرویس مقصد تأیید نشده. قرار است با دستگاهی که همان مدل روی آن کار می‌کند مقایسه شود.
4. پاسخ `200` فهرست مدل‌های شخصی، activeبودن metadata یا نمایش CHAT اثبات اجرای مدل نیست. summary/credits ممکن است از مصرف‌کنندگان دیگر رابط همچنان 403 دهند؛ guard شخصی را برای حذف پیام باز نکنید.

## بررسی کد محلی و پذیرش VDI

آخرین `make check` در این ترد ۷۹ تست Python موفق داشت. تست migration نبود DB_HOST و سپس نبود تنظیم اختیاری API را پیش از اصلاح در هر دو مسیر Compose/Make بازتولید کرد و نسخهٔ نهایی موفق شد. تنظیمات بانک، Redis و SECRET_KEY در Compose واقعی محلی تطبیق داده شدند، بدون چاپ رمز. تست CA توضیح غیر ASCII را می‌پذیرد و PEM خراب/ناقص یا private key را رد و آخرین ورودی ساخت معتبر را حفظ می‌کند.

تست کلاینت یا build جدید در بررسی محلی اجرا نشد. `doctor --server-only` در بررسی‌های قبلی به‌دلیل قدیمی‌بودن تصویر API محلی مک کامل نشد؛ این را به VDI تعمیم ندهید. روی VDI build API/وب با skip checks به درخواست کاربر موفق، سرویس‌ها بررسی و کلاینت توسط خود کاربر تأیید شد. این گزارش شامل پذیرش Runner جدید، مدل یا چت‌فلو نیست.

## کارهای باقی‌مانده، به ترتیب

1. آزمون مستقل خواندن فایل‌های worktree نسخهٔ ۶ و اجرای حداقلی کد Docker روی Runner باقی است. ابتدا دسترسی Docker با حساب کاربر و بدون sudo بررسی شود؛ backend برابر docker، مجوز socket یا وجود تصویر کد را ثابت نمی‌کند. نوشتن/push/merge مجاز یا تأییدشده فرض نشود.
2. انتشار شش کامیت، دریافت روی VDI، جایگزینی دو اصلاح دستی و آزمون اولیهٔ مدل انجام شدند. تنظیمات محلی CA/loopback، دو stash و backupها را حفظ کنید؛ stash قدیمی و overlay انتخابگر را کامل برنگردانید. وضعیت نهایی Git پس از تغییرهای محلی Compose هنوز خوانده نشده است.
3. علت `model_request_failed` اجرای اول با temperature برابر ۰٫۷ قطعی نیست؛ اجرای بعدی با صفر موفق شد. در صورت نیاز به تشخیص بیشتر، فقط خطای غیرمحرمانهٔ HTTP/پاسخ را بررسی کنید؛ نتیجهٔ موفق را بی‌دلیل دوباره اجرا نکنید.
4. پشتیبانی advanced-chat مستقل باقی است؛ Workflow موفق به معنی رفع محدودیت Chatflow نیست. انتشار Workflow آزمایشی نیز انجام نشده است.
5. پایداری Runner پس از بسته‌شدن ترمینال، logout و reboot، و تطبیق کامل بستهٔ نصب‌شده با سورس جدید هنوز بررسی نشده است. pairing مجدد را بی‌علت انجام ندهید.
6. restore واقعی در محیط مجزا و پشتیبان داده‌های جانبی باقی است؛ backup بانک انجام شده را دوباره «انجام‌نشده» گزارش نکنید.
7. doctor سمت سرور روی VDI پس از اصلاح CA و پیش از افزودن loopback موفق شد؛ پس از تغییر Nginx فقط Compose و ping loopback بررسی شدند. درخواست واقعی Jira، GitLab فراتر از خواندن، VDI دوم و پذیرش گستردهٔ چندحسابی/بار فقط در دامنهٔ درخواست بعدی بررسی شوند.

## ادامهٔ تأییدشدهٔ ۳۱ اکتبر؛ CA، Runner و پاسخ واقعی مدل

- پیش از انتشار، fetch زندهٔ GitHub، `make check` با ۷۹ آزمون، اعتبارسنجی Compose و `git diff --check` روی مک موفق شدند. push تا `9e88cc4` و همگامی صفر/صفر شاخه تأیید شد؛ هیچ master یا force push انجام نشد.
- روی VDI، stash قدیمی شش فایل داشت: Compose اصلی، install.py، compose.local، CA runtime و دو فایل انتخابگر. اصلاح app context با سورس رسمی یکسان بود؛ binding قبلی IP با تنظیمات خصوصی جدید پوشش داده شده بود. فقط `infra/compose.vdi-ca.yaml` از والد فایل‌های untracked stash قدیمی بازیابی شد. پس از stash جدید، قدیمی در آن زمان `stash@{1}` بود؛ این شماره را برای آینده ثابت فرض نکنید.
- مسیر CA بعد از `.runtime/compose.build.json` در include اصلی اضافه شد. نسخهٔ پیشین Compose در `.runtime/update-backups/20261031-121618-776998/compose.yaml` محفوظ شد. پنج سرویس api/worker/worker_beat/api_websocket/plugin_daemon بدون build و بدون وابستگی‌ها بازآفرینی شدند؛ درخواست Marketplace قبل از آن خطای self-signed chain و بعد از آن HTTP 200 داد.
- ابتدا Nginx پاسخ ۵۰۲ و ping مستقیم API timeout داشت. لاگ سپس migration موفق و شروع Gunicorn را نشان داد؛ با تکمیل راه‌اندازی، هر دو ping مستقیم و شبکه `pong` شدند. برای این مورد reload اضافی Nginx یا build انجام نشد. `doctor --server-only` سپس موفق و API healthy بود؛ پیام pinned provider not installed مربوط به بررسی نسخهٔ مشخص SDK بود، نه اثبات نبود افزونهٔ OpenAI-compatible نصب‌شده.
- Runner ابتدا خاموش بود و پس از اجرا پیام عمومی stopped داد. فایل تنظیمات موجود، بدون symlink و با مجوز ۶۰۰ بود؛ فقط origin بدون secret بررسی شد: `http://127.0.0.1:8080`. بستهٔ نصب‌شده HTTP غیرloopback را رد می‌کند؛ server در owner_id سورس نیز نقش دارد. آدرس و pairing تغییر نکردند. در فایل محلی CA یک binding اضافی Nginx به `127.0.0.1:${EXPOSE_NGINX_PORT:-8080}:80` افزوده شد؛ backup آن در `.runtime/update-backups/20261031-122946-311457/compose.vdi-ca.yaml` است. Compose هر دو binding شبکه و loopback را نشان داد؛ Nginx جدا بازآفرینی و ping loopback موفق شد. سپس Runner با همان دستور قبلی و بدون sudo online شد.
- curl بدون توکن و با noproxy به `/v1/models` این بار HTTP 200 از `79.132.215.248` داد؛ علت تغییر شبکه نسبت به Connection refused تاریخی معلوم نیست. خطای نبود افزونه ابتدا متعلق به پروژهٔ دیگری بود؛ بازگشت به کلاسور و آزمون اتصال Assist موفق شد. نصب مجدد افزونه انجام نشد.
- Workflow جدید مسیر `شروع → مدل زبانی بزرگ → پایان` دارد. پیام سیستم: «پاسخ‌ها را کوتاه و به زبان فارسی بنویس.»؛ USER: «حاصل جمع ۷ و ۵ را فقط با رقم انگلیسی بنویس. هیچ توضیح دیگری اضافه نکن.»؛ خروجی پایان `answer` از text مدل است. Assist و `Mahyar-VDI-Linux` انتخاب شدند و سورس آمادهٔ Clasor-Sandbox نیز در فرم انتخاب بود. اجرای اول با temperature برابر ۰٫۷ و max_tokens برابر ۱۲۸ در ۱۵٫۷۱۰ ثانیه با `model_request_failed` شکست خورد؛ مجموع صفر توکن/گامِ گزارش شکست، اثبات نرسیدن درخواست به سرویس نیست. پس از تغییر فقط temperature به صفر، اجرای موفق ساعت ۱۲:۵۳ محلی خروجی `{"answer":"12"}`، ۳ گام، ۳۷٫۰۸۸ ثانیه و ۱۰۸۵ توکن نشان داد. این عدد کل توکن‌هاست و با سقف توکن پاسخ یکسان نیست. علت شکست اول هنوز قطعی نیست.
- این شواهد شامل اجرای مدل از Workflow است؛ خواندن فایل سورس، اجرای کد Docker، پشتیبانی Chatflow، انتشار برنامه یا پذیرش تیمی را ثابت نمی‌کند. runtime CA نیز فقط از مسیر درخواست API به Marketplace آزموده شد؛ مسیرهای دیگر تضمین نشده‌اند.

## بررسی همین به‌روزرسانی مستندات

هر دو سند با وضعیت سورس محلی و شواهد تاریخی گفتگو تطبیق داده شدند؛ `make check` با ۷۹ آزمون و بررسی پروژه موفق بود. نحو ۳۲ بلوک shell، وجود ۱۷ لینک محلی، بسته‌بودن code fenceها و `git diff --check` بررسی شدند. این کار فقط مستندسازی بود؛ دستور VDI، build یا تست کلاینت تازه اجرا نشد.

## مراجع چت جدید

- [نصب VDI و رفع خطاهای واقعی](vdi-installation.fa.md)
- [استقرار قابل‌تکرار و تنظیمات جدید](deployment.md)
- [سورس کد و Runner](source-code-runner.md)
- [اجرای محلی](local-execution.md)
- [اتصال‌های شخصی مدل](personal-model-connections.md)
- [انتخاب مدل هنگام اجرای برنامه](program-runtime-model.md)

پیشنهاد شروع: «هر دو سند VDI را بخوان و وضعیت فعلی Git و شواهد جدید را با آن‌ها تطبیق بده. از فهرست پیگیری ادامه بده؛ نصب، انتخاب مدل و ارتقای اولیه انجام شده‌اند. هر بار یک دستور یا اقدام و سپس انتظار برای نتیجه؛ تست کلاینت را بدون درخواست جدید تکرار نکن.»
