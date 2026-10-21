# Data Model: KP-06

وضعیت: طراحی آینده؛ جدول تازه در این تحویل ساخته نشده است.

## Entities and Constraints

### ArtifactDependency

**Fields**: scope، consumer_stage/artifact، producer_artifact، digest، consumed_at.

**Validation and Relationships**: ارجاع به نسخهٔ دقیق؛ no cross-scope؛ dependency immutable پس از مصرف.

### HandoffView

**Fields**: instance، stage، required_artifact_refs، permitted_actor.

**Validation and Relationships**: نمای محاسبه‌شده؛ ذخیرهٔ مجوز دائمی یا تکثیر raw logs ممنوع.

### ActionItem

**Fields**: scope، stage، action، current_actor، blocker، updated_at.

**Validation and Relationships**: نمای projection با authorization تازه؛ count/list یک سیاست.

### RequestProgress

**Fields**: instance، pinned_flowversion، stage_states، responsible.

**Validation and Relationships**: metadata مجاز بدون prompt و credentials؛ stale صریح.

## Shared Integrity and Transactions

- Scope با project_id و workspace واقعی `company_project_workspaces.workspace_id` است؛ tenant مدیریت مرکزی جای workspace تیم نیست.
- composite FK شامل scope برای روابط جدید؛ تعلق app/workflow/run بومی به هم و workspace در تراکنش بررسی شود. UUID canonical، revision عدد صحیح مثبت غیر bool و digest SHA-256 canonical JSON قرارداد.
- immutable history و current pointer با CAS جدا باشند؛ actor از نشست/هویت داخلی معتبر. حذف عضویت تاریخچه را حذف نکند و fresh policy عملیات بعدی را کنترل کند.
- mutation همراه audit و action key payload-bound در یک تراکنش؛ یک key و payload replay، payload متفاوت 409. correlation بین DB/queue/native run نگه داشته شود.
- مسیر حالت: قرارداد [KP-00](../../docs/kara-team-contract-v1.md) مرجع است؛ state یا guard از JSON کاربر پذیرفته نمی‌شود. موجودیت این بسته جای تصمیم انسانی مرحلهٔ دیگر نیست.

## Migration and Rollback

006_team_handoff. runner همان ledger و advisory lock ثابت `210610003`، checksum، preflight و transactional DDL/marker را حفظ کند. شمارهٔ آیندهٔ واقعی با ledger زمان اجرا تطبیق داده شود. فقط دادهٔ لازم این بسته افزوده شود. backup و restore محیط جدا، preservation و آزمون خواندن نسخهٔ سازگار قبلی لازم‌اند؛ rollback با drop تاریخچه یا بازکردن bypass managed مجاز نیست.
