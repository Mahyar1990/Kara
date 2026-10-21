# Research: KP-10

تاریخ: 2026-10-22. بررسی سورس محلی قفل‌شده و قراردادهای پروژه؛ ادعای آزمون زندهٔ قابلیت آینده نیست.

## Decision 1 — معماری موجود

**Decision**: از Celery/Redis و outbox/recovery پذیرفته‌شده استفاده کنید؛ schedule بومی automations.py با actor owner را بدون کنترل به managed تعمیم ندهید. worker یک ServicePrincipal scoped را resolve کند و از port پذیرفته‌شدهٔ import استفاده کند. سیاست منابع در controller و dispatch/resume enforce شود. گزارش projection روی instance/stage/event باشد؛ count و export نیز policy query داشته باشند.

**Rationale**: حفظ account/workspace و موتور موجود، جداسازی workflow فنی از فلو همکاری تیم و انطباق با قرارداد 1.0.0.

**Alternatives considered**: ساخت engine/account service جدید، اتکا به prompt برای مجوز و استفاده از آخرین draft رد شدند؛ scope، actor و pin تاریخی را تضمین نمی‌کنند.

## Decision 2 — داده، سازگاری و آزمون

**Decision**: schema افزایشی موردنیاز همان بسته، قیود scope و audit اتمی؛ خواندن مجوز تازه؛ PostgreSQL برای race و migration و browser برای مسیر انسان.

**Rationale**: make check و مرجع pure، رفتار قفل/DDL و UI زنده را اثبات نمی‌کنند.

**Alternatives considered**: تغییر schema قدیمی، SQLite-only، کپی خروجی build قدیمی و ثبت secret در fixture رد شدند.

## Decision 3 — مرز باز و gate

**Decision**: طراحی event بیرونی باید با اتصال انتخاب‌شده نهایی شود؛ در این مرحله سرویس خارجی واقعی فعال نکنید. اگر عملیاتی idempotency خارجی ندارد unknown اثر باید نیازمند بررسی بماند.

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
