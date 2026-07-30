# Error Record

## Record 001 — Local Flutter toolchain unavailable

- **السبب:** بيئة التنفيذ الحالية لا تحتوي `flutter` أو `dart`.
- **الأثر:** لم يمكن تنفيذ format/analyze/test/build محليًا.
- **ما فشل:** `flutter --version` و`dart --version`.
- **الحل:** إضافة GitHub Actions CI لتنفيذ البوابات على commit المرشح.
- **الملفات المتأثرة:** لا يوجد Source failure؛ حالة Baseline بقيت `CANDIDATE_PENDING_CI`.
- **آخر Baseline مستقر:** لا يوجد Baseline تقني سابق لهذا المستودع؛ هذا أول Candidate.
- **منع التكرار:** لا تتم ترقية Foundation إلى Accepted قبل أدلة CI.

## Resolution 001 - 2026-07-30

- Local Flutter 3.44.1 is available and pinned for CI and Vercel builds.
- Format, analyze, test, and release web build are required before push.
- Foundation status remains candidate pending remote CI and Preview evidence.
