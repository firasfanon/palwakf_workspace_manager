import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../core/presentation/preview_mode_ui.dart';
import '../../../core/theme/palwakf_theme.dart';
import '../../engineering_os/application/execution_run_controller.dart';
import '../../engineering_os/domain/engineering_os_models.dart';
import '../../engineering_os/domain/execution_run_models.dart';
import '../application/operational_authorization.dart';
import '../application/orchestrator_controller.dart';
import '../data/orchestrator_api_client.dart';
import '../domain/orchestrator_models.dart';

class OrchestratorWorkspacePage extends ConsumerStatefulWidget {
  const OrchestratorWorkspacePage({
    super.key,
    this.engineeringTaskId,
  });

  final String? engineeringTaskId;

  @override
  ConsumerState<OrchestratorWorkspacePage> createState() =>
      _OrchestratorWorkspacePageState();
}

class _OrchestratorWorkspacePageState
    extends ConsumerState<OrchestratorWorkspacePage> {
  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_loadWorkspace);
  }

  Future<void> _loadWorkspace() async {
    final orchestrator = ref.read(orchestratorControllerProvider.notifier);
    await orchestrator.load();
    final engineeringTaskId = widget.engineeringTaskId;
    if (engineeringTaskId == null || engineeringTaskId.isEmpty) return;
    final runs = ref.read(
      executionRunContextControllerProvider(engineeringTaskId).notifier,
    );
    await runs.load();
    if (!mounted) return;
    final executionContext = ref
        .read(
          executionRunContextControllerProvider(engineeringTaskId),
        )
        .context;
    if (executionContext != null && executionContext.runs.isNotEmpty) {
      final firstRun = executionContext.runs.first;
      await orchestrator.selectTask(firstRun.executionRunId);
      if (firstRun.operatorTask.repository !=
          'firasfanon/palwakf_workspace_manager') {
        await runs.loadWorkspace(firstRun.executionRunId);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(orchestratorControllerProvider);
    final engineeringTaskId = widget.engineeringTaskId;
    final executionState =
        engineeringTaskId == null || engineeringTaskId.isEmpty
            ? null
            : ref.watch(
                executionRunContextControllerProvider(engineeringTaskId),
              );
    final workspaceState = _focusedWorkspaceState(
      state,
      executionState?.context,
    );
    final authorizationState = ref.watch(operationalAuthorizationProvider);
    final authorization = authorizationState.asData?.value;
    final controller = ref.read(orchestratorControllerProvider.notifier);
    final previewUnavailable = PreviewModeUi.isVisualPreview &&
        state.error != null &&
        state.capabilities == null;
    if (previewUnavailable) {
      return const Material(
        child: Column(
          children: <Widget>[
            PreviewModeBanner(),
            Expanded(
              child: PreviewUnavailablePanel(
                icon: Icons.settings_suggest_outlined,
                title: 'بيانات التشغيل غير متاحة',
                description:
                    'قدرات التشغيل وصف المهام غير متصلين في المعاينة البصرية؛ الغياب هنا لا يعني أن القدرات محجوبة أو أن الصف فارغ.',
              ),
            ),
          ],
        ),
      );
    }
    return Material(
      child: Column(
        children: <Widget>[
          _CapabilityStrip(capabilities: state.capabilities),
          if (engineeringTaskId != null &&
              engineeringTaskId.isNotEmpty &&
              executionState != null)
            _EngineeringExecutionContextBand(
              state: executionState,
              onRefresh: () => ref
                  .read(
                    executionRunContextControllerProvider(
                      engineeringTaskId,
                    ).notifier,
                  )
                  .load(),
              onCreate: authorization?.canDispatch ?? false
                  ? () => _showNewExecutionRun(context, executionState)
                  : null,
            ),
          if (authorization?.readOnly ?? false)
            const _ReadOnlyAuthorizationBand(),
          if (state.error != null)
            _RecoverableError(
              message: state.error!,
              recoverable: state.errorRecoverable,
              onRetry: controller.load,
            ),
          if (state.loading) const LinearProgressIndicator(minHeight: 2),
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final queue = _TaskQueue(
                  state: workspaceState,
                  onSelect: (taskId) async {
                    await controller.selectTask(taskId);
                    if (engineeringTaskId != null &&
                        engineeringTaskId.isNotEmpty) {
                      await ref
                          .read(
                            executionRunContextControllerProvider(
                              engineeringTaskId,
                            ).notifier,
                          )
                          .loadWorkspace(taskId);
                    }
                  },
                  onCreate: engineeringTaskId == null &&
                          (authorization?.canDispatch ?? false)
                      ? () => _showNewTask(context)
                      : null,
                  onCreateProof: engineeringTaskId == null &&
                          (authorization?.canDispatch ?? false)
                      ? controller.createProofTask
                      : null,
                );
                final detail = _TaskDetail(
                  state: workspaceState,
                  controller: controller,
                  authorization: authorization,
                  executionState: executionState,
                  executionController:
                      engineeringTaskId == null || engineeringTaskId.isEmpty
                          ? null
                          : ref.read(
                              executionRunContextControllerProvider(
                                engineeringTaskId,
                              ).notifier,
                            ),
                );
                if (constraints.maxWidth < 760) {
                  return Column(
                    children: <Widget>[
                      SizedBox(height: 260, child: queue),
                      const Divider(height: 1),
                      Expanded(child: detail),
                    ],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    SizedBox(width: 340, child: queue),
                    const VerticalDivider(width: 1),
                    Expanded(child: detail),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  OrchestratorWorkspaceState _focusedWorkspaceState(
    OrchestratorWorkspaceState state,
    EngineeringTaskExecutionContext? executionContext,
  ) {
    final engineeringTaskId = widget.engineeringTaskId;
    if (engineeringTaskId == null || engineeringTaskId.isEmpty) return state;
    if (executionContext == null) {
      return state.copyWith(
        tasks: const <OperatorTask>[],
        clearSelection: true,
      );
    }
    final runIds =
        executionContext.runs.map((run) => run.executionRunId).toSet();
    final focusedTasks = state.tasks
        .where((task) => runIds.contains(task.taskId))
        .toList(growable: false);
    final selectionIsFocused =
        state.selectedTaskId != null && runIds.contains(state.selectedTaskId);
    return state.copyWith(
      tasks: focusedTasks,
      clearSelection: !selectionIsFocused,
    );
  }

  Future<void> _showNewExecutionRun(
    BuildContext context,
    ExecutionRunContextState executionState,
  ) async {
    final parent = executionState.context?.parentTask;
    final engineeringTaskId = widget.engineeringTaskId;
    if (parent == null || engineeringTaskId == null) return;
    final draft = await showDialog<NewExecutionRunDraft>(
      context: context,
      builder: (context) => _NewExecutionRunDialog(parent: parent),
    );
    if (draft == null || !mounted) return;
    try {
      final run = await ref
          .read(
            executionRunContextControllerProvider(engineeringTaskId).notifier,
          )
          .create(draft);
      final orchestrator = ref.read(orchestratorControllerProvider.notifier);
      await orchestrator.load();
      await orchestrator.selectTask(run.executionRunId);
      if (run.operatorTask.repository !=
          'firasfanon/palwakf_workspace_manager') {
        await ref
            .read(
              executionRunContextControllerProvider(engineeringTaskId).notifier,
            )
            .loadWorkspace(run.executionRunId);
      }
    } catch (error) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString())),
      );
    }
  }

  Future<void> _showNewTask(BuildContext context) async {
    final draft = await showDialog<TaskDraft>(
      context: context,
      builder: (context) => const _NewTaskDialog(),
    );
    if (draft == null || !mounted) return;
    try {
      await ref.read(orchestratorControllerProvider.notifier).createTask(draft);
    } on OrchestratorApiException catch (error) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.message)),
      );
    }
  }
}

