# Current Task

```text
TASK_ID=PALWAKF_WORKSPACE_MANAGER_FOUNDATION_V1
STATUS=SOURCE_CHANGED_PENDING_CI
MODE=CONTROLLED_REPOSITORY_MUTATION
REPOSITORY=firasfanon/palwakf_workspace_manager
BRANCH=agent/workspace-manager-foundation-v1
DATABASE_WRITE=NONE
PRODUCTION_MUTATION=NONE
VERCEL_BUILD_CONFIGURATION=IMPLEMENTED
PREVIEW_DEPLOYMENT=PENDING_BRANCH_PUSH
LOCAL_VALIDATION=PASS
ORCHESTRATOR_BACKEND=IMPLEMENTED
ORCHESTRATOR_CODEX_SDK_SMOKE=PASS
ORCHESTRATOR_CODEX_MCP_SMOKE=PASS
ORCHESTRATOR_AGENTS_LIVE_SMOKE=BLOCKED_RUNTIME_KEY_VISIBILITY
ORCHESTRATOR_OFFLINE_VALIDATION=PASS
FLUTTER_FOUNDATION_REVALIDATION=PASS
```

## الهدف

إنشاء Foundation قابلة للبناء والاختبار للـWorkspace Manager بعقود قراءة فقط، قبل ربط Supabase أو المشاريع الفعلية.

## معايير القبول

- Flutter format/analyze/test/build web تمر في CI.
- لا أسرار أو `.env`.
- Resume Engine يفشل مغلقًا عند Drift أو Baseline غير متحقق أو غياب التفويض.
- توثيق المرجع الأعلى ومصادر الحقيقة.
- Baseline وChangelog وHandoff موجودة.
