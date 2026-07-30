import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/app/workspace_manager_app.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/application/orchestrator_controller.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/data/orchestrator_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/domain/orchestrator_models.dart';

class FakeOrchestratorApi implements OrchestratorApi {
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
  Future<OperatorTask> cancel(String taskId) => throw UnimplementedError();

  @override
  Future<OperatorTask> continueTask(String taskId) =>
      throw UnimplementedError();

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

    expect(find.text('حلقة التشغيل الذاتي V1'), findsOneWidget);
    expect(find.text('صف المهام'), findsOneWidget);
    expect(find.text('ترحيل المستخدم'), findsOneWidget);
    expect(find.text('Runtime Capabilities'), findsOneWidget);
    expect(find.text('Automatic Agents'), findsOneWidget);
    expect(find.text('Database'), findsOneWidget);
    expect(find.text('محجوب'), findsWidgets);
    expect(find.byTooltip('مهمة جديدة'), findsOneWidget);
    expect(find.text('Merge'), findsNothing);
    expect(find.text('Production'), findsNothing);
  });
}