class _EngineeringExecutionContextBand extends StatelessWidget {
  const _EngineeringExecutionContextBand({
    required this.state,
    required this.onRefresh,
    required this.onCreate,
  });

  final ExecutionRunContextState state;
  final VoidCallback onRefresh;
  final VoidCallback? onCreate;

  @override
  Widget build(BuildContext context) {
    final executionContext = state.context;
    if (executionContext == null) {
      return Material(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        child: ListTile(
          leading: state.loading
              ? const SizedBox.square(
                  dimension: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.account_tree_outlined),
          title: const Text('تحميل سياق تشغيل المهمة'),
          subtitle: state.error == null ? null : Text(state.error!),
          trailing: IconButton(
            tooltip: 'تحديث سياق التشغيل',
            onPressed: onRefresh,
            icon: const Icon(Icons.refresh),
          ),
        ),
      );
    }

    final parent = executionContext.parentTask;
    final latest =
        executionContext.runs.isEmpty ? null : executionContext.runs.first;
    final authorityHead = parent.latestRemoteTaskSha ?? parent.baseSha;
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              children: <Widget>[
                const Icon(Icons.account_tree_outlined, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'تشغيل المهمة المحكوم · ${parent.title}',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
                Chip(label: Text('Runs: ${executionContext.runs.length}')),
                const SizedBox(width: 8),
                FilledButton.icon(
                  key: const ValueKey<String>(
                    'phase6-create-governed-execution-run',
                  ),
                  onPressed: onCreate,
                  icon: const Icon(Icons.playlist_add_outlined),
                  label: const Text('إنشاء تشغيل محكوم'),
                ),
                IconButton(
                  tooltip: 'تحديث',
                  onPressed: onRefresh,
                  icon: const Icon(Icons.refresh),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              runSpacing: 6,
              children: <Widget>[
                Text('Task: ${parent.taskId}'),
                Text('Branch: ${parent.taskBranch}'),
                Text('HEAD: ${_shortSha(authorityHead)}'),
                Text('Mutation: ${parent.mutationClass}'),
                if (latest != null)
                  Text(
                    'Run state: ${latest.rollup.arabicSignal}',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: parent.scopePatterns
                  .map((scope) => Chip(label: Text(scope)))
                  .toList(growable: false),
            ),
            if (state.error != null) ...<Widget>[
              const SizedBox(height: 6),
              Text(
                state.error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
          ],
        ),
      ),
    );
  }

  static String _shortSha(String value) =>
      value.length <= 10 ? value : value.substring(0, 10);
}

class _NewExecutionRunDialog extends StatefulWidget {
  const _NewExecutionRunDialog({required this.parent});

  final EngineeringTask parent;

  @override
  State<_NewExecutionRunDialog> createState() => _NewExecutionRunDialogState();
}

class _NewExecutionRunDialogState extends State<_NewExecutionRunDialog> {
  static const List<String> _providerModes = <String>[
    'execution_relay',
    'code_review',
    'diagnostic_debug',
    'bounded_bug_fix',
    'engineering_proposal',
    'test_and_regression_analysis',
  ];
  static const Set<String> _readOnlyProviderModes = <String>{
    'code_review',
    'diagnostic_debug',
    'engineering_proposal',
    'test_and_regression_analysis',
  };
  static const Set<String> _mutatingProviderModes = <String>{
    'execution_relay',
    'bounded_bug_fix',
  };

  final prompt = TextEditingController();
  final provider = TextEditingController(text: 'chatgpt');
  final constraints = TextEditingController(
    text: 'NO_SCOPE_EXPANSION\nNO_PRODUCTION\nNO_DATABASE_MUTATION',
  );
  late String providerMode;
  String? promptError;
  String? providerError;
  String? constraintsError;

  @override
  void initState() {
    super.initState();
    providerMode = widget.parent.mutationClass == 'source-write'
        ? 'execution_relay'
        : 'code_review';
  }

  @override
  void dispose() {
    prompt.dispose();
    provider.dispose();
    constraints.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('إنشاء تشغيل محكوم'),
      content: SizedBox(
        width: 680,
        child: SingleChildScrollView(
          child: Column(
            children: <Widget>[
              TextField(
                key: const ValueKey<String>('phase6-run-prompt'),
                controller: prompt,
                minLines: 4,
                maxLines: 8,
                decoration: InputDecoration(
                  labelText: 'مهمة التنفيذ',
                  helperText:
                      'المشروع والمستودع والفرع وHEAD والنطاق تورث من المهمة ولا يمكن توسيعها هنا.',
                  errorText: promptError,
                ),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                key: const ValueKey<String>('phase6-run-provider-mode'),
                initialValue: providerMode,
                decoration: const InputDecoration(
                  labelText: 'وضع المزود',
                ),
                items: _providerModes
                    .map(
                      (mode) => DropdownMenuItem<String>(
                        value: mode,
                        enabled:
                            widget.parent.mutationClass == 'source-write' ||
                                !_mutatingProviderModes.contains(mode),
                        child: Text(mode),
                      ),
                    )
                    .toList(growable: false),
                onChanged: (value) {
                  if (value == null) return;
                  setState(() => providerMode = value);
                },
              ),
              const SizedBox(height: 12),
              TextField(
                key: const ValueKey<String>('phase6-run-provider'),
                controller: provider,
                decoration: InputDecoration(
                  labelText: 'مزود الترحيل',
                  errorText: providerError,
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                key: const ValueKey<String>('phase6-run-constraints'),
                controller: constraints,
                minLines: 3,
                maxLines: 8,
                decoration: InputDecoration(
                  labelText: 'قيود إضافية — سطر لكل قيد',
                  errorText: constraintsError,
                ),
              ),
            ],
          ),
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('إلغاء'),
        ),
        FilledButton(
          key: const ValueKey<String>('phase6-create-run-confirm'),
          onPressed: _submit,
          child: const Text('إنشاء'),
        ),
      ],
    );
  }

  void _submit() {
    final promptValue = prompt.text.trim();
    final providerValue = provider.text.trim();
    final constraintValues = constraints.text
        .split('\n')
        .map((value) => value.trim())
        .where((value) => value.isNotEmpty)
        .toList(growable: false);
    final nextPromptError = promptValue.length < 10
        ? 'اكتب وصفًا لمهمة التنفيذ من 10 أحرف على الأقل.'
        : null;
    final nextProviderError =
        providerValue.length < 2 ? 'مزود الترحيل مطلوب.' : null;
    final nextConstraintsError =
        constraintValues.isEmpty ? 'يجب وجود قيد واحد على الأقل.' : null;
    if (nextPromptError != null ||
        nextProviderError != null ||
        nextConstraintsError != null) {
      setState(() {
        promptError = nextPromptError;
        providerError = nextProviderError;
        constraintsError = nextConstraintsError;
      });
      return;
    }
    final stamp = DateTime.now().toUtc().millisecondsSinceEpoch;
    final parentId = widget.parent.taskId
        .toUpperCase()
        .replaceAll(RegExp(r'[^A-Z0-9_-]'), '_');
    final boundedParent =
        parentId.length > 80 ? parentId.substring(0, 80) : parentId;
    final sandbox = _sandboxForProviderMode(providerMode);
    Navigator.pop(
      context,
      NewExecutionRunDraft(
        executionRunId: '${boundedParent}_RUN_$stamp',
        authorityReference:
            'AUTHORITY://ENGINEERING_TASK/${widget.parent.taskId}',
        prompt: promptValue,
        constraints: constraintValues,
        sandbox: sandbox,
        maxTurns: 6,
        timeoutSeconds: 1800,
        idempotencyKey: 'run:$boundedParent:$stamp',
        relayProviderId: providerValue,
        providerMode: providerMode,
        requiresExplicitAuthorization: true,
      ),
    );
  }

  String _sandboxForProviderMode(String mode) {
    if (_readOnlyProviderModes.contains(mode)) {
      return 'read-only';
    }
    return widget.parent.mutationClass == 'source-write'
        ? 'workspace-write'
        : 'read-only';
  }
}

class _CapabilityStrip extends StatelessWidget {
  const _CapabilityStrip({required this.capabilities});

  final RuntimeCapabilities? capabilities;

  @override
  Widget build(BuildContext context) {
    final values = <({String label, bool enabled, IconData icon})>[
      (
        label: 'المسار الآلي',
        enabled: capabilities?.automaticAgentsAvailable ?? false,
        icon: Icons.auto_awesome_outlined,
      ),
      (
        label: 'ترحيل المستخدم',
        enabled: capabilities?.manualRelayFallback ?? false,
        icon: Icons.forward_to_inbox_outlined,
      ),
      (
        label: 'توجيه القدرات',
        enabled: capabilities?.capabilityRouting ?? false,
        icon: Icons.route_outlined,
      ),
      (
        label: 'تسوية الأدوات',
        enabled: capabilities?.reconciliation ?? false,
        icon: Icons.compare_arrows,
      ),
    ];
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          bottom: BorderSide(color: Theme.of(context).dividerColor),
        ),
      ),
      child: Wrap(
        spacing: 20,
        runSpacing: 8,
        children: values
            .map(
              (value) => Row(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Icon(
                    value.icon,
                    size: 17,
                    color: value.enabled
                        ? PalWakfTheme.successGreen
                        : PalWakfTheme.royalRed,
                  ),
                  const SizedBox(width: 7),
                  Text(value.label),
                  const SizedBox(width: 6),
                  Text(
                    value.enabled ? 'متاح' : 'محجوب',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      color: value.enabled
                          ? PalWakfTheme.successGreen
                          : PalWakfTheme.royalRed,
                    ),
                  ),
                ],
              ),
            )
            .toList(growable: false),
      ),
    );
  }
}

