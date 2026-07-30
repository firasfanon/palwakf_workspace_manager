import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/orchestrator_api_client.dart';
import '../domain/orchestrator_models.dart';

final orchestratorApiProvider = Provider<OrchestratorApi>((ref) {
  return HttpOrchestratorApiClient();
});

final orchestratorControllerProvider =
    StateNotifierProvider<OrchestratorController, OrchestratorWorkspaceState>(
        (ref) {
  return OrchestratorController(ref.watch(orchestratorApiProvider));
});

class OrchestratorWorkspaceState {
  const OrchestratorWorkspaceState({
    this.capabilities,
    this.tasks = const <OperatorTask>[],
    this.selectedTaskId,
    this.toolPlan,
    this.invocations = const <ToolInvocation>[],
    this.reconciliation,
    this.manualPackage,
    this.loading = false,
    this.error,
    this.errorRecoverable = false,
  });

  final RuntimeCapabilities? capabilities;
  final List<OperatorTask> tasks;
  final String? selectedTaskId;
  final ToolPlan? toolPlan;
  final List<ToolInvocation> invocations;
  final ToolReconciliation? reconciliation;
  final ManualDispatchPackage? manualPackage;
  final bool loading;
  final String? error;
  final bool errorRecoverable;

  OperatorTask? get selectedTask {
    for (final task in tasks) {
      if (task.taskId == selectedTaskId) return task;
    }
    return null;
  }

  OrchestratorWorkspaceState copyWith({
    RuntimeCapabilities? capabilities,
    List<OperatorTask>? tasks,
    String? selectedTaskId,
    bool clearSelection = false,
    ToolPlan? toolPlan,
    bool clearToolPlan = false,
    List<ToolInvocation>? invocations,
    ToolReconciliation? reconciliation,
    bool clearReconciliation = false,
    ManualDispatchPackage? manualPackage,
    bool clearManualPackage = false,
    bool? loading,
    String? error,
    bool clearError = false,
    bool? errorRecoverable,
  }) {
    return OrchestratorWorkspaceState(
      capabilities: capabilities ?? this.capabilities,
      tasks: tasks ?? this.tasks,
      selectedTaskId:
          clearSelection ? null : selectedTaskId ?? this.selectedTaskId,
      toolPlan: clearToolPlan ? null : toolPlan ?? this.toolPlan,
      invocations: invocations ?? this.invocations,
      reconciliation:
          clearReconciliation ? null : reconciliation ?? this.reconciliation,
      manualPackage:
          clearManualPackage ? null : manualPackage ?? this.manualPackage,
      loading: loading ?? this.loading,
      error: clearError ? null : error ?? this.error,
      errorRecoverable: errorRecoverable ?? this.errorRecoverable,
    );
  }
}

class OrchestratorController extends StateNotifier<OrchestratorWorkspaceState> {
  OrchestratorController(this._api) : super(const OrchestratorWorkspaceState());

  final OrchestratorApi _api;
  Timer? _pollTimer;
  int _pollAttempts = 0;
  static const int maxPollAttempts = 12;

  Future<void> load() async {
    await _guard(() async {
      final results = await Future.wait<dynamic>(<Future<dynamic>>[
        _api.capabilities(),
        _api.listTasks(),
      ]);
      final tasks = results[1] as List<OperatorTask>;
      state = state.copyWith(
        capabilities: results[0] as RuntimeCapabilities,
        tasks: tasks,
        selectedTaskId:
            state.selectedTaskId ?? (tasks.isEmpty ? null : tasks.first.taskId),
      );
      if (state.selectedTaskId != null) {
        await _loadToolTrace(state.selectedTaskId!);
      }
    });
  }

  Future<void> createTask(TaskDraft draft) async {
    final errors = draft.validate();
    if (errors.isNotEmpty) {
      throw OrchestratorApiException(
        code: 'VALIDATION',
        message: errors.values.first,
        recoverable: true,
      );
    }
    await _guard(() async {
      final task = await _api.createTask(draft);
      final tasks = <OperatorTask>[
        task,
        ...state.tasks.where((value) => value.taskId != task.taskId),
      ];
      state = state.copyWith(
        tasks: tasks,
        selectedTaskId: task.taskId,
        clearToolPlan: true,
        invocations: const <ToolInvocation>[],
        clearReconciliation: true,
        clearManualPackage: true,
      );
      await planTools();
    });
  }

  Future<void> selectTask(String taskId) async {
    state = state.copyWith(
      selectedTaskId: taskId,
      clearToolPlan: true,
      invocations: const <ToolInvocation>[],
      clearReconciliation: true,
      clearManualPackage: true,
    );
    await _loadToolTrace(taskId);
  }

  Future<void> planTools() async {
    final taskId = state.selectedTaskId;
    if (taskId == null) return;
    await _guard(() async {
      final plan = await _api.planTools(taskId);
      state = state.copyWith(toolPlan: plan);
    });
  }

