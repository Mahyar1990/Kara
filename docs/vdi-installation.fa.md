# نصب کارا روی VDI لینوکسی با شبکهٔ محدود

> مسیر قابل‌تکرار جدید در [راهنمای استقرار](deployment.md) آمده است. تغییرات دستی فایل‌های تولیدشده در ادامه، شرح مسیر نصب قبلی‌اند؛ برای نصب جدید از تنظیمات راه‌انداز استفاده کنید.

این راهنما حاصل نصب واقعی در ۲۹ اکتبر ۲۰۲۶ است. هدف، نصب مستقل کارا برای یک کاربر دیگر است؛ حساب‌ها، رمزها و بانک دادهٔ محیط قبلی منتقل نمی‌شوند. دستورها در ترمینال **خود VDI** اجرا می‌شوند. هر مرحله باید موفق شود و سپس مرحلهٔ بعد انجام شود.

موفقیت این نصب به معنی تضمین نصب روی هر شبکه یا نسخهٔ آینده نیست. مسیر زیر خطاهای مشاهده‌شده را از ابتدا پیشگیری می‌کند؛ نسخه‌ها، دسترسی رجیستری و گواهی‌های VDI جدید باید دوباره بررسی شوند.

## نتیجه و محدودهٔ تأییدشده

- API و وب فارسی از سورس ساخته شدند؛ بررسی نوع‌ها، آزمون‌های رابط و ساخت Next.js در Dockerfile فعال ماندند و مراحل ساخت موفق شدند.
- مهاجرت پایهٔ بانک با ایمیج اصلی انجام شد؛ سپس سرویس‌های اختصاصی کارا شروع شدند.
- API داخل کانتینر و از پورت محلی `8080` پاسخ `{"result":"pong"}` داد.
- صفحهٔ نصب فارسی باز شد، حساب مدیر ساخته شد و صفحهٔ پروژه‌های خالی نمایش داده شد.
- در ادامهٔ نصب، پروژه ساخته شد؛ آزمون احراز هویت جیرا و گیت‌لب موفق بود، کاربر رفع خطای توکن مدل را گزارش کرد و worktree هشت‌مخزنی نسخهٔ ۶ آماده و به مقصد اجرا متصل شد. جزئیات در بخش «ادامهٔ راه‌اندازی» آمده است.
- پاسخ واقعی مدل در برنامه، دسترسی واقعی برنامه به سورس، پذیرش همهٔ سرویس‌ها، راه‌اندازی پس از reboot و بازیابی backup هنوز تأیید نشده‌اند. `make doctor` روی VDI در شواهد گفتگو اجرا نشد.
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

این منابع نمونهٔ موفق‌اند، نه حداقل اندازه‌گیری‌شده یا ظرفیت تضمین‌شده. ساخت وب و cacheها فضای بیشتری مصرف می‌کنند؛ فضای `/home` و دیسک Docker جداگانه بررسی شوند. شاخهٔ بالا شاخهٔ همین جلسه است؛ برای انتشار بعدی، شاخه/commit مورد توافق را انتخاب و ثبت کنید. hash دقیق checkout روی VDI در تصاویر این جلسه ثبت نشد؛ hash محیط مک را جای آن ننویسید.

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

## ۳. آماده‌سازی بدون apt در کانتینر bootstrap

مسیر عادی پروژه (`compose.setup.yaml`) از `python:3.12-slim-bookworm` استفاده و Git را با apt نصب می‌کند. روی این شبکه، HTTP مخزن Debian مسدود بود؛ HTTPS هم ابتدا خطای CA و پس از استفاده از CA میزبان، صفحهٔ مسدودی سازمان و 403 داد. برای این VDI، مستقیماً از ایمیج کامل استفاده کنید:

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

```bash
sudo docker tag semitechnologies/weaviate:1.39.2 cr.weaviate.io/semitechnologies/weaviate:1.39.2
```

