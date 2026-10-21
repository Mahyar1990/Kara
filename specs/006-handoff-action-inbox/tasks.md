# Tasks: KP-06 — تحویل خروجی و کارتابل اقدام

**Input**: [spec](spec.md)، [plan](plan.md)، [research](research.md)، [data-model](data-model.md)، [contracts](contracts/interface.md).

**Status**: همهٔ کارهای زیر آینده و انجام‌نشده‌اند. وجود spec/checklist به معنی پیاده‌سازی نیست.

## Phase 1: Setup

- [ ] T001 پیش‌نیاز KP-05 پس از پذیرش، commit مبنا، ledger و imageها را در `docs/kara-kp-06-validation.md` ثبت و gate را احراز کن؛ قبل از تغییر، quickstart همین بسته را بخوان. (SC-001..004)
- [ ] T002 ماتریس دو پروژه/حساب و سناریوهای `infra/api/company_projects/test_team_handoff.py` را از AS-11..AS-32 و edge cases آماده کن؛ داده و credential خصوصی بمانند. (SC-001, SC-002)

## Phase 2: Foundational

- [ ] T003 در `infra/api/company_projects/team_handoff.py` و migration موردنیاز `infra/api/company_projects/team_migrations.py` مدل‌های data-model را با این قیود بساز/بازاستفاده کن: ArtifactDependency: ارجاع به نسخهٔ دقیق؛ no cross-scope؛ dependency immutable پس از مصرف.؛ HandoffView: نمای محاسبه‌شده؛ ذخیرهٔ مجوز دائمی یا تکثیر raw logs ممنوع.؛ ActionItem: نمای projection با authorization تازه؛ count/list یک سیاست.؛ RequestProgress: metadata مجاز بدون prompt و credentials؛ stale صریح. (FR-001..012; SC-003)
- [ ] T004 در `infra/api/company_projects/test_team_handoff.py` ارتقا/عدم افت داده، scope، FK/CAS و rollback/replay مرتبط را روی PostgreSQL آزمون کن؛ شماره و checksum migration قبلی عوض نشود. (FR-001..012; SC-002, SC-003)

## Phase 3: User Story 1 — اقدام‌های من

**Goal**: عضو با حساب خودش مرحله‌های آماده و تصمیم‌های منتظرش را می‌بیند.

**Independent Test**: دو حساب لیست متفاوت بگیرند و کارتابل فرم قدیمی هم باقی بماند.

- [ ] T005 [US1] در `infra/api/company_projects/team_handoff.py` و مرز `infra/api/company_projects/team_handoff_controller.py` این رفتار را پیاده/اثبات کن: «کارتابل تیمی با حساب جاری و scope پروژه، مرحلهٔ ready، تصمیم منتظر و علت blocked را نمایش دهد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-001)
- [ ] T006 [US1] در `infra/api/company_projects/team_handoff.py` و مرز `infra/api/company_projects/team_handoff_controller.py` این رفتار را پیاده/اثبات کن: «اقدام‌های مجاز از سیاست جاری محاسبه شوند؛ عضویت یا grant cached مجوز نباشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-002)
- [ ] T007 [US1] در `infra/api/company_projects/team_handoff.py` و مرز `infra/api/company_projects/team_handoff_controller.py` این رفتار را پیاده/اثبات کن: «کارتابل فرم‌ها و اجراهای بومی و قواعد دسترسی قبلی آن حفظ و از کارهای تیمی قابل تشخیص باشند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-003)
- [ ] T008 [US1] در `infra/api/company_projects/team_handoff.py` و مرز `infra/api/company_projects/team_handoff_controller.py` این رفتار را پیاده/اثبات کن: «لیست صفحه‌بندی و مرتب‌سازی پایدار، loading/empty/error، focus و صفحه‌کلید و نمایش فارسی/RTL داشته باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-004)
- [ ] T009 [US1] در `infra/api/company_projects/test_team_handoff.py` دو سناریوی AS-11/AS-12 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-001..004; SC-001..003)
- [ ] T010 [US1] در `infra/web/overlay/app/components/company-projects/team-inbox.tsx` و `infra/web/team-inbox.spec.mjs` مسیر «اقدام‌های من» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-001..004)

## Phase 4: User Story 2 — دریافت خروجی منتخب

**Goal**: نفر مرحلهٔ بعد خروجی معتبر قبلی را می‌خواند و خودش شروع می‌کند.

**Independent Test**: عضو دوم artifact منتخب را ببیند و raw log یا artifact دیگر را نتواند بخواند.

