# نصب کارا روی VDI لینوکسی با شبکهٔ محدود

> مسیر عمومی و قابل‌تکرار در [راهنمای استقرار](deployment.md) آمده است. این سند تجربهٔ نصب و ارتقای همین VDI تا ۳۱ اکتبر ۲۰۲۶ را ثبت می‌کند؛ وضعیت ادامهٔ کار در [سند تحویل](vdi-handoff-2026-10-31.fa.md) است.

**آخرین وضعیت ۳۱ اکتبر:** سورس تا `9e88cc4` دریافت شد؛ CA سرویس‌های runtime بازگردانده شد، درخواست Marketplace از API پاسخ ۲۰۰ داد و doctor سمت سرور موفق شد. برای Runner، علاوه بر IP شبکه، دسترسی `127.0.0.1:8080` دوباره اضافه شد. اعتبارسنجی Assist در کلاسور و Workflow واقعی با خروجی `{"answer":"12"}` موفق‌اند. خواندن سورس و اجرای کد Docker هنوز بررسی نشده‌اند؛ جزئیات و حدود در بخش ادامهٔ تأییدشدهٔ سند تحویل آمده است. بخش‌های تاریخی این راهنما را با وضعیت جدید یکسان نگیرید.

این راهنما حاصل نصب واقعی ۲۹ اکتبر و ارتقای ۳۰ تا ۳۱ اکتبر ۲۰۲۶ است. هدف، نصب مستقل کارا برای یک کاربر دیگر است؛ حساب‌ها، رمزها و بانک دادهٔ محیط قبلی منتقل نمی‌شوند. دستورها در ترمینال **خود VDI** اجرا می‌شوند. هر مرحله باید موفق شود و سپس مرحلهٔ بعد انجام شود.

موفقیت این نصب به معنی تضمین نصب روی هر شبکه یا نسخهٔ آینده نیست. مسیر زیر خطاهای مشاهده‌شده را از ابتدا پیشگیری می‌کند؛ نسخه‌ها، دسترسی رجیستری و گواهی‌های VDI جدید باید دوباره بررسی شوند.

## نتیجه و محدودهٔ تأییدشده

- در نصب اولیه، ساخت API/وب، بررسی نوع‌ها و آزمون‌های رابط موفق بودند. در ارتقای اخیر نیز تصاویر API/وب و ساخت Next.js موفق شدند؛ به درخواست کاربر، این بار `KARA_WEB_SKIP_CHECKS=true` استفاده شد و بررسی‌های کلاینتِ این مرحله اجرا نشدند.
- مهاجرت پایهٔ بانک با ایمیج اصلی انجام شد؛ سپس سرویس‌های اختصاصی کارا شروع شدند.
- API داخل کانتینر و از پورت محلی `8080` پاسخ `{"result":"pong"}` داد.
- صفحهٔ نصب فارسی باز شد، حساب مدیر ساخته شد و صفحهٔ پروژه‌های خالی نمایش داده شد.
- پروژه ساخته شد؛ آزمون احراز هویت جیرا/گیت‌لب و آماده‌سازی و اتصال worktree هشت‌مخزنی نسخهٔ ۶ موفق بودند. بعداً نمایش و انتخاب مدل شخصی و همگام‌سازی دو کاربر اصلاح شدند؛ این موارد به معنی موفقیت اجرای مدل نیستند.
- در ارتقای اخیر، مهاجرت `Exited (0)`، API/بانک `healthy` و سرویس‌های طولانی‌مدت `Up` بودند؛ ping از مسیر Nginx پاسخ `pong` داد و کاربر تست موفق کلاینت را گزارش کرد. در ادامهٔ ۳۱ اکتبر، `doctor --server-only` روی VDI موفق شد و Workflow واقعی مدل پاسخ داد. خواندن سورس در برنامه، اجرای کد Docker، reboot و بازیابی backup تأیید نشده‌اند. فهرست `pg_restore --list` برای backup بررسی شد، نه restore واقعی.
- فرمان `hello-world` اجرای واقعی کانتینر را ثابت کرد؛ چون ایمیج ممکن بود از قبل موجود باشد، به‌تنهایی مدرک دانلود تازه نبود. دریافت بعدی ایمیج‌های Python، API و سایر سرویس‌ها نیز مشاهده شد.

## محیط و نسخه‌های مشاهده‌شده

| مورد | مقدار نصب این جلسه |
| --- | --- |
| سیستم‌عامل | Ubuntu 22.04.5 LTS، معماری amd64 |
| منابع | ۵ پردازنده، ۲۳ GiB RAM، حدود ۱۸ GiB حافظهٔ available در شروع |
| دیسک | حدود ۵۶ GiB آزاد روی `/`، حدود ۲۳ GiB آزاد روی `/home` در شروع |
| Docker | 29.1.3، داده‌ها در `/var/lib/docker`؛ `/var/lib/containerd` نیز روی دیسک ریشه |
| Compose | 2.40.3؛ حداقل موردنیاز پروژه 2.24.4 |
| Git | 2.55.0 روی میزبان |
| مبنای فنی | Dify 1.17.1؛ commit قفل‌شده `8387590ace4a094de812b7847fc6a4c3a27cd52b` |
| آماده‌سازی جایگزین | `python:3.12-bookworm`؛ Python 3.12.16 و Git 2.39.5 داخل ایمیج |
| وب | `node:24.20.0-alpine`؛ pnpm 12.3.4 |
| Weaviate | 1.39.2 |
| مخزن نصب‌شده | `https://github.com/Mahyar1990/Kara.git`، شاخهٔ `feat/program-team-settings` |

