# Interface Contract: KP-04

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
| `GET/POST /requests` | title, text, attachment_ids، Idempotency-Key | 201 draft و revision1؛ فقط عضو فعال |
| `GET /requests/{id}` | scope جاری | نمای درخواست با current_revision و تصمیم‌های مجاز |
| `POST /requests/{id}/revisions` | expected_revision, text, attachment_ids | 201 revision جدید بدون بازنویسی قبلی |
| `POST /requests/{id}/attachments` | upload یا reference ذخیره‌سازی بومی؛ نوع/سقف از تنظیمات موجود | 201 ref scoped؛ upload و download همان کنترل |
| `GET /requests/{id}/attachments/{attachment_id}` | مجوز پرونده و فایل | محتوای مجاز؛ بدون bypass signed URL |
| `POST /requests/{id}/intake-decisions` | request_revision_id, flow_version_id, outcome, reason, expected_revision | 201 تصمیم واقعی PO؛ approved معتبر یک instance آماده؛ سایر outcome بدون instance |
| `POST /requests/{id}/intake-decisions/{decision_id}/revocations` | reason, expected_revision | 200 رویداد ابطال توسط PO فعلی؛ سابقه دست‌نخورده |

## UI Contract

عضو تیم نیازمندی را مستقل ثبت کند؛ PO واقعی نسخهٔ مشخص درخواست و فلو را با تصمیم صریح برای تولید انتخاب کند. صفحهٔ هر story با کنترل‌های مجاز همان actor، loading/empty/error/conflict و retry امن
نمایش داده شود. route یا دکمهٔ مخفی جای enforcement سرور نیست. فارسی/RTL، label قابل دسترس، focus
پس از خطا و صفحه‌کلید پوشش داده شوند. خطای conflict دادهٔ تازه را نشان دهد و متن کاربر از دست نرود.

## Version and Compatibility

contract version اولیه 1.0-draft؛ [مدل داده](../data-model.md) مرجع فیلد/قید و
[spec](../spec.md) مرجع حقوق کاربر است. API قدیمی عوض نشود؛ نام endpoint هدف پس از تثبیت پیش‌نیاز
با spec/plan/tasks هم‌زمان تغییر کند. migrationهای اعمال‌شده checksumشان بازنویسی نشود.

## Gate and Negative Cases

فلو draft/archived برای ورود جدید نامعتبر است؛ پروندهٔ pin‌شده تابع همان نسخه می‌ماند. اگر ابطال روی instance موجود اثر دارد، hook مسدودکردن مصرف را همین گام بسازید و در KP-07 گسترش دهید.

پذیرش باید این ماتریس را پوشش دهد: چهار outcome، root بدونpo، po پروژه دیگر، نسخهٔ قدیمی، expiry/revoke، دو approve هم‌زمان، request dedupe، فایل بیگانه، requestv2 حفظv1، کارتابل بومی و فرم قدیمی سالم.
