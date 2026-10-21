# Interface Contract: KP-07

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
| `POST /instances/{i}/stages/{s}/revalidations` | expected_revision, fresh_input_refs, reason | ready بدون تأیید خروجی قبلی؛ run جاری |
| `POST /instances/{i}/stages/{s}/reassignments` | expected_revision, finalizer_id, reason | مدیر مجاز؛ 200 revision جدید و مجوز ورودی تازه |
| `POST /instances/{i}/cancellations` | expected_revision, reason | 200 cancelled/requested با stop status واقعی؛ مدیر/PO |
| `POST /instances/{i}/stages/{s}/retries` | expected_revision, reason | ready یا dispatch محدود صریح طبق قرارداد؛ no whole-flow replay |
| `GET /instances/{i}/recovery` | فقط دسترسی مدیریت/مسئول مجاز | eventها و حالت نیازمند اقدام بدون raw credentials |

## UI Contract

تیم بتواند خطا، اصلاح ورودی، تغییر مسئول و لغو را با تاریخچهٔ معتبر مدیریت کند و قطع کارگر یا تکرار درخواست باعث تصمیم و اجرای کنترل‌نشده نشود. صفحهٔ هر story با کنترل‌های مجاز همان actor، loading/empty/error/conflict و retry امن
نمایش داده شود. route یا دکمهٔ مخفی جای enforcement سرور نیست. فارسی/RTL، label قابل دسترس، focus
پس از خطا و صفحه‌کلید پوشش داده شوند. خطای conflict دادهٔ تازه را نشان دهد و متن کاربر از دست نرود.

## Version and Compatibility

contract version اولیه 1.0-draft؛ [مدل داده](../data-model.md) مرجع فیلد/قید و
[spec](../spec.md) مرجع حقوق کاربر است. API قدیمی عوض نشود؛ نام endpoint هدف پس از تثبیت پیش‌نیاز
با spec/plan/tasks هم‌زمان تغییر کند. migrationهای اعمال‌شده checksumشان بازنویسی نشود.

## Gate and Negative Cases

اجرای مدل یا اثر خارجی پس از قبول dispatch ممکن است با retry دوباره شود؛ unknown را با correlation reconcile یا به بررسی انسانی ببرید. تصمیم انسانی و کل فلو را retry نکنید.

پذیرش باید این ماتریس را پوشش دهد: دوstart/دوfinalize، replay same/differentpayload، feedbackbaseold، revoke/finalize race، cancel/callback race، workerrestart، commit-before-dispatch/dispatch-before-runid، outboxleaseexpiry، stale transitive و reassignment همراه فایل.
