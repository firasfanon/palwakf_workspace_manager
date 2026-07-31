# PalWakf Workspace Manager

منصة **PalWakf Workspace Manager / Sovereign Control Plane** هي الذاكرة التشغيلية الدائمة لمحفظة مشاريع PalWakf.  
جلسة ChatGPT واجهة محادثية قابلة للاستبدال، بينما يحتفظ هذا النظام بحالة المشاريع والمهام والـBaselines والأدلة ونقاط الاستئناف.

## الحالة التشغيلية

```text
FOUNDATION_VERSION=0.1.0
FOUNDATION_STATUS=OPERATIONAL_DASHBOARD_CANDIDATE
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

## مساحة العمليات

- نموذج نطاق للمشاريع والمهام والـBaselines والأدلة والانحرافات.
- Reality Gate وDrift Gate وAuthorization Gate.
- Resume Engine حتمي وقابل للاختبار.
- واجهة Flutter Web عربية RTL بصفحة عمليات رئيسية ومسارات موحدة.
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

## Main Dashboard and Operations Shell V1

The operational root is `/dashboard`. The responsive Arabic RTL shell exposes:

```text
/dashboard
/projects
/projects/{project_id}
/tasks
/tools
/tools/{adapter_id}
/alerts
/evidence
/settings/connections
```

Dashboard data is read from the existing authoritative task, project, tool
health, connected-service, audit, checkpoint, and repository-evidence stores.
Unavailable provider values remain `UNKNOWN`; evidence responses expose bounded
relative references only.

```text
GET /v1/dashboard/summary
GET /v1/dashboard/activity?limit=30
GET /v1/alerts
GET /v1/evidence?limit=50
```

The same reads are available to authenticated MCP clients. No public
unauthenticated endpoint is created.

## Self-Hosting Operational Loop V1

The `/tasks` screen is an Arabic RTL operator workspace backed by typed local HTTP
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

## External Project Intake and Reality Adapter V1

The authenticated Orchestrator now registers external repositories and produces
bounded read-only reality baselines through:

```text
POST /v1/projects/intake
GET  /v1/projects
GET  /v1/projects/{project_id}
POST /v1/projects/{project_id}/probe
GET  /v1/projects/{project_id}/reality
GET  /v1/projects/{project_id}/candidate-work-items
POST /v1/projects/{project_id}/prepare-task
```

GitHub probing reads repository identity, immutable HEAD, a bounded file tree,
safe metadata files, and CI status. Secret-risk file names may be reported, but
their values are never read. Local Git probing is disabled unless the resolved
repository root exactly matches `PALWAKF_LOCAL_PROJECT_ALLOWLIST_JSON`.

The first live baseline covers `firasfanon/Pal_Eyes` in
`READ_ONLY_ZERO_MUTATION` mode. Supabase remains blocked even when repository
indicators exist, and prepare-task creates no execution.
