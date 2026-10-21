# Tasks: KP-08 — پذیرش هستهٔ همکاری Kara

**Input**: [spec](spec.md)، [plan](plan.md)، [research](research.md)، [data-model](data-model.md)، [contracts](contracts/interface.md).

**Status**: همهٔ کارهای زیر آینده و انجام‌نشده‌اند. وجود spec/checklist به معنی پیاده‌سازی نیست.

## Phase 1: Setup

- [ ] T001 پیش‌نیاز KP-01 تا KP-07 پذیرفته‌شده، commit مبنا، ledger و imageها را در `docs/kara-kp-08-validation.md` ثبت و gate را احراز کن؛ قبل از تغییر، quickstart همین بسته را بخوان. (SC-001..004)
- [ ] T002 ماتریس دو پروژه/حساب و سناریوهای `infra/api/company_projects/test_team_acceptance.py` را از AS-11..AS-32 و edge cases آماده کن؛ داده و credential خصوصی بمانند. (SC-001, SC-002)

## Phase 2: Foundational

- [ ] T003 در `scripts/kara_core_acceptance.py` manifest و fixture harness را بدون schema/endpoint جدید محصول با این قیود بساز: AcceptanceManifest: بدون token یا حساب واقعی مشتری؛ هر نتیجه به همین snapshot وصل.؛ ScenarioEvidence: status فقط not_run/pass/fail/blocked؛ private evidence در .runtime، گزارش sanitized در docs.؛ SyntheticFixture: اطلاعات ورود خصوصی؛ cleanup فقط دادهٔ متعلق به fixture، تولید دست‌نخورده.؛ AcceptanceDecision: پذیرش از شواهد کامل؛ no model/PO impersonation؛ خروجی این spec هنوز تصمیم پذیرش نیست. (FR-001..012; SC-003)
- [ ] T004 در `infra/api/company_projects/test_team_acceptance.py` محیط پذیرفته‌شده، عدم تغییر schema، دادهٔ baseline و isolation fixture را ثبت کن؛ تست‌ها فقط روی بانک مستقل باشند. (FR-001..012; SC-002, SC-003)

## Phase 3: User Story 1 — سناریوی قطعی چندنفره

**Goal**: تیم آزمایش دو پروژه و دو فلو می‌سازد و یک درخواست را تا پایان دو مرحله پیش می‌برد.

**Independent Test**: با حساب‌های مستقل از intake تا finalize دوم و مشاهدهٔ وضعیت کامل شود.

- [ ] T005 [US1] در `scripts/kara_core_acceptance.py` و مرز `scripts/kara_core_acceptance.py` این رفتار را پیاده/اثبات کن: «آزمون از موتور موجود با دو مرحلهٔ synthetic قطعی استفاده کند و به کیفیت مدل وابسته نباشد.» نتیجهٔ harness و شاهد مطابق `contracts/interface.md` باشد. (FR-001)
- [ ] T006 [US1] در `scripts/kara_core_acceptance.py` و مرز `scripts/kara_core_acceptance.py` این رفتار را پیاده/اثبات کن: «دو پروژه، دو فلو، نسخهٔ دوم فلو و حساب‌های root/manager/PO/TL/designer/developer/QC و normal نامجاز پوشش داده شوند؛ یک حساب می‌تواند چند نقش داشته باشد ولی نشست‌ها مستقل باشند.» نتیجهٔ harness و شاهد مطابق `contracts/interface.md` باشد. (FR-002)
- [ ] T007 [US1] در `scripts/kara_core_acceptance.py` و مرز `scripts/kara_core_acceptance.py` این رفتار را پیاده/اثبات کن: «مسیر دستی از درخواست، چهار outcome ورود، چند دور اصلاح، انتخاب خروجی، تحویل و اتمام با ورودی/نسخهٔ دقیق بررسی شود.» نتیجهٔ harness و شاهد مطابق `contracts/interface.md` باشد. (FR-003)
- [ ] T008 [US1] در `scripts/kara_core_acceptance.py` و مرز `scripts/kara_core_acceptance.py` این رفتار را پیاده/اثبات کن: «UI واقعی فارسی/RTL و صفحه‌کلید و loading/error/conflict و legacy projects/members/inbox/automations/templates بازبینی شوند.» نتیجهٔ harness و شاهد مطابق `contracts/interface.md` باشد. (FR-004)
- [ ] T009 [US1] در `infra/api/company_projects/test_team_acceptance.py` دو سناریوی AS-11/AS-12 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-001..004; SC-001..003)
- [ ] T010 [US1] در `scripts/kara_core_browser.mjs` و `scripts/kara_core_browser.mjs` مسیر «سناریوی قطعی چندنفره» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را در رابط پذیرفته‌شده آزمون کن؛ برای پذیرش صفحه یا API تازهٔ محصول نساز. (SC-004; FR-001..004)

