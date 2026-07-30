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

## Resolution 002 - 2026-07-30

- The stale Codex Desktop process environment was the root cause.
- Governed launchers now inherit the key from Windows User or Machine scope into
  process memory only when the current process does not already contain it.
- Direct Python and uv-launched Python both report `SET` with source class
  `windows_user_inherited`; the value is never reported.
- Repository dotenv loading was removed.

## Record 003 - OpenAI API project quota unavailable

- **Date:** 2026-07-30.
- **Cause:** The real Agents SDK request returned HTTP 429 with error code
  `insufficient_quota`.
- **Impact:** Agents SDK started a real request, but no planner response,
  execution receipt, Codex thread, final response, or live duplicate replay
  could be produced.
- **Source status:** Runtime inheritance, fail-closed startup, lint, 16 tests,
  offline idempotency, HEAD stability, and secret scans pass.
- **Resolution gate:** Enable API quota for the project associated with the
  inherited key, or explicitly authorize a funded project key, then rerun the
  same governed smoke.
- **Security:** No key value was printed, persisted, copied, or committed.
