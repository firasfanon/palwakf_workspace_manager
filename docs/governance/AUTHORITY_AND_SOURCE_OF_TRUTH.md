# Authority and Source of Truth

| المجال | المصدر الحاكم |
|---|---|
| كود المشروع | مستودع GitHub الصحيح والـcommit المثبت |
| حالة التشغيل | Workspace Manager بعد بناء State Store |
| الوثائق والحوكمة | Google Drive |
| الأدلة التقنية | CI / Runner / Git commit / hashes |
| بيانات PalWakf السيادية | الأنظمة المالكة وفق الدليل الأعلى |

## حدود منصة PalWakf الملزمة

- `waqf_assets` الكيان التشغيلي المركزي، والربط عبر `waqf_asset_id`.
- `awqaf_system` Master Data للأوقاف.
- `mustakshif` للتحليل المكاني والتاريخي فقط.
- `billing_system` للمالية والدفع.
- `cases` للقضايا، مع اتجاه `legal_system` الأوسع.
- `tasks` للمهام.
- `assistant` للمعرفة والمساعدة.
- `core` و`waqf` سياديان.
- `public` للـviews وRPC wrappers فقط، وليس لجداول الأساس.

## قاعدة التعارض

```text
PALWAKF_PLATFORM_COMPREHENSIVE_GUIDE.md
> العقود السيادية المعتمدة
> الواقع التقني المثبت
> سجل Workspace Manager
> ملفات التوريث
> ذاكرة المحادثة
```