class _ReadOnlyAuthorizationBand extends StatelessWidget {
  const _ReadOnlyAuthorizationBand();

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: const Padding(
        padding: EdgeInsets.symmetric(horizontal: 20, vertical: 9),
        child: Row(
          children: <Widget>[
            Icon(Icons.lock_outline, size: 18),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                'الجلسة الحالية للقراءة فقط؛ أوامر التغيير معطلة في الواجهة ومرفوضة من الخادم.',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RecoverableError extends StatelessWidget {
  const _RecoverableError({
    required this.message,
    required this.recoverable,
    required this.onRetry,
  });

  final String message;
  final bool recoverable;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
        child: Row(
          children: <Widget>[
            const Icon(Icons.error_outline),
            const SizedBox(width: 10),
            Expanded(child: Text(message)),
            if (recoverable)
              TextButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh, size: 18),
                label: const Text('إعادة المحاولة'),
              ),
          ],
        ),
      ),
    );
  }
}

class _TaskQueue extends StatelessWidget {
  const _TaskQueue({
    required this.state,
    required this.onSelect,
    required this.onCreate,
    required this.onCreateProof,
  });

  final OrchestratorWorkspaceState state;
  final ValueChanged<String> onSelect;
  final VoidCallback? onCreate;
  final VoidCallback? onCreateProof;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Theme.of(context).colorScheme.surface,
      child: Column(
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    'صف المهام',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                ),
                IconButton.filled(
                  tooltip: 'مهمة جديدة',
                  onPressed: onCreate,
                  icon: const Icon(Icons.add),
                ),
                const SizedBox(width: 6),
                IconButton.outlined(
                  tooltip: 'إنشاء مهمة الإثبات الذاتي',
                  onPressed: onCreateProof,
                  icon: const Icon(Icons.self_improvement_outlined),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: state.tasks.isEmpty
                ? const _QueueEmpty()
                : ListView.separated(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    itemCount: state.tasks.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 2),
                    itemBuilder: (context, index) {
                      final task = state.tasks[index];
                      return _TaskQueueItem(
                        task: task,
                        selected: task.taskId == state.selectedTaskId,
                        onTap: () => onSelect(task.taskId),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _QueueEmpty extends StatelessWidget {
  const _QueueEmpty();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(Icons.inbox_outlined, size: 38),
            SizedBox(height: 10),
            Text('لا توجد مهام تشغيلية'),
          ],
        ),
      ),
    );
  }
}

class _TaskQueueItem extends StatelessWidget {
  const _TaskQueueItem({
    required this.task,
    required this.selected,
    required this.onTap,
  });