## Phase 4: User Story 2 — پذیرش منفی و بازیابی

**Goal**: تیم scope، لغو، رقابت و بازیابی backup را روی محیط جدا آزمایش می‌کند.

**Independent Test**: هیچ اثر غیرمجاز و تصمیم مضاعف نماند و restore با محتوای مورد انتظار تطبیق کند.

- [ ] T011 [US2] در `scripts/kara_core_acceptance.py` و مرز `scripts/kara_core_acceptance.py` این رفتار را پیاده/اثبات کن: «ماتریس denial تمام ورودی‌های managed، cross-project، same-project unauthorized، revoked membership و grant را با شواهد مستقیم پوشش دهد.» نتیجهٔ harness و شاهد مطابق `contracts/interface.md` باشد. (FR-005)
- [ ] T012 [US2] در `scripts/kara_core_acceptance.py` و مرز `scripts/kara_core_acceptance.py` این رفتار را پیاده/اثبات کن: «دو start/finalize، action replay/conflict، stale مستقیم/گذرا، late callback و restart با witnessهای داده و event بررسی شوند.» نتیجهٔ harness و شاهد مطابق `contracts/interface.md` باشد. (FR-006)
- [ ] T013 [US2] در `scripts/kara_core_acceptance.py` و مرز `scripts/kara_core_acceptance.py` این رفتار را پیاده/اثبات کن: «backup و restore تازه در محیط جدا با شمار، شناسه، هش محتوا و فایل‌های منتخب بررسی شود؛ دادهٔ واقعی تولید تغییر نکند.» نتیجهٔ harness و شاهد مطابق `contracts/interface.md` باشد. (FR-007)
- [ ] T014 [US2] در `scripts/kara_core_acceptance.py` و مرز `scripts/kara_core_acceptance.py` این رفتار را پیاده/اثبات کن: «هر شکست بحرانی مانع پذیرش هسته باشد؛ گزارش نسخهٔ source/image/fixture و دستور و نتیجه و موارد اجرا نشده را ثبت کند.» نتیجهٔ harness و شاهد مطابق `contracts/interface.md` باشد. (FR-008)
- [ ] T015 [US2] در `infra/api/company_projects/test_team_acceptance.py` دو سناریوی AS-21/AS-22 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-005..008; SC-001..003)
- [ ] T016 [US2] در `scripts/kara_core_browser.mjs` و `scripts/kara_core_browser.mjs` مسیر «پذیرش منفی و بازیابی» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را در رابط پذیرفته‌شده آزمون کن؛ برای پذیرش صفحه یا API تازهٔ محصول نساز. (SC-004; FR-005..008)

## Phase 5: User Story 3 — smoke مدل و تصمیم شروع کلاسور

**Goal**: یک اجرای مدل واقعی جدا از سناریوی قطعی بررسی و سپس نتیجهٔ آمادگی اعلام می‌شود.

**Independent Test**: اثبات deterministic و real model جدا گزارش و شرط شروع کلاسور روشن باشد.

