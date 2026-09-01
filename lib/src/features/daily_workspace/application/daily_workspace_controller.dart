import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../engineering_os/application/engineering_os_controller.dart';
import '../../engineering_os/data/engineering_os_api_client.dart';
import '../../engineering_os/domain/engineering_os_models.dart';
import '../../engineering_os/domain/execution_run_models.dart';
import '../../orchestrator/application/orchestrator_controller.dart';
import '../../orchestrator/data/orchestrator_api_client.dart';
import '../../orchestrator/domain/orchestrator_models.dart';

final dailyWorkspaceControllerProvider =
    StateNotifierProvider<DailyWorkspaceController, DailyWorkspaceState>((ref) {
  return DailyWorkspaceController(
    ref.watch(engineeringOsApiProvider),
    ref.watch(orchestratorApiProvider),
  );
});

enum DailyWorkKind {
  development,
  fix,
  review,
  analysis;

  String get arabicLabel => switch (this) {
        development => 'تطوير',
        fix => 'إصلاح',
        review => 'مراجعة',
        analysis => 'تحليل',
      };

  String get providerMode => switch (this) {
        development => 'execution_relay',
        fix => 'bounded_bug_fix',
        review => 'code_review',
        analysis => 'diagnostic_debug',
      };

  bool get mutating =>
      this == DailyWorkKind.development || this == DailyWorkKind.fix;
}

enum DailyExecutionPhase {
  idle,
  syncing,
  preparing,
  authorizing,
  planning,
  dispatching,
  running,
  completed,
  failed,
}

class DailyWorkspaceState {
  const DailyWorkspaceState({
    this.tasks = const <EngineeringTask>[],
    this.selectedTaskId,
    this.loading = false,
    this.phase = DailyExecutionPhase.idle,
    this.activeRunId,
    this.message,
    this.error,
    this.technicalError,
    this.changedFiles = const <String>[],
  });

  final List<EngineeringTask> tasks;
  final String? selectedTaskId;
  final bool loading;
  final DailyExecutionPhase phase;
  final String? activeRunId;
  final String? message;
  final String? error;
  final String? technicalError;
  final List<String> changedFiles;

  EngineeringTask? get selectedTask {
    for (final task in tasks) {
      if (task.taskId == selectedTaskId) return task;
    }
    return null;
  }

  bool get executing => switch (phase) {
        DailyExecutionPhase.syncing ||
        DailyExecutionPhase.preparing ||
        DailyExecutionPhase.authorizing ||
        DailyExecutionPhase.planning ||
        DailyExecutionPhase.dispatching ||
        DailyExecutionPhase.running =>
          true,
        _ => false,
      };

  DailyWorkspaceState copyWith({
    List<EngineeringTask>? tasks,
    String? selectedTaskId,
    bool? loading,
    DailyExecutionPhase? phase,
    String? activeRunId,
    String? message,
    String? error,
    String? technicalError,
    List<String>? changedFiles,
    bool clearError = false,
    bool clearTechnicalError = false,
    bool clearRun = false,
  }) {
    return DailyWorkspaceState(
      tasks: tasks ?? this.tasks,
      selectedTaskId: selectedTaskId ?? this.selectedTaskId,
      loading: loading ?? this.loading,
      phase: phase ?? this.phase,
      activeRunId: clearRun ? null : activeRunId ?? this.activeRunId,
      message: message ?? this.message,
      error: clearError ? null : error ?? this.error,
      technicalError:
          clearTechnicalError ? null : technicalError ?? this.technicalError,
      changedFiles: changedFiles ?? this.changedFiles,
    );
  }
}

class DailyWorkspaceController extends StateNotifier<DailyWorkspaceState> {
  DailyWorkspaceController(this._engineering, this._orchestrator)
      : super(const DailyWorkspaceState());

  final EngineeringOsApiClient _engineering;
  final OrchestratorApi _orchestrator;

