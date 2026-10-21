# Data Model: KP-02

وضعیت: طراحی آینده؛ جدول تازه در این تحویل ساخته نشده است.

## Entities and Constraints

### ManagedAgent

**Fields**: scope، id، app_id، workflow_id منتشرشده، contract_revision/digest، lifecycle، acl_revision.

**Validation and Relationships**: هر app در scope حداکثر یک تعریف فعال؛ revision مثبت؛ workflow متعلق به همان app/workspace؛ آرشیو تاریخچه را نگه می‌دارد.

### AgentGrant

**Fields**: scope، agent_id، account_id، membership_id، action، granted_by/at.

**Validation and Relationships**: یکتا روی scope/agent/account/action؛ action فقط شش اختیار عملیاتی؛ manage_access ممنوع؛ حذف عضویت grant فعال را بی‌اثر کند.

### PolicyAction

**Fields**: scope، actor، operation، key، payload_digest، result.

**Validation and Relationships**: کلید UUID canonical؛ payload یکسان replay، متفاوت 409؛ audit و افزایش acl_revision اتمی.

### ExecutionBinding

**Fields**: scope، actor، agent، workflow، contract digest، correlation.

**Validation and Relationships**: تحت نشست واقعی؛ نتیجه فقط با بررسی مجدد مجوز خوانده شود؛ تا KP-05 جای پرونده/تأیید PO نیست.

## Shared Integrity and Transactions

- Scope با project_id و workspace واقعی `company_project_workspaces.workspace_id` است؛ tenant مدیریت مرکزی جای workspace تیم نیست.
- composite FK شامل scope برای روابط جدید؛ تعلق app/workflow/run بومی به هم و workspace در تراکنش بررسی شود. UUID canonical، revision عدد صحیح مثبت غیر bool و digest SHA-256 canonical JSON قرارداد.
- immutable history و current pointer با CAS جدا باشند؛ actor از نشست/هویت داخلی معتبر. حذف عضویت تاریخچه را حذف نکند و fresh policy عملیات بعدی را کنترل کند.
- mutation همراه audit و action key payload-bound در یک تراکنش؛ یک key و payload replay، payload متفاوت 409. correlation بین DB/queue/native run نگه داشته شود.
- مسیر حالت: قرارداد [KP-00](../../docs/kara-team-contract-v1.md) مرجع است؛ state یا guard از JSON کاربر پذیرفته نمی‌شود. موجودیت این بسته جای تصمیم انسانی مرحلهٔ دیگر نیست.

## Migration and Rollback

002_team_agents_grants. runner همان ledger و advisory lock ثابت `210610003`، checksum، preflight و transactional DDL/marker را حفظ کند. شمارهٔ آیندهٔ واقعی با ledger زمان اجرا تطبیق داده شود. فقط دادهٔ لازم این بسته افزوده شود. backup و restore محیط جدا، preservation و آزمون خواندن نسخهٔ سازگار قبلی لازم‌اند؛ rollback با drop تاریخچه یا بازکردن bypass managed مجاز نیست.