  final OperatorTask task;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final formatter = DateFormat('HH:mm  yyyy/MM/dd', 'ar');
    return Material(
      color: selected
          ? Theme.of(context).colorScheme.primaryContainer
          : Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  _StatusDot(status: task.status),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      task.taskId,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 7),
              Text(
                '${task.projectId} · ${task.branch}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 5),
              Row(
                children: <Widget>[
                  Expanded(
                    child: Text(
                      task.status.arabicLabel,
                      style: Theme.of(context).textTheme.labelMedium,
                    ),
                  ),
                  Text(
                    formatter.format(task.updatedAt.toLocal()),
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                ],
              ),
              if (task.blocker != null) ...<Widget>[
                const SizedBox(height: 6),
                Text(
                  task.blocker!,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: PalWakfTheme.royalRed,
                    fontSize: 12,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.status});

  final OrchestratorTaskStatus status;

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      OrchestratorTaskStatus.verified => PalWakfTheme.successGreen,
      OrchestratorTaskStatus.running => PalWakfTheme.waqfGold,
      OrchestratorTaskStatus.pendingVerification => Colors.teal,
      OrchestratorTaskStatus.pending => Colors.blueGrey,
      _ => PalWakfTheme.royalRed,
    };
    return Container(
      width: 9,
      height: 9,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

class _TaskDetail extends StatelessWidget {
  const _TaskDetail({
    required this.state,
    required this.controller,
    required this.authorization,
    required this.executionState,
    required this.executionController,
  });

  final OrchestratorWorkspaceState state;
  final OrchestratorController controller;
  final OperationalAuthorizationContext? authorization;
  final ExecutionRunContextState? executionState;
  final ExecutionRunContextController? executionController;

  @override
  Widget build(BuildContext context) {
    final task = state.selectedTask;
    if (task == null) {
      return LayoutBuilder(
        builder: (context, constraints) {
          final minimumHeight =
              constraints.maxHeight > 32 ? constraints.maxHeight - 32 : 0.0;
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: minimumHeight),
              child: Center(
                child: _RuntimeCapabilitiesCard(
                  capabilities: state.capabilities,
                ),
              ),
            ),
          );
        },
      );
    }
    final externalRuntime =
        task.repository != 'firasfanon/palwakf_workspace_manager' &&
            executionState != null &&
            executionController != null;
    return DefaultTabController(
      length: externalRuntime ? 5 : 4,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          _TaskHeader(
            task: task,
            controller: controller,
            authorization: authorization,
          ),
          TabBar(
            isScrollable: true,
            tabs: <Widget>[
              Tab(icon: Icon(Icons.dashboard_outlined), text: 'التفاصيل'),
              Tab(icon: Icon(Icons.route_outlined), text: 'خطة الأدوات'),
              Tab(icon: Icon(Icons.forward_to_inbox_outlined), text: 'الترحيل'),
              const Tab(icon: Icon(Icons.timeline_outlined), text: 'الأحداث'),
              if (externalRuntime)
                const Tab(
                  icon: Icon(Icons.inventory_2_outlined),
                  text: 'مساحة التنفيذ',
                ),
            ],
          ),
          Expanded(
            child: TabBarView(
              children: <Widget>[
                _OverviewTab(task: task),
                _ToolPlanTab(
                  plan: state.toolPlan,
                  invocations: state.invocations,
                  reconciliation: state.reconciliation,
                  onPlan: controller.planTools,
                  canMutate:
                      !externalRuntime && (authorization?.canDispatch ?? false),
                ),
                _RelayTab(
                  task: task,
                  package: state.manualPackage,
                  controller: controller,
                  canMutate: authorization?.canDispatch ?? false,
                ),
                _EventsTab(task: task),
                if (externalRuntime)
                  _ExternalExecutionWorkspaceTab(
                    task: task,
                    state: executionState!,
                    controller: executionController!,
                    orchestratorController: controller,
                    canMutate: authorization?.canDispatch ?? false,
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RuntimeCapabilitiesCard extends StatelessWidget {
  const _RuntimeCapabilitiesCard({required this.capabilities});

  final RuntimeCapabilities? capabilities;

  @override
  Widget build(BuildContext context) {
    final values = <String, bool>{
      'دورة حياة المهمة': capabilities?.taskLifecycle ?? false,
      'الترحيل اليدوي': capabilities?.manualRelayFallback ?? false,
      'توجيه القدرات': capabilities?.capabilityRouting ?? false,
      'تتبع الأدوات': capabilities?.toolDecisionTrace ?? false,
      'التسوية': capabilities?.reconciliation ?? false,
      'الوكلاء الآليون': capabilities?.automaticAgentsAvailable ?? false,
      'قاعدة البيانات': capabilities?.databaseConnected ?? false,
      'تغيير الإنتاج': capabilities?.productionMutation ?? false,
    };
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 540),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              const _SectionTitle(
                icon: Icons.memory_outlined,
                title: 'قدرات التشغيل',
              ),
              const SizedBox(height: 8),
              const Text('اختر مهمة أو أنشئ مهمة جديدة لبدء العمل.'),
              const SizedBox(height: 16),
              ...values.entries.map(
                (entry) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        entry.value
                            ? Icons.check_circle_outline
                            : Icons.block_outlined,
                        size: 18,
                        color: entry.value
                            ? PalWakfTheme.successGreen
                            : PalWakfTheme.royalRed,
                      ),
                      const SizedBox(width: 8),
                      Expanded(child: Text(entry.key)),
                      Text(
                        entry.value ? 'متاح' : 'محجوب',
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TaskHeader extends StatelessWidget {
  const _TaskHeader({
    required this.task,
    required this.controller,
    required this.authorization,
  });

  final OperatorTask task;
  final OrchestratorController controller;
  final OperationalAuthorizationContext? authorization;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  task.taskId,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
              _StatusBadge(status: task.status),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              FilledButton.icon(
                onPressed: task.automaticFailureCode != null ||
                        !(authorization?.canDispatch ?? false) ||
                        task.status == OrchestratorTaskStatus.cancelled ||
                        (task.requiresExplicitAuthorization &&
                            task.authorizedAt == null)
                    ? null
                    : controller.dispatch,
                icon: const Icon(Icons.send_outlined),
                label: Text(
                  task.automaticFailureCode != null
                      ? 'المسار الآلي محجوب'
                      : 'إرسال',
                ),
              ),
              if (task.requiresExplicitAuthorization)
                FilledButton.tonalIcon(
                  onPressed: (authorization?.canDispatch ?? false) &&
                          task.authorizedAt == null
                      ? controller.authorize
                      : null,
                  icon: const Icon(Icons.gavel_outlined),
                  label: Text(
                    task.authorizedAt == null ? 'تفويض التنفيذ' : 'مفوّضة',
                  ),
                ),
              OutlinedButton.icon(
                onPressed: (authorization?.canContinue ?? false) &&
                        (task.status == OrchestratorTaskStatus.failed ||
                            task.status ==
                                OrchestratorTaskStatus.awaitingApproval)
                    ? controller.continueTask
                    : null,
                icon: const Icon(Icons.play_arrow),
                label: const Text('متابعة'),
              ),
              OutlinedButton.icon(
                onPressed: !(authorization?.canCancel ?? false) ||
                        task.status == OrchestratorTaskStatus.verified ||
                        task.status == OrchestratorTaskStatus.cancelled
                    ? null
                    : controller.cancel,
                icon: const Icon(Icons.cancel_outlined),
                label: const Text('إلغاء'),
              ),
              OutlinedButton.icon(
                onPressed: (authorization?.canVerify ?? false) &&
                        task.status ==
                            OrchestratorTaskStatus.pendingVerification
                    ? () => _showVerificationDialog(context, controller)
                    : null,
                icon: const Icon(Icons.fact_check_outlined),
                label: const Text('تحقق مستقل'),
              ),
              IconButton(
                tooltip: 'تحديث المهمة',
                onPressed: controller.refreshSelected,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _showVerificationDialog(
    BuildContext context,
    OrchestratorController controller,
  ) async {
    final input = TextEditingController();
    final receipt = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('إيصال التحقق المستقل'),
        content: TextField(
          controller: input,
          decoration: const InputDecoration(
            labelText: 'CI / verification receipt',
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, input.text.trim()),
            child: const Text('تسجيل'),
          ),
        ],
      ),
    );
    input.dispose();
    if (receipt != null && receipt.length >= 8) {
      await controller.verify(receipt);
    }
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status});

  final OrchestratorTaskStatus status;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        status.arabicLabel,
        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
      ),
    );
  }
}

class _OverviewTab extends StatelessWidget {
  const _OverviewTab({required this.task});

  final OperatorTask task;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: <Widget>[
        const _SectionTitle(
            icon: Icons.gavel_outlined, title: 'السلطة والنطاق'),
        _KeyValueGrid(
          values: <String, String>{
            'المشروع': task.projectId,
            'المستودع': task.repository,
            'الفرع': task.branch,
            'مرجع التفويض': task.authorityReference,
            'حالة التفويض': task.requiresExplicitAuthorization
                ? (task.authorizedAt == null ? 'بانتظار التفويض' : 'مفوّضة')
                : 'تفويض المغلف كافٍ',
            'Sandbox': task.sandbox,
            'مزود الترحيل': task.relayProviderId,
            'النطاق': task.scopePatterns.isEmpty
                ? 'Legacy / غير مقيد في المغلف'
                : task.scopePatterns.join(', '),
            'Idempotency': task.idempotencyKey,
          },
        ),
        const SizedBox(height: 22),
        const _SectionTitle(
          icon: Icons.description_outlined,
          title: 'وصف المهمة',
        ),
        Text(task.prompt),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: task.constraints
              .map((value) => Chip(label: Text(value)))
              .toList(),
        ),
        const SizedBox(height: 22),
        const _SectionTitle(icon: Icons.commit_outlined, title: 'حالة المصدر'),
        _KeyValueGrid(
          values: <String, String>{
            'HEAD المتوقع': task.expectedHead,
            'HEAD قبل التنفيذ': task.beforeHead ?? 'غير متاح',
            'HEAD بعد التنفيذ': task.afterHead ?? 'غير متاح',
            'Thread': task.threadId ?? 'غير متاح',
            'Receipt': task.executionReceipt ?? 'غير متاح',
            'آخر حدث': task.lastEvent,
          },
        ),
        if (task.changedFiles.isNotEmpty) ...<Widget>[
          const SizedBox(height: 22),
          const _SectionTitle(
            icon: Icons.folder_open_outlined,
            title: 'الملفات المتغيرة',
          ),
          ...task.changedFiles.map(
            (value) => ListTile(
              dense: true,
              leading: const Icon(Icons.insert_drive_file_outlined, size: 18),
              title: Text(value),
            ),
          ),
        ],
      ],
    );
  }
}