  Future<void> load({String? preferTaskId}) async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final tasks = await _engineering.tasks();
      String? selected = preferTaskId;
      if (selected == null || !tasks.any((task) => task.taskId == selected)) {
        selected = state.selectedTaskId;
      }
      if (selected == null || !tasks.any((task) => task.taskId == selected)) {
        selected = tasks.isEmpty ? null : tasks.first.taskId;
      }
      state = DailyWorkspaceState(
        tasks: tasks,
        selectedTaskId: selected,
        loading: false,
        phase: state.phase,
        activeRunId: state.activeRunId,
        message: state.message,
        error: state.error,
        technicalError: state.technicalError,
        changedFiles: state.changedFiles,
      );
    } catch (error) {
      state = state.copyWith(
        loading: false,
        error: userMessageForFailure(error),
        technicalError: error.toString(),
      );
    }
  }

  void selectTask(String taskId) {
    if (!state.tasks.any((task) => task.taskId == taskId)) return;
    state = state.copyWith(selectedTaskId: taskId);
  }

  Future<void> execute({
    required String prompt,
    required DailyWorkKind kind,
  }) async {
    final task = state.selectedTask;
    if (task == null) {
      _fail('اختر مهمة مسجلة أولًا.', 'NO_SELECTED_ENGINEERING_TASK');
      return;
    }
    if (prompt.trim().isEmpty) {
      _fail('اكتب ما تريد إنجازه أولًا.', 'EMPTY_DAILY_INTENT');
      return;
    }
    if (task.scopePatterns.isEmpty) {
      _fail(
        'هذه المهمة لا تحتوي نطاق عمل معتمدًا. يلزم تجهيزها من الإدارة المتقدمة.',
        'EMPTY_PARENT_SCOPE',
      );
      return;
    }
    if (kind.mutating && task.mutationClass != 'source-write') {
      _fail(
        'هذه المهمة مسجلة للقراءة فقط ولا تسمح بتعديل المصدر.',
        'PARENT_MUTATION_AUTHORITY_IS_${task.mutationClass}',
      );
      return;
    }

    state = state.copyWith(
      phase: DailyExecutionPhase.syncing,
      message: 'أتحقق من نسخة المشروع الحالية…',
      clearError: true,
      clearTechnicalError: true,
      clearRun: true,
      changedFiles: const <String>[],
    );

    try {
      final synced = await _engineering.syncRemoteCheckpoint(task.taskId);

      state = state.copyWith(
        phase: DailyExecutionPhase.preparing,
        message: 'أجهز التنفيذ ضمن حدود المهمة…',
      );

      final stamp = DateTime.now().microsecondsSinceEpoch;
      final runId = '${task.taskId}_DAILY_$stamp';
      final sandbox = kind.mutating ? 'workspace-write' : 'read-only';

      final run = await _engineering.createExecutionRun(
        task.taskId,
        NewExecutionRunDraft(
          executionRunId: runId,
          authorityReference: 'AUTHORITY://ENGINEERING_TASK/${task.taskId}',
          prompt: buildGovernedPrompt(prompt, kind),
          constraints: const <String>[
            'NO_SCOPE_EXPANSION',
            'NO_PRODUCTION',
            'NO_DATABASE_MUTATION',
            'NO_MERGE',
            'NO_BASELINE_PROMOTION',
            'PROVIDER_CERTIFICATION_TRIAL',
          ],
          sandbox: sandbox,
          maxTurns: 16,
          timeoutSeconds: 1200,
          idempotencyKey: 'daily-$stamp-${task.taskId}',
          relayProviderId: 'auto',
          providerMode: kind.providerMode,
          requiresExplicitAuthorization: true,
        ),
      );

      if (run.operatorTask.expectedHead.toLowerCase() !=
          (synced.latestRemoteTaskSha ?? synced.baseSha).toLowerCase()) {
        throw StateError('DAILY_RUN_EXPECTED_HEAD_BINDING_MISMATCH');
      }

      state = state.copyWith(
        phase: DailyExecutionPhase.authorizing,
        activeRunId: run.executionRunId,
        message: 'أثبت موافقتك وحدود التنفيذ…',
      );
      final authorized = await _orchestrator.authorize(run.operatorTask);

      state = state.copyWith(
        phase: DailyExecutionPhase.planning,
        message: 'أجهز الأدوات اللازمة في الخلفية…',
      );
      final plan = await _orchestrator.planTools(authorized.taskId);
      if (plan.dispatchBlocked) {
        throw StateError('TOOL_PLAN_BLOCKED:${plan.blockers.join('|')}');
      }

      state = state.copyWith(
        phase: DailyExecutionPhase.dispatching,
        message: 'أبدأ التنفيذ الآن…',
      );
      final dispatched = await _orchestrator.dispatch(authorized.taskId);
      if (_acceptTerminal(dispatched)) return;

      state = state.copyWith(
        phase: DailyExecutionPhase.running,
        message: 'يجري تنفيذ المهمة ضمن النطاق المسموح…',
      );
      await _pollUntilTerminal(dispatched.taskId);
    } catch (error) {
      _fail(userMessageForFailure(error), error.toString());
    }
  }

  Future<void> _pollUntilTerminal(String taskId) async {
    for (var attempt = 0; attempt < 300; attempt += 1) {
      await Future<void>.delayed(const Duration(seconds: 2));
      final current = await _orchestrator.taskStatus(taskId);
      if (_acceptTerminal(current)) return;
      state = state.copyWith(
        phase: DailyExecutionPhase.running,
        message: _runningMessage(current.status),
      );
    }
    state = state.copyWith(
      phase: DailyExecutionPhase.running,
      message: 'التنفيذ ما زال مستمرًا. يمكنك مغادرة الصفحة والعودة لاحقًا.',
    );
  }

  bool _acceptTerminal(OperatorTask task) {
    switch (task.status) {
      case OrchestratorTaskStatus.pendingVerification:
        state = state.copyWith(
          phase: DailyExecutionPhase.completed,
          message: task.changedFiles.isEmpty
              ? 'اكتمل التنفيذ وبانتظار التحقق النهائي.'
              : 'اكتمل التنفيذ وتم حفظ التغيير على فرع العمل.',
          changedFiles: task.changedFiles,
        );
        return true;
      case OrchestratorTaskStatus.verified:
        state = state.copyWith(
          phase: DailyExecutionPhase.completed,
          message: 'اكتملت المهمة وتم التحقق من النتيجة.',
          changedFiles: task.changedFiles,
        );
        return true;
      case OrchestratorTaskStatus.failed:
      case OrchestratorTaskStatus.drifted:
      case OrchestratorTaskStatus.timedOut:
      case OrchestratorTaskStatus.cancelled:
        _fail(
          userMessageForFailure(task.blocker ?? task.lastEvent),
          task.blocker ?? task.lastEvent,
        );
        return true;
      case OrchestratorTaskStatus.pending:
      case OrchestratorTaskStatus.queued:
      case OrchestratorTaskStatus.running:
      case OrchestratorTaskStatus.awaitingApproval:
        return false;
    }
  }

  void _fail(String userMessage, String technical) {
    state = state.copyWith(
      phase: DailyExecutionPhase.failed,
      error: userMessage,
      technicalError: technical,
      message: 'لم يتم اعتماد نتيجة ناقصة.',
    );
  }

  static String _runningMessage(OrchestratorTaskStatus status) {
    return switch (status) {
      OrchestratorTaskStatus.pending => 'أجهز المهمة للإرسال…',
      OrchestratorTaskStatus.queued => 'المهمة في صف التنفيذ…',
      OrchestratorTaskStatus.running => 'يجري تنفيذ المهمة…',
      OrchestratorTaskStatus.awaitingApproval =>
        'تحتاج المهمة قرارًا إضافيًا قبل المتابعة.',
      _ => 'أتابع حالة التنفيذ…',
    };
  }

  static String buildGovernedPrompt(String prompt, DailyWorkKind kind) {
    return '''
طلب المستخدم اليومي:
${prompt.trim()}

نوع العمل: ${kind.arabicLabel}

نفّذ هذا الطلب فقط داخل صلاحية ونطاق المهمة الأب المسجلين في Workspace Manager.
لا توسّع النطاق، ولا تدمج إلى main، ولا تنشر، ولا تعدّل قاعدة بيانات أو إنتاج.
إذا لم يكن الطلب ممكنًا داخل النطاق المسموح فتوقف واشرح السبب بدل التخمين.
'''
        .trim();
  }

  static String userMessageForFailure(Object error) {
    final raw = error.toString();
    if (raw.contains('AUTHORIZED_WORKSPACE_WRITE_PRODUCED_NO_SOURCE_CHANGE')) {
      return 'لم ينتج عن المحاولة أي تعديل فعلي. لم يتم تغيير المشروع أو رفع أي ملفات.';
    }
    if (raw.contains('PROVIDER_CERTIFICATION_REQUIRED')) {
      return 'مزود التنفيذ يحتاج اعتمادًا تقنيًا إضافيًا قبل استخدامه لهذه المهمة.';
    }
    if (raw.contains('TOOL_PLAN_BLOCKED') ||
        raw.contains('tool plan') ||
        raw.contains('tool decisions')) {
      return 'تعذر تجهيز خطة التنفيذ الداخلية. لم يبدأ أي تعديل على المشروع.';
    }
    if (raw.contains('HEAD drift') ||
        raw.contains('HEAD_DRIFT') ||
        raw.contains('HEAD_BINDING_MISMATCH')) {
      return 'تغيّرت نسخة المشروع منذ تجهيز المهمة. يلزم تحديثها قبل التنفيذ.';
    }
    if (raw.contains('worktree is not clean') || raw.contains('WORKTREE')) {
      return 'توجد تغييرات محلية غير محسومة. أوقف النظام التنفيذ لحماية العمل الموجود.';
    }
    if (raw.toLowerCase().contains('auth') ||
        raw.contains('401') ||
        raw.contains('403')) {
      return 'جلسة التنفيذ أو صلاحيتها غير جاهزة. أعد الاتصال ثم حاول مرة أخرى.';
    }
    if (raw.contains('NO_SELECTED_ENGINEERING_TASK')) {
      return 'اختر مهمة مسجلة أولًا.';
    }
    return 'تعذر إكمال المهمة بأمان. لم يعتمد النظام نتيجة غير مكتملة.';
  }
}
