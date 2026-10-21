# Tasks: KP-04 — درخواست دستی و تصمیم ورود مالک محصول

**Input**: [spec](spec.md)، [plan](plan.md)، [research](research.md)، [data-model](data-model.md)، [contracts](contracts/interface.md).

**Status**: همهٔ کارهای زیر آینده و انجام‌نشده‌اند. وجود spec/checklist به معنی پیاده‌سازی نیست.

## Phase 1: Setup

- [ ] T001 پیش‌نیاز KP-01 و KP-03 پس از پذیرش، commit مبنا، ledger و imageها را در `docs/kara-kp-04-validation.md` ثبت و gate را احراز کن؛ قبل از تغییر، quickstart همین بسته را بخوان. (SC-001..004)
- [ ] T002 ماتریس دو پروژه/حساب و سناریوهای `infra/api/company_projects/test_team_requests.py` را از AS-11..AS-32 و edge cases آماده کن؛ داده و credential خصوصی بمانند. (SC-001, SC-002)

## Phase 2: Foundational

- [ ] T003 در `infra/api/company_projects/team_requests.py` و migration موردنیاز `infra/api/company_projects/team_migrations.py` مدل‌های data-model را با این قیود بساز/بازاستفاده کن: Request: ثبت بدون instance مجاز؛ source/external_id برای آداپتر آینده رزرو، بدون schema ساختگی Jira.؛ RequestRevision: revision مثبت و یکتا در request؛ متن اصلی immutable؛ attachment scope کنترل.؛ IntakeDecision: مرجع و تصمیم immutable؛ approved واقعی معتبر تنها مجوز ورود؛ تغییر رویداد ابطال مستقل.؛ Instance: حداکثر یک instance برای همان تصمیم؛ tuple دقیق request/flow/digests تطبیق تراکنشی؛ هنوز start خودکار ندارد. (FR-001..012; SC-003)
- [ ] T004 در `infra/api/company_projects/test_team_requests.py` ارتقا/عدم افت داده، scope، FK/CAS و rollback/replay مرتبط را روی PostgreSQL آزمون کن؛ شماره و checksum migration قبلی عوض نشود. (FR-001..012; SC-002, SC-003)

## Phase 3: User Story 1 — ثبت و اصلاح نیازمندی

**Goal**: عضو درخواست را با متن اصلی، فایل و منشأ دستی ثبت و اصلاح می‌کند.

**Independent Test**: متن اولیه و نسخهٔ دوم هر دو قابل بازیابی مجاز باشند.

- [ ] T005 [US1] در `infra/api/company_projects/team_requests.py` و مرز `infra/api/company_projects/team_requests_controller.py` این رفتار را پیاده/اثبات کن: «هر عضو فعال همان پروژه بتواند draft درخواست ثبت کند؛ ثبت به معنی ورود به تولید نباشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-001)
- [ ] T006 [US1] در `infra/api/company_projects/team_requests.py` و مرز `infra/api/company_projects/team_requests_controller.py` این رفتار را پیاده/اثبات کن: «عنوان، متن اصلی، منشأ، ایجادکننده و اصلاحات نسخه‌دار حفظ شوند؛ ویرایش قبلی را پاک نکند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-002)
- [ ] T007 [US1] در `infra/api/company_projects/team_requests.py` و مرز `infra/api/company_projects/team_requests_controller.py` این رفتار را پیاده/اثبات کن: «فایل با درخواست/نسخه و پروژه مرتبط و در upload، preview و download مجوزخوانی بررسی شود؛ لینک عمومی مجوز نباشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-003)
- [ ] T008 [US1] در `infra/api/company_projects/team_requests.py` و مرز `infra/api/company_projects/team_requests_controller.py` این رفتار را پیاده/اثبات کن: «کلیک یا دریافت تکراری با کلید یکسان درخواست یا revision مضاعف نسازد و تعارض نسخه آشکار باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-004)
- [ ] T009 [US1] در `infra/api/company_projects/test_team_requests.py` دو سناریوی AS-11/AS-12 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-001..004; SC-001..003)
- [ ] T010 [US1] در `infra/web/overlay/app/components/company-projects/team-requests.tsx` و `infra/web/team-requests.spec.mjs` مسیر «ثبت و اصلاح نیازمندی» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-001..004)

## Phase 4: User Story 2 — تصمیم واقعی PO

**Goal**: PO نسخهٔ فلو را انتخاب و ورود را تأیید، رد، معوق یا نیازمند اصلاح می‌کند.

**Independent Test**: همان عضو با po بتواند approved بدهد؛ root فاقد po نتواند.

