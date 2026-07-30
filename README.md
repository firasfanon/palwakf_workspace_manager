# PalWakf Workspace Manager

منصة **PalWakf Workspace Manager / Sovereign Control Plane** هي الذاكرة التشغيلية الدائمة لمحفظة مشاريع PalWakf.  
جلسة ChatGPT واجهة محادثية قابلة للاستبدال، بينما يحتفظ هذا النظام بحالة المشاريع والمهام والـBaselines والأدلة ونقاط الاستئناف.

## حالة الأساس

```text
FOUNDATION_VERSION=0.1.0
FOUNDATION_STATUS=CANDIDATE_PENDING_CI
DATABASE_WRITE=NONE
PRODUCTION_MUTATION=NONE
SECRET_VALUES=FORBIDDEN
INITIAL_ADAPTERS=READ_ONLY
ARABIC_RTL_FIRST=TRUE
```

## الأدوار الحاكمة

```text
GitHub        = Source of technical truth
Supabase      = Future operational state store
Google Drive  = Governance documents and evidence
Local Runner  = Future restricted runtime/UAT plane
ChatGPT       = Reasoning and orchestration interface
```

## المرجع الأعلى لمنصة PalWakf

لا ينسخ هذا المستودع الدليل الحاكم ولا يحل محله. المرجع المثبت:

```text
repository: firasfanon/palwakf
ref: 0f7d053bb45c66ff911ddfa17127a1036074330d
path: PALWAKF_PLATFORM_COMPREHENSIVE_GUIDE.md
```

راجع `docs/governance/PLATFORM_GUIDE_PIN.md`.

## حدود Foundation V1

- نموذج نطاق للمشاريع والمهام والـBaselines والأدلة والانحرافات.
- Reality Gate وDrift Gate وAuthorization Gate.
- Resume Engine حتمي وقابل للاختبار.
- واجهة Flutter Web عربية RTL لعرض حالة الأساس.
- عقود قراءة فقط؛ لا اتصال فعلي بقاعدة بيانات.
- CI للفحص والتنسيق والتحليل والاختبارات وبناء Web.

## التشغيل المحلي

```bash
flutter pub get
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
flutter build web --release
```

## قواعد أمنية

- لا تخزن `.env` أو مفاتيح Supabase أو GitHub أو Google.
- لا تستخدم `service_role` في Flutter.
- لا تنشئ جداول تشغيلية في `public`.
- لا تعتبر ادعاء Baseline دليلًا دون `commit/hash/archive`.
- أي Mutation مستقبلية تتطلب تفويضًا صريحًا وأثر تدقيق.

## Orchestrator Backend V1

The local backend under `orchestrator/` provides a governed communication plane
from OpenAI Agents SDK to Codex SDK or Codex MCP.

```text
ORCHESTRATOR_REMOTE_DEPLOYMENT=FALSE
ORCHESTRATOR_DATABASE_WRITE=FALSE
ORCHESTRATOR_PRODUCTION_MUTATION=FALSE
ORCHESTRATOR_CODEX_SANDBOX=READ_ONLY
ORCHESTRATOR_CODEX_APPROVALS=DENY_ALL
```

The backend verifies the repository branch, clean worktree, local HEAD, and
remote HEAD before every dispatch. See `orchestrator/README.md`.

## Self-Hosting Operational Loop V1

The first screen is an Arabic RTL operator workspace backed by typed local HTTP
contracts for task creation, dispatch, status, continue, cancel, independent
verification, manual relay, capability routing, tool decisions, invocation
receipts, and planned-versus-actual reconciliation.

```text
AUTOMATIC_MODE=PRIMARY
USER_RELAY_FALLBACK=CONTROLLED
USER_RELAY_IS_AUTOMATIC_ACCEPTANCE=FALSE
DATABASE_CONNECTED=FALSE
PRODUCTION_ACTIONS=ABSENT
```

The Flutter client reads its non-secret API base URL from
`ORCHESTRATOR_API_BASE_URL` through `--dart-define`. The default is the local
loopback service at `http://127.0.0.1:8421`.

Service bearer values are entered at runtime and remain in Flutter application
memory. They are not accepted through `--dart-define` and are not embedded in
`build/web`. The connected service, OAuth/JWKS remote gate, MCP tools, and Tool
Operational Health model are specified in
`docs/contracts/CONNECTED_SERVICE_AND_CHATGPT_MCP_V1.md`.
