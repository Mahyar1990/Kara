# Tasks: KP-05 — اجرای مرحله، بازخورد و خروجی منتخب

**Input**: [spec](spec.md)، [plan](plan.md)، [research](research.md)، [data-model](data-model.md)، [contracts](contracts/interface.md).

**Status**: همهٔ کارهای زیر آینده و انجام‌نشده‌اند. وجود spec/checklist به معنی پیاده‌سازی نیست.

## Phase 1: Setup

- [ ] T001 پیش‌نیاز KP-02، KP-03 و KP-04 پس از پذیرش، commit مبنا، ledger و imageها را در `docs/kara-kp-05-validation.md` ثبت و gate را احراز کن؛ قبل از تغییر، quickstart همین بسته را بخوان. (SC-001..004)
- [ ] T002 ماتریس دو پروژه/حساب و سناریوهای `infra/api/company_projects/test_team_stages.py` را از AS-11..AS-32 و edge cases آماده کن؛ داده و credential خصوصی بمانند. (SC-001, SC-002)

## Phase 2: Foundational

- [ ] T003 در `infra/api/company_projects/team_stages.py` و migration موردنیاز `infra/api/company_projects/team_migrations.py` مدل‌های data-model را با این قیود بساز/بازاستفاده کن: Stage: state فقط blocked/ready/running/awaiting_feedback/awaiting_decision/completed/failed/stale/cancelled؛ running دقیقاً یک active_attempt؛ revision مثبت.؛ Attempt: حداکثر یک active attempt در stage؛ هر native run به حداکثر یک attempt؛ نتیجهٔ قدیمی حق تحویل ندارد.؛ Feedback/ArtifactRevision: append-only؛ یکتا روی scope/stage/artifact revision؛ model به attempt وصل، human به نویسندهٔ واقعی.؛ StageDecision/Outbox: یک تصمیم مؤثر در base_revision؛ شروع/تصمیم CAS و قفل؛ outbox با replay/reconciliation از اولین dispatch. (FR-001..012; SC-003)
- [ ] T004 در `infra/api/company_projects/test_team_stages.py` ارتقا/عدم افت داده، scope، FK/CAS و rollback/replay مرتبط را روی PostgreSQL آزمون کن؛ شماره و checksum migration قبلی عوض نشود. (FR-001..012; SC-002, SC-003)

## Phase 3: User Story 1 — شروع مرحلهٔ آماده

**Goal**: عضو مجاز ورودی و نسخهٔ فلو را می‌بیند و خودش اجرا را آغاز می‌کند.

**Independent Test**: یک مرحلهٔ ready با یک کلیک یک attempt بسازد و نسخهٔ صحیح اجرا شود.

- [ ] T005 [US1] در `infra/api/company_projects/team_stages.py` و مرز `infra/api/company_projects/team_stages_controller.py` این رفتار را پیاده/اثبات کن: «مرحله از binding همان instance materialize شود؛ شروع فقط با run جاری، تصمیم ورود معتبر و پیش‌نیاز/ورودی تازه مجاز باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-001)
- [ ] T006 [US1] در `infra/api/company_projects/team_stages.py` و مرز `infra/api/company_projects/team_stages_controller.py` این رفتار را پیاده/اثبات کن: «ورودی شامل request/flow/agent/workflow و artifactهای مصرفی و دور feedback با نسخه و هش دقیق باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-002)
- [ ] T007 [US1] در `infra/api/company_projects/team_stages.py` و مرز `infra/api/company_projects/team_stages_controller.py` این رفتار را پیاده/اثبات کن: «شروع تکراری و هم‌زمان فقط یک attempt فعال بسازد؛ ثبت حالت، attempt و ارسال قابل بازیابی یک واحد منطقی باشند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-003)
- [ ] T008 [US1] در `infra/api/company_projects/team_stages.py` و مرز `infra/api/company_projects/team_stages_controller.py` این رفتار را پیاده/اثبات کن: «نتیجه فقط برای همان تلاش فعال و ورودی پذیرفته شود؛ موفقیت فنی پیش‌نویس بسازد و تصمیم انسانی تولید نکند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-004)
- [ ] T009 [US1] در `infra/api/company_projects/test_team_stages.py` دو سناریوی AS-11/AS-12 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-001..004; SC-001..003)
- [ ] T010 [US1] در `infra/web/overlay/app/components/company-projects/team-stages.tsx` و `infra/web/team-stages.spec.mjs` مسیر «شروع مرحلهٔ آماده» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-001..004)

## Phase 4: User Story 2 — بازخورد و اصلاح انسانی

**Goal**: عضو دارای feedback خروجی را چند بار اصلاح می‌کند و تاریخچهٔ والدها را می‌بیند.

**Independent Test**: دو feedback و یک human edit به خروجی‌های مستقل با نویسنده منتهی شوند.