این منابع نمونهٔ موفق‌اند، نه حداقل اندازه‌گیری‌شده یا ظرفیت تضمین‌شده. ساخت وب و cacheها فضای بیشتری مصرف می‌کنند؛ فضای `/home` و دیسک Docker جداگانه بررسی شوند. شاخهٔ بالا شاخهٔ همین جلسه است؛ برای انتشار بعدی، شاخه/commit مورد توافق را انتخاب و ثبت کنید. آخرین pull ثبت‌شده روی VDI از `409bbe4` تا `9a40d78` بود؛ اصلاحات دستی بعدی و commitهای محلی جدید را با این hash یکسان ندانید.

## ۱. بررسی اولیه و دسترسی Docker

```bash
bash -c '
cat /etc/os-release
nproc
free -h
df -h / /var/lib/docker /var/lib/containerd "$HOME"
git --version
docker --version
docker compose version
sudo docker info --format "Server: {{.ServerVersion}} | Root: {{.DockerRootDir}}"
'
```

خطای `permission denied ... /var/run/docker.sock` در این VDI با اجرای Docker از طریق `sudo` رفع شد. تمام دستورهای Docker این راهنما همین روش را دارند؛ عضویت گروه‌ها یا مجوز socket را تغییر نمی‌دهند. رمز sudo را در ترمینال وارد کنید و در گزارش نفرستید.

```bash
sudo docker run --rm hello-world
```

انتظار: `Hello from Docker!`. اگر دسترسی مدیریتی یا Docker موجود نیست، این راهنما نصب خود Docker را پوشش نمی‌دهد.

## ۲. دریافت کامل سورس و کاتالوگ قفل‌شده

```bash
git clone --branch feat/program-team-settings https://github.com/Mahyar1990/Kara.git "$HOME/Kara"
```

از ZIP یا clone کم‌عمق استفاده نکنید. اگر `~/Kara` از قبل وجود دارد، آن را حذف یا overwrite نکنید؛ ابتدا محتوای آن را بررسی و مسیر مستقلی انتخاب کنید.

در این جلسه، حتی clone معمولی commit وابستگی کاتالوگ را نداشت. پیش از setup آن را دریافت کنید:

```bash
git -C "$HOME/Kara" fetch origin fa94108ce3c39a0b96a9377a323b15db147ca88f
```

این fetch شاخه را عوض نمی‌کند. اگر نسخهٔ آینده hash دیگری در خطای setup اعلام کرد، hash همان نسخه لازم است. اگر سرور commit را نداشت، راه‌حل انتقال Git bundle از یک clone معتبر است؛ وابستگی را به commit دلخواه تغییر ندهید.

```bash
git -C "$HOME/Kara" log -1 --format='%H %s'
```

این خروجی را همراه نسخهٔ نصب نگه دارید. اعتبارنامه و توکن Git را در فایل یا دستور قابل اشتراک قرار ندهید.

## تنظیمات پایدار همین VDI

فایل خصوصی `$HOME/Kara/.env.local` هنگام ارتقا وجود نداشت و با مقادیر زیر ساخته شد. این‌ها تنظیمات همین محیط‌اند؛ روی سرور دیگر IP، URL، registry، مسیر CA و نام پروژه را متناسب با آن محیط تعیین کنید. اصلاحات عمومی سورس همچنان برای همهٔ استقرارها لازم‌اند.

```dotenv
DIFY_HTTP_PORT=8080
DIFY_HTTPS_PORT=8443
DIFY_PROJECT_NAME=company-agent-local
DIFY_BIND_ADDRESS=10.20.168.117
DIFY_PUBLIC_URL=http://10.20.168.117:8080
KARA_NPM_REGISTRY=https://nexus3.dotin.ir/repository/Dotin-NPM/
KARA_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
KARA_BOOTSTRAP_IMAGE=python:3.12-bookworm
KARA_TOOLS_IMAGE=python:3.12-bookworm
DIFY_WEAVIATE_IMAGE=semitechnologies/weaviate:1.39.2
```

فایل را با دسترسی محدود نگه دارید و فایل موجود را بدون بررسی بازنویسی نکنید. setup باید تنظیمات خصوصی Dify را حفظ کند. `KARA_CA_BUNDLE` برای آماده‌سازی/ساخت است؛ اعتماد TLS سرویس‌های runtime و Runner باید جداگانه بررسی شود. تنظیم پایه پورت را روی IP بالا bind می‌کند؛ در ادامهٔ همین روز یک binding محلی اضافی برای `127.0.0.1:8080` در overlay همین VDI اضافه و بررسی شد. این دسترسی را روی نصب دیگر فرض نکنید. در مرورگر از URL یکسان بالا استفاده کنید تا cookie و WebSocket با origin دیگری مخلوط نشوند.

## ۳. آماده‌سازی بدون apt در کانتینر bootstrap

در نسخهٔ اولیه، `compose.setup.yaml` از Python slim و نصب Git با apt استفاده می‌کرد؛ نسخهٔ جدید از ایمیج کامل و تنظیمات راه‌انداز پشتیبانی می‌کند. روی این شبکه، HTTP مخزن Debian مسدود بود؛ HTTPS هم ابتدا خطای CA و پس از استفاده از CA میزبان، صفحهٔ مسدودی سازمان و 403 داد. برای این VDI، مستقیماً از ایمیج کامل استفاده کنید:

