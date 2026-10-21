# Data Model: KP-03

وضعیت: طراحی آینده؛ جدول تازه در این تحویل ساخته نشده است.

## Entities and Constraints

### TeamFlow

**Fields**: scope، id، name، current_revision، archived_at.

**Validation and Relationships**: نام در scope یکتا؛ draft revision مثبت؛ archive حذف cascade تاریخچه ندارد.

### FlowVersion

**Fields**: scope، flow_id، revision، digest، stage_bindings، published_by/at.

**Validation and Relationships**: یکتا روی scope/flow/revision؛ published immutable؛ publish اتمی.

### StageBinding

**Fields**: step_key، agent_id، workflow_id، contract_digest، depends_on، input_refs، finalizer_id، decision_role.

**Validation and Relationships**: step_key در نسخه یکتا؛ DAG ساده، حداقل یک مرحله؛ تمام refs و finalizer در scope و مجوز جاری.

### FlowReference

**Fields**: flow_version، instance/decision، retained_workflow.

**Validation and Relationships**: مصرف نسخه جلوی حذف را بگیرد؛ انتشار جدید refs قدیم را بازنویسی نکند.

## Shared Integrity and Transactions

- Scope با project_id و workspace واقعی `company_project_workspaces.workspace_id` است؛ tenant مدیریت مرکزی جای workspace تیم نیست.
- composite FK شامل scope برای روابط جدید؛ تعلق app/workflow/run بومی به هم و workspace در تراکنش بررسی شود. UUID canonical، revision عدد صحیح مثبت غیر bool و digest SHA-256 canonical JSON قرارداد.
- immutable history و current pointer با CAS جدا باشند؛ actor از نشست/هویت داخلی معتبر. حذف عضویت تاریخچه را حذف نکند و fresh policy عملیات بعدی را کنترل کند.
- mutation همراه audit و action key payload-bound در یک تراکنش؛ یک key و payload replay، payload متفاوت 409. correlation بین DB/queue/native run نگه داشته شود.
- مسیر حالت: قرارداد [KP-00](../../docs/kara-team-contract-v1.md) مرجع است؛ state یا guard از JSON کاربر پذیرفته نمی‌شود. موجودیت این بسته جای تصمیم انسانی مرحلهٔ دیگر نیست.

## Migration and Rollback

003_team_flows. runner همان ledger و advisory lock ثابت `210610003`، checksum، preflight و transactional DDL/marker را حفظ کند. شمارهٔ آیندهٔ واقعی با ledger زمان اجرا تطبیق داده شود. فقط دادهٔ لازم این بسته افزوده شود. backup و restore محیط جدا، preservation و آزمون خواندن نسخهٔ سازگار قبلی لازم‌اند؛ rollback با drop تاریخچه یا بازکردن bypass managed مجاز نیست.
