import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:palwakf_workspace_manager/src/app/workspace_application_shell.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/application/execution_run_controller.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/application/engineering_os_controller.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/data/engineering_os_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/domain/engineering_os_models.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/domain/execution_run_models.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/presentation/task_board_page.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/application/orchestrator_controller.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/application/operational_authorization.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/data/orchestrator_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/domain/orchestrator_models.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/presentation/orchestrator_workspace_page.dart';

const parentTask = EngineeringTask(
  taskId: 'WM-PHASE6-ENG-001',
  title: 'تشغيل مهمة محكومة',
  description: 'Vertical slice task',
  projectId: 'PALWAKF_WORKSPACE_MANAGER',
  repository: 'firasfanon/palwakf_workspace_manager',
  baseSha: '343e85ba7578758859e3919d638e339fb45d7427',
  taskBranch: 'task/WM-GOVERNED-TASK-EXECUTION-VERTICAL-SLICE-PHASE6-V1',
  ownerId: 'firas',
  actorId: 'firas',
  actorType: 'HUMAN',
  status: 'READY',
  scopePatterns: <String>['lib/**', 'orchestrator/**', 'test/**'],
  dependsOn: <String>[],
  dependencyMode: 'INDEPENDENT',
  riskClass: 'HIGH',
  mutationClass: 'source-write',
  requiredCapabilities: <String>['source.control'],
  requiredTests: <String>['targeted', 'regression'],
  wipCheckpointStatus: 'NOT_CHECKPOINTED',
  integrationStatus: 'NOT_READY',
);

OperatorTask operatorTask() {
  final now = DateTime.utc(2026, 8, 19);
  return OperatorTask(
    taskId: 'WM_PHASE6_RUN_001',
    projectId: parentTask.projectId,
    repository: parentTask.repository,
    branch: parentTask.taskBranch,
    expectedHead: parentTask.baseSha,
    authorityReference: 'AUTHORITY://PHASE6/GOVERNED_EXECUTION',
    prompt: 'Execute the bounded Phase6 run.',
    constraints: const <String>['NO_SCOPE_EXPANSION'],
    sandbox: 'workspace-write',
    maxTurns: 6,
    timeoutSeconds: 1800,
    idempotencyKey: 'phase6.run.001',
    dispatchMode: 'automatic',
    status: OrchestratorTaskStatus.pending,
    createdAt: now,
    updatedAt: now,
    lastEvent: 'TASK_CREATED',
    events: const <TaskEvent>[],
    changedFiles: const <String>[],
    tests: const <String>[],
    evidence: const <String>[],
    requiresExplicitAuthorization: true,
    automaticFailureCode: 'AUTOMATIC_EXECUTION_PROVIDER_NOT_AUTHORIZED',
    scopePatterns: const <String>['lib/**', 'orchestrator/**', 'test/**'],
    relayProviderId: 'chatgpt',
  );
}

EngineeringExecutionRunView runView() {
  return EngineeringExecutionRunView(
    executionRunId: 'WM_PHASE6_RUN_001',
    legacyOperatorTaskId: 'WM_PHASE6_RUN_001',
    parentEngineeringTaskId: parentTask.taskId,
    parentTask: parentTask,
    operatorTask: operatorTask(),
    rollup: const ExecutionRunRollup(
      parentTaskId: 'WM-PHASE6-ENG-001',
      operatorTaskId: 'WM_PHASE6_RUN_001',
      parentStatus: 'READY',
      runStatus: 'pending',
      signal: 'PENDING',
      automaticParentTransition: false,
      allowedExplicitParentTargets: <String>[],
      reservedRunState: false,
      reason: 'Run-local state does not mutate the parent automatically.',
    ),
  );
}

class FakePhase6EngineeringOsApi extends EngineeringOsApiClient {
  FakePhase6EngineeringOsApi() : super(baseUrl: 'http://127.0.0.1:1');

  int createRunCalls = 0;
  NewExecutionRunDraft? lastDraft;

  @override
  Future<EngineeringOsSummary> summary() async {
    return const EngineeringOsSummary(
      parallelTracks: <String>[],
      tasksByStatus: <String, int>{'READY': 1},
      extensionsByKind: <String, int>{},
      quarantinedExtensions: 0,
      remoteCheckpointedTasks: 0,
    );
  }

  @override
  Future<List<EngineeringTask>> tasks() async =>
      const <EngineeringTask>[parentTask];

  @override
  Future<List<ExtensionRecord>> extensions() async => const <ExtensionRecord>[];

  @override
  Future<EngineeringTaskExecutionContext> executionContext(
      String taskId) async {
    expect(taskId, parentTask.taskId);
    return EngineeringTaskExecutionContext(
      parentTask: parentTask,
      runs: createRunCalls == 0
          ? const <EngineeringExecutionRunView>[]
          : <EngineeringExecutionRunView>[runView()],
    );
  }

