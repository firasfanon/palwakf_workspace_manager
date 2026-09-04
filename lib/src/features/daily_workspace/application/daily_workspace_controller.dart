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

class DailyIntentPreview {
  const DailyIntentPreview({
    required this.task,
    required this.kind,
  });

  final EngineeringTask task;
  final DailyWorkKind kind;

  String get projectLabel =>
      DailyWorkspaceController.friendlyProjectLabel(task.projectId);

  String get workTitle => DailyWorkspaceController.friendlyTaskTitle(task);

  String get confirmationText =>
      'سأتابع «$workTitle» ضمن مشروع «$projectLabel». '
      'سأستخدم حدود العمل المسجلة تلقائيًا، وأتحقق من النتيجة قبل اعتمادها. '
      'لن يتم نشر أو دمج أي تغيير نهائي دون موافقتك.';
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

  String? get selectedProjectId {
    final selected = selectedTask;
    if (selected != null) return selected.projectId;
    return tasks.isEmpty ? null : tasks.first.projectId;
  }

  List<String> get projectIds {
    final values = <String>[];
    for (final task in tasks) {
      if (!values.contains(task.projectId)) values.add(task.projectId);
    }
    return values;
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
        selected = _bestDefaultTask(tasks)?.taskId;
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

  void selectProject(String projectId) {
    final candidates =
        state.tasks.where((task) => task.projectId == projectId).toList();
    final selected = _bestDefaultTask(candidates);
    if (selected == null) return;
    state = state.copyWith(selectedTaskId: selected.taskId);
  }

  void selectTask(String taskId) {
    if (!state.tasks.any((task) => task.taskId == taskId)) return;
    state = state.copyWith(selectedTaskId: taskId);
  }

  DailyIntentPreview previewIntent(String prompt) {
    final normalizedPrompt = prompt.trim();
    if (normalizedPrompt.isEmpty) {
      throw StateError('EMPTY_DAILY_INTENT');
    }

    final projectId = state.selectedProjectId;
    if (projectId == null) {
      throw StateError('NO_DAILY_PROJECT_AVAILABLE');
    }

    final candidates =
        state.tasks.where((task) => task.projectId == projectId).toList();
    if (candidates.isEmpty) {
      throw StateError('NO_WORK_FOR_SELECTED_PROJECT');
    }

    final kind = inferKind(normalizedPrompt);
    final task = _resolveTask(candidates, normalizedPrompt, kind);
    state = state.copyWith(selectedTaskId: task.taskId);
    return DailyIntentPreview(task: task, kind: kind);
  }

  Future<void> execute({
    required String prompt,
    DailyIntentPreview? preview,
  }) async {
    if (prompt.trim().isEmpty) {
      _fail('اكتب ما تريد إنجازه أولًا.', 'EMPTY_DAILY_INTENT');
      return;
    }

    final resolution = preview ?? previewIntent(prompt);
    final task = resolution.task;
    final kind = resolution.kind;

    if (task.scopePatterns.isEmpty) {
      _fail(
        'هذا العمل يحتاج تجهيز نطاقه أولًا. لم يبدأ النظام أي تعديل.',
        'EMPTY_PARENT_SCOPE',
      );
      return;
    }
    if (kind.mutating && task.mutationClass != 'source-write') {
      _fail(
        'هذا العمل مهيأ للمراجعة فقط ولا يسمح بالتعديل الآن.',
        'PARENT_MUTATION_AUTHORITY_IS_${task.mutationClass}',
      );
      return;
    }

    state = state.copyWith(
      selectedTaskId: task.taskId,
      phase: DailyExecutionPhase.syncing,
      message: 'أراجع حالة المشروع…',
      clearError: true,
      clearTechnicalError: true,
      clearRun: true,
      changedFiles: const <String>[],
    );

    try {
      final synced = await _engineering.syncRemoteCheckpoint(task.taskId);

      state = state.copyWith(
        phase: DailyExecutionPhase.preparing,
        message: 'أجهز مساحة العمل…',
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
        message: 'أجهز مساحة العمل…',
      );
      final authorized = await _orchestrator.authorize(run.operatorTask);

      state = state.copyWith(
        phase: DailyExecutionPhase.planning,
        message: 'أجهز مساحة العمل…',
      );
      final plan = await _orchestrator.planTools(authorized.taskId);
      if (plan.dispatchBlocked) {
        throw StateError('TOOL_PLAN_BLOCKED:${plan.blockers.join('|')}');
      }

      state = state.copyWith(
        phase: DailyExecutionPhase.dispatching,
        message: 'أبدأ تنفيذ المطلوب…',
      );
      final dispatched = await _orchestrator.dispatch(authorized.taskId);
      if (_acceptTerminal(dispatched)) return;

      state = state.copyWith(
        phase: DailyExecutionPhase.running,
        message: 'يجري تنفيذ المطلوب الآن…',
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
      message: 'العمل ما زال مستمرًا. يمكنك مغادرة الصفحة والعودة لاحقًا.',
    );
  }

  bool _acceptTerminal(OperatorTask task) {
    switch (task.status) {
      case OrchestratorTaskStatus.pendingVerification:
        state = state.copyWith(
          phase: DailyExecutionPhase.completed,
          message: task.changedFiles.isEmpty
              ? 'اكتمل العمل وبانتظار التحقق النهائي.'
              : 'اكتمل العمل وتم حفظ التغييرات على فرع العمل.',
          changedFiles: task.changedFiles,
        );
        return true;
      case OrchestratorTaskStatus.verified:
        state = state.copyWith(
          phase: DailyExecutionPhase.completed,
          message: 'اكتمل العمل وتم التحقق من النتيجة.',
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
      message: 'لم يعتمد النظام نتيجة غير مكتملة.',
    );
  }

  static String _runningMessage(OrchestratorTaskStatus status) {
    return switch (status) {
      OrchestratorTaskStatus.pending => 'أجهز التنفيذ…',
      OrchestratorTaskStatus.queued => 'العمل جاهز وسيبدأ بعد قليل…',
      OrchestratorTaskStatus.running => 'يجري تنفيذ المطلوب…',
      OrchestratorTaskStatus.awaitingApproval =>
        'يوجد قرار يحتاج موافقتك قبل المتابعة.',
      _ => 'أتابع حالة العمل…',
    };
  }

  static DailyWorkKind inferKind(String prompt) {
    final value = _normalize(prompt);
    final noMutation = _containsAny(value, const <String>[
      'لا تعدل',
      'لا تغير',
      'دون تعديل',
      'بدون تعديل',
      'من غير تعديل',
      'قراءه فقط',
      'read only',
      'read-only',
      'do not modify',
      'without changes',
    ]);

    final scores = <DailyWorkKind, int>{
      DailyWorkKind.development: _weightedIntentScore(
            value,
            directives: const <String>[
              'طور',
              'تطوير',
              'اضف',
              'انشئ',
              'ابن',
              'نفذ',
              'implement',
              'build',
              'add',
              'create',
              'develop',
            ],
          ) -
          (noMutation ? 8 : 0),
      DailyWorkKind.fix: _weightedIntentScore(
            value,
            directives: const <String>[
              'اصلح',
              'اصلاح',
              'صحح',
              'عالج',
              'fix',
              'repair',
            ],
            context: const <String>[
              'مشكله',
              'خطا',
              'خلل',
              'bug',
              'error',
            ],
          ) -
          (noMutation ? 8 : 0),
      DailyWorkKind.review: _weightedIntentScore(
        value,
        directives: const <String>[
          'راجع',
          'مراجعه',
          'دقق',
          'تدقيق',
          'قيم',
          'review',
          'audit',
          'inspect',
        ],
      ),
      DailyWorkKind.analysis: _weightedIntentScore(
        value,
        directives: const <String>[
          'حلل',
          'تحليل',
          'شخص',
          'تشخيص',
          'افحص',
          'analyze',
          'analyse',
          'diagnose',
          'debug',
        ],
      ),
    };

    var best = DailyWorkKind.development;
    var bestScore = scores[best] ?? 0;
    for (final kind in const <DailyWorkKind>[
      DailyWorkKind.fix,
      DailyWorkKind.review,
      DailyWorkKind.analysis,
    ]) {
      final score = scores[kind] ?? 0;
      if (score > bestScore) {
        best = kind;
        bestScore = score;
      }
    }

    if (bestScore <= 0) return DailyWorkKind.development;
    return best;
  }

  static String friendlyProjectLabel(String projectId) {
    switch (projectId.toUpperCase()) {
      case 'PALWAKF_WORKSPACE_MANAGER':
        return 'مساحة عمل PalWakf';
      case 'PAL_EYES':
      case 'PALWAKF_EYES':
        return 'بعيون فلسطينية';
      case 'PALWAKF_PLATFORM':
      case 'PALWAKF_PLATFORM_SYSTEM':
        return 'منصة PalWakf';
      case 'MANASIKUNA_APP':
        return 'مناسكنا';
    }

    final cleaned = projectId
        .replaceFirst(RegExp(r'^PALWAKF_'), '')
        .replaceAll('_', ' ')
        .trim();
    return cleaned.isEmpty ? 'مشروع PalWakf' : cleaned;
  }

  static String friendlyTaskTitle(EngineeringTask task) {
    final id = task.taskId.toUpperCase();

    if (id.contains('DAILY_USER_EXPERIENCE')) {
      return 'تحسين مساحة العمل اليومية';
    }
    if (id.contains('PROVIDER_BOUNDED_WRITE_PROOF')) {
      return 'التحقق من التنفيذ الآمن داخل المشروع';
    }
    if (id.contains('OPERATIONS_SURFACE_PROVIDER_CONTROL_ALIGNMENT')) {
      return 'تحسين تشغيل المساعد داخل مساحة العمل';
    }
    if (id.contains('CODEX_READ_ONLY_PROVIDER_CERT')) {
      return 'التحقق من جاهزية المساعد';
    }
    if (id.contains('GOVERNED_ENGINEERING_PROVIDER_RUNTIME')) {
      return 'تجهيز محرك التنفيذ الآمن';
    }

    final hasArabic = RegExp(r'[\u0600-\u06FF]').hasMatch(task.title);
    final exposesTechnicalTerms = RegExp(
      r'provider|codex|sha|head|branch|dispatch|baseline|control plane|runtime',
      caseSensitive: false,
    ).hasMatch(task.title);

    if (hasArabic && !exposesTechnicalTerms) return task.title;
    return 'متابعة العمل على ${friendlyProjectLabel(task.projectId)}';
  }

  static String friendlyTaskStatus(String status) {
    return switch (status) {
      'READY' => 'جاهز للبدء',
      'WIP_REMOTE_CHECKPOINTED' => 'جاهز للمتابعة',
      'IN_REVIEW' => 'بانتظار المراجعة',
      'INTEGRATED' => 'مكتمل',
      'BLOCKED' => 'يحتاج إجراء',
      'CANCELLED' => 'متوقف',
      _ => 'مسجل',
    };
  }

  static String buildGovernedPrompt(String prompt, DailyWorkKind kind) {
    return '''
طلب المستخدم اليومي:
${prompt.trim()}

نوع العمل المستنتج: ${kind.arabicLabel}

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
      return 'أداة التنفيذ تحتاج تجهيزًا إضافيًا قبل استخدام هذا النوع من العمل.';
    }
    if (raw.contains('TOOL_PLAN_BLOCKED') ||
        raw.contains('tool plan') ||
        raw.contains('tool decisions')) {
      return 'تعذر تجهيز التنفيذ الداخلي. لم يبدأ أي تعديل على المشروع.';
    }
    if (raw.contains('HEAD drift') ||
        raw.contains('HEAD_DRIFT') ||
        raw.contains('HEAD_BINDING_MISMATCH')) {
      return 'تغيّرت نسخة المشروع منذ تجهيز العمل. يلزم تحديثها قبل التنفيذ.';
    }
    if (raw.contains('worktree is not clean') || raw.contains('WORKTREE')) {
      return 'توجد تغييرات محلية غير محسومة. أوقف النظام التنفيذ لحماية العمل الموجود.';
    }
    if (raw.toLowerCase().contains('auth') ||
        raw.contains('401') ||
        raw.contains('403')) {
      return 'جلسة التنفيذ أو صلاحيتها غير جاهزة. أعد الاتصال ثم حاول مرة أخرى.';
    }
    if (raw.contains('NO_DAILY_PROJECT_AVAILABLE') ||
        raw.contains('NO_WORK_FOR_SELECTED_PROJECT')) {
      return 'لا يوجد عمل مسجل وجاهز لهذا المشروع الآن.';
    }
    if (raw.contains('EMPTY_DAILY_INTENT')) {
      return 'اكتب ما تريد إنجازه أولًا.';
    }
    return 'تعذر إكمال العمل بأمان. لم يعتمد النظام نتيجة غير مكتملة.';
  }

  EngineeringTask _resolveTask(
    List<EngineeringTask> candidates,
    String prompt,
    DailyWorkKind kind,
  ) {
    final promptTokens = _tokens(prompt);
    EngineeringTask? best;
    var bestScore = -100000;

    for (final task in candidates) {
      var score = _statusScore(task.status);
      if (task.taskId == state.selectedTaskId) score += 4;
      if (task.scopePatterns.isEmpty) score -= 50;
      if (kind.mutating && task.mutationClass != 'source-write') score -= 40;

      final haystack = _normalize(
        '${task.title} ${task.description} ${task.taskId}',
      );
      for (final token in promptTokens) {
        if (token.length >= 3 && haystack.contains(token)) score += 4;
      }

      if (score > bestScore) {
        best = task;
        bestScore = score;
      }
    }

    return best ?? candidates.first;
  }

  static EngineeringTask? _bestDefaultTask(List<EngineeringTask> tasks) {
    if (tasks.isEmpty) return null;
    EngineeringTask? best;
    var bestScore = -100000;
    for (final task in tasks) {
      var score = _statusScore(task.status);
      if (task.scopePatterns.isEmpty) score -= 20;
      if (score > bestScore) {
        best = task;
        bestScore = score;
      }
    }
    return best ?? tasks.first;
  }

  static int _statusScore(String status) {
    return switch (status) {
      'WIP_REMOTE_CHECKPOINTED' => 60,
      'READY' => 50,
      'IN_REVIEW' => 30,
      'INTEGRATED' => 10,
      'BLOCKED' => -60,
      'CANCELLED' => -100,
      _ => 0,
    };
  }

  static int _weightedIntentScore(
    String value, {
    required List<String> directives,
    List<String> context = const <String>[],
  }) {
    var score = 0;
    for (final keyword in directives) {
      if (value.contains(keyword)) score += 5;
    }
    for (final keyword in context) {
      if (value.contains(keyword)) score += 1;
    }
    return score;
  }

  static bool _containsAny(String value, List<String> phrases) {
    for (final phrase in phrases) {
      if (value.contains(phrase)) return true;
    }
    return false;
  }

  static Set<String> _tokens(String value) {
    return _normalize(value)
        .split(RegExp(r'[\s\-_./,:;()\[\]{}]+'))
        .where((token) => token.trim().isNotEmpty)
        .toSet();
  }

  static String _normalize(String value) {
    return value
        .toLowerCase()
        .replaceAll('أ', 'ا')
        .replaceAll('إ', 'ا')
        .replaceAll('آ', 'ا')
        .replaceAll('ة', 'ه')
        .replaceAll('ى', 'ي')
        .replaceAll('ؤ', 'و')
        .replaceAll('ئ', 'ي')
        .trim();
  }
}
