# مشخصات گام‌های باقی‌ماندهٔ Kara

تاریخ: 2026-10-22. تهیه‌شده با مهارت‌ها، قالب‌ها و helperهای رسمی Spec Kit 1.2.2.
[راهنمای اجرا](../docs/spec-driven-development.md)، [اصول پروژه](../.specify/memory/constitution.md)
و [سوابق این ترد](../docs/kara-thread-record.md) مرجع ادامهٔ کارند.

تمام بسته‌ها **draft طراحی** هستند و تسک‌های پیاده‌سازی آن‌ها بازند. KP-00 و KP-01 قبلاً
پذیرفته شده‌اند؛ برای گذشته spec ساختگی با ادعای اجرای Spec Kit ایجاد نشده است.

| گام | مشخصات | طرح/تسک | پیش‌نیاز شروع |
| --- | --- | --- | --- |
| KP-02 | [تعریف ایجنت قابل اجرا و مجوزهای صریح](002-agent-access/spec.md) | [plan](002-agent-access/plan.md) / [tasks](002-agent-access/tasks.md) | KP-01 پذیرفته‌شده |
| KP-03 | [فلوهای تیمی نسخه‌دار](003-versioned-team-flows/spec.md) | [plan](003-versioned-team-flows/plan.md) / [tasks](003-versioned-team-flows/tasks.md) | KP-02 پس از پذیرش |
| KP-04 | [درخواست دستی و تصمیم ورود مالک محصول](004-requests-po-intake/spec.md) | [plan](004-requests-po-intake/plan.md) / [tasks](004-requests-po-intake/tasks.md) | KP-01 و KP-03 پس از پذیرش |
| KP-05 | [اجرای مرحله، بازخورد و خروجی منتخب](005-stage-feedback/spec.md) | [plan](005-stage-feedback/plan.md) / [tasks](005-stage-feedback/tasks.md) | KP-02، KP-03 و KP-04 پس از پذیرش |
| KP-06 | [تحویل خروجی و کارتابل اقدام](006-handoff-action-inbox/spec.md) | [plan](006-handoff-action-inbox/plan.md) / [tasks](006-handoff-action-inbox/tasks.md) | KP-05 پس از پذیرش |
| KP-07 | [برگشت، لغو، هم‌زمانی و بازیابی](007-recovery-concurrency/spec.md) | [plan](007-recovery-concurrency/plan.md) / [tasks](007-recovery-concurrency/tasks.md) | KP-05 و KP-06 پس از پذیرش؛ ایمنی اولیهٔ dispatch قبلاً لازم بوده است |
| KP-08 | [پذیرش هستهٔ همکاری Kara](008-core-acceptance/spec.md) | [plan](008-core-acceptance/plan.md) / [tasks](008-core-acceptance/tasks.md) | KP-01 تا KP-07 پذیرفته‌شده |
| KP-09 | [ورودی سرویس واسط Jira](009-jira-intake-adapter/spec.md) | [plan](009-jira-intake-adapter/plan.md) / [tasks](009-jira-intake-adapter/tasks.md) | KP-04 پذیرفته‌شده و نمونهٔ واقعی پاک‌سازی‌شدهٔ سرویس واسط؛ نمونه اکنون موجود نیست |
| KP-10 | [خودکارسازی محدود و گزارش درخواست‌ها](010-bounded-automation-reporting/spec.md) | [plan](010-bounded-automation-reporting/plan.md) / [tasks](010-bounded-automation-reporting/tasks.md) | KP-08 پذیرفته‌شده و قرارداد پذیرفته‌شدهٔ اتصال مرتبط؛ برای Jira همچنین KP-09 |

هر پوشه دارای `spec.md`، `research.md`، `plan.md`، `data-model.md`، `contracts/interface.md`،
`quickstart.md`، `tasks.md`، `checklists/requirements.md`، `checklists/review.md` و `execution.md` است.
در مجموع ۲۷ user story، ۱۰۸ الزام FR، ۳۶ معیار SC، ۵۴ سناریوی اصلی و ۲۱۶ تسک باز ثبت شده‌اند.
شناسه‌ها در هر feature مستقل‌اند؛ ارجاع کامل به‌صورت `KP-02/FR-001` است.

## ترتیب و gateها

KP-02 → KP-03 → KP-04 → KP-05 → KP-06 → KP-07 → KP-08؛ سپس ساخت اختصاصی کلاسور.
KP-09 پس از KP-04 و نمونهٔ واقعی سرویس واسط قابل اجراست و پیش‌نیاز عرضهٔ متعهد به Jira است،
ولی پذیرش مسیر دستی و شروع کلاسور پس از هسته را متوقف نمی‌کند. KP-10 به KP-08 و اتصال مرتبط
وابسته است؛ اتوماسیون Jira همچنین KP-09 را لازم دارد. هیچ تصمیم PO/finalizer/TL خودکار جعل نمی‌شود.

ایمنی dispatch و idempotency از اولین dispatch در KP-05 لازم‌اند؛ KP-07 تکمیل بازیابی است.
حفظ نسخهٔ Workflow مصرف‌شده و جلوگیری از bypass از KP-02 شروع می‌شوند، نه پس از ساخت فلو.
نمونهٔ واقعی Jira هنوز نیست؛ port داخلی مشخص شده، نگاشت بیرونی و live acceptance مسدودند.

## روش بازبینی و تکمیل

1. feature را صریح انتخاب کنید؛ `.specify/feature.json` وضعیت محلی است و در Git ثبت نمی‌شود.
2. spec و checklist بازبین را بخوانید؛ quality checklist نویسنده به معنی تست محصول نیست.
3. plan و قراردادها را با سورس/ledger و پیش‌نیاز پذیرفته‌شده تازه کنید؛ سپس tasks/analyze.
4. فقط گام انتخاب‌شده را implement، واقعاً آزمون، با شاهد تحویل و converge کنید.
5. چک‌باکس تسک‌ها تنها پس از شاهد تغییر کند؛ پذیرش هر feature در گزارش اختصاصی ثبت شود.

[گزارش بررسی سازگاری و اجرای ابزار](../docs/spec-kit-adoption-validation.md) محدودیت‌ها و نتایج
این تحویل را ثبت می‌کند. برنامه‌ریزی روی master است؛ نام directory شاخهٔ جدید نساخته است.
