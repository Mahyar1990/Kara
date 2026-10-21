# Implementation Plan: KP-10 — خودکارسازی محدود و گزارش درخواست‌ها

**Branch**: `master` | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)

**Input**: `specs/010-bounded-automation-reporting/spec.md`؛ خروجی `$speckit-plan` بر اساس سورس و قراردادهای فعلی.

## Summary

مدیر اجرای دوره‌ای یا رویدادی محدود و قابل توقف برای دریافت مجاز تنظیم کند و وضعیت درخواست‌ها را بدون جعل تصمیم انسانی گزارش بگیرد.

از Celery/Redis و outbox/recovery پذیرفته‌شده استفاده کنید؛ schedule بومی automations.py با actor owner را بدون کنترل به managed تعمیم ندهید. worker یک ServicePrincipal scoped را resolve کند و از port پذیرفته‌شدهٔ import استفاده کند. سیاست منابع در controller و dispatch/resume enforce شود. گزارش projection روی instance/stage/event باشد؛ count و export نیز policy query داشته باشند.

وضعیت: فقط طراحی. شروع اجرا پس از KP-08 پذیرفته‌شده و قرارداد پذیرفته‌شدهٔ اتصال مرتبط؛ برای Jira همچنین KP-09 و درخواست مرحلهٔ مربوط. برنامه‌های بعدی باید با قرارداد پذیرفته‌شدهٔ پیشینیان تازه شوند.

## Technical Context

**Language/Version**: API Python `~=3.12.0`؛ کلاینت TypeScript 6.0.2، React 19.3.0، Next 16.3.4، Node 24.20.0؛ ابزار Spec Kit محیط Python مستقل دارد.

**Primary Dependencies**: Flask 3.1.3، SQLAlchemy 2.0.49، Celery 5.6.3؛ موتور قفل‌شدهٔ Dify 1.17.1 در محصول Kara؛ Redis client 7.4.0 با Redis server 6 اشتباه نشود.

**Storage**: PostgreSQL 15 و ذخیرهٔ فایل موجود؛ Redis 6 برای queue؛ تاریخچهٔ تصمیم فقط در cache نباشد.

**Testing**: make check برای ساختار و unittest؛ تست واقعی PostgreSQL در infra/api/company_projects؛ typecheck و node/RTL و browser در build کلاینت. شرح پوشش و فرمان‌ها در [quickstart](quickstart.md).

**Target Platform**: همان Compose محلی و Linux server آینده؛ طراحی Kubernetes و اندازه‌گیری production در این بسته نیست.

**Project Type**: افزونهٔ موجود API و frontend همان محصول؛ موتور/سرویس حساب موازی ساخته نمی‌شود.

**Performance Goals**: بدون SLA تولید اختراعی؛ نتایج SC-001..004 و ماتریس پذیرش الزامی‌اند. فهرست‌ها cursor پایدار، default limit=50 و سقف 100 داشته باشند؛ زمان و حجم واقعی در گزارش ثبت شود.

**Constraints**: scope دقیق project/workspace؛ UTC در ذخیره و نمایش تهران؛ secrets خصوصی؛ متن اصلی بدون trim خودکار در digest؛ backward compatibility و additive migrations.

**Scale/Scope**: حداقل دو پروژه و چند حساب مستقل در آزمون؛ فقط KP-10. خارج محدوده: تأیید خودکار PO، finalize به نام انسان، merge خودکار TL، اتوماسیون نامحدود همهٔ مراحل و افزودن Kafka/Kubernetes در این گام.

## Constitution Check

| اصل | پیش از research | پس از طراحی | شاهد طرح |
| --- | --- | --- | --- |
| I. اختیار انسان و scope | pass | pass | هر action با actor واقعی و fresh policy؛ قرارداد رابط و SC-002 |
| II. نسخه و تحویل | pass | pass | مدل داده، immutable refs و SC-003؛ هیچ شروع انسانی جعل نمی‌شود |
| III. سازگاری | pass | pass | overlay، دفتر migration موجود و برنامهٔ rollback؛ upstream read-only |
| IV. شاهد واقعی | pass | pass | quickstart و تسک‌های آزمون؛ هیچ نتیجهٔ آینده موفق علامت نخورده |
| V. spec پیش از اجرا | pass | pass | spec/plan/contracts/tasks و gate پیش‌نیاز؛ Klassor بعد از KP-08 |

این passها بررسی طراحی‌اند و قبولی runtime نیستند. مانع/ریسک باقی‌مانده: طراحی event بیرونی باید با اتصال انتخاب‌شده نهایی شود؛ در این مرحله سرویس خارجی واقعی فعال نکنید. اگر عملیاتی idempotency خارجی ندارد unknown اثر باید نیازمند بررسی بماند.

## Project Structure

### Documentation (this feature)

`specs/010-bounded-automation-reporting/`: spec، plan، research، data-model، contracts/interface، quickstart، tasks، checklists و رکورد اجرای فرایند.

### Source Code (repository root)

مسیرهای زیر **هدف پیاده‌سازی آینده** هستند؛ وجود فایل تازه ادعا نمی‌شود:

- `infra/api/company_projects/team_automation.py`: سرویس/adapter اصلی.
- `infra/api/company_projects/team_automation_controller.py`: مرز ورودی احرازشده یا harness مستقل این بسته.
- `infra/api/company_projects/test_team_automation.py`: آزمون داده و API؛ نه جایگزین make check.
- `infra/web/overlay/app/components/company-projects/team-reporting.tsx` و `infra/web/team-reporting.spec.mjs`: مسیر/آزمون رابط مرتبط.
- `infra/api/company_projects/team_migrations.py`: افزایش بعدی migration برای service principal/schedule/outbox فقط به اندازه نیاز.
- `infra/api/install.py`: hookهای لازم؛ `infra/web/overlay/service/company-projects.ts`: قرارداد کلاینت در صورت نیاز.

**Structure Decision**: ساختار واقعی افزونه حفظ می‌شود؛ نام‌های هدف نهایی پس از بررسی پیش‌نیازها تثبیت شوند و با tasks هم‌زمان تغییر کنند.

## Delivery Sequence and Recovery

1. snapshot/قرارداد پیش‌نیاز و matrix آزمون را تثبیت کنید؛ روی محیط آزمون مستقل کار کنید.
2. مدل و migration لازم را با preflight/checksum/lock موجود و آزمون ارتقا و rollback-DDL بسازید؛ جدول آینده را پیشاپیش نسازید.
3. هر user story را با سرویس، کنترلر، UI و آزمون مستقل تحویل دهید؛ فعال‌سازی capability به قبولی همهٔ مسیرهای امنیتی وابسته است.
4. قبل/بعد schema، backup/restore و سازگاری reader قبلی را بسنجید. بعد از استفادهٔ managed فقط نسخهٔ دارای enforcement مقصد rollback است؛ در غیر این صورت سرویس متوقف و بازیابی کنترل‌شده شود.
5. make check، آزمون‌های مرتبط PostgreSQL، TypeScript/UI، Compose و doctor و browser؛ شواهد sanitized در گزارش همان بسته، raw private در .runtime.

## Complexity Tracking

تخلف توجیه‌نشده‌ای در طرح وجود ندارد؛ موارد وابسته/مسدود مجوز دورزدن gate نیستند. داده/اتصال واقعیِ در دسترس‌نبودن، در quickstart و tasks به‌صورت gate حفظ شده است.