- [ ] T011 [US2] در `infra/api/company_projects/team_stages.py` و مرز `infra/api/company_projects/team_stages_controller.py` این رفتار را پیاده/اثبات کن: «هر feedback دارای base_revision، والد خروجی و نویسنده باشد؛ پایهٔ قدیمی تعارض بدهد و متن دیگران بازنویسی نشود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-005)
- [ ] T012 [US2] در `infra/api/company_projects/team_stages.py` و مرز `infra/api/company_projects/team_stages_controller.py` این رفتار را پیاده/اثبات کن: «ویرایش انسانی خروجی نسخه‌دار مستقل با نویسندهٔ واقعی و والد مشخص بسازد؛ به نام مدل ثبت نشود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-006)
- [ ] T013 [US2] در `infra/api/company_projects/team_stages.py` و مرز `infra/api/company_projects/team_stages_controller.py` این رفتار را پیاده/اثبات کن: «تلاش فنی، retry فنی و دور انسانی جدا شمارش شوند؛ سقف فنی قابل تنظیم باشد و دور انسانی سقف ثابت تحمیلی نداشته باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-007)
- [ ] T014 [US2] در `infra/api/company_projects/team_stages.py` و مرز `infra/api/company_projects/team_stages_controller.py` این رفتار را پیاده/اثبات کن: «متن و artifact کامل مجاز نگهداری و بازیابی شوند؛ rating پیام یا preview کوتاه جای خروجی نهایی نباشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-008)
- [ ] T015 [US2] در `infra/api/company_projects/test_team_stages.py` دو سناریوی AS-21/AS-22 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-005..008; SC-001..003)
- [ ] T016 [US2] در `infra/web/overlay/app/components/company-projects/team-stages.tsx` و `infra/web/team-stages.spec.mjs` مسیر «بازخورد و اصلاح انسانی» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-005..008)

## Phase 5: User Story 3 — نهایی‌سازی صریح

**Goal**: نهایی‌کنندهٔ تعیین‌شده خروجی همان ورودی را انتخاب و تصمیم ثبت می‌کند.

**Independent Test**: کاربر با finalize ولی خارج از finalizer رد شود؛ finalizer با مجوز جاری موفق شود.

- [ ] T017 [US3] در `infra/api/company_projects/team_stages.py` و مرز `infra/api/company_projects/team_stages_controller.py` این رفتار را پیاده/اثبات کن: «فقط finalizer تعیین‌شده با finalize جاری و نقش لازم بتواند از awaiting_decision خروجی همان مرحله و input_digest را انتخاب کند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-009)
- [ ] T018 [US3] در `infra/api/company_projects/team_stages.py` و مرز `infra/api/company_projects/team_stages_controller.py` این رفتار را پیاده/اثبات کن: «گذار حالت دقیقاً با قرارداد KP-00 و expected_revision کنترل شود؛ حالت یا actor ارسالی کاربر معتبر نباشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-010)
- [ ] T019 [US3] در `infra/api/company_projects/team_stages.py` و مرز `infra/api/company_projects/team_stages_controller.py` این رفتار را پیاده/اثبات کن: «نهایی‌سازی، انتخاب artifact و آماده‌کردن مرحلهٔ بعد اتمی باشند؛ هیچ run بعدی خودکار ایجاد نشود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-011)
- [ ] T020 [US3] در `infra/api/company_projects/team_stages.py` و مرز `infra/api/company_projects/team_stages_controller.py` این رفتار را پیاده/اثبات کن: «صفحهٔ مرحله در فارسی/RTL ورودی، تاریخچه، نویسنده، وضعیت، loading/error/conflict و اقدام مجاز را قابل استفاده با صفحه‌کلید نشان دهد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-012)
- [ ] T021 [US3] در `infra/api/company_projects/test_team_stages.py` دو سناریوی AS-31/AS-32 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-009..012; SC-001..003)
- [ ] T022 [US3] در `infra/web/overlay/app/components/company-projects/team-stages.tsx` و `infra/web/team-stages.spec.mjs` مسیر «نهایی‌سازی صریح» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-009..012)

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 در `docs/kara-kp-05-validation.md` نتیجهٔ make check، PostgreSQL مرتبط، build/TypeScript/UI، Compose، startup، doctor و browser واقعی را با نسخه و شاهد/موارد اجرا نشده ثبت کن؛ regressions پروژه/اعضا/inbox/automation/templates حفظ شوند. (SC-001..004)
- [ ] T024 در `docs/kara-kp-05-validation.md` backup/restore، مسیر rollback دارای enforcement، تصمیم پذیرش و محدودیت را ثبت و `specs/005-stage-feedback/tasks.md` را فقط براساس شاهد به‌روز کن؛ commitهای مستقل و branch policy رعایت شوند. (SC-003)

## Dependencies and Execution Order

KP-02، KP-03 و KP-04 پس از پذیرش. T001 و T002 پیش از foundation؛ T003 پیش از T004 و storyها. storyها به ترتیب US1 → US2 → US3 برای یکپارچه‌سازی کامل؛ آزمون هر story به‌تنهایی با fixture معتبر ممکن است. فعال‌کردن قابلیت پیش از تکمیل تمام موارد امنیتی ممنوع است.

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

API عادی run در KP-02 جای تصمیم ورود و stages نیست. content طولانی باید artifact store کامل داشته باشد؛ inbox preview کافی نیست. callback بعد از لغو یا ورودی تازه صرفاً سابقهٔ فنی است.
