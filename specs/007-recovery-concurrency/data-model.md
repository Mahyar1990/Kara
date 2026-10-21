# Data Model: KP-07

وضعیت: طراحی آینده؛ جدول تازه در این تحویل ساخته نشده است.

## Entities and Constraints

### RecoveryEvent

**Fields**: scope، subject، cause، affected_refs، actor/service، time.

**Validation and Relationships**: append-only؛ consumer graph فقط scope جاری؛ history هرگز cascade حذف نشود.

### Reassignment

**Fields**: stage، old/new_finalizer، reason، actor، expected_revision.

**Validation and Relationships**: تراکنش قفل stage و سیاست عضویت؛ finalizer جدید دارای اختیار لازم.

### Cancellation

**Fields**: instance، actor، reason، state، worker_stop_result.

**Validation and Relationships**: completed history باقی؛ queued/running/stop-requested/stopped/unknown از هم متمایز.

### OutboxLease/ActionKey

**Fields**: logical_event_key، payload_digest، lease_owner/until، attempts، next_retry، last_error، correlation/run_id.

**Validation and Relationships**: at-least-once delivery؛ unique logical key؛ retry bounded؛ unknown effect هرگز blind retry نشود.

## Shared Integrity and Transactions

- Scope با project_id و workspace واقعی `company_project_workspaces.workspace_id` است؛ tenant مدیریت مرکزی جای workspace تیم نیست.
- composite FK شامل scope برای روابط جدید؛ تعلق app/workflow/run بومی به هم و workspace در تراکنش بررسی شود. UUID canonical، revision عدد صحیح مثبت غیر bool و digest SHA-256 canonical JSON قرارداد.
- immutable history و current pointer با CAS جدا باشند؛ actor از نشست/هویت داخلی معتبر. حذف عضویت تاریخچه را حذف نکند و fresh policy عملیات بعدی را کنترل کند.
- mutation همراه audit و action key payload-bound در یک تراکنش؛ یک key و payload replay، payload متفاوت 409. correlation بین DB/queue/native run نگه داشته شود.
- مسیر حالت: قرارداد [KP-00](../../docs/kara-team-contract-v1.md) مرجع است؛ state یا guard از JSON کاربر پذیرفته نمی‌شود. موجودیت این بسته جای تصمیم انسانی مرحلهٔ دیگر نیست.

## Migration and Rollback

افزایش بعدی دفتر migration فقط در صورت نیاز به schema؛ شماره بعدی واقعی از ledger. runner همان ledger و advisory lock ثابت `210610003`، checksum، preflight و transactional DDL/marker را حفظ کند. شمارهٔ آیندهٔ واقعی با ledger زمان اجرا تطبیق داده شود. فقط دادهٔ لازم این بسته افزوده شود. backup و restore محیط جدا، preservation و آزمون خواندن نسخهٔ سازگار قبلی لازم‌اند؛ rollback با drop تاریخچه یا بازکردن bypass managed مجاز نیست.
