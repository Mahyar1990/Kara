# Tasks: KP-09 — ورودی سرویس واسط Jira

**Input**: [spec](spec.md)، [plan](plan.md)، [research](research.md)، [data-model](data-model.md)، [contracts](contracts/interface.md).

**Status**: همهٔ کارهای زیر آینده و انجام‌نشده‌اند. وجود spec/checklist به معنی پیاده‌سازی نیست.

## Phase 1: Setup

- [ ] T001 پیش‌نیاز KP-04 پذیرفته‌شده و نمونهٔ واقعی پاک‌سازی‌شدهٔ سرویس واسط؛ نمونه اکنون موجود نیست، commit مبنا، ledger و imageها را در `docs/kara-kp-09-validation.md` ثبت و gate را احراز کن؛ قبل از تغییر، quickstart همین بسته را بخوان. (SC-001..004)
- [ ] T002 ماتریس دو پروژه/حساب و سناریوهای `infra/api/company_projects/test_team_jira.py` را از AS-11..AS-32 و edge cases آماده کن؛ داده و credential خصوصی بمانند. (SC-001, SC-002)

## Phase 2: Foundational

- [ ] T003 در `infra/api/company_projects/team_jira.py` و migration موردنیاز `infra/api/company_projects/team_migrations.py` مدل‌های data-model را با این قیود بساز/بازاستفاده کن: ConnectorBinding: secret فقط private store؛ connector متعلق به scope؛ auth/allowed_sources از قرارداد واقعی تثبیت می‌شوند.؛ ImportEnvelope: port داخلی، schema بیرونی نیست؛ فیلدهای واقعی نامعلوم تا sample؛ raw payload خصوصی.؛ ImportReceipt: یکتا برای محتوای تکراری در scope/connector/source؛ تراکنش با ایجاد requestrevision.؛ MappingRecord: فقط پس از sample تکمیل؛ بدون نام فیلد Jira ساختگی؛ missing و ordering policy صریح. (FR-001..012; SC-003)
- [ ] T004 در `infra/api/company_projects/test_team_jira.py` ارتقا/عدم افت داده، scope، FK/CAS و rollback/replay مرتبط را روی PostgreSQL آزمون کن؛ شماره و checksum migration قبلی عوض نشود. (FR-001..012; SC-002, SC-003)

## Phase 3: User Story 1 — تثبیت قرارداد واقعی سرویس

**Goal**: توسعه‌دهنده نمونهٔ واقعی را پاک‌سازی و نگاشت و خطاهای آن را با تیم ثبت می‌کند.

**Independent Test**: نمونهٔ تأییدشده بدون secret به shape fixture تبدیل و هر فیلد ورودی قابل ردیابی باشد.

- [ ] T005 [US1] در `specs/009-jira-intake-adapter/contracts/interface.md` و `fixtures/kara-jira-service/` پس از دریافت نمونهٔ واقعی این قرارداد/شاهد را ثبت کن: «قبل از نگاشت، نمونهٔ واقعی موفق و خطا، semantics شناسه/نسخه/زمان/صفحه‌بندی و روش auth سرویس واسط دریافت و تأیید شوند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-001)
- [ ] T006 [US1] در `specs/009-jira-intake-adapter/contracts/interface.md` و `fixtures/kara-jira-service/` پس از دریافت نمونهٔ واقعی این قرارداد/شاهد را ثبت کن: «نمونهٔ واقعی و credentials خصوصی بمانند؛ fixture مشترک sanitized و هم‌شکل منبع واقعی و فاقد PII باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-002)
- [ ] T007 [US1] در `specs/009-jira-intake-adapter/contracts/interface.md` و `fixtures/kara-jira-service/` پس از دریافت نمونهٔ واقعی این قرارداد/شاهد را ثبت کن: «قرارداد از سرویس واسط استخراج شود؛ فیلد بومی Jira یا لینک جهت‌دار فرضی جای حقیقت سرویس ننشیند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-003)
- [ ] T008 [US1] در `specs/009-jira-intake-adapter/contracts/interface.md` و `fixtures/kara-jira-service/` پس از دریافت نمونهٔ واقعی این قرارداد/شاهد را ثبت کن: «نبود sample یا دسترسی معتبر وضعیت blocked بسازد؛ بخش داخلی و مسیر دستی مستقل باقی بمانند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-004)
- [ ] T009 [US1] در `infra/api/company_projects/test_team_jira.py` دو سناریوی AS-11/AS-12 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-001..004; SC-001..003)
- [ ] T010 [US1] در `infra/web/overlay/app/components/company-projects/team-jira.tsx` و `infra/web/team-jira.spec.mjs` مسیر «تثبیت قرارداد واقعی سرویس» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-001..004)

## Phase 4: User Story 2 — دریافت درخواست نسخه‌دار

**Goal**: فرد مجاز نیازمندی Jira را در پروژهٔ خودش import می‌کند و متن اصلی را می‌بیند.

**Independent Test**: ورودی معتبر یک request با provenance بسازد؛ اصلاح منبع یک revision جدید بسازد.