class _ExternalExecutionWorkspaceTab extends StatelessWidget {
  const _ExternalExecutionWorkspaceTab({
    required this.task,
    required this.state,
    required this.controller,
    required this.orchestratorController,
    required this.canMutate,
  });

  final OperatorTask task;
  final ExecutionRunContextState state;
  final ExecutionRunContextController controller;
  final OrchestratorController orchestratorController;
  final bool canMutate;

  @override
  Widget build(BuildContext context) {
    final workspace =
        state.workspace?.executionRunId == task.taskId ? state.workspace : null;
    final authorized = task.authorizedAt != null;
    final canOperate = canMutate && authorized;
    final sourceWrite = task.sandbox == 'workspace-write';

    return ListView(
      padding: const EdgeInsets.all(20),
      children: <Widget>[
        const _SectionTitle(
          icon: Icons.inventory_2_outlined,
          title: 'مساحة التنفيذ الخارجية',
        ),
        const SizedBox(height: 8),
        Text(
          'نسخة Git معزولة للمستودع الخارجي. لا يتم الدمج مع main أو ترقية Baseline أو Production من هذه الشاشة.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 14),
        if (state.workspaceLoading) const LinearProgressIndicator(minHeight: 2),
        if (state.workspaceError != null) ...<Widget>[
          const SizedBox(height: 8),
          _WarningBand(message: state.workspaceError!),
        ],
        const SizedBox(height: 12),
        _KeyValueGrid(
          values: <String, String>{
            'المستودع': task.repository,
            'الفرع': task.branch,
            'HEAD المتوقع': task.expectedHead,
            'الحالة': workspace?.lifecycle ?? 'UNPREPARED',
            'HEAD المحلي': workspace?.currentHead ?? 'غير مهيأ',
            'HEAD البعيد': workspace?.remoteHead ?? 'غير متاح',
            'التفويض': authorized ? 'مفوّضة' : 'بانتظار التفويض',
            'المساحة المحلية': workspace?.workspacePath ?? 'غير منشأة',
          },
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: <Widget>[
            FilledButton.tonalIcon(
              key: const ValueKey<String>('external-runtime-prepare'),
              onPressed: canOperate && !(workspace?.checkpointed ?? false)
                  ? () => _run(
                        context,
                        () => controller.prepareWorkspace(task.taskId),
                      )
                  : null,
              icon: const Icon(Icons.inventory_2_outlined),
              label: Text(
                workspace?.prepared ?? false
                    ? 'تحقق من مساحة التنفيذ'
                    : 'تهيئة مساحة التنفيذ',
              ),
            ),
            OutlinedButton.icon(
              key: const ValueKey<String>('external-runtime-apply'),
              onPressed: canOperate &&
                      sourceWrite &&
                      (workspace?.prepared ?? false) &&
                      !(workspace?.checkpointed ?? false)
                  ? () => _applyManifest(context)
                  : null,
              icon: const Icon(Icons.edit_note_outlined),
              label: const Text('تطبيق ملفات محكومة'),
            ),
            OutlinedButton.icon(
              key: const ValueKey<String>('external-runtime-validate'),
              onPressed: canOperate &&
                      (workspace?.prepared ?? false) &&
                      !(workspace?.checkpointed ?? false)
                  ? () => _run(
                        context,
                        () => controller.validateWorkspace(task.taskId),
                      )
                  : null,
              icon: const Icon(Icons.fact_check_outlined),
              label: const Text('تشغيل التحقق'),
            ),
            FilledButton.icon(
              key: const ValueKey<String>('external-runtime-checkpoint'),
              onPressed: canOperate &&
                      sourceWrite &&
                      (workspace?.validationPassed ?? false) &&
                      !(workspace?.checkpointed ?? false)
                  ? () => _checkpoint(context)
                  : null,
              icon: const Icon(Icons.cloud_upload_outlined),
              label: const Text('Remote WIP Checkpoint'),
            ),
            IconButton(
              tooltip: 'تحديث مساحة التنفيذ',
              onPressed: () => controller.loadWorkspace(task.taskId),
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        if (!authorized) ...<Widget>[
          const SizedBox(height: 12),
          const _WarningBand(
            message:
                'يجب تفويض تشغيل المهمة من الشريط العلوي قبل تهيئة أو تعديل مساحة التنفيذ.',
          ),
        ],
        if (workspace != null && workspace.changedFiles.isNotEmpty) ...<Widget>[
          const SizedBox(height: 22),
          const _SectionTitle(
            icon: Icons.folder_open_outlined,
            title: 'الملفات المتغيرة في المساحة المعزولة',
          ),
          ...workspace.changedFiles.map(
            (path) => ListTile(
              dense: true,
              leading: const Icon(Icons.insert_drive_file_outlined, size: 18),
              title: Text(path),
            ),
          ),
        ],
        if (workspace?.validation != null) ...<Widget>[
          const SizedBox(height: 22),
          _SectionTitle(
            icon: workspace!.validation!.allPassed
                ? Icons.check_circle_outline
                : Icons.error_outline,
            title:
                workspace.validation!.allPassed ? 'التحقق ناجح' : 'التحقق فشل',
          ),
          const SizedBox(height: 8),
          ...workspace.validation!.checks.map(
            (result) => ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: Text('${result.check} · ${result.status}'),
              subtitle: Text(
                '${result.durationMs} ms · ${result.commandSummary}',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              children: <Widget>[
                if (result.outputExcerpt.isNotEmpty)
                  Align(
                    alignment: AlignmentDirectional.centerStart,
                    child: SelectableText(result.outputExcerpt),
                  ),
              ],
            ),
          ),
        ],
        if (workspace?.checkpointSha != null) ...<Widget>[
          const SizedBox(height: 22),
          _KeyValueGrid(
            values: <String, String>{
              'Remote checkpoint SHA': workspace!.checkpointSha!,
              'Push': 'NON_FORCE',
              'Remote readback': 'PASS',
              'Integration': 'NO',
              'main': 'NO',
              'Baseline': 'NO',
              'Production': 'NO',
            },
          ),
        ],
      ],
    );
  }

  Future<void> _applyManifest(BuildContext context) async {
    final files = await _showExternalManifestDialog(context);
    if (files == null || !context.mounted) return;
    await _run(
      context,
      () => controller.applyWorkspace(task.taskId, files),
    );
  }

  Future<void> _checkpoint(BuildContext context) async {
    final message = await _showExternalCheckpointDialog(context);
    if (message == null || !context.mounted) return;
    await _run(
      context,
      () async {
        await controller.checkpointWorkspace(
          task.taskId,
          commitMessage: message,
          evidence: const <String>[
            'workspace-manager:external-runtime-v1',
          ],
        );
        await orchestratorController.refreshSelected();
      },
    );
  }

  Future<void> _run(
    BuildContext context,
    Future<void> Function() action,
  ) async {
    try {
      await action();
    } catch (error) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString())),
      );
    }
  }
}

