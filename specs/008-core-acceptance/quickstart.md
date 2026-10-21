# Quickstart Validation: KP-08

این راهنما برای **پس از پیاده‌سازی** است؛ اجرای زیر در وضعیت فعلی قبولی قابلیت آینده ایجاد نمی‌کند.

## Prerequisites

- KP-01 تا KP-07 پذیرفته‌شده. با gate رفع‌نشده آزمون live و acceptance را not_run/blocked ثبت کنید.
- محیط مستقل با بانک بازیابی‌شده، مدل/connector لازم همان بسته و چند حساب synthetic واقعی؛ اطلاعات ورود خصوصی.
- commit/image و schema مبنا، backup و شناسهٔ fixture در گزارش `docs/kara-kp-08-validation.md` ثبت شود.

## Specification Preflight (available now)

```sh
export SPECIFY_FEATURE_DIRECTORY="$PWD/specs/008-core-acceptance"
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

آزمون هدف آینده در `infra/api/company_projects/test_team_acceptance.py` است؛ داخل تصویر API ساخته‌شده و با تنظیم اتصال بانک مستقل اجرا شود.
اگر فایل هنوز ساخته نشده، not_run ثبت کنید؛ فرمان unittest را به موفقیت make check تقلیل ندهید.
الگوی executable پس از وجود فایل و داخل محیط API با `PYTHONPATH=/app/api`:

```sh
python -m unittest company_projects.test_team_acceptance -v
```

متغیرهای اتصال از محیط خصوصی همان harness گرفته شوند؛ secret در command line یا گزارش مشترک قرار نگیرد.
برای build/TypeScript/تست‌های رابط، [راهنمای وب](../../docs/persian-interface.md) و Dockerfile مشترک
را دنبال کنید؛ source تازه کامپایل شود. `scripts/kara_core_browser.mjs` به test runner موجود اضافه شود، صرف وجود فایل اجرا نیست.

## Scenarios and Expected Results

1. US1: با حساب‌های مستقل از intake تا finalize دوم و مشاهدهٔ وضعیت کامل شود.
2. US2: هیچ اثر غیرمجاز و تصمیم مضاعف نماند و restore با محتوای مورد انتظار تطبیق کند.
3. US3: اثبات deterministic و real model جدا گزارش و شرط شروع کلاسور روشن باشد.
4. منفی/بازیابی: همهٔ ده بند بخش۸ readiness، deterministic دومرحله، دوflow/two-project، normalrun، دوfeedback+edit، selectedhandoff، stalegraph، directbypassdenial، concurrentdecisions، restart/restore، modelsmoke جدا و regression موجود.
5. SC-001..004: شش AS و ماتریس denial، حفظ تاریخچه و هر سه مسیر UI با نتایج واقعی تطبیق داده شوند.

## Evidence and Cleanup

برای هر AS/FR، expected/actual، pass/fail/blocked/not_run، commit، image digest، actor synthetic، correlation
و شاهد sanitized ثبت شود. raw نشست، تصویر دارای دادهٔ خصوصی، backup و sample در `.runtime/` بمانند.
cleanup فقط fixture متعلق به این آزمون؛ سپس تنظیم DB و سرویس‌ها به حالت قبلی برگردد و doctor تکرار شود.
برای schema جدید، restore تازه و snapshot داده/فایل بررسی شود. آزمون LLM فقط اگر واقعاً اجرا شد گزارش شود.

## Current Gate

تعداد تست قبلی ۱۱۵ شاهد تاریخی KP-01 است؛ برای پذیرش آینده دوباره relevant suites و سناریوی جدید لازم‌اند. نسخهٔ قدیم compile یا screenshot به‌تنهایی پذیرش جدید نیست.
