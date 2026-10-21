# Tasks: KP-07 — برگشت، لغو، هم‌زمانی و بازیابی

**Input**: [spec](spec.md)، [plan](plan.md)، [research](research.md)، [data-model](data-model.md)، [contracts](contracts/interface.md).

**Status**: همهٔ کارهای زیر آینده و انجام‌نشده‌اند. وجود spec/checklist به معنی پیاده‌سازی نیست.

## Phase 1: Setup

- [ ] T001 پیش‌نیاز KP-05 و KP-06 پس از پذیرش؛ ایمنی اولیهٔ dispatch قبلاً لازم بوده است، commit مبنا، ledger و imageها را در `docs/kara-kp-07-validation.md` ثبت و gate را احراز کن؛ قبل از تغییر، quickstart همین بسته را بخوان. (SC-001..004)
- [ ] T002 ماتریس دو پروژه/حساب و سناریوهای `infra/api/company_projects/test_team_recovery.py` را از AS-11..AS-32 و edge cases آماده کن؛ داده و credential خصوصی بمانند. (SC-001, SC-002)

## Phase 2: Foundational

- [ ] T003 در `infra/api/company_projects/team_recovery.py` و migration موردنیاز `infra/api/company_projects/team_migrations.py` مدل‌های data-model را با این قیود بساز/بازاستفاده کن: RecoveryEvent: append-only؛ consumer graph فقط scope جاری؛ history هرگز cascade حذف نشود.؛ Reassignment: تراکنش قفل stage و سیاست عضویت؛ finalizer جدید دارای اختیار لازم.؛ Cancellation: completed history باقی؛ queued/running/stop-requested/stopped/unknown از هم متمایز.؛ OutboxLease/ActionKey: at-least-once delivery؛ unique logical key؛ retry bounded؛ unknown effect هرگز blind retry نشود. (FR-001..012; SC-003)
- [ ] T004 در `infra/api/company_projects/test_team_recovery.py` ارتقا/عدم افت داده، scope، FK/CAS و rollback/replay مرتبط را روی PostgreSQL آزمون کن؛ شماره و checksum migration قبلی عوض نشود. (FR-001..012; SC-002, SC-003)

## Phase 3: User Story 1 — کهنگی و بررسی مجدد

**Goal**: تغییر خروجی مصرف‌شده، نتایج متأثر را stale و نیازمند تصمیم تازه می‌کند.

**Independent Test**: زنجیرهٔ سه مرحله فقط consumerهای متأثر stale و تاریخچه‌ها را حفظ کند.

- [ ] T005 [US1] در `infra/api/company_projects/team_recovery.py` و مرز `infra/api/company_projects/team_recovery_controller.py` این رفتار را پیاده/اثبات کن: «تغییر request یا producer مصرف‌شده و ابطال تصمیم، consumerهای مستقیم و گذرا را stale و تحویل تازه را مسدود کند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-001)
- [ ] T006 [US1] در `infra/api/company_projects/team_recovery.py` و مرز `infra/api/company_projects/team_recovery_controller.py` این رفتار را پیاده/اثبات کن: «تاریخچهٔ artifact/decision حفظ شود؛ revalidate فقط با ورودی تازه، اختیار جاری و ورود معتبر به ready برسد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-002)
- [ ] T007 [US1] در `infra/api/company_projects/team_recovery.py` و مرز `infra/api/company_projects/team_recovery_controller.py` این رفتار را پیاده/اثبات کن: «نسخهٔ فلو و ایجنت در instance موجود بی‌صدا تغییر نکند؛ بازگشت به معنای نسخه/تصمیم تازه با علت باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-003)
- [ ] T008 [US1] در `infra/api/company_projects/team_recovery.py` و مرز `infra/api/company_projects/team_recovery_controller.py` این رفتار را پیاده/اثبات کن: «علت stale و موارد متأثر در نمای پرونده برای فرد مجاز قابل مشاهده باشند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-004)
- [ ] T009 [US1] در `infra/api/company_projects/test_team_recovery.py` دو سناریوی AS-11/AS-12 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-001..004; SC-001..003)
- [ ] T010 [US1] در `infra/web/overlay/app/components/company-projects/team-recovery.tsx` و `infra/web/team-recovery.spec.mjs` مسیر «کهنگی و بررسی مجدد» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-001..004)

## Phase 4: User Story 2 — لغو و تغییر مسئول

**Goal**: مدیر مسئول را با دلیل عوض می‌کند یا PO مجاز پرونده را لغو می‌کند.

**Independent Test**: مجوز فرد قبلی قطع و فرد تازه فقط artifact لازم را بگیرد؛ نتیجهٔ دیررس تحویل نشود.

