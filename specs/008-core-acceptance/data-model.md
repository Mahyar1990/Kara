# Data Model: KP-08

وضعیت: طراحی آینده؛ جدول تازه در این تحویل ساخته نشده است.

## Entities and Constraints

### AcceptanceManifest

**Fields**: git commit، upstream pin، images/digests، fixture_version، environment، time.

**Validation and Relationships**: بدون token یا حساب واقعی مشتری؛ هر نتیجه به همین snapshot وصل.

### ScenarioEvidence

**Fields**: scenario_id، FR/SC refs، commands، actual/expected، status، evidence_path.

**Validation and Relationships**: status فقط not_run/pass/fail/blocked؛ private evidence در .runtime، گزارش sanitized در docs.

### SyntheticFixture

**Fields**: دو scope، چند account واقعی آزمایش، دو flowversion، deterministic workflow exports.

**Validation and Relationships**: اطلاعات ورود خصوصی؛ cleanup فقط دادهٔ متعلق به fixture، تولید دست‌نخورده.

### AcceptanceDecision

**Fields**: core_result، model_result، unresolved_cases، human review.

**Validation and Relationships**: پذیرش از شواهد کامل؛ no model/PO impersonation؛ خروجی این spec هنوز تصمیم پذیرش نیست.

## Shared Integrity and Transactions

- Scope با project_id و workspace واقعی `company_project_workspaces.workspace_id` است؛ tenant مدیریت مرکزی جای workspace تیم نیست.
- composite FK شامل scope برای روابط جدید؛ تعلق app/workflow/run بومی به هم و workspace در تراکنش بررسی شود. UUID canonical، revision عدد صحیح مثبت غیر bool و digest SHA-256 canonical JSON قرارداد.
- immutable history و current pointer با CAS جدا باشند؛ actor از نشست/هویت داخلی معتبر. حذف عضویت تاریخچه را حذف نکند و fresh policy عملیات بعدی را کنترل کند.
- mutation همراه audit و action key payload-bound در یک تراکنش؛ یک key و payload replay، payload متفاوت 409. correlation بین DB/queue/native run نگه داشته شود.
- مسیر حالت: قرارداد [KP-00](../../docs/kara-team-contract-v1.md) مرجع است؛ state یا guard از JSON کاربر پذیرفته نمی‌شود. موجودیت این بسته جای تصمیم انسانی مرحلهٔ دیگر نیست.

## Migration and Rollback

بدون migration محصول؛ harness آزمون از schema پذیرفته‌شده استفاده می‌کند. runner همان ledger و advisory lock ثابت `210610003`، checksum، preflight و transactional DDL/marker را حفظ کند. شمارهٔ آیندهٔ واقعی با ledger زمان اجرا تطبیق داده شود. فقط دادهٔ لازم این بسته افزوده شود. backup و restore محیط جدا، preservation و آزمون خواندن نسخهٔ سازگار قبلی لازم‌اند؛ rollback با drop تاریخچه یا بازکردن bypass managed مجاز نیست.