```bash
sudo docker run --rm python:3.12-bookworm sh -c 'python --version && git --version && test -s /etc/ssl/certs/ca-certificates.crt && test -f /usr/share/zoneinfo/Asia/Tehran'
```

سپس setup را اجرا کنید:

```bash
sudo docker run --rm \
  -v "$HOME/Kara:/workspace" \
  -v /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro \
  -w /workspace \
  -e HOME=/tmp \
  -e PYTHONUTF8=1 \
  -e PYTHONUNBUFFERED=1 \
  -e PYTHONDONTWRITEBYTECODE=1 \
  python:3.12-bookworm python scripts/compose_setup.py
```

اسکریپت موجود پروژه با مالک پوشهٔ workspace کار می‌کند تا خروجی‌های تولیدشده متعلق به کاربر باشند. انتظار: `Kara sources and private configuration are ready`.

پیام `detached HEAD` برای checkout مبنای قفل‌شدهٔ Dify طبیعی است. فایل‌های `.runtime/dify` را تغییر ندهید. `.runtime/compose.env` و داده‌های runtime خصوصی‌اند؛ نمایش یا انتقال کامل آن‌ها لازم نیست.

گواهی میزبان در این نصب از قبل مورد اعتماد VDI بود و به‌صورت read-only در کانتینر استفاده شد. روی VDI جدید، اگر میزبان هم TLS را نمی‌شناسد، ابتدا CA معتبر سازمان باید تأمین شود؛ این روش CA ناشناخته را معتبر نمی‌کند. از خاموش‌کردن TLS verification یا اعتماد به گواهی leaf استفاده نکنید.

## ۴. دریافت ایمیج‌ها پیش از ساخت

رجیستری `cr.weaviate.io` در نصب حاضر 403 داد، اما مخزن رسمی ناشر در Docker Hub قابل دریافت بود:

```bash
sudo docker pull semitechnologies/weaviate:1.39.2
```

نسخهٔ جدید با `DIFY_WEAVIATE_IMAGE` همین ایمیج را انتخاب می‌کند؛ tag جایگزین فقط در نصب قدیمی برای نام رجیستری upstream لازم بود. سورس ثابت upstream را تغییر ندهید. digest را از خروجی واقعی `docker pull` محیط خود ثبت کنید. معیار این دستور، نام و نسخهٔ مخزن رسمی است؛ برابری digest دو رجیستری در این جلسه جداگانه مقایسه نشد.

```bash
sudo docker pull langgenius/dify-api:1.17.1
```

```bash
sudo docker pull node:24.20.0-alpine
```

باقی سرویس‌ها را ترتیبی دریافت کنید تا خطاهای لایه‌ها قابل تشخیص باشند:

```bash
sudo docker compose --parallel 1 --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" pull nginx db_postgres redis init_permissions sandbox local_sandbox plugin_daemon ssrf_proxy agent_ssrf_proxy agent_backend
```

در این جلسه دریافت هم‌زمان با `failed to copy ... content descriptor ... not found` متوقف شد. دریافت ترتیبی sandboxها و دریافت مستقل API موفق شدند؛ علت قطعی در رجیستری/شبکه تشخیص داده نشد. این خطا در مرحلهٔ `COPY` هم ظاهر شد، ولی در آن مورد نبودن فایل سورس علت نبود؛ متن نهایی به لایهٔ دانلودنشده اشاره می‌کرد. cache یا داده‌های Docker را برای این خطا پاک نکنید.

## ۵. تأیید مخزن npm داخلی

```bash
npm config get registry
```

در این VDI خروجی `https://nexus3.dotin.ir/repository/Dotin-NPM/` بود. این آدرس مختص شبکهٔ شرکت است. اگر VDI دیگر مخزن متفاوتی دارد، ابتدا آدرس تأییدشدهٔ آن محیط را جایگزین و آزمایش کنید.

دریافت metadata به‌تنهایی کافی نیست؛ نصب واقعی نسخهٔ لازم را بررسی کنید:

```bash
sudo docker run --rm \
  -v /etc/ssl/certs/ca-certificates.crt:/tmp/vdi-ca.crt:ro \
  -e NODE_EXTRA_CA_CERTS=/tmp/vdi-ca.crt \
  -e npm_config_registry=https://nexus3.dotin.ir/repository/Dotin-NPM/ \
  node:24.20.0-alpine \
  sh -c 'npm install --prefix /tmp/pnpm-test --ignore-scripts --no-audit --no-fund pnpm@12.3.4 && /tmp/pnpm-test/node_modules/.bin/pnpm --version'
```

انتظار: نصب موفق و خروجی `12.3.4`. این آزمون به احراز هویت اضافی نیاز نداشت. اگر مخزن محیط جدید نیاز به توکن داشت، آن را در Dockerfile یا ENV ثابت قرار ندهید؛ تنظیم build secret لازم است و در این نصب آزمایش نشده است.

## ۶. آماده‌سازی ساخت وب با تنظیمات رسمی

