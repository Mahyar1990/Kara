# Interface Contract: KP-05

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
| `GET /instances/{i}/stages/{s}` | عضو با اختیار همان مرحله | ورودی مجاز، state، record_revision، effective_actions |
| `POST /instances/{i}/stages/{s}/attempts` | expected_revision و کلید اقدام؛ input refs سرور کنترل | 202 attempt؛ run جاری؛ outbox پس از commit |
| `GET /instances/{i}/stages/{s}/artifacts` | مجوز خواندن مرحله | نسخه‌های مجاز و والد/نویسنده؛ نه تمام native logs |
| `POST /instances/{i}/stages/{s}/feedback` | base_revision, parent_artifact_id, text | 201 feedback و ready؛ اجرا دستی |
| `POST /instances/{i}/stages/{s}/artifacts` | base_revision, parent_artifact_id, content, kind=human | 201 نسخهٔ انسانی با actor نشست |
| `POST /instances/{i}/stages/{s}/decision-requests` | expected_revision, artifact_id | awaiting_decision؛ feedback grant |
| `POST /instances/{i}/stages/{s}/finalizations` | expected_revision, selected_artifact_id, reason | 201 تصمیم فقط finalizer جاری؛ بعدی ready، بدون dispatch |

## UI Contract

هر فرد مجاز مرحلهٔ آماده را با ورودی نسخه‌دار اجرا کند، چند دور بازخورد یا ویرایش انسانی ثبت کند و نهایی‌کننده خروجی معتبر منتخب را صریحاً ببندد. صفحهٔ هر story با کنترل‌های مجاز همان actor، loading/empty/error/conflict و retry امن
نمایش داده شود. route یا دکمهٔ مخفی جای enforcement سرور نیست. فارسی/RTL، label قابل دسترس، focus
پس از خطا و صفحه‌کلید پوشش داده شوند. خطای conflict دادهٔ تازه را نشان دهد و متن کاربر از دست نرود.

## Version and Compatibility

contract version اولیه 1.0-draft؛ [مدل داده](../data-model.md) مرجع فیلد/قید و
[spec](../spec.md) مرجع حقوق کاربر است. API قدیمی عوض نشود؛ نام endpoint هدف پس از تثبیت پیش‌نیاز
با spec/plan/tasks هم‌زمان تغییر کند. migrationهای اعمال‌شده checksumشان بازنویسی نشود.

## Gate and Negative Cases

API عادی run در KP-02 جای تصمیم ورود و stages نیست. content طولانی باید artifact store کامل داشته باشد؛ inbox preview کافی نیست. callback بعد از لغو یا ورودی تازه صرفاً سابقهٔ فنی است.

پذیرش باید این ماتریس را پوشش دهد: ready/start، blocked denial، دو start، callback قدیمی و تکراری، دو feedback+human edit، base_revision conflict، finalizer دیگر، grantrevoked، oldartifact denial، manual next، failure/retry و outbox crash window.
