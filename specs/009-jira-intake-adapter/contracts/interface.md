# Interface Contract: KP-09

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
| `Internal adapter port: validate(envelope)` | پاسخ خصوصی سرویس و connector scoped | validated normalized request یا typed error؛ نام فیلد بیرونی هنوز تثبیت نشده |
| `POST /requests/imports/jira` | connector_id, source_reference، expected_revision در update | مسیر هدف؛ payload دقیق source_reference بعد از sample؛ 201 created/200 no-op/409 conflict |
| `GET /requests/imports/{receipt_id}` | عضو دارای مشاهدهٔ request همانscope | وضعیت و provenance sanitized؛ بدون raw credentials |
| `Connector configuration boundary` | فقط root/manager و secretreference معتبر | تنظیمات مشترک فاقد token؛ endpoint دقیق مدیریت پس از sample/auth review |

## UI Contract

نیازمندی دریافت‌شده از سرویس واسط Jira به همان درخواست داخلی نسخه‌دار تبدیل شود، منشأ حفظ و دریافت تکراری کنترل شود و PO همچنان ورود را تصمیم بگیرد. صفحهٔ هر story با کنترل‌های مجاز همان actor، loading/empty/error/conflict و retry امن
نمایش داده شود. route یا دکمهٔ مخفی جای enforcement سرور نیست. فارسی/RTL، label قابل دسترس، focus
پس از خطا و صفحه‌کلید پوشش داده شوند. خطای conflict دادهٔ تازه را نشان دهد و متن کاربر از دست نرود.

## Version and Compatibility

contract version اولیه 1.0-draft؛ [مدل داده](../data-model.md) مرجع فیلد/قید و
[spec](../spec.md) مرجع حقوق کاربر است. API قدیمی عوض نشود؛ نام endpoint هدف پس از تثبیت پیش‌نیاز
با spec/plan/tasks هم‌زمان تغییر کند. migrationهای اعمال‌شده checksumشان بازنویسی نشود.

## Gate and Negative Cases

BLOCKED-INPUT: نمونهٔ موفق/خطا، نسخه‌بندی و ترتیب، صفحه‌بندی، auth، attachment و rate-limit سرویس موجود نیست. plan نگاشت فیلد و پذیرش زنده عمداً نهایی نیست؛ این مانع تکمیل port داخلی/مشخصات رفتار یا مسیر دستی نیست. عرضهٔ متعهد به Jira بدون رفع این gate ممنوع.

پذیرش باید این ماتریس را پوشش دهد: بعد از sample: create/update/no-op، outoforder، concurrentimport، 401/403/429/5xx/timeout/oversize/badformat، missingrequired، crossconnector/project، credentialredaction، PO gate و manualregression؛ فعلاً هیچ livecall انجام نشود.