tag فقط نام محلی اضافه می‌کند؛ نسخهٔ ایمیج تغییر نمی‌کند. نیازی به تغییر سورس ثابت upstream نیست. digest را از خروجی واقعی `docker pull` محیط خود ثبت کنید. معیار این دستور، نام و نسخهٔ مخزن رسمی است؛ برابری digest دو رجیستری در این جلسه جداگانه مقایسه نشد.

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

## ۶. یک‌بار تنظیم ساخت وب مخصوص VDI

چهار مشکل مرتبط در نصب وب مشاهده شد:

1. `apk add tzdata` به دلیل CA نامعتبر شکست خورد؛ با CA میزبان، مخزن Alpine همچنان 403 داد.
2. فایل‌های `/usr/share/zoneinfo` در ایمیج کامل Python موجود بودند؛ به‌جای نصب APK، همان داده‌ها به تصویر وب کپی شدند. این کار نصب بستهٔ Alpine نیست؛ تأمین فایل‌های زمانی لازم است.
3. Corepack ابتدا از npm عمومی و بعد از آدرس غیرمنتظرهٔ `nexus.itr.co` دانلود می‌کرد. علت دقیق این تغییر مسیر ثابت نشد؛ نصب مستقیم همان نسخهٔ pnpm با npm موفق شد.
4. تنظیم `npm_config_registry` به‌تنهایی مانع درخواست عمومی metadata در مرحلهٔ pnpm نشد. افزودن صریح `--registry=...` به `pnpm install` مشکل را حل کرد. بررسی supply-chain، lockfile، typecheck و آزمون‌ها خاموش نشدند.

دستور زیر جایگزین **مجموع اصلاحات دستی این ترد** است. فقط Dockerfile تولیدشده در `.runtime/dify-web-source` و یک کپی CA را تغییر می‌دهد؛ سورس tracked و `.runtime/dify` دست‌نخورده می‌مانند. اسکریپت از Dockerfile tracked دوباره تولید می‌کند و اگر نسخه یا خطوط مورد انتظار عوض شده باشند، متوقف می‌شود. این دستور یکپارچه در قالب همین راهنما تدوین شده؛ اجزای معادل آن روی VDI موفق بودند، اما اجرای تازهٔ کل دستور روی VDI دوم هنوز انجام نشده است.

```bash
sudo docker run --rm -i \
  --user "$(id -u):$(id -g)" \
  -v "$HOME/Kara:/workspace" \
  -v /etc/ssl/certs/ca-certificates.crt:/tmp/vdi-ca.crt:ro \
  python:3.12-bookworm python - <<'PY'
import json
from pathlib import Path
import shutil

root = Path('/workspace')
source = root / '.runtime/dify-web-source'
folder = source / '.company-web'
target = folder / 'Dockerfile'
text = (root / 'infra/web/Dockerfile').read_text()
manager = json.loads((source / 'package.json').read_text())['packageManager']
if manager != 'pnpm@12.3.4':
    raise SystemExit('Package manager changed; review this runbook before patching.')
registry = 'https://nexus3.dotin.ir/repository/Dotin-NPM/'
replacements = {
    'RUN apk add --no-cache tzdata && corepack enable': f'''COPY --from=python:3.12-bookworm /usr/share/zoneinfo /usr/share/zoneinfo
COPY .company-web/vdi-ca.crt /usr/local/share/ca-certificates/vdi-ca.crt
ENV NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/vdi-ca.crt
ENV npm_config_registry={registry}
RUN npm install --global --ignore-scripts --no-audit --no-fund pnpm@12.3.4''',
    'corepack install && ': '',
    'pnpm install --frozen-lockfile': f'pnpm install --registry={registry} --frozen-lockfile',
}
for old in replacements:
    if text.count(old) != 1:
        raise SystemExit(f'Unexpected Dockerfile; no changes made: {old}')
for old, new in replacements.items():
    text = text.replace(old, new, 1)
backup = folder / 'Dockerfile.before-vdi'
if not backup.exists():
    shutil.copyfile(target, backup)
shutil.copyfile('/tmp/vdi-ca.crt', folder / 'vdi-ca.crt')
target.write_text(text)
print('VDI web build configuration is ready.')
PY
```