- [ ] T011 [US2] در `infra/api/company_projects/team_recovery.py` و مرز `infra/api/company_projects/team_recovery_controller.py` این رفتار را پیاده/اثبات کن: «تغییر مسئول فقط توسط ادمین کل یا مدیر با علت و کنترل عضویت/grant/نقش تصمیم شخص جدید انجام شود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-005)
- [ ] T012 [US2] در `infra/api/company_projects/team_recovery.py` و مرز `infra/api/company_projects/team_recovery_controller.py` این رفتار را پیاده/اثبات کن: «لغو با ادمین کل/مدیر/PO همان پروژه و علت انجام شود؛ مرحلهٔ completed بازنویسی نشود ولی پروندهٔ متوقف تحویل تازه نکند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-006)
- [ ] T013 [US2] در `infra/api/company_projects/team_recovery.py` و مرز `infra/api/company_projects/team_recovery_controller.py` این رفتار را پیاده/اثبات کن: «توقف dispatch، cancel صف و درخواست توقف worker با نتیجهٔ واقعی‌شان متمایز نمایش داده شوند؛ kill قطعی ادعا نشود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-007)
- [ ] T014 [US2] در `infra/api/company_projects/team_recovery.py` و مرز `infra/api/company_projects/team_recovery_controller.py` این رفتار را پیاده/اثبات کن: «هر اقدام و callback پس از لغو یا revocation دوباره کنترل و نتیجهٔ دیررس از نهایی‌سازی و dispatch بعدی محروم شود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-008)
- [ ] T015 [US2] در `infra/api/company_projects/test_team_recovery.py` دو سناریوی AS-21/AS-22 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-005..008; SC-001..003)
- [ ] T016 [US2] در `infra/web/overlay/app/components/company-projects/team-recovery.tsx` و `infra/web/team-recovery.spec.mjs` مسیر «لغو و تغییر مسئول» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-005..008)

## Phase 5: User Story 3 — تکرار، رقابت و restart

**Goal**: سیستم پس از قطع نشست یا worker وضعیت را از ثبت پایدار تطبیق می‌دهد.

**Independent Test**: دو finalize فقط یک تصمیم مؤثر، یک action key فقط یک اثر و restart بدون گم‌شدن attempt باشد.

- [ ] T017 [US3] در `infra/api/company_projects/team_recovery.py` و مرز `infra/api/company_projects/team_recovery_controller.py` این رفتار را پیاده/اثبات کن: «CAS، قفل تصمیم و کلید اقدام payload-bound از بازنویسی قدیمی، اثر تکراری و دو attempt فعال جلوگیری کنند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-009)
- [ ] T018 [US3] در `infra/api/company_projects/team_recovery.py` و مرز `infra/api/company_projects/team_recovery_controller.py` این رفتار را پیاده/اثبات کن: «outbox پایدار با lease، تعداد retry محدود، next_retry و وضعیت نیازمند بررسی بازیابی شود؛ رخداد از دست نرود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-010)
- [ ] T019 [US3] در `infra/api/company_projects/team_recovery.py` و مرز `infra/api/company_projects/team_recovery_controller.py` این رفتار را پیاده/اثبات کن: «reconciliation پس از crash از correlation و native run استفاده کند؛ حالت نامعلوم پیش از تکرار اثر بیرونی نیازمند بررسی باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-011)
- [ ] T020 [US3] در `infra/api/company_projects/team_recovery.py` و مرز `infra/api/company_projects/team_recovery_controller.py` این رفتار را پیاده/اثبات کن: «UI فارسی/RTL وضعیت conflict/retry/cancel/recovery و خطای قابل اقدام را نشان و observability بدون secret عامل، نسخه و correlation را ثبت کند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-012)
- [ ] T021 [US3] در `infra/api/company_projects/test_team_recovery.py` دو سناریوی AS-31/AS-32 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-009..012; SC-001..003)
- [ ] T022 [US3] در `infra/web/overlay/app/components/company-projects/team-recovery.tsx` و `infra/web/team-recovery.spec.mjs` مسیر «تکرار، رقابت و restart» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-009..012)

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 در `docs/kara-kp-07-validation.md` نتیجهٔ make check، PostgreSQL مرتبط، build/TypeScript/UI، Compose، startup، doctor و browser واقعی را با نسخه و شاهد/موارد اجرا نشده ثبت کن؛ regressions پروژه/اعضا/inbox/automation/templates حفظ شوند. (SC-001..004)
- [ ] T024 در `docs/kara-kp-07-validation.md` backup/restore، مسیر rollback دارای enforcement، تصمیم پذیرش و محدودیت را ثبت و `specs/007-recovery-concurrency/tasks.md` را فقط براساس شاهد به‌روز کن؛ commitهای مستقل و branch policy رعایت شوند. (SC-003)

## Dependencies and Execution Order

KP-05 و KP-06 پس از پذیرش؛ ایمنی اولیهٔ dispatch قبلاً لازم بوده است. T001 و T002 پیش از foundation؛ T003 پیش از T004 و storyها. storyها به ترتیب US1 → US2 → US3 برای یکپارچه‌سازی کامل؛ آزمون هر story به‌تنهایی با fixture معتبر ممکن است. فعال‌کردن قابلیت پیش از تکمیل تمام موارد امنیتی ممنوع است.

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

اجرای مدل یا اثر خارجی پس از قبول dispatch ممکن است با retry دوباره شود؛ unknown را با correlation reconcile یا به بررسی انسانی ببرید. تصمیم انسانی و کل فلو را retry نکنید.