  @override
  Future<EngineeringExecutionRunView> createExecutionRun(
    String taskId,
    NewExecutionRunDraft draft,
  ) async {
    expect(taskId, parentTask.taskId);
    expect(draft.relayProviderId, 'chatgpt');
    lastDraft = draft;
    createRunCalls += 1;
    return runView();
  }
}

class FakePhase6OrchestratorApi implements OrchestratorApi {
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
  Future<List<ToolOperationalHealth>> toolsHealth() async =>
      const <ToolOperationalHealth>[];

  @override
  Future<List<ToolHealthAlert>> toolAlerts() async => const <ToolHealthAlert>[];

  @override
  Future<OperatorTask> authorize(OperatorTask task) =>
      throw UnimplementedError();

  @override
  Future<OperatorTask> cancel(String taskId) => throw UnimplementedError();

  @override
  Future<OperatorTask> continueTask(String taskId) =>
      throw UnimplementedError();

  @override
  Future<OperatorTask> createProofTask() => throw UnimplementedError();

  @override
  Future<OperatorTask> createTask(TaskDraft draft) =>
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
  Future<ToolOperationalHealth> probeTool(String adapterId) =>
      throw UnimplementedError();

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
  Future<ToolPlan> toolDecisions(String taskId) async {
    throw OrchestratorApiException(
      code: 'HTTP_404',
      message: 'Tool decisions are not persisted in this test.',
      recoverable: true,
    );
  }

  @override
  Future<ToolOperationalHealth> toolHealth(String adapterId) =>
      throw UnimplementedError();

  @override
  Future<List<ToolInvocation>> toolInvocations(String taskId) async {
    throw OrchestratorApiException(
      code: 'HTTP_404',
      message: 'Tool invocations are not persisted in this test.',
      recoverable: true,
    );
  }

  @override
  Future<ToolReconciliation> toolReconciliation(String taskId) async {
    throw OrchestratorApiException(
      code: 'HTTP_404',
      message: 'Tool reconciliation is not persisted in this test.',
      recoverable: true,
    );
  }

  @override
  Future<OperatorTask> verify({
    required String taskId,
    required String receipt,
    required String head,
  }) =>
      throw UnimplementedError();
}

const phase6Authorization = OperationalAuthorizationContext(
  clientId: 'phase6-test',
  scopes: <String>['tasks:read', 'tasks:dispatch'],
  readOnly: false,
  canDispatch: true,
  canContinue: true,
  canCancel: true,
  canVerify: true,
  canProbeTools: false,
);

