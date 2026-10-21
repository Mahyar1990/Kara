# Spec Kit Execution Record: KP-04

تاریخ: 2026-10-22؛ CLI 1.2.2، integration Codex؛ branch قبل/بعد `master`.

این رکورد گزارش اجرای مراحل توسط ایجنت است، نه خروجی یک مولد معنایی CLI. مهارت‌های رسمی
در `.agents/skills/` خوانده و به‌ترتیب دنبال شدند. templateها و helperهای رسمی زیر واقعاً اجرا شدند؛
متن spec/design/tasks را ایجنت با زمینهٔ پروژه نوشته است. هیچ subprocess Codex یا LLM جدا برای
نوشتن خودکار این فایل‌ها فراخوانی نشد. افزونه/hook نصب نشده، بنابراین hookهای پیش/پس اجرا وجود نداشتند.

| مرحلهٔ ایجنت | آرگومان/زمینه | خروجی |
| --- | --- | --- |
| `$speckit-specify` | KP-04: عضو تیم نیازمندی را مستقل ثبت کند؛ PO واقعی نسخهٔ مشخص درخواست و فلو را با تصمیم صریح برای تولید انتخاب کند. | spec و quality checklist با قالب رسمی |
| `$speckit-clarify` | تصمیم‌های قبلی کاربر و taxonomy skill؛ صفر سؤال تازه | مرزها و dependency در spec؛ gate ورودی جدا |
| `$speckit-plan` | upstream pin، Python/Flask/PostgreSQL/overlay؛ research خواندنی | research، plan، data-model، contracts، quickstart |
| `$speckit-checklist` | reviewer پیش از اجرا؛ تمرکز scope/version/failure/UX | review checklist باز و reviewer-owned |
| `$speckit-tasks` | سه story و قیود مدل و سناریوها | 24 تسک باز؛ traceability دوازده FR و چهار SC |
| `$speckit-analyze` | spec/plan/tasks و constitution پس از helper پیش‌نیاز | نتیجهٔ خواندنی در گزارش تجمیعی مستندات ثبت می‌شود |

## Actual Helper Invocations

مسیر feature برای هر helper به `specs/004-requests-po-intake` تنظیم شد؛ نام BRANCH_NAME در JSON ساخت، نام feature
است و در نبود git extension هیچ checkout ایجاد نمی‌کند.

```sh
.specify/scripts/bash/create-new-feature.sh --json --number 4 --short-name requests-po-intake عضو تیم نیازمندی را مستقل ثبت کند؛ PO واقعی نسخهٔ مشخص درخواست و فلو را با تصمیم صریح برای تولید انتخاب کند.
.specify/scripts/bash/check-prerequisites.sh --json --paths-only
.specify/scripts/bash/setup-plan.sh --json
.specify/scripts/bash/check-prerequisites.sh --json --template checklist-template
.specify/scripts/bash/setup-tasks.sh --json
.specify/scripts/bash/check-prerequisites.sh --json --require-spec --require-tasks --include-tasks
```

همهٔ helperها exit=0؛ JSON خام در `.runtime/spec-kit/kp-04-helpers.json` خصوصی و خارج Git است.

## Outcome and Next Gate

مشخصات draft و طرح اولیه کامل؛ هر ۱۲ FR به تسک وصل است. همهٔ تسک‌های اجرا باز و review checklist بدون تأیید reviewer است. فلو draft/archived برای ورود جدید نامعتبر است؛ پروندهٔ pin‌شده تابع همان نسخه می‌ماند. اگر ابطال روی instance موجود اثر دارد، hook مسدودکردن مصرف را همین گام بسازید و در KP-07 گسترش دهید.

`implement` و `converge` اجرا نشدند؛ هیچ ایجنت کلاسور، جدول محصول یا issue بیرونی در این کار ساخته نشد.
