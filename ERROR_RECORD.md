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

## Record 002 - Agents runtime credential not visible

- **Date:** 2026-07-30.
- **Cause:** `OPENAI_API_KEY` was not visible to the Python process used for the
  Agents SDK live smoke.
- **Impact:** The live Agents planner call stopped before an API request.
- **Successful isolation:** Codex SDK and Codex MCP read-only live smokes passed
  through the authenticated local Codex runtime.
- **Source status:** Offline lint, tests, health, and both Codex transports pass.
- **Resolution gate:** Inject `OPENAI_API_KEY` into the orchestrator process at
  runtime, then rerun the full Agents-to-Codex dispatch.
- **Security:** No key value was printed, copied, or committed.
