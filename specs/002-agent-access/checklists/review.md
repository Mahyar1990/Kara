# Requirements Review Checklist: KP-02

**Purpose**: بازبینی کیفیت نیازمندی توسط reviewer، پیش از implement.

**Created**: 2026-10-22

**Feature**: [spec.md](../spec.md)

## Completeness and Consistency

- [ ] CHK001 آیا مرز هر سه story و سناریوی مثبت/منفی آن با FRهای مرتبط روشن است؟ [Completeness; Spec §User Scenarios]
- [ ] CHK002 آیا تفاوت مدیریت، run، PO و finalizer بدون اختیار ضمنی نوشته شده است؟ [Clarity; Spec §Requirements; Constitution I]
- [ ] CHK003 آیا همهٔ refs نسخه‌دار و اثر تغییر/ابطال در داده و رابط هم‌معنا هستند؟ [Consistency; data-model; Constitution II]
- [ ] CHK004 آیا خطا، رقابت، تکرار و لغو مجوز outcome قابل مشاهده دارند؟ [Coverage; Spec §Edge Cases; contracts]
- [ ] CHK005 آیا SC-001..004 قابل سنجش‌اند و شاهد آینده از نتیجهٔ انجام‌شده تفکیک شده؟ [Measurability; Spec §Success Criteria]
- [ ] CHK006 آیا dependency و خارج‌محدوده و gate زیر روشن‌اند و شرط شروع را نمی‌پوشانند؟ [Dependencies; Spec §Assumptions]
- [ ] CHK007 آیا متن فارسی/RTL، keyboard و empty/loading/error/conflict برای هر مسیر مشخص‌اند؟ [UX completeness; contracts §UI]
- [ ] CHK008 آیا migration، rollback دارای enforcement و عدم ورود secret به Git صریح‌اند؟ [Safety; plan; data-model]

## Notes

ماتریس ورودی باید هم Community نصب‌شده و هم قابلیت Enterprise استفاده‌شده را جدا ثبت کند؛ Enterprise این محیط تست نشده است. نبود پوشش هر ورودی، مانع فعال‌کردن managed است.

موارد تازه طبق skill رسمی checklist باز مانده‌اند؛ reviewer مالک علامت‌گذاری است. این‌ها تسک پیاده‌سازی یا شاهد پذیرش runtime نیستند.
