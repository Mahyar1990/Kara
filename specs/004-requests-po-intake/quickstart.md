# Quickstart Validation: KP-04

این راهنما برای **پس از پیاده‌سازی** است؛ اجرای زیر در وضعیت فعلی قبولی قابلیت آینده ایجاد نمی‌کند.

## Prerequisites

- KP-01 و KP-03 پس از پذیرش. با gate رفع‌نشده آزمون live و acceptance را not_run/blocked ثبت کنید.
- محیط مستقل با بانک بازیابی‌شده، مدل/connector لازم همان بسته و چند حساب synthetic واقعی؛ اطلاعات ورود خصوصی.
- commit/image و schema مبنا، backup و شناسهٔ fixture در گزارش `docs/kara-kp-04-validation.md` ثبت شود.

## Specification Preflight (available now)

```sh
export SPECIFY_FEATURE_DIRECTORY="$PWD/specs/004-requests-po-intake"
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

آزمون هدف آینده در `infra/api/company_projects/test_team_requests.py` است؛ داخل تصویر API ساخته‌شده و با تنظیم اتصال بانک مستقل اجرا شود.
اگر فایل هنوز ساخته نشده، not_run ثبت کنید؛ فرمان unittest را به موفقیت make check تقلیل ندهید.
الگوی executable پس از وجود فایل و داخل محیط API با `PYTHONPATH=/app/api`:

```sh
python -m unittest company_projects.test_team_requests -v
```

متغیرهای اتصال از محیط خصوصی همان harness گرفته شوند؛ secret در command line یا گزارش مشترک قرار نگیرد.
برای build/TypeScript/تست‌های رابط، [راهنمای وب](../../docs/persian-interface.md) و Dockerfile مشترک
را دنبال کنید؛ source تازه کامپایل شود. `infra/web/team-requests.spec.mjs` به test runner موجود اضافه شود، صرف وجود فایل اجرا نیست.

## Scenarios and Expected Results

1. US1: متن اولیه و نسخهٔ دوم هر دو قابل بازیابی مجاز باشند.
2. US2: همان عضو با po بتواند approved بدهد؛ root فاقد po نتواند.
3. US3: پس از تغییر متن، تصمیم v1 برای v2 مجوز ایجاد نکند.
4. منفی/بازیابی: چهار outcome، root بدونpo، po پروژه دیگر، نسخهٔ قدیمی، expiry/revoke، دو approve هم‌زمان، request dedupe، فایل بیگانه، requestv2 حفظv1، کارتابل بومی و فرم قدیمی سالم.
5. SC-001..004: شش AS و ماتریس denial، حفظ تاریخچه و هر سه مسیر UI با نتایج واقعی تطبیق داده شوند.

## Evidence and Cleanup

برای هر AS/FR، expected/actual، pass/fail/blocked/not_run، commit، image digest، actor synthetic، correlation
و شاهد sanitized ثبت شود. raw نشست، تصویر دارای دادهٔ خصوصی، backup و sample در `.runtime/` بمانند.
cleanup فقط fixture متعلق به این آزمون؛ سپس تنظیم DB و سرویس‌ها به حالت قبلی برگردد و doctor تکرار شود.
برای schema جدید، restore تازه و snapshot داده/فایل بررسی شود. آزمون LLM فقط اگر واقعاً اجرا شد گزارش شود.

## Current Gate

فلو draft/archived برای ورود جدید نامعتبر است؛ پروندهٔ pin‌شده تابع همان نسخه می‌ماند. اگر ابطال روی instance موجود اثر دارد، hook مسدودکردن مصرف را همین گام بسازید و در KP-07 گسترش دهید.
