# Quickstart Validation: KP-05

این راهنما برای **پس از پیاده‌سازی** است؛ اجرای زیر در وضعیت فعلی قبولی قابلیت آینده ایجاد نمی‌کند.

## Prerequisites

- KP-02، KP-03 و KP-04 پس از پذیرش. با gate رفع‌نشده آزمون live و acceptance را not_run/blocked ثبت کنید.
- محیط مستقل با بانک بازیابی‌شده، مدل/connector لازم همان بسته و چند حساب synthetic واقعی؛ اطلاعات ورود خصوصی.
- commit/image و schema مبنا، backup و شناسهٔ fixture در گزارش `docs/kara-kp-05-validation.md` ثبت شود.

## Specification Preflight (available now)

```sh
export SPECIFY_FEATURE_DIRECTORY="$PWD/specs/005-stage-feedback"
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

آزمون هدف آینده در `infra/api/company_projects/test_team_stages.py` است؛ داخل تصویر API ساخته‌شده و با تنظیم اتصال بانک مستقل اجرا شود.
اگر فایل هنوز ساخته نشده، not_run ثبت کنید؛ فرمان unittest را به موفقیت make check تقلیل ندهید.
الگوی executable پس از وجود فایل و داخل محیط API با `PYTHONPATH=/app/api`:

```sh
python -m unittest company_projects.test_team_stages -v
```

متغیرهای اتصال از محیط خصوصی همان harness گرفته شوند؛ secret در command line یا گزارش مشترک قرار نگیرد.
برای build/TypeScript/تست‌های رابط، [راهنمای وب](../../docs/persian-interface.md) و Dockerfile مشترک
را دنبال کنید؛ source تازه کامپایل شود. `infra/web/team-stages.spec.mjs` به test runner موجود اضافه شود، صرف وجود فایل اجرا نیست.

## Scenarios and Expected Results

1. US1: یک مرحلهٔ ready با یک کلیک یک attempt بسازد و نسخهٔ صحیح اجرا شود.
2. US2: دو feedback و یک human edit به خروجی‌های مستقل با نویسنده منتهی شوند.
3. US3: کاربر با finalize ولی خارج از finalizer رد شود؛ finalizer با مجوز جاری موفق شود.
4. منفی/بازیابی: ready/start، blocked denial، دو start، callback قدیمی و تکراری، دو feedback+human edit، base_revision conflict، finalizer دیگر، grantrevoked، oldartifact denial، manual next، failure/retry و outbox crash window.
5. SC-001..004: شش AS و ماتریس denial، حفظ تاریخچه و هر سه مسیر UI با نتایج واقعی تطبیق داده شوند.

## Evidence and Cleanup

برای هر AS/FR، expected/actual، pass/fail/blocked/not_run، commit، image digest، actor synthetic، correlation
و شاهد sanitized ثبت شود. raw نشست، تصویر دارای دادهٔ خصوصی، backup و sample در `.runtime/` بمانند.
cleanup فقط fixture متعلق به این آزمون؛ سپس تنظیم DB و سرویس‌ها به حالت قبلی برگردد و doctor تکرار شود.
برای schema جدید، restore تازه و snapshot داده/فایل بررسی شود. آزمون LLM فقط اگر واقعاً اجرا شد گزارش شود.

## Current Gate

API عادی run در KP-02 جای تصمیم ورود و stages نیست. content طولانی باید artifact store کامل داشته باشد؛ inbox preview کافی نیست. callback بعد از لغو یا ورودی تازه صرفاً سابقهٔ فنی است.