گواهی‌های مورد اعتماد VDI در ایمیج وب قرار می‌گیرند و Node از آن‌ها استفاده می‌کند؛ trust store سیستم میزبان تغییر نمی‌کند. این ایمیج مختص محیط سازمان است. فایل CA عمومی است و کلید خصوصی نیست، ولی تنظیمات سازمانی و ایمیج تولیدشده را بی‌بررسی منتشر نکنید.

**هر اجرای مجدد setup این Dockerfile تولیدشده را بازنویسی می‌کند.** پس از setup یا به‌روزرسانی، این مرحله را دوباره و با کنترل سازگاری اجرا کنید. فرمان `make up` نیز ممکن است سورس ساخت را دوباره آماده کند؛ برای این محیط از مسیر Compose مستندشده استفاده کنید.

## ۷. ساخت بدون شروع زودهنگام API

```bash
sudo docker compose --parallel 1 --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" build api web
```

ساخت اولیه می‌تواند چندین دقیقه طول بکشد. در نصب حاضر دریافت بسته‌ها، بررسی نوع‌ها، آزمون‌های رابط و کامپایل وب موفق شدند. هنگام شکست، آخرین خط خطا و مرحلهٔ شکست را بخوانید؛ موفقیت `Built` با آماده‌بودن سرویس تفاوت دارد.

## ۸. مهاجرت پایه پیش از سرویس‌های اختصاصی

این ترتیب برای clone و بانک تازه مهم است. در ترد ابتدا همهٔ سرویس‌ها شروع شدند و API در مهاجرت اختصاصی با `tenant_account_joins does not exist` شکست خورد. برای نصب بعدی از ابتدا وابستگی‌ها را روشن کنید:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" up -d --no-build --pull missing db_postgres redis weaviate
```

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" ps db_postgres redis weaviate
```

پیش از مهاجرت، PostgreSQL باید `healthy` باشد. اگر قبلاً همهٔ سرویس‌ها را روشن کرده‌اید، ابتدا آن چهار سرویس را متوقف کنید:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" stop api worker worker_beat api_websocket
```

سپس با **ایمیج اصلی** مهاجرت پایه را اجرا کنید، نه ایمیج سفارشی کارا:

```bash
sudo docker run --rm \
  --network company-agent-local_default \
  --env-file "$HOME/Kara/.runtime/compose.env" \
  --workdir /app/api \
  --entrypoint /app/api/.venv/bin/flask \
  langgenius/dify-api:1.17.1 db upgrade
```

نام شبکه مربوط به نام پیش‌فرض پروژه است. اگر نام پروژه را در تنظیمات تغییر داده‌اید، شبکه و نام پروژه باید مطابق همان محیط باشند. env به‌صورت فایل خصوصی خوانده می‌شود؛ آن را چاپ نکنید. انتظار: اجرای upgradeها و پایان با exit code صفر. برای بانک دارای دادهٔ قبلی، پیش از ارتقا backup معتبر تهیه کنید؛ داده‌های آن محیط را حذف نکنید.

این ترتیب پیشنهادی از اقدامات موفق جلسه استخراج شده است؛ بازاجرای کامل آن روی بانک تازهٔ دوم در این ترد انجام نشد. راه‌حل تعمیر تجربه‌شده، توقف چهار سرویس، اجرای همین `db upgrade` و شروع دوبارهٔ آن‌ها بود.

## ۹. راه‌اندازی و بررسی پاسخ واقعی

```bash
sudo docker compose --parallel 1 --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" up -d --no-build --pull missing
```

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" ps -a
```

