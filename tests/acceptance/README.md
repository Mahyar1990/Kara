# پذیرش زندهٔ هستهٔ تیمی Kara (KP-08)

`kara_team_lifecycle.py` سناریوی ساختگی چندحسابی را از مسیر HTTP واقعی و موتور بومی اجرا می‌کند. آزمون واحد یا جزئی از `make check` نیست. به سرویس‌های محلی، PostgreSQL، Redis، تصاویر فعلی Kara و پوشهٔ خصوصی شواهد نیاز دارد. هیچ LLM در این سناریو فراخوانی نمی‌شود.

## آماده‌سازی و ترتیب اجرا

1. از بانک اصلی پشتیبان و snapshot شمار/hash جدول‌های کسب‌وکار بگیرید. پشتیبان را در **بانک تازه** با نام دقیق `kara_kp08_acceptance` بازیابی کنید؛ بانک موجود را overwrite نکنید. ورود اولیهٔ مدیر و پروژه‌های قبلی از همین پشتیبان می‌آیند. تصویرهای API و وب باید با سورس فعلی منطبق باشند.
2. یک override خصوصی Compose بسازید که `DB_DATABASE` سرویس‌های `api`، `worker`، `worker_beat` و `api_websocket` را به بانک آزمون تغییر دهد. فقط API را با override بالا بیاورید؛ worker، beat و websocket را در ابتدا متوقف نگه دارید. Compose را با `config --quiet` بررسی کنید. همهٔ سرویس‌ها از همان Redis و nginx محلی استفاده می‌کنند؛ این آزمون را روی محیط مشترک/تولید اجرا نکنید.
3. فایل آزمون را read-only در `/acceptance.py` و پوشهٔ خصوصی خارج از Git را در `/proof` به کانتینر یک‌بارهٔ API mount کنید. فرمان هر مرحله `/app/api/.venv/bin/python /acceptance.py <phase>` است. همان فایل‌های Compose، env و project-name راه‌انداز `scripts/local_dify.py` را به کار ببرید؛ `compose(..., capture=True)` خروجی خصوصی و خطای subprocess را نیز ذخیره کند.
4. یک بار `seed` و سپس `exercise` را اجرا کنید. seed حساب‌های ساختگی با رمز تصادفی، دو پروژه، دو برنامهٔ قطعی، grant، نقش PO و دو فلو می‌سازد. رمزها فقط در `/proof/fixture.json` با دسترسی 0600 ذخیره می‌شوند. هویت/برنامهٔ پایه با fixture پایگاه داده ساخته می‌شود؛ عملیات تیمی از HTTP و JWT/CSRF حساب واقعی استفاده می‌کنند. این شاهد دعوت ایمیلی یا onboarding نیست.
5. API را واقعاً restart کنید و منتظر ping بمانید. worker را با همان override بالا بیاورید، `after-restart` را اجرا و worker را دوباره متوقف کنید. این مرحله تحویل تلاش pending واقعی به Celery را بررسی می‌کند.
6. `controls` را اجرا کنید. clock قدیمی برای یک تلاش claim‌شده، شبیه‌سازی orphan است؛ کشتن واقعی worker در تماس بیرونی انجام نمی‌شود. خروجی موفق نهایی دقیقاً هشت WorkflowRun متعلق به دو برنامهٔ fixture را بررسی می‌کند.
7. با ورود واقعی حساب بازبین، پروژهٔ مجاز، پرونده، خروجی تحویل‌شده، سابقه و وضعیت نهایی را در مرورگر بررسی کنید؛ خروج و ورود دوباره نباید سابقه را از بین ببرد. رمزها را چاپ نکنید. تصویر و لاگ را خصوصی نگه دارید.
8. از بانک آزمون نهایی پشتیبان بگیرید، در بانک تازهٔ دیگری بازیابی و شمار/hash محتوا را مقایسه کنید. سپس تمام سرویس‌ها را با تنظیمات اصلی (`make up`) به `dify` برگردانید؛ snapshot اصلی، Compose، `make doctor` و پروژه‌های قبلی در مرورگر بررسی شوند. بانک اصلی را از dump آزمون بازیابی نکنید.