Future<List<Map<String, dynamic>>?> _showExternalManifestDialog(
  BuildContext context,
) async {
  final input = TextEditingController(
    text: '[\n'
        '  {\n'
        '    "path": "lib/path/to/file.dart",\n'
        '    "preimage_mode": "EXACT_CANONICAL_SHA256",\n'
        '    "expected_preimage_canonical_sha256": "<64-hex-sha256>",\n'
        '    "postimage_text": "complete file contents"\n'
        '  }\n'
        ']',
  );
  String? validationError;
  final result = await showDialog<List<Map<String, dynamic>>>(
    context: context,
    builder: (dialogContext) => StatefulBuilder(
      builder: (context, setDialogState) => AlertDialog(
        title: const Text('تطبيق ملفات محكومة'),
        content: SizedBox(
          width: 760,
          child: TextField(
            key: const ValueKey<String>('external-runtime-manifest-json'),
            controller: input,
            minLines: 14,
            maxLines: 24,
            decoration: InputDecoration(
              labelText: 'File mutation manifest JSON',
              helperText:
                  'أرسل القائمة الكاملة للملفات المتغيرة الحالية. المسارات والنطاق وHEAD تتحقق منها الخدمة.',
              errorText: validationError,
              alignLabelWithHint: true,
            ),
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () {
              try {
                final decoded = jsonDecode(input.text);
                if (decoded is! List<dynamic> || decoded.isEmpty) {
                  throw const FormatException('القائمة فارغة أو غير صالحة.');
                }
                final files = decoded
                    .map(
                      (value) => Map<String, dynamic>.from(
                        value as Map<dynamic, dynamic>,
                      ),
                    )
                    .toList(growable: false);
                Navigator.pop(dialogContext, files);
              } catch (error) {
                setDialogState(() {
                  validationError = 'Manifest غير صالح: $error';
                });
              }
            },
            child: const Text('تطبيق'),
          ),
        ],
      ),
    ),
  );
  input.dispose();
  return result;
}

Future<String?> _showExternalCheckpointDialog(BuildContext context) async {
  final input = TextEditingController(
    text: 'fix(project): governed external workspace checkpoint',
  );
  final result = await showDialog<String>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: const Text('إنشاء Remote WIP Checkpoint'),
      content: SizedBox(
        width: 620,
        child: TextField(
          key: const ValueKey<String>('external-runtime-commit-message'),
          controller: input,
          decoration: const InputDecoration(
            labelText: 'Commit message',
            helperText:
                'Push عادي بدون force إلى task branch فقط. لا يوجد merge أو main.',
          ),
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.pop(dialogContext),
          child: const Text('إلغاء'),
        ),
        FilledButton(
          onPressed: () {
            final value = input.text.trim();
            if (value.length >= 4) Navigator.pop(dialogContext, value);
          },
          child: const Text('إنشاء ورفع'),
        ),
      ],
    ),
  );
  input.dispose();
  return result;
}

class _ToolPlanTab extends StatelessWidget {
  const _ToolPlanTab({
    required this.plan,
    required this.invocations,
    required this.reconciliation,
    required this.onPlan,
    required this.canMutate,
  });