`init_permissions` یک کار اولیه است؛ پایان موفق آن با کد صفر طبیعی است. سرویس‌های طولانی‌مدت نباید در چرخهٔ restart باشند. برای تأیید API:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:5001/console/api/ping', timeout=20).read().decode())"
```

```bash
curl --noproxy '*' --fail --show-error --max-time 20 http://127.0.0.1:8080/console/api/ping
```

انتظار در هر دو: `{"result":"pong"}`. در این جلسه curl معمولی به `localhost` پاسخ 502 داد، اما API مستقیم و سپس curl با `127.0.0.1` و `--noproxy` موفق شدند. چون هم نام میزبان و هم رفتار proxy تغییر کردند و زمان هم گذشته بود، علت قطعی 502 آخر از این آزمایش به‌تنهایی معلوم نیست؛ آن را قطعاً خرابی Nginx یا قطعاً proxy ننامید. از دستور مستقیم بالا برای بررسی محلی استفاده کنید؛ نیازی به خاموش‌کردن پراکسی کل سیستم نیست.

اگر شکست خورد:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" logs --since 3m --tail 80 api nginx
```

خطای migration با 502 زمان شروع یا مشکل مسیر شبکه متفاوت است. `Listening at ...:5001` نشانهٔ شروع Gunicorn است؛ پاسخ واقعی ping مدرک بهتری برای دسترس‌پذیری API است. در این جلسه لاگ `Database migration skipped` بعد از اجرای دستی پایه مانع پاسخ موفق نشد.

## ۱۰. ساخت حساب مستقل

