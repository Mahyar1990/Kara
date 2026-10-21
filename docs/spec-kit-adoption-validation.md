# گزارش پذیرش ابزار Spec Kit و بررسی مشخصات آینده

تاریخ: ۲۰۲۶-۱۰-۲۲. مبنای قبل از این کار `36ca09c` روی `master`؛ تغییر این تحویل ابزار توسعه و
مستندات است. هیچ endpoint، schema، image اجرایی، حساب، اتوماسیون یا ایجنت کلاسور عوض نشده است.

## نصب و فرمان‌های واقعی

- منبع رسمی GitHub، release `v1.2.2`، SHA `74be0a63e93c7087c5b06556b7561810d8f78a45`.
- نصب `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.2.2`
  با مسیرهای UV محدود به `.runtime/spec-kit/`؛ ۴۱ بسته واقعاً دریافت/نصب شدند. تلاش اول در sandbox
  با DNS failure مواجه شد؛ تکرار با دسترسی شبکه موفق شد. TLS غیرفعال نشد.
- `specify version`: نسخهٔ CLI برابر 1.2.2، Python ابزار 3.11.15. منشأ نصب علاوه بر version با
  خروجی resolve به SHA و metadata نصب قابل بررسی است؛ صرف version شاهد provenance نیست.
- `bash scripts/spec-kit.sh bootstrap` نیز با SHA ثابت دوباره واقعاً اجرا شد: ۴۱ بسته resolve/check و
  version موفق. آزمون در sandbox به محدودیت DNS خورد و تکرار دارای دسترسی شبکه موفق شد؛ نصب
  سراسری یا تغییر PATH لازم نشد چون wrapper باینری محلی را صریح اجرا می‌کند. `direct_url.json`
  منشأ GitHub و commit دقیق قفل‌شده را تأیید کرد.
- `specify init --here --force --non-interactive --integration codex --script sh --ignore-agent-tools`:
  موفق؛ مهارت‌ها، templates، shell helpers و workflow رسمی نصب شدند؛ branch و AGENTS اولیه حفظ شدند.
- constitution-template از helper رسمی resolve شد؛ constitution 1.0.0 از تصمیم‌ها و قراردادهای موجود
  نوشته شد. Sync Impact Report موقت طبق skill قبل از commit حذف و نسخهٔ خصوصی آن نگهداری شد.
- برای **هر کدام** از ۹ feature، به‌ترتیب helperهای واقعی create-new-feature، paths-only، setup-plan،
  checklist template، setup-tasks و check-prerequisites اجرا و JSON موفق بررسی شد. اجرای آخر prerequisites
  با require-spec/require-tasks/include-tasks نیز برای همهٔ ۹ بسته تکرار شد.

[execution.md هر بسته](../specs/README.md) آرگومان مرحلهٔ ایجنت، helperها و نتیجه را ثبت می‌کند.
مهارت‌ها دستورهای ایجنت‌اند؛ shell command برای تولید خودکار متن معنایی مستقل از ایجنت وجود ندارد.
ایجنت همین جلسه متن رسمی skillها را دنبال و خروجی‌ها را بر اساس قالب resolveشده تکمیل کرد.
در Phase 0 برنامه‌ریزی، research خواندنی مطابق skill plan به یک ایجنت پژوهشی سپرده شد؛ نتیجهٔ آن
در research.md ثبت شد. هیچ اجرای دیگر Codex برای تولید spec و هیچ اجرای مدل محصول ادعا نمی‌شود.

## بررسی کیفیت و analyze

تحلیل مطابق skill `speckit-analyze` پس از tasks و اجرای پیش‌نیاز رسمی، خواندنی انجام شد؛ این سند
گزارش تجمیعی تحویل است و خروجی یک subcommand shell به نام analyze نیست. اصلاحات در مرحلهٔ نویسندگی
پیش از تحلیل نهایی شامل جداکردن مکانیزم داده از spec کسب‌وکار، افزودن guard حذف نسخه و مسیرهای بومی،
تفکیک harness پذیرش از API محصول و صریح‌کردن طرح مشروط Jira بود.

