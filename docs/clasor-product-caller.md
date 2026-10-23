# caller تخصصی کلاسور و بررسی API پایلوت

**وضعیت: اتصال HTTP و ذخیره/بازخوانی پیش‌نویس واقعی بررسی شد؛ تکمیل ورودی TL روی API واقعی هنوز ممکن نشده است.** مرحلهٔ موجود پایلوت failed، با صفر Artifact معتبر و صفر تصمیم نهایی است و مرحلهٔ planning در آن فلو وجود ندارد. هیچ تصمیم PO برای عبور آزمون ساخته نشده است.

[caller.py](../clasor_agents/product_flow/caller.py) لایهٔ HTTP برای [نگاشت و پیش‌پرواز](clasor-product-flow.md) است. فقط کتابخانهٔ استاندارد Python استفاده می‌شود؛ کاربر، workspace و عضویت از نشست واقعی سرور خوانده می‌شوند. خطاهای HTTP/شبکه کد کوتاه دارند؛ بدنهٔ پاسخ، password، cookie و توکن در متن خطا بازنشر نمی‌شوند. redirect رد می‌شود، TLS بررسی می‌شود و HTTP فقط برای loopback پذیرفته است.

## عملیات در دسترس

| تابع | اثر |
| --- | --- |
| login(email, password) | ورود بومی، cookie در حافظه؛ password طبق API بومی Base64 می‌شود، این رمزنگاری نیست |
| enter(workspace_id) | انتخاب پروژهٔ تعیین‌شده و تطبیق workspace پاسخ |
| actor(account_id, workspace_id) | GET profile/context/roles و دریافت incarnation عضویت جاری |
| options() | GET گزینه‌های ساخت فلو در همان پروژه؛ برای کاربر عادی ممکن است ۴۰۳ باشد |
| snapshot(request_id, instance_id, stage_id) | خواندن درخواست، خلاصهٔ اجرای همان پرونده و جزئیات مجاز مرحله |
| published_binding(instance, step_key) | خواندن FlowVersion دقیق و تطبیق digest؛ مرحلهٔ غایب رد می‌شود |
| save_draft(body, key, flow_id=None) | POST/PUT پیش‌نویس و GET مستقل برای تطبیق محتوا، revision و حفظ اشاره‌گر انتشار |
| prepare_setup(...) | خواندن تازه، تعیین مسئول از نشست و ساخت packet اولیهٔ TL؛ بدون نوشتن |
| apply_setup(...) | خواندن مجدد، مقایسه با packet ذخیره‌شده، فقط POST feedback آماده‌سازی و GET مستقل؛ سپس پیش‌پرواز |

محدودهٔ transport عمداً endpoint اجرای مدل، retry مرحله، finalize، request_decision، تصمیم ورود PO و انتشار فلو/Workflow را ندارد. خروجی apply_setup صرفاً verified و بدنه/کلید پیشنهادی run برای بررسی بعدی است؛ این بدنه ارسال نمی‌شود. خواندن FlowVersion جای بررسی برابری Workflow نصب‌شده با export را نمی‌گیرد.

برای استفاده، در caller مورد اعتماد پس از خواندن تنظیمات خصوصی:

```python
from clasor_agents.product_flow.caller import Caller
client = Caller(config['origin'], config['project_id'])
client.login(config['email'], config['password'])
client.enter(config['workspace_id'])
actor = client.actor(config['account_id'], config['workspace_id'])
```

config باید از فایل خصوصی خارج Git بیاید؛ مقدار واقعی credential در کد/فرمان یا stdout قرار نگیرد. نمونهٔ عمومی عمداً credential، شناسهٔ حساب واقعی یا فایل cookie ندارد. cookiejar فقط در حافظه است و نشست منقضی‌شده خودکار به حساب دیگری تبدیل یا retry نمی‌شود. استفاده از هویت سرور/توکن مدیر برای جعل مسئول مرحله در این caller وجود ندارد.

برای ساخت، بدنهٔ bind یا template را با Idempotency-Key مستقل به save_draft بدهید؛ قالب ناقص فقط برای ذخیره و بازبینی است و قابل انتشار نیست. پیش از ارسال، body و کلید را خصوصی ذخیره کنید. اگر نتیجهٔ شبکه نامشخص بود، همان کلید و بدنهٔ عملیات را دوباره استفاده کنید؛ caller کلید تازه را به جای retry عملیات قبلی نمی‌سازد و خودش retry خودکار ندارد.

