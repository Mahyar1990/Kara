# Tasks: KP-10 — خودکارسازی محدود و گزارش درخواست‌ها

**Input**: [spec](spec.md)، [plan](plan.md)، [research](research.md)، [data-model](data-model.md)، [contracts](contracts/interface.md).

**Status**: همهٔ کارهای زیر آینده و انجام‌نشده‌اند. وجود spec/checklist به معنی پیاده‌سازی نیست.

## Phase 1: Setup

- [ ] T001 پیش‌نیاز KP-08 پذیرفته‌شده و قرارداد پذیرفته‌شدهٔ اتصال مرتبط؛ برای Jira همچنین KP-09، commit مبنا، ledger و imageها را در `docs/kara-kp-10-validation.md` ثبت و gate را احراز کن؛ قبل از تغییر، quickstart همین بسته را بخوان. (SC-001..004)
- [ ] T002 ماتریس دو پروژه/حساب و سناریوهای `infra/api/company_projects/test_team_automation.py` را از AS-11..AS-32 و edge cases آماده کن؛ داده و credential خصوصی بمانند. (SC-001, SC-002)

## Phase 2: Foundational

- [ ] T003 در `infra/api/company_projects/team_automation.py` و migration موردنیاز `infra/api/company_projects/team_migrations.py` مدل‌های data-model را با این قیود بساز/بازاستفاده کن: ServicePrincipal: هویت سرویس مستقل؛ هیچ نقش PO انسانی یا finalize human grant؛ دسترسی قابل لغو.؛ AutomationVersion: draft disabled؛ انتشار immutable و active pointer CAS؛ اتصال به نسخهٔ پذیرفته‌شده.؛ Delivery/EffectReceipt: یکتا در scope/source/event/operation؛ retry step-only؛ unknown external effect نیازمند reconcile.؛ RequestReport: derived projection؛ count/export مجاز؛ UTC در storage و نمایش تهران. (FR-001..012; SC-003)
- [ ] T004 در `infra/api/company_projects/test_team_automation.py` ارتقا/عدم افت داده، scope، FK/CAS و rollback/replay مرتبط را روی PostgreSQL آزمون کن؛ شماره و checksum migration قبلی عوض نشود. (FR-001..012; SC-002, SC-003)

## Phase 3: User Story 1 — تعریف اتوماسیون محدود

**Goal**: مدیر منبع، هویت سرویس، نسخه و برنامهٔ مجاز را تعیین می‌کند و فعال‌سازی صریح انجام می‌دهد.

**Independent Test**: یک تعریف draft بدون اثر باشد و پس از enable فقط عملیات مجاز منبع را انجام دهد.

- [ ] T005 [US1] در `infra/api/company_projects/team_automation.py` و مرز `infra/api/company_projects/team_automation_controller.py` این رفتار را پیاده/اثبات کن: «فقط root/manager بتواند اتوماسیون scoped را ایجاد، فعال، ویرایش و متوقف کند؛ ساخت اولیه disabled باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-001)
- [ ] T006 [US1] در `infra/api/company_projects/team_automation.py` و مرز `infra/api/company_projects/team_automation_controller.py` این رفتار را پیاده/اثبات کن: «هویت سرویس مستقل از نشست مالک پروژه و دارای عملیات و منابع صریح و حداقلی باشد؛ حساب انسانی جعل نشود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-002)
- [ ] T007 [US1] در `infra/api/company_projects/team_automation.py` و مرز `infra/api/company_projects/team_automation_controller.py` این رفتار را پیاده/اثبات کن: «نسخهٔ تعریف، اتصال، عملیات، trigger و محدوده در هر اجرا ثبت و تغییر تعریف بی‌صدا اجرای جاری را عوض نکند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-003)
- [ ] T008 [US1] در `infra/api/company_projects/team_automation.py` و مرز `infra/api/company_projects/team_automation_controller.py` این رفتار را پیاده/اثبات کن: «service principal هرگز تصمیم واقعی PO، finalization انسانی یا merge TL ایجاد نکند؛ مرز اتوماسیون برای کاربر واضح باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-004)
- [ ] T009 [US1] در `infra/api/company_projects/test_team_automation.py` دو سناریوی AS-11/AS-12 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-001..004; SC-001..003)
- [ ] T010 [US1] در `infra/web/overlay/app/components/company-projects/team-reporting.tsx` و `infra/web/team-reporting.spec.mjs` مسیر «تعریف اتوماسیون محدود» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-001..004)

## Phase 4: User Story 2 — دریافت قابل توقف و تکرارپذیر

**Goal**: اتوماسیون دریافت مجاز را با کنترل تکرار و retry محدود انجام می‌دهد و توقف اثر بعدی را می‌بندد.

**Independent Test**: رویداد تکراری یک اثر داشته باشد و پس از disable dispatch تازه نشود.

