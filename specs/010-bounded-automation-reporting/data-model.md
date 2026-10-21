# Data Model: KP-10

وضعیت: طراحی آینده؛ جدول تازه در این تحویل ساخته نشده است.

## Entities and Constraints

### ServicePrincipal

**Fields**: scope، id، enabled، permitted_operations/resources، policy_revision.

**Validation and Relationships**: هویت سرویس مستقل؛ هیچ نقش PO انسانی یا finalize human grant؛ دسترسی قابل لغو.

### AutomationVersion

**Fields**: scope، automation، revision، trigger، connector_ref، operation، service_ref، enabled.

**Validation and Relationships**: draft disabled؛ انتشار immutable و active pointer CAS؛ اتصال به نسخهٔ پذیرفته‌شده.

### Delivery/EffectReceipt

**Fields**: event_key، action_key، payload_digest، attempt_count، next_retry، result_ref، effect_status.

**Validation and Relationships**: یکتا در scope/source/event/operation؛ retry step-only؛ unknown external effect نیازمند reconcile.

### RequestReport

**Fields**: scope، filters، as_of، cursor، status، actor، provenance.

**Validation and Relationships**: derived projection؛ count/export مجاز؛ UTC در storage و نمایش تهران.

## Shared Integrity and Transactions

- Scope با project_id و workspace واقعی `company_project_workspaces.workspace_id` است؛ tenant مدیریت مرکزی جای workspace تیم نیست.
- composite FK شامل scope برای روابط جدید؛ تعلق app/workflow/run بومی به هم و workspace در تراکنش بررسی شود. UUID canonical، revision عدد صحیح مثبت غیر bool و digest SHA-256 canonical JSON قرارداد.
- immutable history و current pointer با CAS جدا باشند؛ actor از نشست/هویت داخلی معتبر. حذف عضویت تاریخچه را حذف نکند و fresh policy عملیات بعدی را کنترل کند.
- mutation همراه audit و action key payload-bound در یک تراکنش؛ یک key و payload replay، payload متفاوت 409. correlation بین DB/queue/native run نگه داشته شود.
- مسیر حالت: قرارداد [KP-00](../../docs/kara-team-contract-v1.md) مرجع است؛ state یا guard از JSON کاربر پذیرفته نمی‌شود. موجودیت این بسته جای تصمیم انسانی مرحلهٔ دیگر نیست.

## Migration and Rollback

افزایش بعدی migration برای service principal/schedule/outbox فقط به اندازه نیاز. runner همان ledger و advisory lock ثابت `210610003`، checksum، preflight و transactional DDL/marker را حفظ کند. شمارهٔ آیندهٔ واقعی با ledger زمان اجرا تطبیق داده شود. فقط دادهٔ لازم این بسته افزوده شود. backup و restore محیط جدا، preservation و آزمون خواندن نسخهٔ سازگار قبلی لازم‌اند؛ rollback با drop تاریخچه یا بازکردن bypass managed مجاز نیست.
