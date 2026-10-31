# تحویل ادامهٔ راه‌اندازی Kara روی VDI — ۳۱ اکتبر ۲۰۲۶

سند زندهٔ تحویل برای ادامهٔ کار است؛ این نسخه نصب اولیه و ادامهٔ رفع خطا/ارتقای ۳۰ تا ۳۱ اکتبر ۲۰۲۶ را پوشش می‌دهد. شواهد VDI از تصاویر و گزارش کاربرند؛ ویرایش این سند به معنی بررسی زندهٔ دوبارهٔ VDI نیست. هر ترد، کارهای انجام‌شده و پیگیری‌ها را با حفظ مرز شواهد به‌روز کند.

## هدف و روش ادامه

Kara روی VDI لینوکسی کاربر نصب شده است. هدف فعلی، تکمیل یک آزمون واقعی مدل و سپس آزمون دسترسی برنامه به سورس آماده‌شده است؛ نصب را از ابتدا تکرار نکنید.

- به فارسی و مرحله‌به‌مرحله راهنمایی کنید: در هر پاسخ فقط یک دستور کامل قابل کپی یا یک اقدام مشخص رابط، سپس منتظر تصویر/نتیجه بمانید.
- shell محلی Codex روی مک است؛ با ترمینال VDI یکی نیست. دستورهای `$HOME/Kara` باید در خود VDI اجرا شوند. از تغییر سورس محلی مک، تغییر VDI را نتیجه نگیرید.
- فایل‌های `sources/` در پوشهٔ مادر مک مرجع فقط‌خواندنی‌اند. دستورهای AGENTS.md مخزن محلی را پیش از تغییر بخوانید.
- توکن/رمز، کل فایل env، device.json و داده‌های خصوصی را درخواست یا در سند ثبت نکنید. TLS verification و validatorهای امنیت/خروجی را برای عبور از خطا خاموش نکنید. تست کلاینتی فعلاً به درخواست کاربر اجرا نشود؛ در build ارتقای اخیر، فقط با درخواست صریح کاربر `KARA_WEB_SKIP_CHECKS=true` استفاده شد. build وب با آزمون رابط یا اجرای مدل یکی نیست.
- «کتابخانه» تعریف قابلیت، «برنامه» آماده‌کردن اجرا، و «فلو» همکاری انسانی است. فعلاً آزمون کوچک واقعی انجام دهید؛ اجرای تیمی کلاسور یا تأیید انسانی را انجام‌شده فرض نکنید.

## نقطهٔ فعلی و اولویت ادامه

نصب مجدد لازم نیست. سورس VDI تا `9a40d78` دریافت، setup و build تصاویر API/وب موفق و سرویس‌ها راه‌اندازی شدند. مهاجرت `Exited (0)` و API/بانک `healthy` بودند؛ وب، WebSocket و Workerها در حال اجرا بودند. مسیر Nginx پاسخ `{"result":"pong"}` داد. کاربر سپس کلاینت را هم تست و تأیید کرد؛ این گزارش، موفقیت اجرای واقعی مدل را ثابت نمی‌کند.

دو اصلاح تازهٔ CA و محیط مهاجرت ابتدا دستی روی VDI اعمال شدند؛ نسخهٔ عمومی و تکمیلی آن‌ها در چهار کامیت محلی ثبت شده و هنوز در این ترد push نشده‌اند. اولویت کدی، انتشار با درخواست کاربر و تطبیق اصلاحات دستی VDI با نسخهٔ رسمی است. اولویت آزمون مدل، بررسی مسیر شبکه از دستگاهی است که مدل روی آن کار می‌کند؛ کاربر گفت فعلاً دسترسی ندارد و بعداً نتیجه را می‌فرستد.

## وضعیت تأییدشده و حدود