نصب اولیه با CA و سپس 403 در `apk`، دانلود ناموفق Corepack و درخواست pnpm به registry عمومی مواجه شد. راه‌حل اکنون در سورس پروژه است: فایل‌های zoneinfo از ایمیج کامل، نصب مستقیم نسخهٔ قفل‌شدهٔ pnpm و تعیین صریح registry. setup، CA و تنظیمات ساخت را از `.env.local` به سورس تولیدشده منتقل می‌کند.

اسکریپت قدیمی جایگزینی دستی Dockerfile در `.runtime/dify-web-source` را دوباره اجرا نکنید؛ پس از setup جدید به آن نیاز نیست. فایل‌های upstream در `.runtime/dify` را ویرایش نکنید. CA سازمان وارد تصویر ساخت می‌شود؛ trust store میزبان تغییر نمی‌کند و ایمیج سازمانی را بی‌بررسی منتشر نکنید.

در ارتقای همین VDI، اعتبارسنجی CA ابتدا به علت decode اجباری ASCII شکست خورد، درحالی‌که بارگذاری مستقیم فایل با OpenSSL موفق بود. اصلاح عمومی `scripts/build_environment.py` اکنون از `load_verify_locations(cafile=...)` استفاده می‌کند و رد کلید خصوصی و دادهٔ نامعتبر را حفظ کرده است. در checkout قدیمی `9a40d78` این اصلاح دستی با backup اعمال شد؛ commit مربوطه `5335cc9` است. از حذف بایت‌های غیر ASCII یا خاموش‌کردن TLS استفاده نکنید. bundle مشاهده‌شده ۱۹۵۰۳۱ بایت، ۱۲۵ نشانگر و ۱۲۳ CA بارگذاری‌شده داشت؛ علت اختلاف شمارش بررسی نشد.

## ۷. ساخت بدون شروع زودهنگام API

```bash
sudo docker compose --parallel 1 --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" build api web
```

ساخت اولیه می‌تواند چندین دقیقه طول بکشد. فرمان بالا کنترل‌های پیش‌فرض را دارد. در ارتقای اخیر، با درخواست صریح کاربر فرمان زیر استفاده و هر دو تصویر ساخته شدند؛ آن را معادل اجرای آزمون‌های کلاینت ندانید:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" build --build-arg KARA_WEB_SKIP_CHECKS=true api web
```

هنگام شکست، آخرین خط خطا و مرحلهٔ شکست را بخوانید؛ موفقیت `Built` با آماده‌بودن سرویس تفاوت دارد.

## ۸. مهاجرت پایه پیش از سرویس‌های اختصاصی

در نصب اولیه، شروع زودهنگام API باعث `tenant_account_joins does not exist` شد. مسیر فعلی Compose سرویس یک‌بارهٔ `migration` دارد: با ایمیج پایهٔ `langgenius/dify-api:1.17.1`، پیش از API، Worker، Worker Beat و WebSocket، `flask db upgrade` اجرا می‌شود. هر چهار نقش به پایان موفق آن وابسته‌اند. برای بانک موجود ابتدا backup معتبر بگیرید.

در ارتقای همین VDI، محیط بانک به migration منتقل نشده بود و اتصال اشتباهاً به `localhost:5432` انجام می‌شد. افزودن دستی env_file خصوصی این نصب را رفع کرد. اصلاح نهایی سورس در `infra/compose.local.yaml`، سرویس `api` را مستقیماً از `docker-compose.yaml` upstream گسترش می‌دهد تا تنظیمات API و env_fileهای اختیاری آن نیز حفظ شوند؛ ایمیج پایه و نبود build سفارشی حفظ شده‌اند. مسیر مطلق `/home/m.zhiani/...` را وارد تنظیمات عمومی نکنید.

پس از setup/build، فرمان بخش بعد مهاجرت را با وابستگی‌هایش اجرا می‌کند. خطای migration را با حذف volume، حذف بانک یا دورزدن وابستگی رفع نکنید. مهاجرت موفق همین VDI با `Exited (0)` مشاهده شد؛ نصب تازهٔ دوم با اصلاح نهایی سورس هنوز آزموده نشده است.

## ۹. راه‌اندازی و بررسی پاسخ واقعی

```bash
sudo docker compose --parallel 1 --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" up -d --no-build
```

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" ps -a
```

`migration` و `init_permissions` کارهای یک‌باره‌اند؛ پایان موفق هر دو با کد صفر طبیعی است. سرویس‌های طولانی‌مدت نباید در چرخهٔ restart باشند. برای تأیید API:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:5001/console/api/ping', timeout=20).read().decode())"
```

```bash
curl --noproxy '*' --fail --show-error --max-time 20 http://10.20.168.117:8080/console/api/ping
```

انتظار در هر دو: `{"result":"pong"}`. آدرس بیرونی بالا مخصوص bind همین VDI است؛ روی دستگاه دیگر URL همان استقرار را استفاده کنید. در نصب اولیه آزمون localhost با proxy خطای 502 داشت؛ در بررسی بعدی API مستقیم سالم بود. این خطای تاریخی را علت قطعی همهٔ 502ها ندانید. پس از recreate کانتینرها نیز یک بار reload Nginx مشکل آدرس داخلی قدیمی را رفع کرد؛ نسخهٔ جدید تنظیم Docker DNS دارد، اما آزمون بار/قطعی جداگانه انجام نشده است.

اگر شکست خورد:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" logs --since 3m --tail 80 api nginx
```

