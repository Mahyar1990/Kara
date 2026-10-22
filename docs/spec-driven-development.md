# توسعهٔ مبتنی بر مشخصات در Kara

تاریخ پذیرش: ۲۰۲۶-۱۰-۲۲. از این تصمیم به بعد، تغییر محصول از spec شروع می‌شود.
مبنای رفتار پذیرفته‌شدهٔ قبلی در قرارداد KP-00 و گزارش‌های KP-01 باقی می‌ماند؛ نصب ابزار
به معنی ایجاد خودکار مشخصات گذشته، پیاده‌سازی آینده یا پذیرش آن نیست.

## نصب و پیکربندی

[Spec Kit رسمی](https://github.com/github/spec-kit) نسخهٔ `1.2.2` از GitHub نصب شد؛
commit دقیق در [قفل ابزار](../infra/spec-kit.lock.json) است. Python ابزار `3.11.15` است و
محیط ابزار از Python برنامه جداست. پیش‌نیاز نصب دوباره، Git، Python 3.11+، uv و اینترنت است.

از ریشهٔ مخزن:

```sh
bash scripts/spec-kit.sh bootstrap
bash scripts/spec-kit.sh version
```

معادل نصب محلی `make spec-bootstrap` و بررسی ساختاری اسناد `make spec-check` است؛
بررسی دوم بدون اینترنت و بدون اجرای مدل یا محیط محصول کار می‌کند.

ابزار و cache در `.runtime/spec-kit/` و خارج Git می‌مانند. نصب اولیه با دستور رسمی
`uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.2.2`
و متغیرهای `UV_CACHE_DIR`، `UV_TOOL_DIR` و `UV_TOOL_BIN_DIR` محدود به همین پروژه انجام شد.
نسخهٔ tag به commit قفل‌شده resolve شد؛ bootstrap از خود commit استفاده می‌کند.
تنظیمات TLS و محیط Python برنامه تغییر نکردند.
متن مجوز upstream برای فایل‌های رسمی کپی‌شده در [UPSTREAM-LICENSE](../.specify/UPSTREAM-LICENSE) حفظ شده است.

دستور راه‌اندازی که واقعاً اجرا شد:

```sh
bash scripts/spec-kit.sh init --here --force --non-interactive --integration codex --script sh --ignore-agent-tools
```

این دستور، قالب‌ها و اسکریپت‌های رسمی `.specify/` و مهارت‌های Codex در `.agents/skills/`
را نصب کرد. `--ignore-agent-tools` فقط بررسی وجود باینری Codex CLI را حذف می‌کند؛ این جلسه
خود ایجنت اجراکننده است. `AGENTS.md` و سورس برنامه بازنویسی نشدند. init مجدد را روی کار
ناتمام اجرا نکنید؛ `--force` ممکن است فایل مدیریت‌شدهٔ هم‌نام را جایگزین کند. templateها و
skillهای نصب‌شده دست‌نخورده با manifest هش نگهداری می‌شوند. افزونهٔ git، انتشار issue،
سرویس خارجی یا تنظیمات سراسری Codex فعال نشده‌اند.

## دستورهای روزمره

دستورهای زیر **در چت ایجنت** اجرا می‌شوند، نه shell. شکل رسمی Codex در این نسخه `$speckit-*`
است؛ در کلاینت‌های دیگر ممکن است `/speckit-*` باشد. پس از بازکردن مجدد پروژه، مهارت‌ها از
`.agents/skills/` قابل شناسایی‌اند. در همین جلسه متن SKILL.md هر مرحله خوانده و دنبال شد؛
مدل فایل‌های معنایی را می‌نویسد و helperهای واقعی، قالب و پیش‌نیاز را resolve می‌کنند.

```text
$speckit-constitution اصول موجود Kara را از AGENTS.md و قرارداد تیم استخراج و حفظ کن.
$speckit-specify نیازمندی محدود مرحلهٔ انتخاب‌شده را با حفظ قراردادها مشخص کن.
$speckit-clarify ابهام‌ها، دسترسی، نسخه‌ها و معیار پذیرش را بررسی کن.
$speckit-plan طرح را با سورس قفل‌شده و overlayهای موجود سازگار کن.
$speckit-checklist کیفیت نیازمندی‌ها و مرزهای دسترسی و شکست را بازبینی کن.
$speckit-tasks وظایف قابل آزمون را به تفکیک user story و وابستگی بنویس.
$speckit-analyze سازگاری spec، plan، tasks و constitution را بررسی کن.
```

هر بار یک feature انتخاب شود. برای نمونه، پیش از ادامهٔ KP-02 در shell:

```sh
export SPECIFY_FEATURE_DIRECTORY="$PWD/specs/002-agent-access"
.specify/scripts/bash/check-prerequisites.sh --json --require-spec --require-tasks --include-tasks
```

یا در پیام چت مسیر `specs/002-agent-access` را صریح بدهید تا ایجنت همین متغیر را برای
helperها تنظیم کند. `.specify/feature.json` اشاره‌گر محلی و ignored است؛ در Git به اشتراک
گذاشته نمی‌شود. تغییر شاخه، feature فعال را عوض نمی‌کند. طبق تصمیم جدید کاربر،
افزودن Spec Kit و برنامه‌ریزی‌های همین مجموعه روی `feat/spec-kit` نگهداری می‌شوند؛ `master` فعلاً
فاقد این تغییرات است و `clasor-agents` تا ساخت اختصاصی کلاسور هم‌سطح خود `master` می‌ماند.
در پایان این تحویل، اشاره‌گر همین checkout به KP-02 برگشت و پیش‌نیازهای آن دوباره بررسی شدند.

پس از انتخاب مرحله توسط کاربر و رفع پیش‌نیازهای آن:

```text
$speckit-implement فقط مرحله و تسک‌های مجاز انتخاب‌شده را اجرا کن.
$speckit-converge پیاده‌سازی و شاهد آزمون را با همهٔ الزامات تطبیق بده.
```

در این تحویل implement و converge برای KP-02 به بعد اجرا نمی‌شوند؛ همهٔ تسک‌های اجرا
باز می‌مانند. دستور `taskstoissues` اجرا نمی‌شود و هیچ issue بیرونی ساخته نشده است.

## تکمیل و نگهداری مستندات

هر بسته spec، research، plan، data-model، contracts، quickstart، tasks و checklist دارد.
نخست رفتار در spec، سپس تصمیم فنی و رابط در plan/contracts، بعد ترتیب کار در tasks تغییر کند.
برای تغییر رفتار، analyze دوباره اجرا شود؛ پیش از اجرای بسته‌های دورتر، خروجی پذیرفته‌شدهٔ
بسته‌های قبلی به طراحی منتقل شود. اسناد فعلی طرح کامل اولیه‌اند و تأیید runtime نیستند.

checklist بررسی کیفیت spec می‌تواند با شاهد متنی علامت بخورد؛ این علامت قبولی اجرا نیست.
تسک فقط پس از انجام کار و ثبت شاهد مربوط علامت می‌خورد. گزارش تحویل باید نسخهٔ سورس،
دستورها، نتایج واقعی، موارد اجرا نشده، migration/rollback، کامیت‌ها و شرط شروع بعدی را ثبت کند.
برای کار مشترک `make check` الزامی است؛ آزمون PostgreSQL و UI جزو خودکار این فرمان نیستند.
برای runtime، Compose، راه‌اندازی، doctor و سناریوی واقعی رابط نیز لازم‌اند.

مدارک گذشته از [فهرست این ترد](kara-thread-record.md) و برنامهٔ آینده از
[فهرست مشخصات](../specs/README.md) در دسترس‌اند. نمونهٔ واقعی Jira هنوز دریافت نشده؛
نگاشت و پذیرش زندهٔ KP-09 باید تا دریافت آن مسدود بماند.

مرجع روش اجرا: [راهنمای رسمی نسخهٔ ثابت](https://github.com/github/spec-kit/blob/v1.2.2/docs/quickstart.md)
و [افزودن به پروژهٔ موجود](https://github.com/github/spec-kit/blob/v1.2.2/docs/guides/existing-projects.md).
