# Resume Protocol V1

## الإدخال

```yaml
project_key:
repository:
expected_head:
actual_head:
baseline_id:
baseline_status:
task_id:
task_status:
authorization_mode:
open_drifts:
requested_operation:
```

## التسلسل

1. قراءة آخر Checkpoint.
2. قراءة حقيقة المستودع وHEAD.
3. مقارنة HEAD المتوقع والفعلي.
4. التحقق من Baseline.
5. التحقق من المهمة الحالية.
6. فحص Drift المفتوح.
7. فحص التفويض.
8. إنشاء خطة استئناف حتمية.
9. تنفيذ Mutation فقط عند تفويض صريح.
10. التقاط الأدلة وكتابة Checkpoint جديد.

## حالات المنع

```text
REPOSITORY_NOT_REACHABLE
REMOTE_HEAD_NOT_VERIFIED
REMOTE_HEAD_DRIFT_DETECTED
BASELINE_NOT_VERIFIED
UNRESOLVED_DRIFT:<id>
EXPLICIT_MUTATION_AUTHORIZATION_REQUIRED
```

## قاعدة «استكمل العمل»

العبارة الطبيعية لا تعني تفويضًا عامًا للكتابة. هي تفويض لقراءة الحالة، التحقق من الواقع، وإعداد أو متابعة العملية داخل حدود التفويض المسجل.