| ویژگی | FR | Story | سناریوی اصلی | تسک باز | پوشش FR→تسک | وضعیت طراحی/شروع |
| --- | --- | --- | --- | --- | --- | --- |
| KP-02 | 12 | 3 | 6 | 24 | 100% | آمادهٔ بازبینی؛ KP-01 پذیرفته است؛ فعال‌سازی پس از تکمیل ماتریس enforcement |
| KP-03 | 12 | 3 | 6 | 24 | 100% | draft؛ منتظر پذیرش KP-02 |
| KP-04 | 12 | 3 | 6 | 24 | 100% | draft؛ منتظر KP-03 و نقش‌های KP-01 |
| KP-05 | 12 | 3 | 6 | 24 | 100% | draft؛ منتظر KP-02..04؛ outbox از اولین dispatch لازم |
| KP-06 | 12 | 3 | 6 | 24 | 100% | draft؛ منتظر KP-05 |
| KP-07 | 12 | 3 | 6 | 24 | 100% | draft؛ منتظر KP-05/06؛ ایمنی اولیهٔ صف قبلاً لازم است |
| KP-08 | 12 | 3 | 6 | 24 | 100% | draft پذیرش؛ منتظر KP-01..07 |
| KP-09 | 12 | 3 | 6 | 24 | 100% | port داخلی طراحی‌شده؛ نگاشت/قرارداد بیرونی و live acceptance مسدود به sample |
| KP-10 | 12 | 3 | 6 | 24 | 100% | draft؛ منتظر هسته و اتصال مرتبط؛ Jira وابسته به KP-09 |

پوشش ۱۰۰٪ یعنی هر FR ارجاع به تسک اجرای رفتار و آزمون/UI دارد؛ کیفیت اجرای آینده را اثبات نمی‌کند.
جدول کامل هر requirement و task ID در tasks.md همان بسته است. setup/foundation/polish به SCهای
پذیرش و storyهای مربوط متصل‌اند؛ تسک بدون هدف محصولی شناسایی نشد. همهٔ ۲۱۶ تسک اجرا بازند.

| شناسه | نوع/شدت | محل | نتیجه و اقدام لازم |
| --- | --- | --- | --- |
| D1 | وابستگی / HIGH | KP-09 plan و قرارداد | sample موفق/خطا، auth، pagination، ordering و semantics نسخه موجود نیست؛ mapper بیرونی و پذیرش live تا دریافت آن اجرا نشوند |
| D2 | وابستگی / MEDIUM | plan همهٔ بسته‌های بعدی | نام‌های هدف endpoint/مدل آینده‌اند؛ پس از پذیرش predecessor قرارداد نهایی به آن‌ها منتقل و analyze دوباره انجام شود |
| G1 | gate امنیت / HIGH هنگام activation | KP-02 plan و FR-006/011 | همهٔ ورودی‌ها enforce یا deny و delete/bind serialized شوند؛ طرح آن را پوشش داده، شاهد runtime هنوز باید ساخته شود |
| G2 | gate انسانی / MEDIUM | review checklist همهٔ بسته‌ها | ۸ معیار تازهٔ بازبین در هر feature بازند؛ نویسنده به جای بازبین تأیید نداده است |

تعارض بحرانی حل‌نشده با constitution، FR بدون تسک، تسک یتیم و ابهام رفتاری بحرانیِ داخلی در بررسی نهایی
شناسایی نشد. D1 نقص ورودی بیرونی شناخته‌شده است و مجوز حدس‌زدن قرارداد نمی‌دهد. این تحلیل مجوز
پیاده‌سازی خودکار همهٔ roadmap نیست؛ قدم بعد بازبینی و انتخاب اجرای KP-02 است.

