# Data Model: KP-04

وضعیت: طراحی آینده؛ جدول تازه در این تحویل ساخته نشده است.

## Entities and Constraints

### Request

**Fields**: scope، id، title، source=manual، created_by/at، current_revision.

**Validation and Relationships**: ثبت بدون instance مجاز؛ source/external_id برای آداپتر آینده رزرو، بدون schema ساختگی Jira.

### RequestRevision

**Fields**: request، revision، original_text، edited_text، digest، parent، author، attachment_refs.

**Validation and Relationships**: revision مثبت و یکتا در request؛ متن اصلی immutable؛ attachment scope کنترل.

### IntakeDecision

**Fields**: request_revision_ref، flow_version_ref، outcome، mode=real، actor، reason، time، expiry/revocation.

**Validation and Relationships**: مرجع و تصمیم immutable؛ approved واقعی معتبر تنها مجوز ورود؛ تغییر رویداد ابطال مستقل.

### Instance

**Fields**: scope، id، request_revision_id، flow_version_id، intake_decision_id، status.

**Validation and Relationships**: حداکثر یک instance برای همان تصمیم؛ tuple دقیق request/flow/digests تطبیق تراکنشی؛ هنوز start خودکار ندارد.

## Shared Integrity and Transactions

- Scope با project_id و workspace واقعی `company_project_workspaces.workspace_id` است؛ tenant مدیریت مرکزی جای workspace تیم نیست.
- composite FK شامل scope برای روابط جدید؛ تعلق app/workflow/run بومی به هم و workspace در تراکنش بررسی شود. UUID canonical، revision عدد صحیح مثبت غیر bool و digest SHA-256 canonical JSON قرارداد.
- immutable history و current pointer با CAS جدا باشند؛ actor از نشست/هویت داخلی معتبر. حذف عضویت تاریخچه را حذف نکند و fresh policy عملیات بعدی را کنترل کند.
- mutation همراه audit و action key payload-bound در یک تراکنش؛ یک key و payload replay، payload متفاوت 409. correlation بین DB/queue/native run نگه داشته شود.
- مسیر حالت: قرارداد [KP-00](../../docs/kara-team-contract-v1.md) مرجع است؛ state یا guard از JSON کاربر پذیرفته نمی‌شود. موجودیت این بسته جای تصمیم انسانی مرحلهٔ دیگر نیست.

## Migration and Rollback

004_team_requests. runner همان ledger و advisory lock ثابت `210610003`، checksum، preflight و transactional DDL/marker را حفظ کند. شمارهٔ آیندهٔ واقعی با ledger زمان اجرا تطبیق داده شود. فقط دادهٔ لازم این بسته افزوده شود. backup و restore محیط جدا، preservation و آزمون خواندن نسخهٔ سازگار قبلی لازم‌اند؛ rollback با drop تاریخچه یا بازکردن bypass managed مجاز نیست.