نمونهٔ اجرای یک phase از ریشهٔ مخزن، پس از آماده‌سازی override و بانک جداگانه (برای مراحل بعد فقط `seed` را با نام همان مرحله جایگزین کنید):

```sh
.venv/bin/python - seed <<'PYTHON'
import subprocess, sys
from pathlib import Path
sys.path.insert(0, 'scripts')
import local_dify
phase = sys.argv[1]
assert phase in ('seed', 'exercise', 'after-restart', 'controls')
proof = Path('.runtime/kp08').resolve()
assert proof.is_dir() and (proof / 'override.yaml').is_file()
args = ['-f', str(proof / 'override.yaml'), 'run', '--rm', '--no-deps',
        '-v', str(proof) + ':/proof',
        '-v', str(Path('tests/acceptance/kara_team_lifecycle.py').resolve()) + ':/acceptance.py:ro',
        '--entrypoint', '/app/api/.venv/bin/python', 'api', '/acceptance.py', phase]
try:
    result = local_dify.compose(args, capture=True)
except subprocess.CalledProcessError as error:
    (proof / (phase + '.log')).write_text((error.stdout or '') + (error.stderr or ''))
    raise SystemExit('FAIL; inspect private phase log before retrying')
(proof / (phase + '.log')).write_text((result.stdout or '') + (result.stderr or ''))
print(phase + ': PASS')
PYTHON
```

هر مرحله فقط یک بار و به ترتیب اجرا شود. پس از شکست، لاگ و وضعیت خصوصی را بررسی کنید؛ تکرار کورکورانهٔ phase ممکن است fixture تازه بسازد یا شمار اجرا را تغییر دهد. برای پذیرش کامل دوباره، شواهد قبلی را حفظ و محیط آزمون تازه‌ای از پشتیبان اصلی آماده کنید. مسیرهای فایل، فرمان‌های override و توقف/بازگردانی سرویس‌ها مسئولیت اجراکننده‌اند؛ این فایل به‌تنهایی محیط را جابه‌جا نمی‌کند. guard نام بانک، پیش از import برنامه، اجرای اتفاقی با تنظیمات اصلی را رد می‌کند.

## پوشش و حدود

| معیار برنامهٔ آمادگی | شاهد این سناریو |
| --- | --- |
| ۱–۳ | ادمین کل، دو مدیر/پروژه، دو فلو، انتخاب PO، ورود بدون تصمیم رد، اجرای عضو normal با grant، مسیر debug بومی بسته |
| ۴–۵ | دو بازخورد، artifact انسانی، نهایی‌کنندهٔ PO، تحویل فقط خروجی منتخب به نفر دوم، اجرای دستی و بازخورد نفر دوم |
| ۶–۷ | reopen و stale، جلوگیری از انتخاب artifact قدیمی، تصمیم‌های تازه با حفظ تاریخچه؛ رد پروژهٔ دیگر، عضو نامجاز، حذف نقش/لغو grant، CSRF |
| ۸ | finalize هم‌زمان 200/409 و replay، تکرار run/تحویل موتور، pending پس از restart واقعی، orphan/retry صریح، لغو terminal |
| ۹ | انتشار فلو و تغییر pointer نسخهٔ بومی بدون تغییر binding پرونده؛ بازیابی پشتیبان با تطبیق داده |
| ۱۰ | HTTP/DB/WorkflowRun/Celery + مرورگر؛ smoke مستقل مدل طبق راهنمای اتصال شرکت |

تغییر pointer بومی با fixture DB انجام می‌شود؛ API جدیدی برای بازتعریف ایجنت ساخته نشده است. آزمون شکست فنی موتور، تغییر مسئول و سایر رگرسیون‌های جزئیِ موفق در [پذیرش KP-07](../../docs/kara-kp07-validation.md) ثبت شده‌اند و بی‌دلیل تکرار نمی‌شوند. کیفیت مدل، provider بومی LLM، Jira، بار و تضمین exactly-once آثار بیرونی در این پذیرش اثبات نمی‌شوند. نتیجهٔ اجرای این مرحله در [گزارش KP-08](../../docs/kara-kp08-validation.md) ثبت می‌شود.