- [ ] T011 [US2] در `infra/api/company_projects/team_automation.py` و مرز `infra/api/company_projects/team_automation_controller.py` این رفتار را پیاده/اثبات کن: «هر dispatch/resume/result مجوز service، scope، enabled بودن و نسخهٔ مجاز را تازه بررسی کند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-005)
- [ ] T012 [US2] در `infra/api/company_projects/team_automation.py` و مرز `infra/api/company_projects/team_automation_controller.py` این رفتار را پیاده/اثبات کن: «دریافت دوره‌ای و رویدادی از همان adapter و dedupe استفاده کند؛ event identity و action key پایدار باشند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-006)
- [ ] T013 [US2] در `infra/api/company_projects/team_automation.py` و مرز `infra/api/company_projects/team_automation_controller.py` این رفتار را پیاده/اثبات کن: «retry روی همان گام با سقف و backoff محدود باشد؛ اثر بیرونی نامعلوم بدون idempotency یا reconciliation کورکورانه تکرار نشود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-007)
- [ ] T014 [US2] در `infra/api/company_projects/team_automation.py` و مرز `infra/api/company_projects/team_automation_controller.py` این رفتار را پیاده/اثبات کن: «توقف schedule، جلوگیری از dispatch و stop-requested کار جاری تفکیک شوند؛ نتیجهٔ دیررس مجوز تصمیم انسانی نسازد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-008)
- [ ] T015 [US2] در `infra/api/company_projects/test_team_automation.py` دو سناریوی AS-21/AS-22 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-005..008; SC-001..003)
- [ ] T016 [US2] در `infra/web/overlay/app/components/company-projects/team-reporting.tsx` و `infra/web/team-reporting.spec.mjs` مسیر «دریافت قابل توقف و تکرارپذیر» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-005..008)

## Phase 5: User Story 3 — گزارش قابل ردیابی

**Goal**: عضو مجاز گزارش وضعیت و مسئول و منشأ درخواست‌ها و شکست دریافت را می‌بیند.

**Independent Test**: گزارش با پرونده و شمارندهٔ scoped تطبیق و دادهٔ پروژهٔ دیگر پنهان بماند.

- [ ] T017 [US3] در `infra/api/company_projects/team_automation.py` و مرز `infra/api/company_projects/team_automation_controller.py` این رفتار را پیاده/اثبات کن: «گزارش وضعیت، مسئول، زمان انتظار، منشأ و شکست/توقف را به نسخهٔ پرونده و رخداد واقعی متصل کند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-009)
- [ ] T018 [US3] در `infra/api/company_projects/team_automation.py` و مرز `infra/api/company_projects/team_automation_controller.py` این رفتار را پیاده/اثبات کن: «فیلتر، export، شمارنده و جستجو همان scope و محرمانگی محتوای پرونده را رعایت کنند؛ secret و raw prompt وارد گزارش نشوند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-010)
- [ ] T019 [US3] در `infra/api/company_projects/team_automation.py` و مرز `infra/api/company_projects/team_automation_controller.py` این رفتار را پیاده/اثبات کن: «زمان‌ها با معنای یکسان ذخیره و به وقت تهران نمایش داده شوند؛ گزارش در زمان مشخص snapshot/cursor پایدار داشته باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-011)
- [ ] T020 [US3] در `infra/api/company_projects/team_automation.py` و مرز `infra/api/company_projects/team_automation_controller.py` این رفتار را پیاده/اثبات کن: «رابط فارسی/RTL و empty/loading/error/conflict و صفحه‌کلید و regression اتوماسیون بومی حفظ شوند؛ فعال‌سازی واقعی فقط در محدودهٔ مجاز کاربر باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-012)
- [ ] T021 [US3] در `infra/api/company_projects/test_team_automation.py` دو سناریوی AS-31/AS-32 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-009..012; SC-001..003)
- [ ] T022 [US3] در `infra/web/overlay/app/components/company-projects/team-reporting.tsx` و `infra/web/team-reporting.spec.mjs` مسیر «گزارش قابل ردیابی» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-009..012)

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 در `docs/kara-kp-10-validation.md` نتیجهٔ make check، PostgreSQL مرتبط، build/TypeScript/UI، Compose، startup، doctor و browser واقعی را با نسخه و شاهد/موارد اجرا نشده ثبت کن؛ regressions پروژه/اعضا/inbox/automation/templates حفظ شوند. (SC-001..004)
- [ ] T024 در `docs/kara-kp-10-validation.md` backup/restore، مسیر rollback دارای enforcement، تصمیم پذیرش و محدودیت را ثبت و `specs/010-bounded-automation-reporting/tasks.md` را فقط براساس شاهد به‌روز کن؛ commitهای مستقل و branch policy رعایت شوند. (SC-003)

## Dependencies and Execution Order

KP-08 پذیرفته‌شده و قرارداد پذیرفته‌شدهٔ اتصال مرتبط؛ برای Jira همچنین KP-09. T001 و T002 پیش از foundation؛ T003 پیش از T004 و storyها. storyها به ترتیب US1 → US2 → US3 برای یکپارچه‌سازی کامل؛ آزمون هر story به‌تنهایی با fixture معتبر ممکن است. فعال‌کردن قابلیت پیش از تکمیل تمام موارد امنیتی ممنوع است.

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

طراحی event بیرونی باید با اتصال انتخاب‌شده نهایی شود؛ در این مرحله سرویس خارجی واقعی فعال نکنید. اگر عملیاتی idempotency خارجی ندارد unknown اثر باید نیازمند بررسی بماند.