- [ ] T011 [US2] در `infra/api/company_projects/team_requests.py` و مرز `infra/api/company_projects/team_requests_controller.py` این رفتار را پیاده/اثبات کن: «فقط PO فعال همان پروژه با نشست واقعی تصمیم ورود دهد؛ اختیار مدیریتی و متن مدل جای تصمیم نباشند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-005)
- [ ] T012 [US2] در `infra/api/company_projects/team_requests.py` و مرز `infra/api/company_projects/team_requests_controller.py` این رفتار را پیاده/اثبات کن: «outcome از approved/rejected/deferred/changes_requested و reason و زمان ثبت شود؛ فقط approved معتبر راه ورود را باز کند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-006)
- [ ] T013 [US2] در `infra/api/company_projects/team_requests.py` و مرز `infra/api/company_projects/team_requests_controller.py` این رفتار را پیاده/اثبات کن: «تصمیم به شناسه/نسخه/هش دقیق درخواست و FlowVersion همان پروژه متصل باشد؛ latest خودکار انتخاب نشود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-007)
- [ ] T014 [US2] در `infra/api/company_projects/team_requests.py` و مرز `infra/api/company_projects/team_requests_controller.py` این رفتار را پیاده/اثبات کن: «ایجاد تصمیم و حداکثر یک پروندهٔ مرتبط اتمی و تکرارپذیر باشد؛ تأیید مرحلهٔ اول را خودکار اجرا نکند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-008)
- [ ] T015 [US2] در `infra/api/company_projects/test_team_requests.py` دو سناریوی AS-21/AS-22 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-005..008; SC-001..003)
- [ ] T016 [US2] در `infra/web/overlay/app/components/company-projects/team-requests.tsx` و `infra/web/team-requests.spec.mjs` مسیر «تصمیم واقعی PO» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-005..008)

## Phase 5: User Story 3 — اصلاح پس از تصمیم

**Goal**: PO نسخهٔ اصلاح‌شده را دوباره بررسی و تصمیم قدیمی را جدا نگه می‌دارد.

**Independent Test**: پس از تغییر متن، تصمیم v1 برای v2 مجوز ایجاد نکند.

- [ ] T017 [US3] در `infra/api/company_projects/team_requests.py` و مرز `infra/api/company_projects/team_requests_controller.py` این رفتار را پیاده/اثبات کن: «تغییر درخواست یا FlowVersion، تصمیم قبلی را به نسخهٔ تازه منتقل نکند؛ ابطال رویداد صریح و تاریخچه immutable بماند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-009)
- [ ] T018 [US3] در `infra/api/company_projects/team_requests.py` و مرز `infra/api/company_projects/team_requests_controller.py` این رفتار را پیاده/اثبات کن: «حذف نقش PO، تاریخچهٔ تصمیم را حذف نکند ولی اقدام تازه نیازمند اختیار جاری باشد؛ expiry/revocation در مصرف کنترل شوند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-010)
- [ ] T019 [US3] در `infra/api/company_projects/team_requests.py` و مرز `infra/api/company_projects/team_requests_controller.py` این رفتار را پیاده/اثبات کن: «فهرست و جزئیات فقط اطلاعات مجاز پروژه و فایل‌های درخواست را برگردانند؛ دادهٔ اتصال محرمانه نمایش داده نشود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-011)
- [ ] T020 [US3] در `infra/api/company_projects/team_requests.py` و مرز `infra/api/company_projects/team_requests_controller.py` این رفتار را پیاده/اثبات کن: «رابط فارسی/RTL، نسخهٔ انتخابی، معنای تصمیم‌ها و حالت pending/error/conflict را نشان دهد؛ دکمهٔ تأیید انتخاب ازپیش‌تأییدشده نسازد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-012)
- [ ] T021 [US3] در `infra/api/company_projects/test_team_requests.py` دو سناریوی AS-31/AS-32 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-009..012; SC-001..003)
- [ ] T022 [US3] در `infra/web/overlay/app/components/company-projects/team-requests.tsx` و `infra/web/team-requests.spec.mjs` مسیر «اصلاح پس از تصمیم» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-009..012)

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 در `docs/kara-kp-04-validation.md` نتیجهٔ make check، PostgreSQL مرتبط، build/TypeScript/UI، Compose، startup، doctor و browser واقعی را با نسخه و شاهد/موارد اجرا نشده ثبت کن؛ regressions پروژه/اعضا/inbox/automation/templates حفظ شوند. (SC-001..004)
- [ ] T024 در `docs/kara-kp-04-validation.md` backup/restore، مسیر rollback دارای enforcement، تصمیم پذیرش و محدودیت را ثبت و `specs/004-requests-po-intake/tasks.md` را فقط براساس شاهد به‌روز کن؛ commitهای مستقل و branch policy رعایت شوند. (SC-003)

## Dependencies and Execution Order

KP-01 و KP-03 پس از پذیرش. T001 و T002 پیش از foundation؛ T003 پیش از T004 و storyها. storyها به ترتیب US1 → US2 → US3 برای یکپارچه‌سازی کامل؛ آزمون هر story به‌تنهایی با fixture معتبر ممکن است. فعال‌کردن قابلیت پیش از تکمیل تمام موارد امنیتی ممنوع است.

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

فلو draft/archived برای ورود جدید نامعتبر است؛ پروندهٔ pin‌شده تابع همان نسخه می‌ماند. اگر ابطال روی instance موجود اثر دارد، hook مسدودکردن مصرف را همین گام بسازید و در KP-07 گسترش دهید.