  final ToolPlan? plan;
  final List<ToolInvocation> invocations;
  final ToolReconciliation? reconciliation;
  final VoidCallback onPlan;
  final bool canMutate;

  @override
  Widget build(BuildContext context) {
    if (plan == null) {
      return Center(
        child: FilledButton.icon(
          onPressed: canMutate ? onPlan : null,
          icon: const Icon(Icons.route_outlined),
          label: const Text('إنشاء خطة الأدوات'),
        ),
      );
    }
    return ListView(
      padding: const EdgeInsets.all(20),
      children: <Widget>[
        const _ProjectToolProfileBand(),
        const SizedBox(height: 18),
        if (plan!.dispatchBlocked)
          _WarningBand(message: plan!.blockers.join(' · ')),
        const _SectionTitle(
          icon: Icons.account_tree_outlined,
          title: 'قرارات الاختيار',
        ),
        const SizedBox(height: 8),
        ...plan!.decisions.map(
          (decision) => _ToolDecisionRow(decision: decision),
        ),
        const SizedBox(height: 22),
        const _SectionTitle(
          icon: Icons.timeline_outlined,
          title: 'المخطط مقابل المنفذ',
        ),
        const SizedBox(height: 8),
        if (invocations.isEmpty)
          const Text('لا توجد invocation receipts بعد.')
        else
          ...invocations.map(
            (invocation) => ListTile(
              dense: true,
              leading: const Icon(Icons.check_circle_outline, size: 20),
              title: Text(invocation.adapterId),
              subtitle: Text(
                <String>[
                  invocation.capabilityId,
                  if (invocation.commandSummary != null)
                    invocation.commandSummary!,
                  if (invocation.outputExcerpt != null)
                    invocation.outputExcerpt!,
                ].join('\n'),
                maxLines: 6,
                overflow: TextOverflow.ellipsis,
              ),
              trailing: Text(invocation.status),
            ),
          ),
        if (reconciliation != null) ...<Widget>[
          const Divider(),
          _KeyValueGrid(
            values: <String, String>{
              'المخطط': reconciliation!.planned.join(', '),
              'المنفذ': reconciliation!.actual.join(', '),
              'المفقود': reconciliation!.missing.join(', '),
              'غير المتوقع': reconciliation!.unexpected.join(', '),
              'الحالة': reconciliation!.reconciled ? 'متطابق' : 'غير متصالح',
            },
          ),
        ],
      ],
    );
  }
}

class _ProjectToolProfileBand extends StatelessWidget {
  const _ProjectToolProfileBand();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border.all(color: Theme.of(context).dividerColor),
        borderRadius: BorderRadius.circular(6),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Project Tool Profile',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
          SizedBox(height: 6),
          Text('Flutter · Python · FastAPI · GitHub Actions · Vercel'),
          SizedBox(height: 4),
          Text('محظور: relational.runtime / Supabase'),
        ],
      ),
    );
  }
}

class _ToolDecisionRow extends StatelessWidget {
  const _ToolDecisionRow({required this.decision});

  final ToolDecision decision;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).dividerColor),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  decision.capabilityId,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Text(
                decision.selectedAdapterId ?? 'مستبعد',
                style: TextStyle(
                  color: decision.blocked
                      ? PalWakfTheme.royalRed
                      : PalWakfTheme.sovereignBlue,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 5),
          Text(decision.selectedReason),
          if (decision.approvalRequired)
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text(
                'يتطلب موافقة بشرية',
                style: TextStyle(color: PalWakfTheme.royalRed),
              ),
            ),
          ...decision.exclusions.map(
            (exclusion) => Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                '${exclusion.adapterId}: ${exclusion.reason}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RelayTab extends StatelessWidget {
  const _RelayTab({
    required this.task,
    required this.package,
    required this.controller,
    required this.canMutate,
  });

  final OperatorTask task;
  final ManualDispatchPackage? package;
  final OrchestratorController controller;
  final bool canMutate;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: <Widget>[
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.errorContainer,
            borderRadius: BorderRadius.circular(6),
          ),
          child: const Row(
            children: <Widget>[
              Icon(Icons.info_outline),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'USER RELAY FALLBACK لا يثبت قبول الاتصال الآلي ولا يغلق بوابة Agents.',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        const _SectionTitle(
          icon: Icons.forward_to_inbox_outlined,
          title: 'حزمة الإرسال اليدوي',
        ),
        const SizedBox(height: 8),
        if (!task.manualFallbackAvailable)
          const Text('يتاح المسار اليدوي بعد تسجيل فشل آلي أو اختيار صريح.')
        else if (package == null)
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: FilledButton.icon(
              onPressed: canMutate &&
                      (!task.requiresExplicitAuthorization ||
                          task.authorizedAt != null)
                  ? controller.generateManualPackage
                  : null,
              icon: const Icon(Icons.inventory_2_outlined),
              label: const Text('إنشاء الحزمة'),
            ),
          )
        else ...<Widget>[
          _KeyValueGrid(
            values: <String, String>{
              'Receipt': package!.receipt,
              'Envelope SHA-256': package!.canonicalHash,
              'وقت الإنشاء': package!.generatedAt.toLocal().toIso8601String(),
              'مزود الترحيل': package!.relayProviderId,
              'النطاق': task.scopePatterns.isEmpty
                  ? 'Legacy / غير محدد'
                  : task.scopePatterns.join(', '),
            },
          ),
          const SizedBox(height: 12),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: FilledButton.tonalIcon(
              onPressed: () {
                Clipboard.setData(
                  ClipboardData(
                    text: const JsonEncoder.withIndent('  ')
                        .convert(package!.envelope),
                  ),
                );
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('تم نسخ الحزمة')),
                );
              },
              icon: const Icon(Icons.copy_outlined),
              label: const Text('نسخ الحزمة'),
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              OutlinedButton.icon(
                onPressed: canMutate ? controller.markManualDispatched : null,
                icon: const Icon(Icons.outbox_outlined),
                label: const Text('تم الترحيل'),
              ),
              OutlinedButton.icon(
                onPressed:
                    canMutate ? () => _recordAcknowledgement(context) : null,
                icon: const Icon(Icons.link_outlined),
                label: const Text('تسجيل إقرار التنفيذ الخارجي'),
              ),
              OutlinedButton.icon(
                onPressed: !canMutate || task.threadId == null
                    ? null
                    : () => _importResult(context),
                icon: const Icon(Icons.file_download_done_outlined),
                label: const Text('استيراد النتيجة'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SelectableText(
            const JsonEncoder.withIndent('  ').convert(package!.envelope),
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
          ),
        ],
      ],
    );
  }

  Future<void> _recordAcknowledgement(BuildContext context) async {
    final input = TextEditingController(text: task.threadId);
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('إقرار التنفيذ الخارجي'),
        content: TextField(
          controller: input,
          decoration:
              const InputDecoration(labelText: 'Thread / task reference'),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, input.text.trim()),
            child: const Text('تسجيل'),
          ),
        ],
      ),
    );
    input.dispose();
    if (value != null && value.length >= 4) {
      await controller.recordManualAcknowledgement(value);
    }
  }

  Future<void> _importResult(BuildContext context) async {
    final input = TextEditingController(
      text: const JsonEncoder.withIndent('  ').convert(
        <String, dynamic>{
          'thread_reference': task.threadId,
          'before_head': task.expectedHead,
          'after_head': '',
          'commit_sha': '',
          'result_summary': '',
          'changed_files': <String>[],
          'tests': <String>[],
          'evidence': <String>[],
        },
      ),
    );
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('استيراد نتيجة منظمة'),
        content: SizedBox(
          width: 640,
          child: TextField(
            controller: input,
            minLines: 12,
            maxLines: 20,
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, input.text),
            child: const Text('استيراد'),
          ),
        ],
      ),
    );
    input.dispose();
    if (value == null) return;
    try {
      await controller.importManualResult(
        jsonDecode(value) as Map<String, dynamic>,
      );
    } on FormatException {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('JSON غير صالح')),
      );
    }
  }
}

