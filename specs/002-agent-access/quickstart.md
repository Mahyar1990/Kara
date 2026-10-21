# Quickstart Validation: KP-02

این راهنما برای **پس از پیاده‌سازی** است؛ اجرای زیر در وضعیت فعلی قبولی قابلیت آینده ایجاد نمی‌کند.

## Prerequisites

- KP-01 پذیرفته‌شده. با gate رفع‌نشده آزمون live و acceptance را not_run/blocked ثبت کنید.
- محیط مستقل با بانک بازیابی‌شده، مدل/connector لازم همان بسته و چند حساب synthetic واقعی؛ اطلاعات ورود خصوصی.
- commit/image و schema مبنا، backup و شناسهٔ fixture در گزارش `docs/kara-kp-02-validation.md` ثبت شود.

## Specification Preflight (available now)

```sh
export SPECIFY_FEATURE_DIRECTORY="$PWD/specs/002-agent-access"
.specify/scripts/bash/check-prerequisites.sh --json --require-spec --require-tasks --include-tasks
make check
```

در چت: `$speckit-analyze` با مسیر همین feature. بررسی ساختار و quality با پذیرش اجرا فرق دارد.

## Runtime Preparation (only after implementation)

```sh
make setup
make up
make doctor
```

از راهنمای [محیط محلی](../../docs/local-development.md) و [شواهد KP-01](../../docs/kara-kp01-validation.md)
برای Compose و PostgreSQL/نشست/CSRF محیط مستقل استفاده کنید. `make up` را پیش از انتخاب DB آزمایشی
برای تست تغییردهنده اجرا نکنید؛ default به محیط اصلی اشاره می‌کند. تست‌ها و حساب مصنوعی وارد بانک اصلی نشوند.

آزمون هدف آینده در `infra/api/company_projects/test_team_agents.py` است؛ داخل تصویر API ساخته‌شده و با تنظیم اتصال بانک مستقل اجرا شود.
اگر فایل هنوز ساخته نشده، not_run ثبت کنید؛ فرمان unittest را به موفقیت make check تقلیل ندهید.
الگوی executable پس از وجود فایل و داخل محیط API با `PYTHONPATH=/app/api`:

```sh
python -m unittest company_projects.test_team_agents -v
```

متغیرهای اتصال از محیط خصوصی همان harness گرفته شوند؛ secret در command line یا گزارش مشترک قرار نگیرد.
برای build/TypeScript/تست‌های رابط، [راهنمای وب](../../docs/persian-interface.md) و Dockerfile مشترک
را دنبال کنید؛ source تازه کامپایل شود. `infra/web/team-agents.spec.mjs` به test runner موجود اضافه شود، صرف وجود فایل اجرا نیست.

## Scenarios and Expected Results

1. US1: مدیر دو عضو را با اختیار متفاوت ثبت کند و پس از بازخوانی همان نسخه و اختیارها را ببیند.
2. US2: یک normal مجاز اجرا کند؛ همان فرد نتواند draft یا مجوز دیگری را ویرایش کند.
3. US3: با نشست باز، grant را لغو کنید؛ درخواست بعدی رد شود و سابقهٔ اجرا باقی بماند.
4. منفی/بازیابی: root/owner/admin/editor/normal، دو پروژه، run-only، لغو در نشست باز، grant حذف و عضویت مجدد، REST مستقیم و public/service/debug/node/loop/socket/trigger/queue/tool، stop با task بیگانه، republish و delete/bind هم‌زمان؛ برنامهٔ legacy همان رفتار قبلی داشته باشد.
5. SC-001..004: شش AS و ماتریس denial، حفظ تاریخچه و هر سه مسیر UI با نتایج واقعی تطبیق داده شوند.

## Evidence and Cleanup

برای هر AS/FR، expected/actual، pass/fail/blocked/not_run، commit، image digest، actor synthetic، correlation
و شاهد sanitized ثبت شود. raw نشست، تصویر دارای دادهٔ خصوصی، backup و sample در `.runtime/` بمانند.
cleanup فقط fixture متعلق به این آزمون؛ سپس تنظیم DB و سرویس‌ها به حالت قبلی برگردد و doctor تکرار شود.
برای schema جدید، restore تازه و snapshot داده/فایل بررسی شود. آزمون LLM فقط اگر واقعاً اجرا شد گزارش شود.

## Current Gate

ماتریس ورودی باید هم Community نصب‌شده و هم قابلیت Enterprise استفاده‌شده را جدا ثبت کند؛ Enterprise این محیط تست نشده است. نبود پوشش هر ورودی، مانع فعال‌کردن managed است.
