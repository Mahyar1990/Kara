# Implementation Plan: KP-05 — اجرای مرحله، بازخورد و خروجی منتخب

**Branch**: `master` | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)

**Input**: `specs/005-stage-feedback/spec.md`؛ خروجی `$speckit-plan` بر اساس سورس و قراردادهای فعلی.

## Summary

هر فرد مجاز مرحلهٔ آماده را با ورودی نسخه‌دار اجرا کند، چند دور بازخورد یا ویرایش انسانی ثبت کند و نهایی‌کننده خروجی معتبر منتخب را صریحاً ببندد.

مرجع pure kara_contracts/team.py را از طریق adapter با context معتبر runtime متصل کنید؛ پارامترهای guards/system را از JSON نپذیرید. SQLAlchemy row lock/CAS و unique partial index برای active attempt لازم‌اند. از موتور موجود با pinned Workflow و actual Account استفاده کنید. outbox و action_keys را از همان اولین start بسازید؛ KP-07 توسعهٔ recovery است نه اولین ایمنی. callback internal را به active attempt و run واقعی authenticate/correlate کنید؛ state machine صرف جای قفل DB نیست.

وضعیت: فقط طراحی. شروع اجرا پس از KP-02، KP-03 و KP-04 پس از پذیرش و درخواست مرحلهٔ مربوط. برنامه‌های بعدی باید با قرارداد پذیرفته‌شدهٔ پیشینیان تازه شوند.

## Technical Context

**Language/Version**: API Python `~=3.12.0`؛ کلاینت TypeScript 6.0.2، React 19.3.0، Next 16.3.4، Node 24.20.0؛ ابزار Spec Kit محیط Python مستقل دارد.

**Primary Dependencies**: Flask 3.1.3، SQLAlchemy 2.0.49، Celery 5.6.3؛ موتور قفل‌شدهٔ Dify 1.17.1 در محصول Kara؛ Redis client 7.4.0 با Redis server 6 اشتباه نشود.

**Storage**: PostgreSQL 15 و ذخیرهٔ فایل موجود؛ Redis 6 برای queue؛ تاریخچهٔ تصمیم فقط در cache نباشد.

**Testing**: make check برای ساختار و unittest؛ تست واقعی PostgreSQL در infra/api/company_projects؛ typecheck و node/RTL و browser در build کلاینت. شرح پوشش و فرمان‌ها در [quickstart](quickstart.md).

**Target Platform**: همان Compose محلی و Linux server آینده؛ طراحی Kubernetes و اندازه‌گیری production در این بسته نیست.

**Project Type**: افزونهٔ موجود API و frontend همان محصول؛ موتور/سرویس حساب موازی ساخته نمی‌شود.

**Performance Goals**: بدون SLA تولید اختراعی؛ نتایج SC-001..004 و ماتریس پذیرش الزامی‌اند. فهرست‌ها cursor پایدار، default limit=50 و سقف 100 داشته باشند؛ زمان و حجم واقعی در گزارش ثبت شود.

**Constraints**: scope دقیق project/workspace؛ UTC در ذخیره و نمایش تهران؛ secrets خصوصی؛ متن اصلی بدون trim خودکار در digest؛ backward compatibility و additive migrations.

**Scale/Scope**: حداقل دو پروژه و چند حساب مستقل در آزمون؛ فقط KP-05. خارج محدوده: تحویل عمومی همهٔ لاگ‌ها، اجرای خودکار مرحلهٔ بعد، محدودیت ثابت بی‌دلیل دور انسانی و بازیابی پیشرفتهٔ KP-07؛ حداقل ایمنی dispatch همین‌جا لازم است.

## Constitution Check

| اصل | پیش از research | پس از طراحی | شاهد طرح |
| --- | --- | --- | --- |
| I. اختیار انسان و scope | pass | pass | هر action با actor واقعی و fresh policy؛ قرارداد رابط و SC-002 |
| II. نسخه و تحویل | pass | pass | مدل داده، immutable refs و SC-003؛ هیچ شروع انسانی جعل نمی‌شود |
| III. سازگاری | pass | pass | overlay، دفتر migration موجود و برنامهٔ rollback؛ upstream read-only |
| IV. شاهد واقعی | pass | pass | quickstart و تسک‌های آزمون؛ هیچ نتیجهٔ آینده موفق علامت نخورده |
| V. spec پیش از اجرا | pass | pass | spec/plan/contracts/tasks و gate پیش‌نیاز؛ Klassor بعد از KP-08 |

این passها بررسی طراحی‌اند و قبولی runtime نیستند. مانع/ریسک باقی‌مانده: API عادی run در KP-02 جای تصمیم ورود و stages نیست. content طولانی باید artifact store کامل داشته باشد؛ inbox preview کافی نیست. callback بعد از لغو یا ورودی تازه صرفاً سابقهٔ فنی است.

## Project Structure

### Documentation (this feature)

`specs/005-stage-feedback/`: spec، plan، research، data-model، contracts/interface، quickstart، tasks، checklists و رکورد اجرای فرایند.

### Source Code (repository root)

مسیرهای زیر **هدف پیاده‌سازی آینده** هستند؛ وجود فایل تازه ادعا نمی‌شود:

- `infra/api/company_projects/team_stages.py`: سرویس/adapter اصلی.
- `infra/api/company_projects/team_stages_controller.py`: مرز ورودی احرازشده یا harness مستقل این بسته.
- `infra/api/company_projects/test_team_stages.py`: آزمون داده و API؛ نه جایگزین make check.
- `infra/web/overlay/app/components/company-projects/team-stages.tsx` و `infra/web/team-stages.spec.mjs`: مسیر/آزمون رابط مرتبط.
- `infra/api/company_projects/team_migrations.py`: 005_team_sessions.
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