class _EventsTab extends StatelessWidget {
  const _EventsTab({required this.task});

  final OperatorTask task;

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.all(20),
      itemCount: task.events.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        final event = task.events.reversed.elementAt(index);
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Padding(
              padding: const EdgeInsets.only(top: 5),
              child: _StatusDot(status: event.status),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    event.type,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  Text(event.message),
                  Text(
                    event.occurredAt.toLocal().toIso8601String(),
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.icon, required this.title});

  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Icon(icon, size: 20, color: PalWakfTheme.sovereignBlue),
        const SizedBox(width: 8),
        Text(
          title,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
      ],
    );
  }
}

class _KeyValueGrid extends StatelessWidget {
  const _KeyValueGrid({required this.values});

  final Map<String, String> values;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth >= 700
            ? (constraints.maxWidth - 12) / 2
            : constraints.maxWidth;
        return Wrap(
          spacing: 12,
          runSpacing: 8,
          children: values.entries
              .map(
                (entry) => SizedBox(
                  width: width,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          entry.key,
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                        const SizedBox(height: 2),
                        SelectableText(
                          entry.value.isEmpty ? '—' : entry.value,
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                ),
              )
              .toList(growable: false),
        );
      },
    );
  }
}

class _WarningBand extends StatelessWidget {
  const _WarningBand({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(10),
      color: Theme.of(context).colorScheme.errorContainer,
      child: Row(
        children: <Widget>[
          const Icon(Icons.block_outlined),
          const SizedBox(width: 8),
          Expanded(child: Text(message)),
        ],
      ),
    );
  }
}

class _NewTaskDialog extends StatefulWidget {
  const _NewTaskDialog();

  @override
  State<_NewTaskDialog> createState() => _NewTaskDialogState();
}

class _NewTaskDialogState extends State<_NewTaskDialog> {
  final _formKey = GlobalKey<FormState>();
  final _taskId = TextEditingController();
  final _head = TextEditingController();
  final _authority = TextEditingController();
  final _prompt = TextEditingController();
  final _constraints = TextEditingController(
    text: 'NO_PRODUCTION, NO_DATABASE, PRESERVE_AUTHORITY',
  );
  final _idempotency = TextEditingController();
  int _maxTurns = 4;
  int _timeout = 300;
  String _sandbox = 'workspace-write';

  @override
  void dispose() {
    _taskId.dispose();
    _head.dispose();
    _authority.dispose();
    _prompt.dispose();
    _constraints.dispose();
    _idempotency.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('مهمة تشغيلية جديدة'),
      content: SizedBox(
        width: 680,
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            child: Column(
              children: <Widget>[
                _field(_taskId, 'معرّف المهمة'),
                _field(_head, 'HEAD المتوقع (40 محرفًا)'),
                _field(_authority, 'مرجع التفويض'),
                _field(
                  _prompt,
                  'وصف المهمة',
                  minLines: 3,
                  maxLines: 7,
                ),
                _field(_constraints, 'القيود، مفصولة بفاصلة'),
                _field(_idempotency, 'مفتاح idempotency'),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  initialValue: _sandbox,
                  decoration: const InputDecoration(labelText: 'Sandbox'),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem(
                      value: 'read-only',
                      child: Text('قراءة فقط'),
                    ),
                    DropdownMenuItem(
                      value: 'workspace-write',
                      child: Text('كتابة مساحة العمل'),
                    ),
                  ],
                  onChanged: (value) => _sandbox = value ?? _sandbox,
                ),
                const SizedBox(height: 12),
                Row(
                  children: <Widget>[
                    Expanded(
                      child: TextFormField(
                        initialValue: '$_maxTurns',
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'الحد الأقصى للجولات',
                        ),
                        onChanged: (value) =>
                            _maxTurns = int.tryParse(value) ?? 0,
                        validator: (value) =>
                            (int.tryParse(value ?? '') ?? 0) < 1
                                ? 'مطلوب'
                                : null,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextFormField(
                        initialValue: '$_timeout',
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'المهلة بالثواني',
                        ),
                        onChanged: (value) =>
                            _timeout = int.tryParse(value) ?? 0,
                        validator: (value) =>
                            (int.tryParse(value ?? '') ?? 0) < 30
                                ? '30 ثانية على الأقل'
                                : null,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('إلغاء'),
        ),
        FilledButton.icon(
          onPressed: _submit,
          icon: const Icon(Icons.add_task),
          label: const Text('إنشاء'),
        ),
      ],
    );
  }

  Widget _field(
    TextEditingController controller,
    String label, {
    int minLines = 1,
    int maxLines = 1,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: controller,
        minLines: minLines,
        maxLines: maxLines,
        decoration: InputDecoration(labelText: label),
        validator: (value) =>
            value == null || value.trim().isEmpty ? 'هذا الحقل مطلوب' : null,
      ),
    );
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    final draft = TaskDraft(
      taskId: _taskId.text,
      projectId: 'PALWAKF_WORKSPACE_MANAGER',
      repository: 'firasfanon/palwakf_workspace_manager',
      branch: 'agent/workspace-manager-foundation-v1',
      expectedHead: _head.text,
      authorityReference: _authority.text,
      prompt: _prompt.text,
      constraints: _constraints.text
          .split(',')
          .map((value) => value.trim())
          .where((value) => value.isNotEmpty)
          .toList(growable: false),
      sandbox: _sandbox,
      maxTurns: _maxTurns,
      timeoutSeconds: _timeout,
      idempotencyKey: _idempotency.text,
      automaticFailureCode: 'OPENAI_API_PROJECT_INSUFFICIENT_QUOTA',
    );
    final errors = draft.validate();
    if (errors.isNotEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(errors.values.first)),
      );
      return;
    }
    Navigator.pop(context, draft);
  }
}