| بخش | نتیجه و محدودیت |
| --- | --- |
| ارتقای Kara | VDI روی `9a40d78` به‌اضافهٔ دو اصلاح دستی؛ کلاینت طبق گزارش کاربر اوکی |
| بانک و API | migration و init_permissions با کد صفر؛ API و PostgreSQL healthy؛ ping شبکه pong |
| شبکه و همکاری | آدرس canonical شبکه تنظیم شد؛ ایراد token ناشی از اختلاف host و خطای application context رفع شدند؛ کاربر رفع همگام‌سازی دو طرف را تأیید کرد |
| پروژه | کلاسور، `81fc0c17-ba88-496f-a95d-ff1dc910e5d0` |
| جیرا | آزمون احراز هویت تاریخی موفق؛ درخواست واقعی گسترده تأیید نشده |
| گیت‌لب و سورس | آزمون تاریخی موفق؛ هر ۸ مخزن نسخهٔ ۶ آماده و به مقصد متصل شدند |
| Runner | `Mahyar-VDI-Linux`؛ pairing و اجرای تاریخی موفق؛ آخرین آزمون‌های اتصال مدل به Runner رسیده و failed شده‌اند؛ روشن‌بودن فعلی را دوباره بررسی کنید |
| مدل در ویرایشگر | هر دو مدل شخصی نمایش داده شدند؛ Assist انتخاب شد و هشدار کاذب ناسازگار به CHAT تغییر کرد |
| آزمون واقعی مدل | پاسخ واقعی موفق ثبت نشده؛ جدیدترین آزمون‌ها model_request_failed؛ یک آزمون قدیمی‌تر succeeded بود |
| برنامهٔ فعلی | Chatflow Basic: Chatbot از نوع advanced-chat؛ در مسیر اجرای محلی پشتیبانی نمی‌شود؛ انتشار تأیید نشده |
| پشتیبان | dump بانک و تنظیمات تهیه و pg_restore --list موفق؛ restore واقعی و پشتیبان کامل داده‌های جانبی باقی است |

برنامهٔ موجود:

```text
http://10.20.168.117:8080/app/c6501f4d-79ed-4447-abf4-bb20b1cd064c/workflow
```

پیش‌فرض قالب `gpt-5.4-mini` با provider غایب `langgenius/openai/openai` بود. اکنون `AIFA-Sand-Assist` انتخاب شده است. دو اتصال `AIFA-LLM-Sand-Assist` و `AIFA-LLM-Sand-Dev` به provider `langgenius/openai_api_compatible/openai_api_compatible` مربوط‌اند. نام مدل ذخیره‌شده Assist برابر `AIFA-Sand-Assist-Model` و نام واقعی آن در سرویس `assistance-model` است؛ نام نمایشی را با شناسهٔ فراخوانی یکسان نگیرید.

## محیط و مسیرها

- VDI: Ubuntu 22.04.5 LTS amd64، ۵ CPU، ۲۳ GiB RAM؛ ارقام فضای آزاد ابتدای نصب‌اند و اکنون باید دوباره بررسی شوند.
- Docker 29.1.3، Compose 2.40.3؛ فرمان‌های Docker نصب با sudo انجام شدند.
- مخزن Kara روی VDI: `$HOME/Kara`، از `https://github.com/Mahyar1990/Kara.git`، شاخهٔ نصب `feat/program-team-settings`. آخرین SHA کوتاه مشاهده‌شده `9a40d78` است؛ اصلاحات دستی بعدی را نیز در موجودی تغییرات ثبت کنید.
- مخزن محلی مک: `/Users/mahyar/Documents/Other Projects/CompanyAgentPlatform/company-agent-platform`؛ این checkout مستقل از VDI است.
- مبنای Dify: 1.17.1، commit `8387590ace4a094de812b7847fc6a4c3a27cd52b`. `.runtime/dify` را تغییر ندهید.
- Runner: `$HOME/kara-runner`، venv همان پوشه، Python میزبان ۳.۱۰؛ دادهٔ pairing خصوصی `~/.config/kara-source-runner/device.json`.
- مسیر سورس Runner: `$HOME/KaraSourceWorkspaces`؛ سورس روی VDI است، نه در filesystem مک.
- آدرس canonical برنامه: `http://10.20.168.117:8080` برای مدیر و همکاران. binding جدید روی همین IP است؛ localhost/127.0.0.1 را دسترس‌پذیر فرض نکنید. کوکی میزبان‌ها مستقل است؛ localhost مک نیز به VDI اشاره نمی‌کند.

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

شاخهٔ همهٔ کارها `feat/program-team-settings` است. آخرین انتشار تأییدشده در این ترد و آخرین pull VDI، `9a40d78` بود. وضعیت ریموت در زمان ادامه دوباره خوانده شود. چهار کامیت زیر پس از آن محلی‌اند و هنوز در این ترد منتشر نشده‌اند:

| کامیت | تغییر |
| --- | --- |
| `5335cc9` | خواندن CA با cafile در OpenSSL به جای decode اجباری ASCII |
| `bf8f6cd` | اصلاح اولیهٔ دریافت محیط بانک در migration |
| `81d793b` | تست رد PEM خراب/ناقص یا کلید خصوصی پس از گواهی معتبر |
| `bcd6651` | تکمیل migration با ارث‌بری صریح API upstream و فایل‌های اختیاری محیط |

کامیت `6024f34` نیز سند تحویل ترد قدیمی‌تر را ساخته و در checkout محلی موجود است؛ آمار ahead را ثابت فرض نکنید. اصلاح WebSocket در `5055d7b` و انتخابگر در `d499489` و `9a40d78` قبلاً منتشر شده‌اند. انتخابگر به summary مشترک وابسته نیست؛ مسیرهای مشترک اعتبارنامه در backend باز نشده‌اند.

قبل از pull، تغییرات tracked/untracked VDI با نام زیر stash شدند:

```text
vdi-before-remote-update-2026-10-30
```

**stash را یکجا apply/pop نکنید.** شامل compose قدیمی، CA runtime، اصلاح install.py و overlay دستی انتخابگر است. overlay می‌تواند patch رسمی را بازنویسی کند. فایل‌های ignored `.runtime` در stash جابه‌جا نشدند.