void main() {
  testWidgets('engineering task carries its identity into the operations route',
      (tester) async {
    tester.view.physicalSize = const Size(1280, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final router = GoRouter(
      initialLocation: '/tasks',
      routes: <RouteBase>[
        ShellRoute(
          builder: (context, state, child) => WorkspaceApplicationShell(
            location: state.uri.path,
            child: child,
          ),
          routes: <RouteBase>[
            GoRoute(
              path: '/tasks',
              builder: (context, state) => const EngineeringTaskBoardPage(),
            ),
            GoRoute(
              path: '/operations',
              builder: (context, state) => Center(
                child: Text(
                  'PARENT=${state.uri.queryParameters['engineeringTaskId']}',
                ),
              ),
            ),
          ],
        ),
      ],
    );
    addTearDown(router.dispose);

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          engineeringOsApiProvider.overrideWithValue(
            FakePhase6EngineeringOsApi(),
          ),
          operationalAuthorizationProvider.overrideWith(
            (ref) async => phase6Authorization,
          ),
        ],
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    final bridge = find.byKey(
      const ValueKey<String>('engineering-task-operations-WM-PHASE6-ENG-001'),
    );
    expect(bridge, findsOneWidget);
    await tester.ensureVisible(bridge);
    await tester.tap(bridge);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('PARENT=WM-PHASE6-ENG-001'), findsOneWidget);
  });

  test('execution context controller creates a run and refreshes real context',
      () async {
    final api = FakePhase6EngineeringOsApi();
    final container = ProviderContainer(
      overrides: <Override>[
        engineeringOsApiProvider.overrideWithValue(api),
      ],
    );
    addTearDown(container.dispose);

    final notifier = container.read(
      executionRunContextControllerProvider(parentTask.taskId).notifier,
    );
    await notifier.load();
    expect(
      container
          .read(executionRunContextControllerProvider(parentTask.taskId))
          .context!
          .runs,
      isEmpty,
    );

    final created = await notifier.create(
      const NewExecutionRunDraft(
        executionRunId: 'WM_PHASE6_RUN_001',
        authorityReference: 'AUTHORITY://PHASE6/GOVERNED_EXECUTION',
        prompt: 'Execute one bounded governed Phase6 source change.',
        constraints: <String>['NO_SCOPE_EXPANSION'],
        sandbox: 'workspace-write',
        maxTurns: 6,
        timeoutSeconds: 1800,
        idempotencyKey: 'phase6.run.001',
        relayProviderId: 'chatgpt',
        providerMode: 'bounded_bug_fix',
      ),
    );

    expect(created.executionRunId, 'WM_PHASE6_RUN_001');
    expect(api.lastDraft!.providerMode, 'bounded_bug_fix');
    expect(api.lastDraft!.toJson()['provider_mode'], 'bounded_bug_fix');
    final refreshed = container.read(
      executionRunContextControllerProvider(parentTask.taskId),
    );
    expect(
      refreshed.context!.runs.single.operatorTask.branch,
      parentTask.taskBranch,
    );
    expect(
      refreshed.context!.runs.single.operatorTask.relayProviderId,
      'chatgpt',
    );
    expect(
      refreshed.context!.runs.single.rollup.automaticParentTransition,
      isFalse,
    );
  });

  test('execution run draft defaults provider mode for legacy callers', () {
    const draft = NewExecutionRunDraft(
      executionRunId: 'WM_PHASE6_RUN_001',
      authorityReference: 'AUTHORITY://PHASE6/GOVERNED_EXECUTION',
      prompt: 'Execute one bounded governed Phase6 source change.',
      constraints: <String>['NO_SCOPE_EXPANSION'],
      sandbox: 'workspace-write',
      maxTurns: 6,
      timeoutSeconds: 1800,
      idempotencyKey: 'phase6.run.001',
      relayProviderId: 'chatgpt',
    );

    expect(draft.providerMode, 'execution_relay');
    expect(draft.toJson()['provider_mode'], 'execution_relay');
  });

  testWidgets('operations run dialog sends governed provider mode selection',
      (tester) async {
    tester.view.physicalSize = const Size(1280, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final api = FakePhase6EngineeringOsApi();
    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          engineeringOsApiProvider.overrideWithValue(api),
          orchestratorApiProvider
              .overrideWithValue(FakePhase6OrchestratorApi()),
          operationalAuthorizationProvider.overrideWith(
            (ref) async => phase6Authorization,
          ),
        ],
        child: const MaterialApp(
          home: OrchestratorWorkspacePage(
            engineeringTaskId: 'WM-PHASE6-ENG-001',
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    await tester.tap(
      find.byKey(
        const ValueKey<String>('phase6-create-governed-execution-run'),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.enterText(
      find.byKey(const ValueKey<String>('phase6-run-prompt')),
      'Review the governed scope without mutating source files.',
    );
    await tester.tap(
      find.byKey(const ValueKey<String>('phase6-run-provider-mode')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('code_review').last);
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const ValueKey<String>('phase6-create-run-confirm')),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(api.lastDraft!.providerMode, 'code_review');
    expect(api.lastDraft!.sandbox, 'read-only');
    expect(api.lastDraft!.toJson()['provider_mode'], 'code_review');
  });

  test('task-scoped operations suppress standalone legacy task creation', () {
    final source = File(
      'lib/src/features/orchestrator/presentation/orchestrator_workspace_page.dart',
    ).readAsStringSync();

    expect(source, contains('engineeringTaskId == null &&'));
    expect(source, contains('إنشاء تشغيل محكوم'));
    expect(source, contains('phase6-create-governed-execution-run'));
    expect(source, contains('phase6-run-provider-mode'));
    expect(source, contains('test_and_regression_analysis'));
  });

  test('phase6 source keeps governed run product contracts', () {
    expect(
      parentTask.scopePatterns,
      containsAll(<String>['lib/**', 'orchestrator/**', 'test/**']),
    );
    expect(runView().rollup.arabicSignal, 'بانتظار التنفيذ');
    expect(runView().operatorTask.manualFallbackAvailable, isTrue);
  });
  test('governed run dialog exposes visible Arabic validation', () {
    final source = File(
      'lib/src/features/orchestrator/presentation/orchestrator_workspace_page.dart',
    ).readAsStringSync();

    expect(source, contains('اكتب وصفًا لمهمة التنفيذ من 10 أحرف على الأقل.'));
    expect(source, contains('مزود الترحيل مطلوب.'));
    expect(source, contains('يجب وجود قيد واحد على الأقل.'));
    expect(source, contains('errorText: promptError'));
    expect(source, contains('errorText: providerError'));
    expect(source, contains('errorText: constraintsError'));
  });
}
