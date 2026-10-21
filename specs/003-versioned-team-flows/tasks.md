# Tasks: KP-03 — فلوهای تیمی نسخه‌دار

**Input**: [spec](spec.md)، [plan](plan.md)، [research](research.md)، [data-model](data-model.md)، [contracts](contracts/interface.md).

**Status**: همهٔ کارهای زیر آینده و انجام‌نشده‌اند. وجود spec/checklist به معنی پیاده‌سازی نیست.

## Phase 1: Setup

- [ ] T001 پیش‌نیاز KP-02 پس از پذیرش، commit مبنا، ledger و imageها را در `docs/kara-kp-03-validation.md` ثبت و gate را احراز کن؛ قبل از تغییر، quickstart همین بسته را بخوان. (SC-001..004)
- [ ] T002 ماتریس دو پروژه/حساب و سناریوهای `infra/api/company_projects/test_team_flows.py` را از AS-11..AS-32 و edge cases آماده کن؛ داده و credential خصوصی بمانند. (SC-001, SC-002)

## Phase 2: Foundational

- [ ] T003 در `infra/api/company_projects/team_flows.py` و migration موردنیاز `infra/api/company_projects/team_migrations.py` مدل‌های data-model را با این قیود بساز/بازاستفاده کن: TeamFlow: نام در scope یکتا؛ draft revision مثبت؛ archive حذف cascade تاریخچه ندارد.؛ FlowVersion: یکتا روی scope/flow/revision؛ published immutable؛ publish اتمی.؛ StageBinding: step_key در نسخه یکتا؛ DAG ساده، حداقل یک مرحله؛ تمام refs و finalizer در scope و مجوز جاری.؛ FlowReference: مصرف نسخه جلوی حذف را بگیرد؛ انتشار جدید refs قدیم را بازنویسی نکند. (FR-001..012; SC-003)
- [ ] T004 در `infra/api/company_projects/test_team_flows.py` ارتقا/عدم افت داده، scope، FK/CAS و rollback/replay مرتبط را روی PostgreSQL آزمون کن؛ شماره و checksum migration قبلی عوض نشود. (FR-001..012; SC-002, SC-003)

## Phase 3: User Story 1 — تعریف چند فلو

**Goal**: عضو دارای مجوز بومی ویرایش دو فلو با ترتیب و ایجنت متفاوت می‌سازد.

**Independent Test**: دو draft مستقل ذخیره و بازخوانی شوند؛ عضو عادی نتواند آن‌ها را تغییر دهد.

- [ ] T005 [US1] در `infra/api/company_projects/team_flows.py` و مرز `infra/api/company_projects/team_flows_controller.py` این رفتار را پیاده/اثبات کن: «ساخت و ویرایش فلو فقط با مجوز بومی معتبر همان پروژه انجام شود؛ run ایجنت حق طراحی فلو ندهد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-001)
- [ ] T006 [US1] در `infra/api/company_projects/team_flows.py` و مرز `infra/api/company_projects/team_flows_controller.py` این رفتار را پیاده/اثبات کن: «هر پروژه چند فلو با نام یکتا و مراحل دارای کلید پایدار داشته باشد؛ وابستگی‌های ساده و ورودی هر مرحله مشخص باشند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-002)
- [ ] T007 [US1] در `infra/api/company_projects/team_flows.py` و مرز `infra/api/company_projects/team_flows_controller.py` این رفتار را پیاده/اثبات کن: «هر مرحله به نسخهٔ دقیق ایجنت و نسخهٔ منتشرشدهٔ اجرای آن، قرارداد و نهایی‌کنندهٔ فعال متصل باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-003)
- [ ] T008 [US1] در `infra/api/company_projects/team_flows.py` و مرز `infra/api/company_projects/team_flows_controller.py` این رفتار را پیاده/اثبات کن: «هر تغییر draft با نسخهٔ مورد انتظار کنترل و سابقهٔ عامل نگه داشته شود؛ ذخیرهٔ هم‌زمان تغییر دیگری را بازنویسی نکند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-004)
- [ ] T009 [US1] در `infra/api/company_projects/test_team_flows.py` دو سناریوی AS-11/AS-12 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-001..004; SC-001..003)
- [ ] T010 [US1] در `infra/web/overlay/app/components/company-projects/team-flows.tsx` و `infra/web/team-flows.spec.mjs` مسیر «تعریف چند فلو» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-001..004)

## Phase 4: User Story 2 — انتشار معتبر

**Goal**: عضو مجاز نسخهٔ کامل فلو را منتشر می‌کند و خطای مرحلهٔ ناقص را می‌بیند.

**Independent Test**: فلو معتبر منتشر شود؛ cycle و مرحلهٔ بدون finalizer منتشر نشوند.