برای TL، ابتدا prepare_setup و packet کامل آن را با دسترسی 0600 ذخیره کنید. apply_setup به همان package معتبر PA-04 و همان account/workspace نیاز دارد؛ یک بار قبل از POST دوباره snapshot و binding را می‌خواند و packet را بازسازی/تطبیق می‌دهد. فقط feedback آماده‌سازی نخستین ورودی، با کلید ذخیره‌شده، ارسال می‌شود. بعد از POST، پاسخ mutation به‌تنهایی شاهد قبولی نیست و GET مستقل + planning_run لازم است. در صورت قطع ارتباط پس از ثبت، فراخوانی مجدد با همان packet می‌تواند از readback ثابت کند ثبت قبلاً انجام شده است؛ ثبت دوم یا اجرای مدل خودکار انجام نمی‌شود. تغییر نسخه/مسئول/رسید/ورودی باعث خطا است.

## شواهد این گام

در ۲۳ اکتبر ۲۰۲۶، روی پایلوت محلی موجود و با حساب‌های ساختگیِ قبلی:

- ورود بومی PO، TL و عضو بدون مجوز و تطبیق پروژه/عضویت موفق شد؛ نشست یا رمز در Git ثبت نشد.
- options واقعی دو ایجنت قابل مشاهده برای PO داشت. یک **پیش‌نویس ناقص دومرحله‌ای و منتشرنشده** با API ذخیره و محتوای آن با GET مستقل تطبیق داده شد؛ شناسه‌های مسئول/ایجنتِ حل‌نشده به جای حدس null ماندند. هیچ Workflow یا فلویی منتشر نشد.
- درخواست/اجرای قبلی از API خوانده شد: analysis در failed، صفر Artifact و تصمیم نهایی و نبود planning. خواندن binding برنامه‌ریزی به caller_binding_missing رسید؛ ساخت/ارسال ورودی TL بر این مبنا انجام نشد.
- API options برای TL و عضو بدون مجوز، هر دو ۴۰۳ داد؛ حساب عادی برای کار تخصصی editor نشد.
- state/revision/round، attempts، artifacts، feedback و decisions مرحلهٔ قبلی پیش و پس از smoke برابر ماندند. لاگ، پاسخ‌ها و شناسهٔ پیش‌نویس در `.runtime/clasor-product-http/` با دسترسی خصوصی حفظ شدند.

این شاهد، ثبت ورودی TL یا پذیرش واقعی PO → TL نیست. نمی‌توان مرحلهٔ شکست‌خورده را با پاسخ fixture یا تصمیم آزمایشی به تحلیل مصوب تبدیل کرد. به همین دلیل مسیر موفق apply_setup با replay ساختگی در آزمون واحد بررسی شد و موفقیت زندهٔ آن ادعا نمی‌شود.

make check نهایی با ۱۱۷ آزمون موفق شد. هفت آزمون متمرکز transport شامل محدودیت عملیات، redirect/origin، عدم نشت خطا، هویت نشست، CSRF/idempotency، حفظ انتشار در readback پیش‌نویس و مسیر آماده‌سازی/بازیابی بدون dispatch هستند. API عمومی، upstream و رابط محصول تغییر نکردند؛ smoke کلاینت موضوعیت نداشت. سرویس موجود فقط خوانده/استفاده شد و rebuild یا migration انجام نشد.

[تعریف‌های بومی دو نقش](clasor-native-definitions.md) اکنون در نسخه‌های مستقل آماده و ثبت شده‌اند و پیش‌نویس فلو تکمیل شده است؛ گزارش این بخش مربوط به smoke پیش از آن آماده‌سازی است. هر انتشار فلو باید به نسخهٔ دقیق و اختیار سازنده مقید باشد. گیت انسانی PO و پذیرش معنایی PA-04، مانع واقعی رسیدن TL به تحویل معتبر باقی می‌مانند. رفع metadata پایان مدل، حفظ اصل درخواست و hook عمومی پیش از finalize همچنان متعلق به master هستند.
