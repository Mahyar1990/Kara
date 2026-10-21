# Interface Contract: KP-02

وضعیت: قرارداد هدف، پیاده‌سازی نشده. برای endpointها پیشوند
`/console/api/company/projects/{project_id}/team` است؛ موارد harness/port داخلی endpoint عمومی نیستند.

## Authentication, Scope and Common Shape

نشست، CSRF و workspace جاری بومی حفظ شوند. actor/role/state/guards از بدنه گرفته نشوند.
root برای مدیریت cross-workspace از مسیر مدیریتی موجود استفاده کند؛ این استثنا حق PO یا run نمی‌سازد.
هر child به scope والد کنترل شود؛ object بیگانه حتی با UUID معتبر 404، actor شناخته‌شدهٔ فاقد اختیار 403.
آرایه‌های لیست cursor پایدار، default limit=50، max=100؛ summary فاقد secret/prompt/log خصوصی باشد.

mutationهای console دارای `Idempotency-Key` از نوع UUID canonical و revision موردانتظار صحیح مثبت هستند
(برای create بدون رکورد موجود، revision فقط بعد از ایجاد معنی دارد). JSON شامل متن کاربر بی‌صدا trim نشود.
پاسخ نمای تک‌رکورد id، revision و دادهٔ مجاز موضوع؛ ایجاد جدید 201، async پذیرفته‌شده 202، خواندن/اصلاح 200.
خطا دارای code ثابت، message فارسی قابل اقدام و correlation_id بدون جزئیات داخلی حساس است.

| وضعیت | معنای قرارداد |
| --- | --- |
| 400 | قالب، UUID، کلید یا revision نامعتبر |
| 401 | نشست معتبر نیست؛ قواعد CSRF بومی نیز برقرار است |
| 403 | حساب فعال فاقد اختیار اقدام |
| 404 | موضوع موجود یا در scope قابل دسترسی نیست؛ عدم افشای پروژهٔ دیگر |
| 409 | revision قدیمی، رقابت یا همان کلید با payload متفاوت |
| 422 | پیش‌نیاز/مرجع/حالت معنایی نامعتبر؛ خطای قابل اصلاح فیلدی |

replay با key و payload یکسان، همان نتیجهٔ منطقی ذخیره‌شده و بدون اثر تازه برگرداند؛ ACL جاری برای
خواندن نتیجه دوباره کنترل شود. هش و idempotency کلید، مجوز یا امضای انسان نیستند.

## Operations

| عملیات | ورودی و شرط | خروجی/رفتار |
| --- | --- | --- |
| `GET /agents` | فهرست تعاریف مجاز؛ cursor/limit | metadata حداقلی و effective_actions، بدون prompt/secret |
| `POST /agents` | app_id, workflow_id, contract_revision, contract_digest | 201 تعریف؛ فقط root/manager ثبت و grant اولیه را صریح می‌سازند؛ ویرایش/انتشار بعدی هر دو مجوز بومی و grant لازم دارد |
| `GET /agents/{id}/grants` | مدیر scope | ACL و acl_revision؛ فقط مدیر مجاز |
| `PUT /agents/{id}/grants` | expected_revision, grants[{account_id,actions}] | 200 سیاست جدید یا replay؛ replace اتمی، حساب‌های دیگر scope رد |
| `POST /agents/{id}/runs` | workflow_id ثابت، inputs مطابق قرارداد | 202 correlation/run مجاز با حساب caller؛ فقط run؛ اجرای مستقل پیش از stages حق تحویل ندارد |
| `GET /agents/{id}/runs/{run_id}` | خواندن نتیجه متعلق به اجرای caller با grant جاری | 200 دادهٔ مجاز؛ حداقل ACL برای حالت managed؛ route بومی جایگزین نباشد |
| `POST /agents/{id}/runs/{run_id}/stop` | run متعلق به caller، expected_revision | 202 درخواست توقف؛ task_id به‌تنهایی شاهد مالکیت نیست |
| `POST /agents/{id}/archive` | expected_revision, reason | 200 archived؛ شروع تازه ممنوع؛ منابع تاریخی حفظ |

## Managed Definition Lifecycle

ثبت اولیه تنها root/manager با preflight و grantهای اولیهٔ صریح است. این ثبت و مدیریت ACL
جای مجوز بومی ویرایش/انتشار نیست؛ حتی مدیر برای ویرایش محتوای برنامه به مجوز بومی متناظر نیاز دارد.
مسیرهای بومی تغییر graph، publish، restore/import، delete و socket collaboration برای managed app
هم native permission و هم edit_definition/publish_definition مربوط را کنترل کنند. grant تنها
امکان انتشار به عضو normal نمی‌دهد. افزودن publication جدید یک definition snapshot تازه می‌سازد؛
bindingهای مصرف‌شده با workflow_id/contract digest قبلی حفظ می‌شوند. سیاست view حداقل metadata است؛
خواندن نتیجهٔ یک run همچنان به caller/attempt و grant جاری محدود است. feedback/finalize در KP-02
مجوز قابل تنظیم‌اند؛ عملیات مرحله‌ای آن‌ها در KP-05 و با تصمیم ورود معتبر پیاده می‌شود.

| عملیات تیمی تکمیلی | شرط | نتیجه |
| --- | --- | --- |
| `PUT /agents/{id}` | expected_revision، metadata/نسخهٔ انتخابی؛ edit_definition و native edit | snapshot تعریف تازه و audit؛ بدون تغییر pin پرونده‌های قبلی |
| انتشار گراف بومی managed | publish_definition و native publish؛ scope/app/workflow معتبر | publication جدید؛ pointer نسخهٔ مصرف‌شده عوض نشود |
| حذف workflow/app بومی referenced | guard در همان قفل منبع و refs managed | 409 تا وجود ارجاع تاریخی؛ بدون حذف تاریخچه |

## UI Contract

ادمین کل یا مدیر پروژه یک برنامهٔ منتشرشده را به ایجنت مدیریت‌شده متصل کند و اقدام‌های مجاز هر عضو را جدا تعیین کند تا عضو عادی بتواند کار مجازش را بدون دسترسی ویرایش انجام دهد. صفحهٔ هر story با کنترل‌های مجاز همان actor، loading/empty/error/conflict و retry امن
نمایش داده شود. route یا دکمهٔ مخفی جای enforcement سرور نیست. فارسی/RTL، label قابل دسترس، focus
پس از خطا و صفحه‌کلید پوشش داده شوند. خطای conflict دادهٔ تازه را نشان دهد و متن کاربر از دست نرود.

## Version and Compatibility

contract version اولیه 1.0-draft؛ [مدل داده](../data-model.md) مرجع فیلد/قید و
[spec](../spec.md) مرجع حقوق کاربر است. API قدیمی عوض نشود؛ نام endpoint هدف پس از تثبیت پیش‌نیاز
با spec/plan/tasks هم‌زمان تغییر کند. migrationهای اعمال‌شده checksumشان بازنویسی نشود.

## Gate and Negative Cases

ماتریس ورودی باید هم Community نصب‌شده و هم قابلیت Enterprise استفاده‌شده را جدا ثبت کند؛ Enterprise این محیط تست نشده است. نبود پوشش هر ورودی، مانع فعال‌کردن managed است.

پذیرش باید این ماتریس را پوشش دهد: root/owner/admin/editor/normal، دو پروژه، run-only، لغو در نشست باز، grant حذف و عضویت مجدد، REST مستقیم و public/service/debug/node/loop/socket/trigger/queue/tool، stop با task بیگانه، republish و delete/bind هم‌زمان؛ برنامهٔ legacy همان رفتار قبلی داشته باشد.
