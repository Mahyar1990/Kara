# Data Model: KP-05

وضعیت: طراحی آینده؛ جدول تازه در این تحویل ساخته نشده است.

## Entities and Constraints

### Stage

**Fields**: scope، instance، step_key، workflow_id، finalizer_id، decision_role، record_revision، input_digest، state، active_attempt_id.

**Validation and Relationships**: state فقط blocked/ready/running/awaiting_feedback/awaiting_decision/completed/failed/stale/cancelled؛ running دقیقاً یک active_attempt؛ revision مثبت.

### Attempt

**Fields**: stage، actor، input_snapshot/digest، workflow_id، workflow_run_id، status، mode، time.

**Validation and Relationships**: حداکثر یک active attempt در stage؛ هر native run به حداکثر یک attempt؛ نتیجهٔ قدیمی حق تحویل ندارد.

### Feedback/ArtifactRevision

**Fields**: stage، base_revision، parent_artifact، author، text، digest، input_digest، kind=model|human.

**Validation and Relationships**: append-only؛ یکتا روی scope/stage/artifact revision؛ model به attempt وصل، human به نویسندهٔ واقعی.

### StageDecision/Outbox

**Fields**: stage، selected_artifact، base_revision، input_digest، actor، outcome؛ action_key، lease، dispatch status.

**Validation and Relationships**: یک تصمیم مؤثر در base_revision؛ شروع/تصمیم CAS و قفل؛ outbox با replay/reconciliation از اولین dispatch.

## Shared Integrity and Transactions

- Scope با project_id و workspace واقعی `company_project_workspaces.workspace_id` است؛ tenant مدیریت مرکزی جای workspace تیم نیست.
- composite FK شامل scope برای روابط جدید؛ تعلق app/workflow/run بومی به هم و workspace در تراکنش بررسی شود. UUID canonical، revision عدد صحیح مثبت غیر bool و digest SHA-256 canonical JSON قرارداد.
- immutable history و current pointer با CAS جدا باشند؛ actor از نشست/هویت داخلی معتبر. حذف عضویت تاریخچه را حذف نکند و fresh policy عملیات بعدی را کنترل کند.
- mutation همراه audit و action key payload-bound در یک تراکنش؛ یک key و payload replay، payload متفاوت 409. correlation بین DB/queue/native run نگه داشته شود.
- مسیر حالت: قرارداد [KP-00](../../docs/kara-team-contract-v1.md) مرجع است؛ state یا guard از JSON کاربر پذیرفته نمی‌شود. موجودیت این بسته جای تصمیم انسانی مرحلهٔ دیگر نیست.

## Migration and Rollback

005_team_sessions. runner همان ledger و advisory lock ثابت `210610003`، checksum، preflight و transactional DDL/marker را حفظ کند. شمارهٔ آیندهٔ واقعی با ledger زمان اجرا تطبیق داده شود. فقط دادهٔ لازم این بسته افزوده شود. backup و restore محیط جدا، preservation و آزمون خواندن نسخهٔ سازگار قبلی لازم‌اند؛ rollback با drop تاریخچه یا بازکردن bypass managed مجاز نیست.