- [ ] T011 [US2] در `infra/api/company_projects/team_jira.py` و مرز `infra/api/company_projects/team_jira_controller.py` این رفتار را پیاده/اثبات کن: «پاسخ اعتبارسنجی‌شده به قرارداد داخلی KP-04 تبدیل و متن اصلی و provenance حفظ شوند؛ فقدان داده صریح باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-005)
- [ ] T012 [US2] در `infra/api/company_projects/team_jira.py` و مرز `infra/api/company_projects/team_jira_controller.py` این رفتار را پیاده/اثبات کن: «اختیار import و credential به همان پروژه محدود باشد؛ account/service actor واقعی دریافت ثبت شود و secret در پاسخ یا log نباشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-006)
- [ ] T013 [US2] در `infra/api/company_projects/team_jira.py` و مرز `infra/api/company_projects/team_jira_controller.py` این رفتار را پیاده/اثبات کن: «کلید dedupe ترکیب scope، connector و external identity باشد؛ محتوای یکسان no-op و تغییر واقعی revision تازه بسازد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-007)
- [ ] T014 [US2] در `infra/api/company_projects/team_jira.py` و مرز `infra/api/company_projects/team_jira_controller.py` این رفتار را پیاده/اثبات کن: «خطای شبکه، auth، format و rate-limit از هم قابل تشخیص و retry محدود فقط برای خواندن ایمن باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-008)
- [ ] T015 [US2] در `infra/api/company_projects/test_team_jira.py` دو سناریوی AS-21/AS-22 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-005..008; SC-001..003)
- [ ] T016 [US2] در `infra/web/overlay/app/components/company-projects/team-jira.tsx` و `infra/web/team-jira.spec.mjs` مسیر «دریافت درخواست نسخه‌دار» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-005..008)

## Phase 5: User Story 3 — ورود با تصمیم PO و دریافت مجدد

**Goal**: PO پس از import نسخهٔ فلو را انتخاب می‌کند و دریافت بعدی به تصمیم قبلی دست نمی‌زند.

**Independent Test**: دوباره‌خوانی همان issue instance تکراری نسازد و نسخهٔ تازه نیازمند تصمیم مناسب باشد.

- [ ] T017 [US3] در `infra/api/company_projects/team_jira.py` و مرز `infra/api/company_projects/team_jira_controller.py` این رفتار را پیاده/اثبات کن: «import به‌خودی‌خود flow انتخاب، PO approval ثبت یا مرحله اجرا نکند؛ مسیر تصمیم KP-04 حفظ شود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-009)
- [ ] T018 [US3] در `infra/api/company_projects/team_jira.py` و مرز `infra/api/company_projects/team_jira_controller.py` این رفتار را پیاده/اثبات کن: «یک پاسخ قدیمی یا خارج‌ترتیب متن جدید را بازنویسی نکند؛ اگر نسخهٔ منبع قابل مقایسه نیست، conflict نیازمند بررسی ثبت شود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-010)
- [ ] T019 [US3] در `infra/api/company_projects/team_jira.py` و مرز `infra/api/company_projects/team_jira_controller.py` این رفتار را پیاده/اثبات کن: «خطای import به درخواست‌های دستی و سابقهٔ قبلی آسیب نزند؛ حذف issue منبع تاریخچهٔ داخلی را حذف نکند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-011)
- [ ] T020 [US3] در `infra/api/company_projects/team_jira.py` و مرز `infra/api/company_projects/team_jira_controller.py` این رفتار را پیاده/اثبات کن: «رابط فارسی/RTL منشأ، آخرین دریافت، no-op/conflict/error و شرط PO را نشان دهد؛ پذیرش live تا نمونه و اتصال واقعی قابل اجرا اعلام نشود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-012)
- [ ] T021 [US3] در `infra/api/company_projects/test_team_jira.py` دو سناریوی AS-31/AS-32 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-009..012; SC-001..003)
- [ ] T022 [US3] در `infra/web/overlay/app/components/company-projects/team-jira.tsx` و `infra/web/team-jira.spec.mjs` مسیر «ورود با تصمیم PO و دریافت مجدد» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-009..012)

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 در `docs/kara-kp-09-validation.md` نتیجهٔ make check، PostgreSQL مرتبط، build/TypeScript/UI، Compose، startup، doctor و browser واقعی را با نسخه و شاهد/موارد اجرا نشده ثبت کن؛ regressions پروژه/اعضا/inbox/automation/templates حفظ شوند. (SC-001..004)
- [ ] T024 در `docs/kara-kp-09-validation.md` backup/restore، مسیر rollback دارای enforcement، تصمیم پذیرش و محدودیت را ثبت و `specs/009-jira-intake-adapter/tasks.md` را فقط براساس شاهد به‌روز کن؛ commitهای مستقل و branch policy رعایت شوند. (SC-003)

## Dependencies and Execution Order

KP-04 پذیرفته‌شده و نمونهٔ واقعی پاک‌سازی‌شدهٔ سرویس واسط؛ نمونه اکنون موجود نیست. T001 و T002 پیش از foundation؛ T003 پیش از T004 و storyها. storyها به ترتیب US1 → US2 → US3 برای یکپارچه‌سازی کامل؛ آزمون هر story به‌تنهایی با fixture معتبر ممکن است. فعال‌کردن قابلیت پیش از تکمیل تمام موارد امنیتی ممنوع است.

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

BLOCKED-INPUT: نمونهٔ موفق/خطا، نسخه‌بندی و ترتیب، صفحه‌بندی، auth، attachment و rate-limit سرویس موجود نیست. plan نگاشت فیلد و پذیرش زنده عمداً نهایی نیست؛ این مانع تکمیل port داخلی/مشخصات رفتار یا مسیر دستی نیست. عرضهٔ متعهد به Jira بدون رفع این gate ممنوع.