- [ ] T017 [US3] در `scripts/kara_core_acceptance.py` و مرز `scripts/kara_core_acceptance.py` این رفتار را پیاده/اثبات کن: «حداقل یک smoke مدل واقعی در محیط روشن جدا اجرا شود؛ موفقیت mock به‌عنوان مدل گزارش نشود.» نتیجهٔ harness و شاهد مطابق `contracts/interface.md` باشد. (FR-009)
- [ ] T018 [US3] در `scripts/kara_core_acceptance.py` و مرز `scripts/kara_core_acceptance.py` این رفتار را پیاده/اثبات کن: «آمادگی orchestration و کیفیت مدل دو نتیجهٔ جدا باشند؛ شکست مدل مخفی یا به خطای فلو تعبیر نشود.» نتیجهٔ harness و شاهد مطابق `contracts/interface.md` باشد. (FR-010)
- [ ] T019 [US3] در `scripts/kara_core_acceptance.py` و مرز `scripts/kara_core_acceptance.py` این رفتار را پیاده/اثبات کن: «ساخت اختصاصی کلاسور تنها پس از پذیرش کل چک‌لیست هسته آغاز شود؛ تست‌های synthetic دارایی تخصصی کلاسور تلقی نشوند.» نتیجهٔ harness و شاهد مطابق `contracts/interface.md` باشد. (FR-011)
- [ ] T020 [US3] در `scripts/kara_core_acceptance.py` و مرز `scripts/kara_core_acceptance.py` این رفتار را پیاده/اثبات کن: «گزارش نهایی pass/fail/blocked هر سناریو، محدودیت و مسئول اقدام بعدی را داشته باشد؛ خودکار هیچ تأیید PO یا TL ایجاد نکند.» نتیجهٔ harness و شاهد مطابق `contracts/interface.md` باشد. (FR-012)
- [ ] T021 [US3] در `infra/api/company_projects/test_team_acceptance.py` دو سناریوی AS-31/AS-32 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-009..012; SC-001..003)
- [ ] T022 [US3] در `scripts/kara_core_browser.mjs` و `scripts/kara_core_browser.mjs` مسیر «smoke مدل و تصمیم شروع کلاسور» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را در رابط پذیرفته‌شده آزمون کن؛ برای پذیرش صفحه یا API تازهٔ محصول نساز. (SC-004; FR-009..012)

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 در `docs/kara-kp-08-validation.md` نتیجهٔ make check، PostgreSQL مرتبط، build/TypeScript/UI، Compose، startup، doctor و browser واقعی را با نسخه و شاهد/موارد اجرا نشده ثبت کن؛ regressions پروژه/اعضا/inbox/automation/templates حفظ شوند. (SC-001..004)
- [ ] T024 در `docs/kara-kp-08-validation.md` backup/restore، مسیر rollback دارای enforcement، تصمیم پذیرش و محدودیت را ثبت و `specs/008-core-acceptance/tasks.md` را فقط براساس شاهد به‌روز کن؛ commitهای مستقل و branch policy رعایت شوند. (SC-003)

## Dependencies and Execution Order

KP-01 تا KP-07 پذیرفته‌شده. T001 و T002 پیش از foundation؛ T003 پیش از T004 و storyها. storyها به ترتیب US1 → US2 → US3 برای یکپارچه‌سازی کامل؛ آزمون هر story به‌تنهایی با fixture معتبر ممکن است. فعال‌کردن قابلیت پیش از تکمیل تمام موارد امنیتی ممنوع است.

## Parallel Opportunities

برای هر US، پس از تثبیت سرویس/قرارداد، آزمون UI و backend در فایل‌های جدا امکان کار موازی دارند؛ روی shared controller/migration هم‌زمان تغییر ندهید. در این لیست [P] پیش‌فرض نداریم چون پیش‌نیازهای مشترک هنوز ساخته نشده‌اند.

## Implementation Strategy

MVP نخست US1 به‌صورت محدود در محیط آزمون؛ سپس US2 و US3 و پذیرش کامل. پذیرش هر story جای عبور از gateهای کل بسته نیست. ابتدا پیش‌نیاز و قرارداد فعلی را احراز، سپس تسک انتخاب‌شده را پیاده، تست و commit کن؛ کل roadmap با یک implement اجرا نشود.

## Requirement Traceability

| Requirement | Story | Implementation/Test/UI tasks |
| --- | --- | --- |
| FR-001 | US1 | T005, T009, T010 |
| FR-002 | US1 | T006, T009, T010 |
| FR-003 | US1 | T007, T009, T010 |
| FR-004 | US1 | T008, T009, T010 |
| FR-005 | US2 | T011, T015, T016 |
| FR-006 | US2 | T012, T015, T016 |
| FR-007 | US2 | T013, T015, T016 |
| FR-008 | US2 | T014, T015, T016 |
| FR-009 | US3 | T017, T021, T022 |
| FR-010 | US3 | T018, T021, T022 |
| FR-011 | US3 | T019, T021, T022 |
| FR-012 | US3 | T020, T021, T022 |
| SC-001, SC-002, SC-003, SC-004 | All | T001, T002, T004, story test/UI tasks, T023, T024 |

## Blocking Conditions

تعداد تست قبلی ۱۱۵ شاهد تاریخی KP-01 است؛ برای پذیرش آینده دوباره relevant suites و سناریوی جدید لازم‌اند. نسخهٔ قدیم compile یا screenshot به‌تنهایی پذیرش جدید نیست.