- [ ] T011 [US2] در `infra/api/company_projects/team_handoff.py` و مرز `infra/api/company_projects/team_handoff_controller.py` این رفتار را پیاده/اثبات کن: «مجوز خواندن artifact منتخب مستقل از حق مشاهدهٔ همهٔ اجرا، پیام‌ها، promptها و اطلاعات اتصال باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-005)
- [ ] T012 [US2] در `infra/api/company_projects/team_handoff.py` و مرز `infra/api/company_projects/team_handoff_controller.py` این رفتار را پیاده/اثبات کن: «تحویل به consumer مرحله و artifact producer دقیق با نسخه/هش متصل و در همان پروژه محدود باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-006)
- [ ] T013 [US2] در `infra/api/company_projects/team_handoff.py` و مرز `infra/api/company_projects/team_handoff_controller.py` این رفتار را پیاده/اثبات کن: «فایل و لینک دانلود تحویلی نیز مجوز جاری consumer را کنترل کنند؛ URL قابل حدس یا دائمی مجوز نباشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-007)
- [ ] T014 [US2] در `infra/api/company_projects/team_handoff.py` و مرز `infra/api/company_projects/team_handoff_controller.py` این رفتار را پیاده/اثبات کن: «ready شدن یا notification شروع خودکار نسازد؛ فقط فرد دارای run مرحلهٔ بعد آن را آغاز کند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-008)
- [ ] T015 [US2] در `infra/api/company_projects/test_team_handoff.py` دو سناریوی AS-21/AS-22 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-005..008; SC-001..003)
- [ ] T016 [US2] در `infra/web/overlay/app/components/company-projects/team-inbox.tsx` و `infra/web/team-inbox.spec.mjs` مسیر «دریافت خروجی منتخب» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-005..008)

## Phase 5: User Story 3 — پیگیری کل درخواست

**Goal**: عضو مجاز وضعیت کل فلو و مسئول فعلی و مانع کار خودش را دنبال می‌کند.

**Independent Test**: پروندهٔ دومرحله‌ای وضعیت و مسئول درست با جزئیات محدود نشان دهد.

- [ ] T017 [US3] در `infra/api/company_projects/team_handoff.py` و مرز `infra/api/company_projects/team_handoff_controller.py` این رفتار را پیاده/اثبات کن: «نمای درخواست وضعیت مرحله‌ها، مسئول فعلی، نسخهٔ فلو و علت انتظار/برگشت را با جزئیات مجاز نشان دهد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-009)
- [ ] T018 [US3] در `infra/api/company_projects/team_handoff.py` و مرز `infra/api/company_projects/team_handoff_controller.py` این رفتار را پیاده/اثبات کن: «اطلاعات فهرست و شمارنده و جستجو نیز جداسازی پروژه و محرمانگی محتوا را حفظ کنند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-010)
- [ ] T019 [US3] در `infra/api/company_projects/team_handoff.py` و مرز `infra/api/company_projects/team_handoff_controller.py` این رفتار را پیاده/اثبات کن: «ثبت نهایی‌سازی و dependency و ready شدن بعدی سازگار باشد؛ refresh تکراری تحویل مضاعف نسازد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-011)
- [ ] T020 [US3] در `infra/api/company_projects/team_handoff.py` و مرز `infra/api/company_projects/team_handoff_controller.py` این رفتار را پیاده/اثبات کن: «stale یا revoked شدن ورودی و تغییر مسئول، دسترسی تازه و actionable بودن را فوراً براساس دادهٔ معتبر اصلاح کند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-012)
- [ ] T021 [US3] در `infra/api/company_projects/test_team_handoff.py` دو سناریوی AS-31/AS-32 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-009..012; SC-001..003)
- [ ] T022 [US3] در `infra/web/overlay/app/components/company-projects/team-inbox.tsx` و `infra/web/team-inbox.spec.mjs` مسیر «پیگیری کل درخواست» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-009..012)

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 در `docs/kara-kp-06-validation.md` نتیجهٔ make check، PostgreSQL مرتبط، build/TypeScript/UI، Compose، startup، doctor و browser واقعی را با نسخه و شاهد/موارد اجرا نشده ثبت کن؛ regressions پروژه/اعضا/inbox/automation/templates حفظ شوند. (SC-001..004)
- [ ] T024 در `docs/kara-kp-06-validation.md` backup/restore، مسیر rollback دارای enforcement، تصمیم پذیرش و محدودیت را ثبت و `specs/006-handoff-action-inbox/tasks.md` را فقط براساس شاهد به‌روز کن؛ commitهای مستقل و branch policy رعایت شوند. (SC-003)

## Dependencies and Execution Order

KP-05 پس از پذیرش. T001 و T002 پیش از foundation؛ T003 پیش از T004 و storyها. storyها به ترتیب US1 → US2 → US3 برای یکپارچه‌سازی کامل؛ آزمون هر story به‌تنهایی با fixture معتبر ممکن است. فعال‌کردن قابلیت پیش از تکمیل تمام موارد امنیتی ممنوع است.

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

normal یا finalizer ممکن است editor نباشند؛ resolver بومی payload را برای این همکاری باز نکنید. مجوز دانلود فایل و شمارنده‌ها هم باید scoped باشند.
