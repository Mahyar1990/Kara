# Research: KP-08

تاریخ: 2026-10-22. بررسی سورس محلی قفل‌شده و قراردادهای پروژه؛ ادعای آزمون زندهٔ قابلیت آینده نیست.

## Decision 1 — معماری موجود

**Decision**: harness عمومی در scripts/ و fixture sanitized در fixtures/kara-team-core ساخته شود؛ آزمون‌های PostgreSQL کنار تست‌های فعلی باشند. دو workflow قطعی exportشده در fixture نگهداری شوند، بدون agents DSL کلاسور. از UI واقعی ساخته‌شدهٔ overlay و endpointهای واقعی استفاده کنید؛ تست bypass ادمین جای journey کاربران نیست. DB restore و worker fault injection در محیط جدا؛ مدل واقعی فقط مرحلهٔ smoke مستقل.

**Rationale**: حفظ account/workspace و موتور موجود، جداسازی workflow فنی از فلو همکاری تیم و انطباق با قرارداد 1.0.0.

**Alternatives considered**: ساخت engine/account service جدید، اتکا به prompt برای مجوز و استفاده از آخرین draft رد شدند؛ scope، actor و pin تاریخی را تضمین نمی‌کنند.

## Decision 2 — داده، سازگاری و آزمون

**Decision**: schema افزایشی موردنیاز همان بسته، قیود scope و audit اتمی؛ خواندن مجوز تازه؛ PostgreSQL برای race و migration و browser برای مسیر انسان.

**Rationale**: make check و مرجع pure، رفتار قفل/DDL و UI زنده را اثبات نمی‌کنند.

**Alternatives considered**: تغییر schema قدیمی، SQLite-only، کپی خروجی build قدیمی و ثبت secret در fixture رد شدند.

## Decision 3 — مرز باز و gate

**Decision**: تعداد تست قبلی ۱۱۵ شاهد تاریخی KP-01 است؛ برای پذیرش آینده دوباره relevant suites و سناریوی جدید لازم‌اند. نسخهٔ قدیم compile یا screenshot به‌تنهایی پذیرش جدید نیست.

**Rationale**: طراحی داخلی را می‌توان مشخص کرد؛ شاهد بیرونی یا قرارداد پیشینیان را نمی‌توان ساختگی تکمیل کرد.

**Alternatives considered**: نسبت‌دادن تأیید تازه به کاربر، حدس sample یا اعلام پذیرش از روی طرح رد شد.

## Source Evidence

- `infra/dify.lock.json`: upstream commit `8387590ace4a094de812b7847fc6a4c3a27cd52b`.
- `.runtime/dify/api/pyproject.toml` و `uv.lock`؛ `.runtime/dify/docker/docker-compose.yaml` و `pnpm-workspace.yaml`: stack واقعی.
- `.runtime/dify/api/services/app_generate_service.py` (`_get_workflow`) و `services/workflow_service.py` (`get_published_workflow_by_id`, `delete_workflow`): pin واقعی و محدودیت retention بومی.
- `.runtime/dify/api/controllers/console/app/workflow.py`، `controllers/web/workflow.py`، `controllers/service_api/app/workflow.py`، `tasks/async_workflow_tasks.py` و `controllers/console/socketio/workflow.py`: ورودی‌ها و permissionهای بومی.
- `infra/api/company_projects/team.py`, `team_controller.py`, `team_migrations.py`, `inbox.py`, `automations.py`: seamهای فعلی؛ اصل source در runtime و خارج Git می‌ماند.
- [قرارداد](../../docs/kara-team-contract-v1.md)، [مدل داده](../../docs/kara-team-data-migration.md)، [پذیرش قبلی](../../docs/kara-kp01-closeout.md).

Phase 0 از research خواندنی یک ایجنت مطابق skill رسمی plan استفاده کرد؛ هیچ runtime یا branch در research تغییر نکرد. نام endpoint و جدول در این طرح هدف آینده‌اند.
