# Implementation Plan: KP-08 — پذیرش هستهٔ همکاری Kara

**Branch**: `master` | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)

**Input**: `specs/008-core-acceptance/spec.md`؛ خروجی `$speckit-plan` بر اساس سورس و قراردادهای فعلی.

## Summary

پیش از ساخت ایجنت‌های کلاسور، همکاری چندنفره با دو مرحلهٔ قطعی و شواهد واقعی API، داده و رابط پذیرفته شود و کیفیت مدل جدا سنجیده شود.

harness عمومی در scripts/ و fixture sanitized در fixtures/kara-team-core ساخته شود؛ آزمون‌های PostgreSQL کنار تست‌های فعلی باشند. دو workflow قطعی exportشده در fixture نگهداری شوند، بدون agents DSL کلاسور. از UI واقعی ساخته‌شدهٔ overlay و endpointهای واقعی استفاده کنید؛ تست bypass ادمین جای journey کاربران نیست. DB restore و worker fault injection در محیط جدا؛ مدل واقعی فقط مرحلهٔ smoke مستقل.

وضعیت: فقط طراحی. شروع اجرا پس از KP-01 تا KP-07 پذیرفته‌شده و درخواست مرحلهٔ مربوط. برنامه‌های بعدی باید با قرارداد پذیرفته‌شدهٔ پیشینیان تازه شوند.

## Technical Context

**Language/Version**: API Python `~=3.12.0`؛ کلاینت TypeScript 6.0.2، React 19.3.0، Next 16.3.4، Node 24.20.0؛ ابزار Spec Kit محیط Python مستقل دارد.

**Primary Dependencies**: Flask 3.1.3، SQLAlchemy 2.0.49، Celery 5.6.3؛ موتور قفل‌شدهٔ Dify 1.17.1 در محصول Kara؛ Redis client 7.4.0 با Redis server 6 اشتباه نشود.

**Storage**: PostgreSQL 15 و ذخیرهٔ فایل موجود؛ Redis 6 برای queue؛ تاریخچهٔ تصمیم فقط در cache نباشد.

**Testing**: make check برای ساختار و unittest؛ تست واقعی PostgreSQL در infra/api/company_projects؛ typecheck و node/RTL و browser در build کلاینت. شرح پوشش و فرمان‌ها در [quickstart](quickstart.md).

**Target Platform**: همان Compose محلی و Linux server آینده؛ طراحی Kubernetes و اندازه‌گیری production در این بسته نیست.

**Project Type**: افزونهٔ موجود API و frontend همان محصول؛ موتور/سرویس حساب موازی ساخته نمی‌شود.

**Performance Goals**: بدون SLA تولید اختراعی؛ نتایج SC-001..004 و ماتریس پذیرش الزامی‌اند. فهرست‌ها cursor پایدار، default limit=50 و سقف 100 داشته باشند؛ زمان و حجم واقعی در گزارش ثبت شود.

**Constraints**: scope دقیق project/workspace؛ UTC در ذخیره و نمایش تهران؛ secrets خصوصی؛ متن اصلی بدون trim خودکار در digest؛ backward compatibility و additive migrations.

**Scale/Scope**: حداقل دو پروژه و چند حساب مستقل در آزمون؛ فقط KP-08. خارج محدوده: ساخت ایجنت تخصصی کلاسور، ادعای آمادگی production/Kubernetes، جایگزینی تست واقعی با mock و پذیرش Jira بدون اتصال.

## Constitution Check

| اصل | پیش از research | پس از طراحی | شاهد طرح |
| --- | --- | --- | --- |
| I. اختیار انسان و scope | pass | pass | هر action با actor واقعی و fresh policy؛ قرارداد رابط و SC-002 |
| II. نسخه و تحویل | pass | pass | مدل داده، immutable refs و SC-003؛ هیچ شروع انسانی جعل نمی‌شود |
| III. سازگاری | pass | pass | overlay، دفتر migration موجود و برنامهٔ rollback؛ upstream read-only |
| IV. شاهد واقعی | pass | pass | quickstart و تسک‌های آزمون؛ هیچ نتیجهٔ آینده موفق علامت نخورده |
| V. spec پیش از اجرا | pass | pass | spec/plan/contracts/tasks و gate پیش‌نیاز؛ Klassor بعد از KP-08 |

این passها بررسی طراحی‌اند و قبولی runtime نیستند. مانع/ریسک باقی‌مانده: تعداد تست قبلی ۱۱۵ شاهد تاریخی KP-01 است؛ برای پذیرش آینده دوباره relevant suites و سناریوی جدید لازم‌اند. نسخهٔ قدیم compile یا screenshot به‌تنهایی پذیرش جدید نیست.

## Project Structure

### Documentation (this feature)

`specs/008-core-acceptance/`: spec، plan، research، data-model، contracts/interface، quickstart، tasks، checklists و رکورد اجرای فرایند.

### Source Code (repository root)

مسیرهای زیر **هدف پیاده‌سازی آینده** هستند؛ وجود فایل تازه ادعا نمی‌شود:

- `scripts/kara_core_acceptance.py`: سرویس/adapter اصلی.
- `scripts/kara_core_acceptance.py`: مرز ورودی احرازشده یا harness مستقل این بسته.
- `infra/api/company_projects/test_team_acceptance.py`: آزمون داده و API؛ نه جایگزین make check.
- `scripts/kara_core_browser.mjs` و `scripts/kara_core_browser.mjs`: مسیر/آزمون رابط مرتبط.
- `infra/api/company_projects/team_migrations.py`: بدون migration محصول؛ harness آزمون از schema پذیرفته‌شده استفاده می‌کند.
- `fixtures/kara-team-core/`: نمونه‌ها و exportهای قطعی؛ `docs/kara-kp-08-validation.md`: گزارش؛ هیچ hook یا صفحهٔ محصول تازه صرفاً برای پذیرش اضافه نشود.

**Structure Decision**: ساختار واقعی افزونه حفظ می‌شود؛ نام‌های هدف نهایی پس از بررسی پیش‌نیازها تثبیت شوند و با tasks هم‌زمان تغییر کنند.

## Delivery Sequence and Recovery

1. snapshot/قرارداد پیش‌نیاز و matrix آزمون را تثبیت کنید؛ روی محیط آزمون مستقل کار کنید.
2. مدل و migration لازم را با preflight/checksum/lock موجود و آزمون ارتقا و rollback-DDL بسازید؛ جدول آینده را پیشاپیش نسازید.
3. هر user story را با سرویس، کنترلر، UI و آزمون مستقل تحویل دهید؛ فعال‌سازی capability به قبولی همهٔ مسیرهای امنیتی وابسته است.
4. قبل/بعد schema، backup/restore و سازگاری reader قبلی را بسنجید. بعد از استفادهٔ managed فقط نسخهٔ دارای enforcement مقصد rollback است؛ در غیر این صورت سرویس متوقف و بازیابی کنترل‌شده شود.
5. make check، آزمون‌های مرتبط PostgreSQL، TypeScript/UI، Compose و doctor و browser؛ شواهد sanitized در گزارش همان بسته، raw private در .runtime.

## Complexity Tracking

تخلف توجیه‌نشده‌ای در طرح وجود ندارد؛ موارد وابسته/مسدود مجوز دورزدن gate نیستند. داده/اتصال واقعیِ در دسترس‌نبودن، در quickstart و tasks به‌صورت gate حفظ شده است.
