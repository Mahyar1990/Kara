# Tasks: KP-02 — تعریف ایجنت قابل اجرا و مجوزهای صریح

**Input**: [spec](spec.md)، [plan](plan.md)، [research](research.md)، [data-model](data-model.md)، [contracts](contracts/interface.md).

**Status**: همهٔ کارهای زیر آینده و انجام‌نشده‌اند. وجود spec/checklist به معنی پیاده‌سازی نیست.

## Phase 1: Setup

- [ ] T001 پیش‌نیاز KP-01 پذیرفته‌شده، commit مبنا، ledger و imageها را در `docs/kara-kp-02-validation.md` ثبت و gate را احراز کن؛ قبل از تغییر، quickstart همین بسته را بخوان. (SC-001..004)
- [ ] T002 ماتریس دو پروژه/حساب و سناریوهای `infra/api/company_projects/test_team_agents.py` را از AS-11..AS-32 و edge cases آماده کن؛ داده و credential خصوصی بمانند. (SC-001, SC-002)

## Phase 2: Foundational

- [ ] T003 در `infra/api/company_projects/team_agents.py` و migration موردنیاز `infra/api/company_projects/team_migrations.py` مدل‌های data-model را با این قیود بساز/بازاستفاده کن: ManagedAgent: هر app در scope حداکثر یک تعریف فعال؛ revision مثبت؛ workflow متعلق به همان app/workspace؛ آرشیو تاریخچه را نگه می‌دارد.؛ AgentGrant: یکتا روی scope/agent/account/action؛ action فقط شش اختیار عملیاتی؛ manage_access ممنوع؛ حذف عضویت grant فعال را بی‌اثر کند.؛ PolicyAction: کلید UUID canonical؛ payload یکسان replay، متفاوت 409؛ audit و افزایش acl_revision اتمی.؛ ExecutionBinding: تحت نشست واقعی؛ نتیجه فقط با بررسی مجدد مجوز خوانده شود؛ تا KP-05 جای پرونده/تأیید PO نیست. (FR-001..012; SC-003)
- [ ] T004 در `infra/api/company_projects/test_team_agents.py` ارتقا/عدم افت داده، scope، FK/CAS و rollback/replay مرتبط را روی PostgreSQL آزمون کن؛ شماره و checksum migration قبلی عوض نشود. (FR-001..012; SC-002, SC-003)

## Phase 3: User Story 1 — ثبت تعریف و مجوز

**Goal**: مدیر پروژه از برنامه‌های همان پروژه نسخهٔ منتشرشده را انتخاب و مجوزهای اعضای فعال را ذخیره می‌کند.

**Independent Test**: مدیر دو عضو را با اختیار متفاوت ثبت کند و پس از بازخوانی همان نسخه و اختیارها را ببیند.

- [ ] T005 [US1] در `infra/api/company_projects/team_agents.py` و مرز `infra/api/company_projects/team_agents_controller.py` این رفتار را پیاده/اثبات کن: «فقط ادمین کل فعال یا مدیر همان پروژه بتواند دسترسی را تغییر دهد؛ manage_access با grant واگذار نشود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-001)
- [ ] T006 [US1] در `infra/api/company_projects/team_agents.py` و مرز `infra/api/company_projects/team_agents_controller.py` این رفتار را پیاده/اثبات کن: «view، run، feedback، finalize، edit_definition و publish_definition جدا ثبت شوند؛ نقش کاری یا عنوان مدیر جای grant عملیاتی نباشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-002)
- [ ] T007 [US1] در `infra/api/company_projects/team_agents.py` و مرز `infra/api/company_projects/team_agents_controller.py` این رفتار را پیاده/اثبات کن: «تعریف به برنامه و نسخهٔ منتشرشدهٔ دقیق همان پروژه، نسخهٔ قرارداد و هش آن متصل شود؛ draft و ارجاع خارج پروژه رد شوند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-003)
- [ ] T008 [US1] در `infra/api/company_projects/team_agents.py` و مرز `infra/api/company_projects/team_agents_controller.py` این رفتار را پیاده/اثبات کن: «عضویت مجدد، مجوز حذف‌شدهٔ عضویت قبلی را زنده نکند؛ تغییر مجوز دارای عامل، زمان، revision و سابقهٔ قابل پیگیری باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-004)
- [ ] T009 [US1] در `infra/api/company_projects/test_team_agents.py` دو سناریوی AS-11/AS-12 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-001..004; SC-001..003)
- [ ] T010 [US1] در `infra/web/overlay/app/components/company-projects/team-agents.tsx` و `infra/web/team-agents.spec.mjs` مسیر «ثبت تعریف و مجوز» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-001..004)

## Phase 4: User Story 2 — اجرای مجاز با حساب عادی

**Goal**: عضو عادی دارای run، نسخهٔ مجاز ایجنت را در مسیر کنترل‌شده اجرا می‌کند و حق انتشار نمی‌گیرد.

**Independent Test**: یک normal مجاز اجرا کند؛ همان فرد نتواند draft یا مجوز دیگری را ویرایش کند.