taxonomy clarify: نقش/مرز، نسخه/هویت، UX، شکست/تکرار، امنیت، معیار پایان و اصطلاحات با تصمیم‌های قبلی
پوشش داده شدند؛ سؤال تازه پرسیده نشد. SLA و ظرفیت production به کار انتشار آینده واگذار شده‌اند؛
وابستگی بیرونی Jira باز و صریح blocked است. quality checklist خود مشخصات تکمیل شد؛ checklist بازبین
عمداً باز است. هیچ `implement` یا `converge` برای قابلیت آینده اجرا نشده است.

## بررسی‌های قابل بازتولید این تحویل

```sh
bash scripts/spec-kit.sh version
make spec-check
make check
```

`check_specs.py` وجود همهٔ artifactها، یکتایی prefix و FR/task ID، نگاشت FRها به taskهای موجود،
مسیر صریح وظیفه، لینک‌ها، fenceها، scaffold حل‌نشده، syntax shell و هش manifestهای upstream را بررسی
می‌کند. این validator معنای requirement، مجوز واقعی، PostgreSQL و UI را نمی‌آزماید.

شواهد خام نصب/قالب/helper در `.runtime/spec-kit/` خصوصی‌اند. `sources/` و checkout قفل‌شدهٔ
`.runtime/dify` تغییر نکرده‌اند. هیچ push، ایجاد issue، ارسال بیرونی یا فعال‌سازی automation انجام نشد.
برای این تغییر صرفاً مستندات/ابزار، build کامل وب و آزمون تغییردهندهٔ DB تکرار نمی‌شود؛ نتایج تاریخی
KP-01 در [closeout](kara-kp01-closeout.md) و [فهرست ترد](kara-thread-record.md) جدا ثبت‌اند.

## نتیجهٔ بررسی نهایی

`make spec-check` و `make check` موفق: ۹ feature، ۱۰۸ FR، ۲۱۶ تسک و ۵۴ آزمون مشترک.
هش فایل‌های رسمی skill/helper/template با manifestهای نصب تطبیق دارد و syntax تمام shellها معتبر است.
بررسی فقط‌خواندنی کلاینت محلی خارج sandbox: `/projects` با 307 به احراز هویت هدایت شد و پاسخ نهایی
با دنبالکردن redirect برابر HTTP 200 بود؛ این smoke بدون نشست، آزمون مجدد نقش‌های UI نیست.
checkout upstream بدون تغییر است. شاخهٔ رزرو با master هم‌سطح و اختلاف `0 0` باقی می‌ماند؛
تغییرات این تحویل محلی‌اند و push نشده‌اند.

## کامیت‌های این تحویل

| کامیت | هدف مستقل |
| --- | --- |
| `31f6f44` | نصب/راه‌اندازی Spec Kit ثابت و constitution 1.0.0 |
| `329c7e2` | مشخصات و طرح KP-02، دسترسی و ایجنت مدیریت‌شده |
| `43d539c` | مشخصات و طرح KP-03، فلو نسخه‌دار |
| `031d613` | مشخصات و طرح KP-04، درخواست و تصمیم PO |
| `23ba3d7` | مشخصات و طرح KP-05، اجرا و بازخورد |
| `7808a93` | مشخصات و طرح KP-06، تحویل و کارتابل |
| `285d9c3` | مشخصات و طرح KP-07، بازیابی و هم‌زمانی |
| `7962d25` | مشخصات و طرح KP-08، پذیرش هسته |
| `c81df51` | مشخصات و طرح مشروط KP-09، سرویس Jira |
| `d91b59c` | مشخصات و طرح KP-10، اتوماسیون محدود و گزارش |

کامیت یکپارچه‌سازی راهنما، فهرست شواهد و validator با مسیرهای همین سند در `git log -- docs/ scripts/check_specs.py`
قابل بازیابی است؛ شناسهٔ کامیتِ حاوی خود سند داخل همان کامیت قابل ثبت نیست.
