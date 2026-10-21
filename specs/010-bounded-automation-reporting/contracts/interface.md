# Interface Contract: KP-10

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
| `GET/POST /automations/team` | name, connector_id, operation, schedule/event config, service_principal_id | هدف افزونهٔ team جدا از native automation؛ created disabled و scoped |
| `PUT /automations/team/{id}` | expected_revision و تنظیمات نسخهٔ تازه | 200 draft/newrevision؛ مدیر مجاز |
| `POST /automations/team/{id}/enable` | expected_revision, version_id | explicit enable؛ فقط connector/principal معتبر |
| `POST /automations/team/{id}/disable` | expected_revision, reason | dispatch جدید بسته و stop status شفاف |
| `GET /automations/team/{id}/deliveries` | cursor, limit | رخداد/attempt/اثر sanitized scoped |
| `GET /reports/requests` | filters, cursor, limit, as_of | metadata مجاز و snapshot/cursor پایدار؛ export همان سیاست |

## UI Contract

مدیر اجرای دوره‌ای یا رویدادی محدود و قابل توقف برای دریافت مجاز تنظیم کند و وضعیت درخواست‌ها را بدون جعل تصمیم انسانی گزارش بگیرد. صفحهٔ هر story با کنترل‌های مجاز همان actor، loading/empty/error/conflict و retry امن
نمایش داده شود. route یا دکمهٔ مخفی جای enforcement سرور نیست. فارسی/RTL، label قابل دسترس، focus
پس از خطا و صفحه‌کلید پوشش داده شوند. خطای conflict دادهٔ تازه را نشان دهد و متن کاربر از دست نرود.

## Version and Compatibility

contract version اولیه 1.0-draft؛ [مدل داده](../data-model.md) مرجع فیلد/قید و
[spec](../spec.md) مرجع حقوق کاربر است. API قدیمی عوض نشود؛ نام endpoint هدف پس از تثبیت پیش‌نیاز
با spec/plan/tasks هم‌زمان تغییر کند. migrationهای اعمال‌شده checksumشان بازنویسی نشود.

## Gate and Negative Cases

طراحی event بیرونی باید با اتصال انتخاب‌شده نهایی شود؛ در این مرحله سرویس خارجی واقعی فعال نکنید. اگر عملیاتی idempotency خارجی ندارد unknown اثر باید نیازمند بررسی بماند.

پذیرش باید این ماتریس را پوشش دهد: draftdisabled، manageronly، principalnarrow/revoked، duplicatedelivery، disablequeued، versionchangeinflight، boundedretry و unknown-effect، nofakeapproval/merge، reportscoping/count/export/Tehrantime و nativeautomationregression.