تنظیمات خصوصی `$HOME/Kara/.env.local` ساخته شدند؛ برای مقادیر همین VDI و دستورهای بازتولید به [راهنمای نصب](vdi-installation.fa.md#تنظیمات-پایدار-همین-vdi) مراجعه کنید. IP، registry داخلی و CA به سورس عمومی hardcode نشوند.

دو تغییر دستی که فعلاً روی VDI باقی‌اند:

- `scripts/build_environment.py`: استفاده از `context.load_verify_locations(cafile=str(source))`. فایل سیستم ۱۲۵ marker و بایت غیر ASCII داشت؛ OpenSSL آن را با ۱۲۳ گواهی بارگذاری کرد. عدد marker معیار تعداد گواهی یکتا نیست و علت اختلاف تعداد جداگانه بررسی نشده است. TLS غیرفعال نشد.
- `infra/compose.local.yaml`: افزودن env_file مطلق `/home/m.zhiani/Kara/.runtime/compose.env` به migration. پیش از آن تمام DB متغیرها غایب بودند و localhost:5432 رد می‌شد؛ پس از اصلاح مقصد db_postgres:5432 و اجرای migration موفق بود. نسخهٔ عمومی نهایی در `bcd6651` به‌جای مسیر مطلق از `extends.file: docker-compose.yaml` استفاده می‌کند تا `.env` و فایل‌های اختیاری upstream را بگیرد.

پشتیبان پیش از ارتقا:

```text
/home/m.zhiani/Kara/.runtime/update-backups/20261030-234607
```

فایل‌های `env.local`، `compose.env`، `compose.build.json`، `database.dump` و `database-list.txt` نگهداری شدند. dump با `pg_dump -Fc` ساخته و فهرست با `pg_restore --list` خوانده شد؛ restore واقعی تست نشده و این پشتیبان، snapshot کامل فایل‌های آپلود/دانش/worktree نیست. نسخه‌های اصلی دو فایل اصلاح‌شده هم در زیرپوشه‌های زمان‌دار همین update-backups محفوظ‌اند.

## تشخیص مدل و چت‌فلو؛ دو مسئلهٔ مستقل

1. پیش‌نمایش برنامه در `local_dispatch.submit` پیش از تماس با مدل رد شد؛ شرط فعلی فقط `app.mode == 'workflow'` را می‌پذیرد. برنامهٔ فعلی `advanced-chat` است. خطای BadRequest به 500 تبدیل شد. پشتیبانی چت‌فلو پیاده‌سازی نشده؛ حذف شرط به‌تنهایی راه‌حل نیست.
2. آزمون مستقل اتصال شخصی روی Runner انجام شد. ردیف‌های جدید `local_rpc` با `model_request_failed` failed بودند و یک ردیف قدیمی‌تر succeeded بود. مسیر خطا `model_client_boundary → local_rpc.model_call → local_rpc.wait` است؛ خطای generic، HTTP/TLS دقیق را ثابت نمی‌کند.
3. Base URL مشاهده‌شدهٔ Assist: `https://aifa-chatbot.sandpod.ir/v1`؛ DNS در VDI برابر `79.132.215.248`. درخواست بدون توکن به `/v1/models` با curl هم با noproxy و هم بدون آن، Connection refused روی 443 و HTTP=000 داد. اتصال هنوز به بررسی توکن/TLS نرسیده است؛ صحت DNS یا وضعیت سرویس مقصد تأیید نشده. قرار است با دستگاهی که همان مدل روی آن کار می‌کند مقایسه شود.
4. پاسخ `200` فهرست مدل‌های شخصی، activeبودن metadata یا نمایش CHAT اثبات اجرای مدل نیست. summary/credits ممکن است از مصرف‌کنندگان دیگر رابط همچنان 403 دهند؛ guard شخصی را برای حذف پیام باز نکنید.

## بررسی کد محلی و پذیرش VDI

آخرین `make check` در این ترد ۷۹ تست Python موفق داشت. تست migration نبود DB_HOST و سپس نبود تنظیم اختیاری API را پیش از اصلاح در هر دو مسیر Compose/Make بازتولید کرد و نسخهٔ نهایی موفق شد. تنظیمات بانک، Redis و SECRET_KEY در Compose واقعی محلی تطبیق داده شدند، بدون چاپ رمز. تست CA توضیح غیر ASCII را می‌پذیرد و PEM خراب/ناقص یا private key را رد و آخرین ورودی ساخت معتبر را حفظ می‌کند.

تست کلاینت یا build جدید در بررسی محلی اجرا نشد. `doctor --server-only` در بررسی‌های قبلی به‌دلیل قدیمی‌بودن تصویر API محلی مک کامل نشد؛ این را به VDI تعمیم ندهید. روی VDI build API/وب با skip checks به درخواست کاربر موفق، سرویس‌ها بررسی و کلاینت توسط خود کاربر تأیید شد. این گزارش شامل پذیرش Runner جدید، مدل یا چت‌فلو نیست.

## کارهای باقی‌مانده، به ترتیب

1. انتشار کامیت‌های محلی فقط با درخواست کاربر؛ ابتدا ref زندهٔ ریموت و تغییرات محلی را بخوانید. force push یا تغییر master انجام نشود.
2. پس از انتشار، تطبیق دو اصلاح دستی VDI با سورس رسمی؛ قبل از pull وضعیت Git را حفظ کنید. stash قدیمی و overlay انتخابگر را کامل برنگردانید. فایل‌های خصوصی، backup و تنظیم CA runtime را حفظ و وضعیت نهایی را ثبت کنید.
3. بررسی DNS و مسیر 443 سرویس مدل از دستگاهی که مدل در آن کار می‌کند؛ کاربر فعلاً به آن دستگاه دسترسی ندارد. توکن را حدس نزنید و TLS را خاموش نکنید.
4. برای اجرای برنامه از workflow پشتیبانی‌شده استفاده کنید یا پشتیبانی advanced-chat را به‌عنوان کار مستقل طراحی کنید؛ خطای 500 به معنی خطای سرویس مدل نیست. سپس یک پاسخ واقعی مدل ثبت شود.
5. آزمون مستقل خواندن فایل‌های worktree نسخهٔ ۶ و اجرای حداقلی کد Docker روی Runner باقی است. Chatbot ساده خودبه‌خود سورس را نمی‌خواند؛ نوشتن/push/merge مجاز یا تأییدشده فرض نشود.
6. پایداری Runner پس از بسته‌شدن ترمینال، logout و reboot، و تطبیق بستهٔ Runner با سرور جدید هنوز بررسی نشده است. pairing مجدد را بی‌علت انجام ندهید.
7. restore واقعی در محیط مجزا و پشتیبان داده‌های جانبی باقی است؛ backup بانک انجام شده را دوباره «انجام‌نشده» گزارش نکنید.
8. doctor سمت سرور روی VDI، درخواست واقعی Jira، GitLab فراتر از خواندن، VDI دوم و پذیرش گستردهٔ چندحسابی/بار، فقط در دامنهٔ درخواست بعدی بررسی شوند. رفع همگام‌سازی دوطرفه قبلاً تأیید شده ولی آزمون بار نبوده است.

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