در Firefox **داخل VDI**، [صفحهٔ نصب کارا](http://127.0.0.1:8080/install) را باز کنید. ایمیل، نام و رمز مدیر جدید را وارد و «راه‌اندازی» را انتخاب کنید. شرط مشاهده‌شدهٔ فرم: حداقل ۸ نویسه شامل حرف و عدد. رمز را در اسکرین‌شات آشکار نکنید.

پس از موفقیت، [پروژه‌ها](http://127.0.0.1:8080/projects) باز می‌شود. خالی‌بودن پروژه‌ها در نصب مستقل طبیعی است؛ clone سورس پروژه‌ها و داده‌های محیط قبلی را منتقل نمی‌کند. در این نقطه نصب اولیه پذیرفته شده است. اتصال مدل مرحلهٔ جداگانه‌ای است.

نوار Firefox با متن `You must log in to this network...` در تصاویر وجود داشت، ولی صفحهٔ محلی و ساخت حساب موفق بودند؛ آن نوار را مدرک شکست نصب کارا در نظر نگیرید.

## استفادهٔ روزمره، به‌روزرسانی و تحویل

شروع روزمره، بدون ساخت مجدد:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" up -d --no-build --pull missing
```

توقف با حفظ داده‌ها:

```bash
sudo docker compose --project-directory "$HOME/Kara" -f "$HOME/Kara/compose.yaml" stop
```

برای به‌روزرسانی: وضعیت Git و backup را بررسی، نسخهٔ مورد توافق را دریافت، setup را اجرا، اصلاحات مرحلهٔ ۶ را دوباره اعمال و سازگاری نسخه‌ها را کنترل کنید؛ سپس build و مهاجرت متناسب با همان نسخه را انجام دهید. دستورهای این سند را کورکورانه برای نسخهٔ جدید استفاده نکنید.

`.runtime` را حذف نکنید؛ `docker compose down -v`، `docker system prune` و پاک‌کردن volumeها راه‌حل معمول خطاهای این نصب نیستند. این ترد چنین پاک‌سازی‌ای انجام نداد.

در تحویل نفر بعد ثبت کنید: commit واقعی سورس، نسخه و معماری ایمیج‌ها، آدرس مخزن داخلی، تاریخ اعتبار CA، نتیجهٔ ساخت و migration، هر دو ping و ورود به صفحهٔ پروژه‌ها. env، رمز مدیر، کلید مدل، داده‌های بانک، cacheهای شخصی و کل `.runtime` را به مخزن Git یا گزارش عمومی اضافه نکنید.

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
| 502 با API سالم | آزمون مستقیم API و سپس curl با noproxy/127.0.0.1 موفق شد؛ علت آخر قطعی نبود |

## ادامهٔ راه‌اندازی: اتصال‌ها، Runner و worktree

این بخش بر اساس تصاویر و گزارش کاربر تا ۳۰ اکتبر ۲۰۲۶، برای تحویل در ۳۱ اکتبر ثبت شده است؛ وضعیت زندهٔ VDI در زمان خواندن باید دوباره بررسی شود. [سند تحویل چت](vdi-handoff-2026-10-31.fa.md) نقطهٔ توقف و فهرست پیگیری را دارد. این بخش تغییر جدیدی روی VDI اعمال نمی‌کند.

### گواهی سرویس‌های در حال اجرا و نصب افزونهٔ مدل

قابل‌دسترسی‌بودن Marketplace از میزبان، اعتماد TLS داخل API را ثابت نمی‌کند. در این نصب، `curl` میزبان پاسخ ۲۰۰ داد ولی Python داخل API با `self-signed certificate in certificate chain` شکست خورد. آزمون همان درخواست با CA معتبر میزبان در API پاسخ ۲۰۰ داد.

روی **همین VDI**، فایل محلی `infra/compose.vdi-ca.yaml` ساخته و بعد از `.runtime/compose.build.json` به فهرست مسیرهای Compose اصلی اضافه شد. برای سرویس‌های `api`، `worker`، `worker_beat`، `api_websocket` و `plugin_daemon`، bundle میزبان در مسیر یکسان `/etc/ssl/certs/ca-certificates.crt` به‌صورت read-only mount شد؛ متغیرهای `REQUESTS_CA_BUNDLE`، `SSL_CERT_FILE` و `PIP_CERT` به همین مسیر اشاره کردند. نسخهٔ پشتیبان Compose در `.runtime/compose.before-vdi-ca.yaml` نگهداری شد. این فایل‌ها تنظیمات محلی‌اند؛ CA یا اعتبارنامه را وارد Git نکنید.

پس از `config --quiet` موفق، تنظیم با فرمان زیر اعمال شد؛ restart ساده برای اعمال mount و env جدید کافی نیست:

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

کد در prompt وارد شد؛ آن را در گفتگو یا دستور ثابت قرار ندهید. تنظیم دستگاه در `~/.config/kara-source-runner/device.json` خصوصی است. اجرای Runner بدون sudo:

```bash
cd "$HOME/kara-runner" && REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt .venv/bin/python -m kara_source_runner run
```

پیام‌های مشاهده‌شده `Code execution backend: docker` و `Runner online` بودند. این پیام به‌تنهایی اثبات اجرای موفق کد با Docker و مجوز socket کاربر نیست؛ آن آزمون هنوز باقی است. ترمینال باید باز بماند؛ Ctrl+C Runner را متوقف می‌کند. pairing تکراری برای هر بار اجرا لازم نیست. سرویس دائمی/شروع پس از reboot در این گفتگو تنظیم نشد.

### اتصال‌های شخصی و دریافت سورس

- جیرا: پس از pairing، اجرای Runner و انتخاب مقصد اجرای پروژه، آزمون اتصال و احراز هویت موفق شد. موفقیت آزمون، مجوز جست‌وجوی همهٔ درخواست‌ها را ثابت نمی‌کند.
- مدل: دو اتصال شخصی ثبت شدند؛ خطای اولیه ناشی از توکن اشتباه بود و کاربر رفع آن را گزارش کرد. هنوز خروجی واقعی یک برنامه با این مدل در تصاویر ثبت نشده است.
- گیت‌لب: توکن شخصی با دسترسی خواندن مخزن و هویت کاربر ساخته و آزمون اتصال موفق شد. توکن فقط در فرم اتصال ذخیره شد؛ هیچ توکنی در این سند نیست.
- برای worktree، حداکثر ۸ بخش با شناسه، مسیر نسبی جداگانه، مخزن/برنچ و اتصال شخصی تعریف شد؛ ذخیرهٔ فرم فقط تعریف را ثبت می‌کند. «آماده‌سازی روی Runner» دریافت واقعی و ثبت commit هر بخش را انجام می‌دهد.
- در آماده‌سازی اولیه، چند مخزن دریافت شدند ولی یک آدرس اشتباه بود؛ `Preparation failed: git_failed` رخ داد. اصلاح URL مخزن باید در تعریف worktree نیز ذخیره شود؛ سپس آماده‌سازی تازه انجام شود. تاریخچهٔ ناموفق قبلی باقی می‌ماند.
- `curl` بدون احراز هویت به Git smart-HTTP پاسخ ۴۰۱ داد که برای مخزن خصوصی طبیعی بود؛ با توکن پاسخ ۲۰۰ دریافت شد. موفقیت مخزن اول، وجود/مجوز مخزن بعدی را ثابت نمی‌کند. توکن را در URL ننویسید و برای تشخیص، TLS را خاموش نکنید.
- هنگام غیرفعال‌بودن آماده‌سازی، Runner واقعاً متوقف بود و فهرست «Runner مقصد» نیز انتخاب نداشت. Runner دوباره اجرا و مقصد انتخاب شد؛ صرف وجود دستگاه paired کافی نیست.
- آماده‌سازی نهایی با وضعیت «آماده»، نسخهٔ تعریف ۶ و commit هر ۸ مخزن تأیید شد. سپس در «Runnerهای شخصی ← ویرایش مقصد»، همان نتیجه از فهرست «فایل‌های سورس در دسترس اجرا» انتخاب و «ذخیرهٔ مقصد اجرا» زده شد. پیام موفقیت و انتخاب ذخیره‌شده در تصویر ثبت شدند.

فایل‌ها زیر `$HOME/KaraSourceWorkspaces/<preparation-id>` روی VDI هستند. هر آماده‌سازی پوشهٔ تازه‌ای دارد؛ فایل‌های تلاش قبلی را برای رفع خطا حذف نکنید. اتصال سورس به مقصد به‌تنهایی اجرای برنامه یا مجوز نوشتن/push/merge ایجاد نمی‌کند. جزئیات در [راهنمای سورس و Runner](source-code-runner.md) و [اجرای محلی](local-execution.md) است.

### نقطهٔ توقف آزمون برنامه

در استودیو برنامه‌ای وجود نداشت. از «ایجاد از قالب»، `Chatflow Basic: Chatbot` ساخته شد. گرهٔ LLM قالب به `langgenius/openai/openai` و مدل `gpt-5.4-mini` اشاره می‌کرد؛ خطای `Provider langgenius/openai/openai does not exist` دیده شد. این افزونه با افزونهٔ نصب‌شدهٔ OpenAI-API-compatible متفاوت است. قدم بعد، انتخاب مدل/ارائه‌دهندهٔ سازگار با اتصال شخصی موجود در گرهٔ LLM است؛ نصب مجدد کل محیط یا نصب افزونهٔ OpenAI صرفاً به دلیل پیش‌فرض قالب لازم نیست. هنوز نتیجهٔ انتخاب مدل و اجرای واقعی دریافت نشده است. Chatbot ساده، آزمون دسترسی به سورس نیست؛ آن را جداگانه با ابزار/مرحلهٔ مناسب و اجرای واقعی بررسی کنید.

مراجع: [راهنمای عمومی Docker پروژه](docker-quickstart.md)، [Docker image رسمی Weaviate](https://hub.docker.com/r/semitechnologies/weaviate)، [اتصال مدل](company-model-connection.md).