- [ ] T011 [US2] در `infra/api/company_projects/team_agents.py` و مرز `infra/api/company_projects/team_agents_controller.py` این رفتار را پیاده/اثبات کن: «run برای عضو عادی مجاز باشد و هیچ حق editor، انتشار، PO یا نهایی‌سازی ضمنی نسازد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-005)
- [ ] T012 [US2] در `infra/api/install.py` و `infra/api/company_projects/team_agents.py` و مرز `infra/api/company_projects/team_agents_controller.py` این رفتار را پیاده/اثبات کن: «تمام مسیرهای اجرای برنامهٔ مدیریت‌شده، توقف، مشاهدهٔ نتیجه، debug، ابزار، trigger و ادامهٔ صف سیاست واحد را اعمال یا صریحاً مسدود کنند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-006)
- [ ] T013 [US2] در `infra/api/company_projects/team_agents.py` و مرز `infra/api/company_projects/team_agents_controller.py` این رفتار را پیاده/اثبات کن: «ورودی actor، وضعیت مجوز یا شناسهٔ نسخهٔ انتخاب‌نشده از کاربر معتبر تلقی نشود؛ اجرای مجاز همیشه به نسخهٔ ثابت متصل باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-007)
- [ ] T014 [US2] در `infra/api/company_projects/team_agents.py` و مرز `infra/api/company_projects/team_agents_controller.py` این رفتار را پیاده/اثبات کن: «برای برنامهٔ قدیمی ثبت‌نشده، رفتار بومی باقی بماند؛ تبدیل به managed اقدامی صریح با preflight مسیرهای عمومی و زمان‌بندی باشد.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-008)
- [ ] T015 [US2] در `infra/api/company_projects/test_team_agents.py` دو سناریوی AS-21/AS-22 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-005..008; SC-001..003)
- [ ] T016 [US2] در `infra/web/overlay/app/components/company-projects/team-agents.tsx` و `infra/web/team-agents.spec.mjs` مسیر «اجرای مجاز با حساب عادی» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-005..008)

## Phase 5: User Story 3 — لغو و حفظ نسخه

**Goal**: مدیر مجوز را لغو می‌کند و عضو در درخواست بعدی دیگر حق اجرا یا خواندن دادهٔ تازهٔ خصوصی ندارد.

**Independent Test**: با نشست باز، grant را لغو کنید؛ درخواست بعدی رد شود و سابقهٔ اجرا باقی بماند.

- [ ] T017 [US3] در `infra/api/company_projects/team_agents.py` و مرز `infra/api/company_projects/team_agents_controller.py` این رفتار را پیاده/اثبات کن: «لغو grant، حذف عضویت یا غیرفعال‌شدن حساب در اقدام بعدی و تحویل نتیجه دوباره کنترل شود؛ سابقه حذف نشود.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-009)
- [ ] T018 [US3] در `infra/api/company_projects/team_agents.py` و مرز `infra/api/company_projects/team_agents_controller.py` این رفتار را پیاده/اثبات کن: «ثبت تکراری یک اقدام یکسان فقط یک اثر داشته باشد؛ دادهٔ متفاوت با همان کلید و revision قدیمی تعارض آشکار بدهند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-010)
- [ ] T019 [US3] در `infra/api/install.py` (guard native WorkflowService.delete_workflow با قفل منبع) و `infra/api/company_projects/team_agents.py` و مرز `infra/api/company_projects/team_agents_controller.py` این رفتار را پیاده/اثبات کن: «نسخهٔ اجرایی ارجاع‌شده با انتشار تازه جابه‌جا و با حذف بومی ناپدید نشود؛ حذف و اتصال هم‌زمان کنترل شوند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-011)
- [ ] T020 [US3] در `infra/api/company_projects/team_agents.py` و مرز `infra/api/company_projects/team_agents_controller.py` این رفتار را پیاده/اثبات کن: «رابط فارسی و RTL، loading/empty/error/conflict و استفاده با صفحه‌کلید را پوشش دهد؛ خواندن تعریف اطلاعات اتصال، prompt خصوصی و لاگ دیگران را باز نکند.» پاسخ و خطا مطابق `contracts/interface.md` باشد. (FR-012)
- [ ] T021 [US3] در `infra/api/company_projects/test_team_agents.py` دو سناریوی AS-31/AS-32 و edge caseهای مرتبط را با witness داده و fresh policy اجرا کن؛ تست mock صرف کافی نیست. (FR-009..012; SC-001..003)
- [ ] T022 [US3] در `infra/web/overlay/app/components/company-projects/team-agents.tsx` و `infra/web/team-agents.spec.mjs` مسیر «لغو و حفظ نسخه» با loading/empty/error/conflict، label، focus، صفحه‌کلید، متن فارسی و RTL را بساز/آزمون کن؛ قرارداد `infra/web/overlay/service/company-projects.ts` در صورت نیاز به‌روزرسانی شود. (SC-004; FR-009..012)

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 در `docs/kara-kp-02-validation.md` نتیجهٔ make check، PostgreSQL مرتبط، build/TypeScript/UI، Compose، startup، doctor و browser واقعی را با نسخه و شاهد/موارد اجرا نشده ثبت کن؛ regressions پروژه/اعضا/inbox/automation/templates حفظ شوند. (SC-001..004)
- [ ] T024 در `docs/kara-kp-02-validation.md` backup/restore، مسیر rollback دارای enforcement، تصمیم پذیرش و محدودیت را ثبت و `specs/002-agent-access/tasks.md` را فقط براساس شاهد به‌روز کن؛ commitهای مستقل و branch policy رعایت شوند. (SC-003)

## Dependencies and Execution Order

KP-01 پذیرفته‌شده. T001 و T002 پیش از foundation؛ T003 پیش از T004 و storyها. storyها به ترتیب US1 → US2 → US3 برای یکپارچه‌سازی کامل؛ آزمون هر story به‌تنهایی با fixture معتبر ممکن است. فعال‌کردن قابلیت پیش از تکمیل تمام موارد امنیتی ممنوع است.

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

ماتریس ورودی باید هم Community نصب‌شده و هم قابلیت Enterprise استفاده‌شده را جدا ثبت کند؛ Enterprise این محیط تست نشده است. نبود پوشش هر ورودی، مانع فعال‌کردن managed است.
