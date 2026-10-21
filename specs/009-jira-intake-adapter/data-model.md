# Data Model: KP-09

وضعیت: طراحی آینده؛ جدول تازه در این تحویل ساخته نشده است.

## Entities and Constraints

### ConnectorBinding

**Fields**: scope، id، source_system، credential_reference، allowed_sources، enabled.

**Validation and Relationships**: secret فقط private store؛ connector متعلق به scope؛ auth/allowed_sources از قرارداد واقعی تثبیت می‌شوند.

### ImportEnvelope

**Fields**: scope، connector_id، source_identity، source_revision، original_payload_ref، received_at، actor.

**Validation and Relationships**: port داخلی، schema بیرونی نیست؛ فیلدهای واقعی نامعلوم تا sample؛ raw payload خصوصی.

### ImportReceipt

**Fields**: scope، connector، external_identity، content_digest، request_revision، status.

**Validation and Relationships**: یکتا برای محتوای تکراری در scope/connector/source؛ تراکنش با ایجاد requestrevision.

### MappingRecord

**Fields**: upstream_path، internal_field، required/optional، transform، sample_ref.

**Validation and Relationships**: فقط پس از sample تکمیل؛ بدون نام فیلد Jira ساختگی؛ missing و ordering policy صریح.

## Shared Integrity and Transactions

- Scope با project_id و workspace واقعی `company_project_workspaces.workspace_id` است؛ tenant مدیریت مرکزی جای workspace تیم نیست.
- composite FK شامل scope برای روابط جدید؛ تعلق app/workflow/run بومی به هم و workspace در تراکنش بررسی شود. UUID canonical، revision عدد صحیح مثبت غیر bool و digest SHA-256 canonical JSON قرارداد.
- immutable history و current pointer با CAS جدا باشند؛ actor از نشست/هویت داخلی معتبر. حذف عضویت تاریخچه را حذف نکند و fresh policy عملیات بعدی را کنترل کند.
- mutation همراه audit و action key payload-bound در یک تراکنش؛ یک key و payload replay، payload متفاوت 409. correlation بین DB/queue/native run نگه داشته شود.
- مسیر حالت: قرارداد [KP-00](../../docs/kara-team-contract-v1.md) مرجع است؛ state یا guard از JSON کاربر پذیرفته نمی‌شود. موجودیت این بسته جای تصمیم انسانی مرحلهٔ دیگر نیست.

## Migration and Rollback

افزایش بعدی migration فقط پس از تثبیت نمونه و در صورت نیاز به dedupe/provenance. runner همان ledger و advisory lock ثابت `210610003`، checksum، preflight و transactional DDL/marker را حفظ کند. شمارهٔ آیندهٔ واقعی با ledger زمان اجرا تطبیق داده شود. فقط دادهٔ لازم این بسته افزوده شود. backup و restore محیط جدا، preservation و آزمون خواندن نسخهٔ سازگار قبلی لازم‌اند؛ rollback با drop تاریخچه یا بازکردن bypass managed مجاز نیست.
