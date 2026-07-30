# Control Plane Architecture V1

## الهدف

فصل حالة العمل الدائمة عن جلسة المحادثة وربط كل قرار أو استئناف بواقع تقني قابل للتحقق.

```text
ChatGPT / Human Operator
          |
          v
Workspace Manager
  |-- Registry
  |-- Resume Engine
  |-- Reality Gate
  |-- Drift Gate
  |-- Authorization Gate
  |-- Evidence / Checkpoint
          |
          +--> GitHub Adapter (read first)
          +--> Drive Adapter (governance/evidence)
          +--> Supabase Adapter (future dev state store)
          +--> Restricted Local Runner (future)
```

## الطبقات

1. **Domain:** مشاريع، مستودعات، مهام، Baselines، أدلة، Drift، Resume.
2. **Application:** بوابات حتمية وسياسات Fail-Closed.
3. **Adapters:** قراءة GitHub/Drive أولًا، ثم كتابة محكومة في مراحل مستقلة.
4. **Presentation:** Flutter Web عربية RTL.
5. **Evidence:** أحداث غير قابلة لإعادة التفسير مرتبطة بـcommit/hash.

## القرار التقني الأولي

- Flutter Web للواجهة، باستخدام `flutter_riverpod.dart` وGoRouter.
- لا يستخدم `legacy.dart`.
- Supabase مرشح State Store لاحق، وليس جزءًا من Foundation V1.
- لا SQL Apply ولا اتصال إنتاج في هذه الدفعة.
- GitHub هو مصدر الحقيقة للكود.
- Google Drive هو سجل الحوكمة والأدلة، لا State Machine تشغيلية.

## الكيانات المركزية

```text
Project
Repository
Task
ExecutionRun
VerificationResult
Baseline
Evidence
Blocker
Drift
ResumeState
Event
```

## سياسة الفشل

أي نقص في HEAD أو Baseline أو تفويض أو Drift مرتفع يؤدي إلى:

```text
FAIL_CLOSED
NO_MUTATION
REPORT_BLOCKER
WRITE_EVIDENCE_AFTER_AUTHORIZATION_ONLY
```