- [ ] T011 [US2] در `infra/api/company_projects/team_flows.py` و مرز `infra/api/company_projects/team_flows_controller.py` این رفتار را پیاده/اثبات کن: «انتشار نیازمند مجوز بومی انتشار و بررسی تازهٔ همهٔ bindingها و مجوزهای لازم باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-005)
- [ ] T012 [US2] در `infra/api/company_projects/team_flows.py` و مرز `infra/api/company_projects/team_flows_controller.py` این رفتار را پیاده/اثبات کن: «مرحلهٔ تکراری، چرخه، وابستگی گم‌شده، نسخهٔ draft و نهایی‌کنندهٔ نامعتبر مانع انتشار شوند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-006)
- [ ] T013 [US2] در `infra/api/company_projects/team_flows.py` و مرز `infra/api/company_projects/team_flows_controller.py` این رفتار را پیاده/اثبات کن: «نسخهٔ منتشرشده شامل همهٔ bindingها و هش محتوا تغییرناپذیر باشد؛ ویرایش نسخهٔ تازه بسازد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-007)
- [ ] T014 [US2] در `infra/api/company_projects/team_flows.py` و مرز `infra/api/company_projects/team_flows_controller.py` این رفتار را پیاده/اثبات کن: «خطای اعتبارسنجی به مرحله و فیلد مشخص وصل باشد؛ ذخیرهٔ draft ناقص با اخطار مجاز ولی publication ناقص ممنوع باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-008)
- [ ] T015 [US2] در `infra/api/company_projects/test_team_flows.py` دو سناریوی AS-21/AS-22 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-005..008; SC-001..003)
- [ ] T016 [US2] در `infra/web/overlay/app/components/company-projects/team-flows.tsx` و `infra/web/team-flows.spec.mjs` مسیر «انتشار معتبر» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-005..008)

## Phase 5: User Story 3 — آرشیو و حفظ اجراهای قبلی

**Goal**: تیم نسخهٔ دوم را منتشر و نسخهٔ قبلی را برای پروندهٔ فعال حفظ می‌کند.

**Independent Test**: پروندهٔ نمونه روی v1 بماند؛ ورودی تازه بتواند v2 را انتخاب کند.

- [ ] T017 [US3] در `infra/api/company_projects/team_flows.py` و مرز `infra/api/company_projects/team_flows_controller.py` این رفتار را پیاده/اثبات کن: «نسخهٔ تازه هیچ instance یا تصمیم قبلی را خودکار تغییر ندهد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-009)
- [ ] T018 [US3] در `infra/api/company_projects/team_flows.py` و مرز `infra/api/company_projects/team_flows_controller.py` این رفتار را پیاده/اثبات کن: «آرشیو انتخاب جدید را ببندد ولی خواندن مجاز تاریخچه و ادامهٔ نسخهٔ pin‌شده را حذف نکند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-010)
- [ ] T019 [US3] در `infra/api/company_projects/team_flows.py` و مرز `infra/api/company_projects/team_flows_controller.py` این رفتار را پیاده/اثبات کن: «حذف یا تغییر app/workflow/agent مصرف‌شده با guard و قفل جلوگیری شود؛ references از scope خارج نشوند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-011)
- [ ] T020 [US3] در `infra/api/company_projects/team_flows.py` و مرز `infra/api/company_projects/team_flows_controller.py` این رفتار را پیاده/اثبات کن: «رابط فارسی/RTL مراحل، مسئول‌ها، نسخه و خطاهای empty/loading/conflict را قابل استفاده با صفحه‌کلید نشان دهد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-012)
- [ ] T021 [US3] در `infra/api/company_projects/test_team_flows.py` دو سناریوی AS-31/AS-32 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-009..012; SC-001..003)
- [ ] T022 [US3] در `infra/web/overlay/app/components/company-projects/team-flows.tsx` و `infra/web/team-flows.spec.mjs` مسیر «آرشیو و حفظ اجراهای قبلی» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-009..012)

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 در `docs/kara-kp-03-validation.md` نتیجهٔ make check، PostgreSQL مرتبط، build/TypeScript/UI، Compose، startup، doctor و browser واقعی را با نسخه و شاهد/موارد اجرا نشده ثبت کن؛ regressions پروژه/اعضا/inbox/automation/templates حفظ شوند. (SC-001..004)
- [ ] T024 در `docs/kara-kp-03-validation.md` backup/restore، مسیر rollback دارای enforcement، تصمیم پذیرش و محدودیت را ثبت و `specs/003-versioned-team-flows/tasks.md` را فقط براساس شاهد به‌روز کن؛ commitهای مستقل و branch policy رعایت شوند. (SC-003)

## Dependencies and Execution Order

KP-02 پس از پذیرش. T001 و T002 پیش از foundation؛ T003 پیش از T004 و storyها. storyها به ترتیب US1 → US2 → US3 برای یکپارچه‌سازی کامل؛ آزمون هر story به‌تنهایی با fixture معتبر ممکن است. فعال‌کردن قابلیت پیش از تکمیل تمام موارد امنیتی ممنوع است.

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

طرح JSON به‌تنهایی صحت scope یا immutability نیست؛ DB keyها و سرویس publication باید با هم آزموده شوند. نسخهٔ دقیق agent پس از قرارداد نهایی KP-02 تثبیت شود.