  Future<void> dispatch() async {
    await _taskCommand(_api.dispatch, startPolling: true);
  }

  Future<void> continueTask() async {
    await _taskCommand(_api.continueTask, startPolling: true);
  }

  Future<void> cancel() async {
    await _taskCommand(_api.cancel);
  }

  Future<void> verify(String receipt) async {
    final task = state.selectedTask;
    if (task == null || task.afterHead == null) return;
    await _guard(() async {
      final updated = await _api.verify(
        taskId: task.taskId,
        receipt: receipt,
        head: task.afterHead!,
      );
      _replaceTask(updated);
    });
  }

  Future<void> generateManualPackage() async {
    final taskId = state.selectedTaskId;
    if (taskId == null) return;
    await _guard(() async {
      final package = await _api.generateManualPackage(taskId);
      state = state.copyWith(manualPackage: package);
      await refreshSelected();
    });
  }

  Future<void> markManualDispatched() async {
    final task = state.selectedTask;
    final package = state.manualPackage;
    if (task == null || package == null) return;
    await _guard(() async {
      _replaceTask(
        await _api.markManualDispatched(
          taskId: task.taskId,
          packageReceipt: package.receipt,
        ),
      );
    });
  }

  Future<void> recordManualAcknowledgement(String threadReference) async {
    final task = state.selectedTask;
    final package = state.manualPackage;
    if (task == null || package == null) return;
    await _guard(() async {
      _replaceTask(
        await _api.recordManualAcknowledgement(
          taskId: task.taskId,
          packageReceipt: package.receipt,
          threadReference: threadReference,
        ),
      );
    });
  }

  Future<void> importManualResult(Map<String, dynamic> result) async {
    final task = state.selectedTask;
    final package = state.manualPackage;
    if (task == null || package == null) return;
    final payload = <String, dynamic>{
      ...result,
      'package_receipt': package.receipt,
      'thread_reference': result['thread_reference'] ?? task.threadId,
    };
    await _guard(() async {
      _replaceTask(
        await _api.importManualResult(taskId: task.taskId, result: payload),
      );
    });
  }

  Future<void> refreshSelected() async {
    final taskId = state.selectedTaskId;
    if (taskId == null) return;
    await _guard(() async {
      _replaceTask(await _api.taskStatus(taskId));
      await _loadToolTrace(taskId);
    });
  }

  Future<void> _taskCommand(
    Future<OperatorTask> Function(String taskId) command, {
    bool startPolling = false,
  }) async {
    final taskId = state.selectedTaskId;
    if (taskId == null) return;
    await _guard(() async {
      _replaceTask(await command(taskId));
      await _loadToolTrace(taskId);
      if (startPolling &&
          state.selectedTask?.status == OrchestratorTaskStatus.running) {
        _startPolling(taskId);
      }
    });
  }

  Future<void> _loadToolTrace(String taskId) async {
    try {
      final results = await Future.wait<dynamic>(<Future<dynamic>>[
        _api.toolDecisions(taskId),
        _api.toolInvocations(taskId),
        _api.toolReconciliation(taskId),
      ]);
      state = state.copyWith(
        toolPlan: results[0] as ToolPlan,
        invocations: results[1] as List<ToolInvocation>,
        reconciliation: results[2] as ToolReconciliation,
      );
    } on OrchestratorApiException catch (error) {
      if (error.code != 'HTTP_404' && error.code != 'HTTP_409') rethrow;
    }
  }

  void _startPolling(String taskId) {
    _pollTimer?.cancel();
    _pollAttempts = 0;
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (timer) async {
      _pollAttempts += 1;
      if (_pollAttempts > maxPollAttempts) {
        timer.cancel();
        state = state.copyWith(
          error: 'توقفت المتابعة بعد عدد محاولات محدود. يمكن التحديث يدويًا.',
          errorRecoverable: true,
        );
        return;
      }
      try {
        final task = await _api.taskStatus(taskId);
        _replaceTask(task);
        if (task.status != OrchestratorTaskStatus.running &&
            task.status != OrchestratorTaskStatus.pending) {
          timer.cancel();
          await _loadToolTrace(taskId);
        }
      } on OrchestratorApiException {
        if (_pollAttempts >= maxPollAttempts) timer.cancel();
      }
    });
  }

  void _replaceTask(OperatorTask updated) {
    state = state.copyWith(
      tasks: state.tasks
          .map((task) => task.taskId == updated.taskId ? updated : task)
          .toList(growable: false),
    );
  }

  Future<void> _guard(Future<void> Function() action) async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      await action();
      state = state.copyWith(loading: false, clearError: true);
    } on OrchestratorApiException catch (error) {
      state = state.copyWith(
        loading: false,
        error: error.message,
        errorRecoverable: error.recoverable,
      );
    } catch (error) {
      state = state.copyWith(
        loading: false,
        error: error.toString(),
        errorRecoverable: true,
      );
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }
}