خطای migration با 502 زمان شروع یا مشکل مسیر شبکه متفاوت است. `Listening at ...:5001` نشانهٔ شروع Gunicorn است؛ پاسخ واقعی ping مدرک بهتری برای دسترس‌پذیری API است. در این جلسه لاگ `Database migration skipped` بعد از اجرای دستی پایه مانع پاسخ موفق نشد.

## ۱۰. ساخت حساب مستقل

این مرحله فقط برای نصب تازه است؛ هنگام ارتقا حساب موجود را دوباره نسازید. در Firefox **داخل VDI**، [صفحهٔ نصب کارا](http://10.20.168.117:8080/install) را باز کنید. ایمیل، نام و رمز مدیر جدید را وارد و «راه‌اندازی» را انتخاب کنید. شرط مشاهده‌شدهٔ فرم: حداقل ۸ نویسه شامل حرف و عدد. رمز را در اسکرین‌شات آشکار نکنید.

پس از موفقیت، [پروژه‌ها](http://10.20.168.117:8080/projects) باز می‌شود. خالی‌بودن پروژه‌ها در نصب مستقل طبیعی است؛ clone سورس پروژه‌ها و داده‌های محیط قبلی را منتقل نمی‌کند. در این نقطه نصب اولیه پذیرفته شده است. اتصال مدل مرحلهٔ جداگانه‌ای است.

نوار Firefox با متن `You must log in to this network...` در تصاویر وجود داشت، ولی صفحهٔ محلی و ساخت حساب موفق بودند؛ آن نوار را مدرک شکست نصب کارا در نظر نگیرید.

## استفادهٔ روزمره، به‌روزرسانی و تحویل

شروع روزمره، بدون ساخت مجدد:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" up -d --no-build
```

توقف با حفظ داده‌ها:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" stop
```

برای به‌روزرسانی: وضعیت Git و backup را بررسی، نسخهٔ مورد توافق را دریافت، تنظیمات خصوصی را حفظ و setup را اجرا کنید؛ سپس build و مهاجرت متناسب با همان نسخه را انجام دهید. اصلاح دستی قدیمی Dockerfile یا stash را یکجا برنگردانید؛ تفاوت‌های محلی را با سورس جدید تطبیق دهید. دستورهای این سند را کورکورانه برای نسخهٔ جدید استفاده نکنید.

`.runtime` را حذف نکنید؛ `docker compose down -v`، `docker system prune` و پاک‌کردن volumeها راه‌حل معمول خطاهای این نصب نیستند. این ترد چنین پاک‌سازی‌ای انجام نداد.

در تحویل نفر بعد ثبت کنید: commit واقعی سورس، نسخه و معماری ایمیج‌ها، آدرس مخزن داخلی، تاریخ اعتبار CA، نتیجهٔ ساخت و migration، هر دو ping و ورود به صفحهٔ پروژه‌ها. env، رمز مدیر، کلید مدل، داده‌های بانک، cacheهای شخصی و کل `.runtime` را به مخزن Git یا گزارش عمومی اضافه نکنید.

## ارتقای تأییدشدهٔ ۳۰ تا ۳۱ اکتبر ۲۰۲۶

- تغییرات tracked و untracked نصب قبلی با `git stash push --include-untracked -m "vdi-before-remote-update-2026-10-30"` حفظ شدند؛ stash شامل overlay قدیمی CA و model-selector هم بود. آن را حذف یا کامل apply/pop نکنید؛ فایل‌های ignored runtime در این عملیات منتقل نشدند.
- pull از شاخهٔ `feat/program-team-settings` با fast-forward تا `9a40d78` موفق شد. `.env.local` بالا ساخته شد و backup در `/home/m.zhiani/Kara/.runtime/update-backups/20261030-234607` ثبت شد: `env.local`، `compose.env`، `compose.build.json`، `database.dump` و `database-list.txt`.
- dump با `pg_dump -Fc` گرفته و با `pg_restore --list` خوانده شد؛ این مدرک restore واقعی یا backup کامل فایل‌ها، vectorها و volumeها نیست. پیش از عملیات پرریسک آینده، backup تازه و متناسب با داده‌های همان زمان لازم است.
- پس از اصلاح دستی CA، setup با حفظ تنظیمات خصوصی و بررسی ۵۹۴۷ کلید فارسی موفق شد؛ build API/وب موفق بود. پس از اصلاح محیط migration، اجرای `up -d --no-build` بدون خطا تمام شد و ping از Nginx پاسخ `pong` داد. کاربر تست موفق کلاینت را گزارش کرد.
- اصلاح‌های عمومی: `5335cc9` اعتبارسنجی فایل CA، `bf8f6cd` انتقال صریح محیط migration، `81d793b` آزمون CA خراب پس از گواهی معتبر و `bcd6651` ارث‌بری کامل تنظیمات اختیاری upstream. تغییر نهایی migration در commit آخر است. این چهار commit هنگام تحویل اولیه منتشر نشده بودند؛ در ادامهٔ ۳۱ اکتبر همراه دو کامیت مستندات تا `9e88cc4` منتشر و روی VDI دریافت شدند.
- بررسی نهایی کد محلی `make check` با ۷۹ آزمون موفق بود؛ اجرای واقعی migration جدید، build/تست کلاینت محلی انجام نشد. شکست تاریخی `doctor --server-only` روی مک با تصویر قدیمی API، وضعیت VDI را توصیف نمی‌کند. چک مستنداتِ این به‌روزرسانی جدا از این شواهد تاریخی ثبت می‌شود.

## فهرست خطاهای واقعی و اقدام موفق

| علامت | تشخیص/اقدام این جلسه |
| --- | --- |
| دسترسی Docker socket رد شد | اجرای Docker با sudo؛ بدون تغییر مجوز socket |
| apt روی HTTP: 403 | مخزن Debian در مسیر شبکه قابل دسترس نبود |
| apt روی HTTPS: issuer unknown | CA میزبان به کانتینر موقت داده شد؛ TLS رفع شد ولی 403 باقی ماند |
| صفحهٔ `Local URLfilter Block` | مسدودی سازمان تأیید شد؛ bootstrap با ایمیج کامل و بدون apt انجام شد |
| `Pinned template catalog is missing` | fetch صریح commit کاتالوگ روی میزبان |
| رجیستری Weaviate: 403 | دریافت همان نسخه از مخزن رسمی Docker Hub و tag محلی |
| لایهٔ image: `not found` | دریافت ترتیبی سرویس‌ها و pull مستقل ایمیج پایهٔ API موفق شد |
| apk: CA و سپس 403 | فایل‌های zoneinfo از Python کامل؛ نصب APK لازم نشد |
| Corepack: 403 یا آدرس غیرمنتظره | نصب مستقیم pnpm 12.3.4 با npm از Nexus داخلی |
| pnpm metadata از npm عمومی: 403 | تعیین صریح registry در فرمان pnpm؛ کنترل‌ها حفظ شدند |
| `tenant_account_joins` موجود نبود | توقف سرویس‌های اختصاصی، migration با ایمیج اصلی، شروع دوباره |
| `KARA_CA_BUNDLE` نامعتبر / `UnicodeDecodeError` | فایل با OpenSSL معتبر بود؛ حذف decode اجباری ASCII و اعتبارسنجی cafile با حفظ کنترل‌ها |
| migration به `localhost:5432` | متغیرهای بانک غایب بودند؛ انتقال env خصوصی روی VDI و اصلاح ارث‌بری upstream در سورس |
| مدل شخصی در انتخابگر نبود / 403 summary | اصلاح انتخابگر و patch رسمی؛ endpoint اعتبارات مشترک عمداً مسدود ماند |
| WebSocket خطای app context / token | اصلاح context سمت سرور و origin ثابت؛ همگام‌سازی دو کاربر تأیید شد |
| Chatflow خطای 500 پیش از مدل | مسیر local dispatch فقط workflow را می‌پذیرد؛ پشتیبانی advanced-chat هنوز باقی است |
| مدل `Connection refused` پورت 443 | بررسی علت در شبکه/سرویس هنوز باقی است؛ خطای قبل از TLS و احراز هویت |
| 502 با API سالم | آزمون مستقیم API و سپس curl با noproxy/127.0.0.1 موفق شد؛ علت آخر قطعی نبود |

## ادامهٔ راه‌اندازی: اتصال‌ها، Runner و worktree

این بخش بر اساس تصاویر و گزارش کاربر تا ۳۰ اکتبر ۲۰۲۶، برای تحویل در ۳۱ اکتبر ثبت شده است؛ وضعیت زندهٔ VDI در زمان خواندن باید دوباره بررسی شود. [سند تحویل چت](vdi-handoff-2026-10-31.fa.md) نقطهٔ توقف و فهرست پیگیری را دارد. این بخش تغییر جدیدی روی VDI اعمال نمی‌کند.

### گواهی سرویس‌های در حال اجرا و نصب افزونهٔ مدل

قابل‌دسترسی‌بودن Marketplace از میزبان، اعتماد TLS داخل API را ثابت نمی‌کند. در این نصب، `curl` میزبان پاسخ ۲۰۰ داد ولی Python داخل API با `self-signed certificate in certificate chain` شکست خورد. آزمون همان درخواست با CA معتبر میزبان در API پاسخ ۲۰۰ داد.

روی **همین VDI**، فایل محلی `infra/compose.vdi-ca.yaml` ساخته و بعد از `.runtime/compose.build.json` به فهرست مسیرهای Compose اصلی اضافه شد. برای سرویس‌های `api`، `worker`، `worker_beat`، `api_websocket` و `plugin_daemon`، bundle میزبان در مسیر یکسان `/etc/ssl/certs/ca-certificates.crt` به‌صورت read-only mount شد؛ متغیرهای `REQUESTS_CA_BUNDLE`، `SSL_CERT_FILE` و `PIP_CERT` به همین مسیر اشاره کردند. نسخهٔ پشتیبان Compose در `.runtime/compose.before-vdi-ca.yaml` نگهداری شد. این فایل‌ها تنظیمات محلی‌اند؛ CA یا اعتبارنامه را وارد Git نکنید.

**وضعیت تاریخی و ادامهٔ جدید:** این overlay هنگام ارتقا همراه تغییر Compose در stash ذخیره شد. در ادامهٔ ۳۱ اکتبر فقط همین فایل از stash بازیابی، بعد از `.runtime/compose.build.json` به include اصلی افزوده و Compose اعتبارسنجی شد؛ بازآفرینی پنج سرویس زیر انجام و آزمون API به Marketplace دوباره HTTP 200 داد. کل stash بازگردانده نشد. restart ساده برای mount/env جدید کافی نیست:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" up -d --no-build --no-deps api worker worker_beat api_websocket plugin_daemon
```

آزمون داخل API پس از اعمال تنظیم:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" exec -T api python -c "import requests; r=requests.get('https://marketplace.dify.ai/', timeout=20); print('HTTP status:', r.status_code)"
```

پاسخ مشاهده‌شده ۲۰۰ بود و کاربر سپس نصب موفق افزونهٔ `langgenius/openai_api_compatible` نسخهٔ `0.0.73` را گزارش کرد. قبل از رفع CA، API خطای `Reached maximum retries` برای download-url و Plugin Daemon خطای `plugin not found` داشت. نصب افزونه ممکن است به دریافت وابستگی‌های Python نیز نیاز داشته باشد؛ نتیجهٔ همین نصب را تضمین شبکهٔ دیگر ندانید. این تنظیم runtime مستقل از `KARA_CA_BUNDLE` برای bootstrap/build در [راهنمای استقرار](deployment.md) است. پیش از به‌روزرسانی، ادغام فایل‌های Compose و حفظ تنظیم محلی را بررسی کنید.

### نصب و اجرای Runner شخصی

از صفحهٔ «Runnerهای شخصی»، بستهٔ همان نسخهٔ برنامه دریافت شد و با Python میزبان در پوشهٔ `$HOME/kara-runner` استخراج شد:

```bash
python3 -m zipfile -e "$HOME/Downloads/kara-source-runner.zip" "$HOME/kara-runner"
```

```bash
python3 -m venv "$HOME/kara-runner/.venv"
```

```bash
"$HOME/kara-runner/.venv/bin/python" -m pip install --cert /etc/ssl/certs/ca-certificates.crt -r "$HOME/kara-runner/requirements.txt"
```

Python میزبان این نصب ۳.۱۰ بود و pip از مخزن داخلی تنظیم‌شدهٔ میزبان استفاده کرد. آدرس index و امکان دریافت بسته‌ها را روی دستگاه دیگر بررسی کنید؛ نصب روی Python میزبان با Python ۳.۱۲ کانتینر bootstrap یکی نیست.

در رابط، نام دستگاه ثبت و کد یک‌بارمصرف ساخته شد. سپس:

```bash
cd "$HOME/kara-runner" && .venv/bin/python -m kara_source_runner pair --server http://127.0.0.1:8080
```

فرمان بالا مربوط به pairing اولیهٔ Runner روی همان VDI است؛ برای دستگاه paired دوباره اجرا نشود. بستهٔ نصب‌شده HTTP غیرloopback را رد می‌کند؛ برای pairing تازه روی شبکه از HTTPS معتبر استفاده کنید. در ادامهٔ ۳۱ اکتبر، pairing فعلی تغییر نکرد و با افزودن binding محلی Nginx به `127.0.0.1:8080` دوباره online شد. تغییر origin در device.json، owner_id سورس‌های آماده را نیز تغییر می‌دهد؛ آن را بدون طرح انتقال تغییر ندهید. کد pairing در prompt وارد می‌شود، نه گفتگو یا دستور ثابت. تنظیم دستگاه در `~/.config/kara-source-runner/device.json` خصوصی است. اجرای Runner بدون sudo:

```bash
cd "$HOME/kara-runner" && REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt .venv/bin/python -m kara_source_runner run
```

پیام‌های مشاهده‌شده `Code execution backend: docker` و `Runner online` بودند. این پیام به‌تنهایی اثبات اجرای موفق کد با Docker و مجوز socket کاربر نیست؛ آن آزمون هنوز باقی است. ترمینال باید باز بماند؛ Ctrl+C Runner را متوقف می‌کند. pairing تکراری برای هر بار اجرا لازم نیست. سرویس دائمی/شروع پس از reboot در این گفتگو تنظیم نشد.

### اتصال‌های شخصی و دریافت سورس

- جیرا: پس از pairing، اجرای Runner و انتخاب مقصد اجرای پروژه، آزمون اتصال و احراز هویت موفق شد. موفقیت آزمون، مجوز جست‌وجوی همهٔ درخواست‌ها را ثابت نمی‌کند.
- مدل: دو اتصال شخصی ثبت شدند؛ آزمون‌های تاریخی `model_request_failed` داشتند. در ادامهٔ ۳۱ اکتبر، اعتبارسنجی Assist در کلاسور و Workflow سه‌گرهی با پاسخ واقعی `12` موفق شدند؛ علت شکست اجرای قبلی با temperature برابر ۰٫۷ قطعی نیست.
- گیت‌لب: توکن شخصی با دسترسی خواندن مخزن و هویت کاربر ساخته و آزمون اتصال موفق شد. توکن فقط در فرم اتصال ذخیره شد؛ هیچ توکنی در این سند نیست.
- برای worktree، حداکثر ۸ بخش با شناسه، مسیر نسبی جداگانه، مخزن/برنچ و اتصال شخصی تعریف شد؛ ذخیرهٔ فرم فقط تعریف را ثبت می‌کند. «آماده‌سازی روی Runner» دریافت واقعی و ثبت commit هر بخش را انجام می‌دهد.
- در آماده‌سازی اولیه، چند مخزن دریافت شدند ولی یک آدرس اشتباه بود؛ `Preparation failed: git_failed` رخ داد. اصلاح URL مخزن باید در تعریف worktree نیز ذخیره شود؛ سپس آماده‌سازی تازه انجام شود. تاریخچهٔ ناموفق قبلی باقی می‌ماند.
- `curl` بدون احراز هویت به Git smart-HTTP پاسخ ۴۰۱ داد که برای مخزن خصوصی طبیعی بود؛ با توکن پاسخ ۲۰۰ دریافت شد. موفقیت مخزن اول، وجود/مجوز مخزن بعدی را ثابت نمی‌کند. توکن را در URL ننویسید و برای تشخیص، TLS را خاموش نکنید.
- هنگام غیرفعال‌بودن آماده‌سازی، Runner واقعاً متوقف بود و فهرست «Runner مقصد» نیز انتخاب نداشت. Runner دوباره اجرا و مقصد انتخاب شد؛ صرف وجود دستگاه paired کافی نیست.
- آماده‌سازی نهایی با وضعیت «آماده»، نسخهٔ تعریف ۶ و commit هر ۸ مخزن تأیید شد. سپس در «Runnerهای شخصی ← ویرایش مقصد»، همان نتیجه از فهرست «فایل‌های سورس در دسترس اجرا» انتخاب و «ذخیرهٔ مقصد اجرا» زده شد. پیام موفقیت و انتخاب ذخیره‌شده در تصویر ثبت شدند.

فایل‌ها زیر `$HOME/KaraSourceWorkspaces/<preparation-id>` روی VDI هستند. هر آماده‌سازی پوشهٔ تازه‌ای دارد؛ فایل‌های تلاش قبلی را برای رفع خطا حذف نکنید. اتصال سورس به مقصد به‌تنهایی اجرای برنامه یا مجوز نوشتن/push/merge ایجاد نمی‌کند. جزئیات در [راهنمای سورس و Runner](source-code-runner.md) و [اجرای محلی](local-execution.md) است.

### وضعیت فعلی آزمون برنامه و کارهای باقی‌مانده

برنامهٔ `Chatflow Basic: Chatbot` ابتدا به provider نصب‌نشدهٔ `langgenius/openai/openai` و `gpt-5.4-mini` اشاره می‌کرد. بعداً اشکال انتخابگر مدل شخصی رفع شد: هر دو مدل دیده شدند، Assist انتخاب شد و پیام ناسازگاری اشتباه رفع شد. patch رسمی در `infra/web/personal-model-selector.patch` است و با آماده‌سازی سورس تازه اعمال می‌شود؛ overlay دستی قدیمی انتخابگر را برنگردانید. مسیر summary اعتبارات مشترک عمداً 403 می‌دهد و نباید برای عبور از UI باز شود؛ سایر مصرف‌کنندگان احتمالی آن نیاز به مرور دارند.

در زمان تحویل اولیه دو مانع مستقل وجود داشت؛ وضعیت جدید هر یک:

1. پیش‌نمایش این برنامه از نوع `advanced-chat`، پیش از فراخوانی مدل در `local_dispatch.submit` رد می‌شود؛ مسیر فعلی فقط `workflow` را می‌پذیرد و خطا به 500 تبدیل می‌شود. پشتیبانی chatflow باید با حفظ مرز اجرای محلی اضافه شود؛ حذف guard یا fallback اجرای سروری راه‌حل پذیرفته‌شده نیست.
2. اعتبارسنجی اتصال شخصی از مسیر local RPC قبلاً `BadGateway` و `model_request_failed` می‌داد. اتصال Assist به `https://aifa-chatbot.sandpod.ir/v1` با نام سرویس `assistance-model` است. DNS در VDI آدرس `79.132.215.248` داد؛ curl تاریخی روی 443 خطای `Connection refused` و `HTTP=000` داشت. در ادامهٔ ۳۱ اکتبر، curl بدون توکن و با noproxy از همان IP پاسخ HTTP 200 گرفت؛ اعتبارسنجی Assist در پروژهٔ کلاسور و Workflow واقعی نیز موفق شدند. علت تغییر دسترسی نسبت به گذشته قطعی نیست. خطای نبود افزونه در پروژه‌ای دیگر، با بازگشت کاربر به کلاسور برطرف شد؛ نصب مجدد لازم نشد.

همگام‌سازی دو کاربر پس از اصلاح WebSocket/app context و origin تأیید شد. اجرای مدل اکنون با Workflow «آزمون مدل روی VDI» تأیید جداگانه دارد: `{"answer":"12"}`، ۳ گام، ۳۷٫۰۸۸ ثانیه و ۱۰۸۵ توکن؛ temperature صفر و max_tokens برابر ۱۲۸ بود. انتشار برنامه، خواندن سورس و اجرای کد Docker هنوز تأیید نشده‌اند. پیگیری‌های فعلی شامل آزمون کد/سورس، تطبیق کامل نسخهٔ Runner، پشتیبانی Chatflow در صورت درخواست، جست‌وجوی جیرا، reboot/اجرای دائمی Runner، restore واقعی و نصب VDI دوم‌اند. جزئیات، backupها و وضعیت انتشار/CA در [سند تحویل](vdi-handoff-2026-10-31.fa.md) است.

مراجع: [راهنمای عمومی Docker پروژه](docker-quickstart.md)، [Docker image رسمی Weaviate](https://hub.docker.com/r/semitechnologies/weaviate)، [اتصال مدل](company-model-connection.md).
