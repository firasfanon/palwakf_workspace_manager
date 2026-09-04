import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/app/workspace_manager_app.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/application/orchestrator_controller.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/data/orchestrator_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/domain/orchestrator_models.dart';

class FakeOrchestratorApi implements OrchestratorApi {
  FakeOrchestratorApi({
    this.tools = const <ToolOperationalHealth>[],
    this.alerts = const <ToolHealthAlert>[],
  });

  final List<ToolOperationalHealth> tools;
  final List<ToolHealthAlert> alerts;

  @override
  Future<RuntimeCapabilities> capabilities() async {
    return const RuntimeCapabilities(
      version: 'SELF_HOSTING_OPERATIONAL_LOOP_V1',
      taskLifecycle: true,
      manualRelayFallback: true,
      capabilityRouting: true,
      toolDecisionTrace: true,
      reconciliation: true,
      automaticAgentsAvailable: false,
      databaseConnected: false,
      productionMutation: false,
    );
  }

  @override
  Future<List<OperatorTask>> listTasks() async => const <OperatorTask>[];

  @override
  Future<List<ToolOperationalHealth>> toolsHealth() async => tools;

  @override
  Future<ToolOperationalHealth> toolHealth(String adapterId) =>
      throw UnimplementedError();

  @override
  Future<List<ToolHealthAlert>> toolAlerts() async => alerts;

  @override
  Future<ToolOperationalHealth> probeTool(String adapterId) =>
      throw UnimplementedError();

  @override
  Future<OperatorTask> cancel(String taskId) => throw UnimplementedError();

  @override
  Future<OperatorTask> continueTask(String taskId) =>
      throw UnimplementedError();

  @override
  Future<OperatorTask> createTask(TaskDraft draft) =>
      throw UnimplementedError();

  @override
  Future<OperatorTask> createProofTask() => throw UnimplementedError();

  @override
  Future<OperatorTask> authorize(OperatorTask task) =>
      throw UnimplementedError();

  @override
  Future<OperatorTask> dispatch(String taskId) => throw UnimplementedError();

  @override
  Future<ManualDispatchPackage> generateManualPackage(String taskId) =>
      throw UnimplementedError();

  @override
  Future<OperatorTask> importManualResult({
    required String taskId,
    required Map<String, dynamic> result,
  }) =>
      throw UnimplementedError();

  @override
  Future<OperatorTask> markManualDispatched({
    required String taskId,
    required String packageReceipt,
  }) =>
      throw UnimplementedError();

  @override
  Future<ToolPlan> planTools(String taskId) => throw UnimplementedError();

  @override
  Future<OperatorTask> recordManualAcknowledgement({
    required String taskId,
    required String packageReceipt,
    required String threadReference,
  }) =>
      throw UnimplementedError();

  @override
  Future<OperatorTask> taskStatus(String taskId) => throw UnimplementedError();

  @override
  Future<ToolPlan> toolDecisions(String taskId) => throw UnimplementedError();

  @override
  Future<List<ToolInvocation>> toolInvocations(String taskId) =>
      throw UnimplementedError();

  @override
  Future<ToolReconciliation> toolReconciliation(String taskId) =>
      throw UnimplementedError();

  @override
  Future<OperatorTask> verify({
    required String taskId,
    required String receipt,
    required String head,
  }) =>
      throw UnimplementedError();
}

void main() {
  testWidgets('operator workspace renders capability state and safe actions', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          orchestratorApiProvider.overrideWithValue(FakeOrchestratorApi()),
        ],
        child: const WorkspaceManagerApp(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('الإدارة المتقدمة'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('مركز التشغيل'));
    await tester.pumpAndSettle();

    expect(find.text('صف المهام'), findsOneWidget);
    expect(find.text('ترحيل المستخدم'), findsOneWidget);
    expect(find.text('قدرات التشغيل'), findsOneWidget);
    expect(find.text('الوكلاء الآليون'), findsOneWidget);
    expect(find.text('قاعدة البيانات'), findsOneWidget);
    expect(find.text('محجوب'), findsWidgets);
    expect(find.byTooltip('مهمة جديدة'), findsOneWidget);
    expect(find.byTooltip('إنشاء مهمة الإثبات الذاتي'), findsOneWidget);
    expect(find.text('Merge'), findsNothing);
    expect(find.text('Production'), findsNothing);
  });

  testWidgets('tool operational health dashboard is reachable', (tester) async {
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          orchestratorApiProvider.overrideWithValue(FakeOrchestratorApi()),
        ],
        child: const WorkspaceManagerApp(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('الإدارة المتقدمة'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('الأدوات'));
    await tester.pumpAndSettle();

    expect(find.text('الأدوات'), findsWidgets);
    expect(find.text('سجل الأدوات'), findsOneWidget);
    expect(find.text('لا توجد بيانات مصادق عليها'), findsOneWidget);
  });

  testWidgets('tools surface separates Codex relay authority from development',
      (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1280, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    const unknown =
        HealthFact(value: null, provenance: 'NOT_EXPOSED_BY_PROVIDER');
    const codex = ToolOperationalHealth(
      adapterId: 'codex',
      displayName: 'Codex',
      requiredAdapter: true,
      connection: unknown,
      authentication:
          HealthFact(value: 'SET', provenance: 'VERIFIED_RUNTIME_PROBE'),
      permission:
          HealthFact(value: 'authorized', provenance: 'VERIFIED_PLATFORM_UI'),
      entitlement: unknown,
      quota:
          HealthFact(value: 'AVAILABLE', provenance: 'VERIFIED_RUNTIME_PROBE'),
      usage: unknown,
      cost: unknown,
      balance: unknown,
      creditExpiry: unknown,
      renewal: unknown,
      rateLimit: unknown,
      freshness: HealthFact(value: 'fresh', provenance: 'VERIFIED_PLATFORM_UI'),
      operatorActions: <String>[],
      evidence: <String>[],
      roleAuthorities: <String, String>{
        'autonomous_development': 'SUSPENDED',
        'governed_patch_relay': 'AUTHORIZED_GOVERNED_SCOPE',
        'git_transport': 'AUTHORIZED_GOVERNED_SCOPE',
      },
    );
    final alert = ToolHealthAlert(
      alertId: 'github-authentication',
      adapterId: 'github',
      severity: 'warning',
      code: 'AUTHENTICATION_UNVERIFIED',
      message: 'لا توجد أدلة حالية تثبت مصادقة الأداة أو المزود.',
      operatorAction: 'شغّل فحصًا موثقًا للمصادقة دون عرض أي قيمة سرية.',
      observedAt: DateTime.utc(2026, 8, 15),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          orchestratorApiProvider.overrideWithValue(
            FakeOrchestratorApi(
              tools: const <ToolOperationalHealth>[codex],
              alerts: <ToolHealthAlert>[alert],
            ),
          ),
        ],
        child: const WorkspaceManagerApp(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('الإدارة المتقدمة'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('الأدوات'));
    await tester.pumpAndSettle();

    expect(find.text('نقل Git/patch محكوم · التطوير المستقل موقوف'),
        findsOneWidget);
    expect(find.textContaining('SET · AVAILABLE'), findsNothing);
    expect(
        find.textContaining('لا توجد أدلة حالية تثبت مصادقة الأداة أو المزود.'),
        findsOneWidget);
    expect(find.textContaining('شغّل فحصًا موثقًا للمصادقة'), findsOneWidget);
    expect(find.text('AUTHENTICATION_UNVERIFIED'), findsOneWidget);
  });
}
