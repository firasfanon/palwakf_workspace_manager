import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/presentation/preview_mode_ui.dart';
import '../../orchestrator/application/operational_authorization.dart';
import '../application/engineering_os_controller.dart';
import '../domain/engineering_os_models.dart';

class EngineeringTaskBoardPage extends ConsumerStatefulWidget {
  const EngineeringTaskBoardPage({super.key});

  @override
  ConsumerState<EngineeringTaskBoardPage> createState() =>
      _EngineeringTaskBoardPageState();
}

class _EngineeringTaskBoardPageState
    extends ConsumerState<EngineeringTaskBoardPage> {
  @override
  void initState() {
    super.initState();
    Future<void>.microtask(
      () => ref.read(engineeringOsControllerProvider.notifier).load(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(engineeringOsControllerProvider);
    final authorization = ref.watch(operationalAuthorizationProvider);
    final canDispatch = authorization.asData?.value.canDispatch ?? false;
    final summary = state.summary;
    final dataAvailable = summary != null && state.error == null;
    final previewUnavailable =
        PreviewModeUi.isVisualPreview && state.error != null && summary == null;
    return Column(
      children: <Widget>[
        if (state.loading) const LinearProgressIndicator(minHeight: 2),
        _Header(
          active: PreviewModeUi.metricValue(
            state.tasks
                .where(
                  (task) =>
                      task.status != 'INTEGRATED' &&
                      task.status != 'CANCELLED' &&
                      task.status != 'SUPERSEDED',
                )
                .length,
            dataAvailable: dataAvailable,
          ),
          checkpointed: PreviewModeUi.metricValue(
            summary?.remoteCheckpointedTasks ?? 0,
            dataAvailable: dataAvailable,
          ),
          quarantined: PreviewModeUi.metricValue(
            summary?.quarantinedExtensions ?? 0,
            dataAvailable: dataAvailable,
          ),
          onRefresh: ref.read(engineeringOsControllerProvider.notifier).load,
          onCreate: previewUnavailable || !canDispatch
              ? null
              : () => _showCreateTask(context),
        ),
        if (previewUnavailable)
          const PreviewModeBanner()
        else if (state.error != null)
          Material(
            color: Theme.of(context).colorScheme.errorContainer,
            child: ListTile(
              leading: const Icon(Icons.error_outline),
              title: Text(state.error!),
              trailing: TextButton(
                onPressed:
                    ref.read(engineeringOsControllerProvider.notifier).load,
                child: const Text('إعادة المحاولة'),
              ),
            ),
          ),
        Expanded(
          child: previewUnavailable
              ? const _TaskBoardPreviewUnavailable()
              : state.tasks.isEmpty
                  ? const _EmptyBoard()
                  : _Board(
                      tasks: state.tasks,
                      canSyncRemoteWip: canDispatch,
                      onSyncRemoteWip: (task) =>
                          _syncRemoteWip(context, task),
                    ),
        ),
      ],
    );
  }

  Future<void> _showCreateTask(BuildContext context) async {
    final draft = await showDialog<NewEngineeringTaskDraft>(
      context: context,
      builder: (context) => const _NewTaskDialog(),
    );
    if (draft == null || !mounted) return;
    try {
      await ref
          .read(engineeringOsControllerProvider.notifier)
          .createTask(draft);
    } catch (error) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.toString())));
    }
  }

  Future<void> _syncRemoteWip(
    BuildContext context,
    EngineeringTask task,
  ) async {
    try {
      final updated = await ref
          .read(engineeringOsControllerProvider.notifier)
          .syncRemoteCheckpoint(task.taskId);
      if (!context.mounted) return;
      final sha = updated.latestRemoteTaskSha ?? '—';
      final shortSha = sha.length > 10 ? sha.substring(0, 10) : sha;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('تم التحقق من WIP البعيد ومزامنته: $shortSha'),
        ),
      );
    } catch (error) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString())),
      );
    }
  }
}

class _TaskBoardPreviewUnavailable extends StatelessWidget {
  const _TaskBoardPreviewUnavailable();

  @override
  Widget build(BuildContext context) {
    return const Column(
      children: <Widget>[
        Expanded(
          child: PreviewUnavailablePanel(
            icon: Icons.task_alt_outlined,
            title: 'بيانات المهام غير متاحة',
            description:
                'هذه معاينة بصرية ولا تمثل سجل مهام فارغًا. القيم التشغيلية ستظهر بعد الاتصال بمصدر الحقيقة.',
          ),
        ),
        Padding(
          padding: EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: EngineeringTaskPreviewCapabilitySample(),
        ),
      ],
    );
  }
}

class EngineeringTaskPreviewCapabilitySample extends StatelessWidget {
  const EngineeringTaskPreviewCapabilitySample({super.key});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      width: double.infinity,
      child: Card(
        key: const ValueKey<String>(
          'engineering-task-preview-capability-sample',
        ),
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 18,
            runSpacing: 12,
            children: <Widget>[
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 760),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Icon(
                      Icons.visibility_outlined,
                      color: scheme.secondary,
                    ),
                    const SizedBox(width: 12),
                    Flexible(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                            'نموذج معاينة غير تشغيلي',
                            style: Theme.of(context)
                                .textTheme
                                .titleSmall
                                ?.copyWith(fontWeight: FontWeight.w800),
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            'هذا المثال يعرض موضع وسلوك عناصر الواجهة فقط؛ لا يمثل مهمة أو حالة أو قيمة تشغيلية حقيقية.',
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              OutlinedButton.icon(
                key: const ValueKey<String>(
                  'preview-task-operations-capability-sample',
                ),
                onPressed: () => context.go('/operations'),
                icon: const Icon(Icons.settings_suggest_outlined, size: 18),
                label: const Text('مركز التشغيل'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.active,
    required this.checkpointed,
    required this.quarantined,
    required this.onRefresh,
    required this.onCreate,
  });

  final String active;
  final String checkpointed;
  final String quarantined;
  final VoidCallback onRefresh;
  final VoidCallback? onCreate;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 14),
      child: Wrap(
        alignment: WrapAlignment.spaceBetween,
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 16,
        runSpacing: 12,
        children: <Widget>[
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'لوحة المهام الهندسية',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const SizedBox(height: 4),
              const Text(
                'تُستأنف المهمة من فرع المهمة البعيد في GitHub، لا من جهاز سابق.',
              ),
            ],
          ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              _Metric(label: 'نشطة', value: active),
              _Metric(label: 'نقاط العمل المرفوعة', value: checkpointed),
              _Metric(label: 'توسعات بالحجر', value: quarantined),
              IconButton.outlined(
                tooltip: 'تحديث',
                onPressed: onRefresh,
                icon: const Icon(Icons.refresh),
              ),
              FilledButton.icon(
                onPressed: onCreate,
                icon: const Icon(Icons.add_task),
                label: const Text('مهمة جديدة'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Chip(label: Text('$label: $value'));
  }
}

class _Board extends StatefulWidget {
  const _Board({
    required this.tasks,
    required this.canSyncRemoteWip,
    required this.onSyncRemoteWip,
  });

  final List<EngineeringTask> tasks;
  final bool canSyncRemoteWip;
  final Future<void> Function(EngineeringTask task) onSyncRemoteWip;

  @override
  State<_Board> createState() => _BoardState();
}

class _BoardState extends State<_Board> {
  final ScrollController _horizontalController = ScrollController();
  final ScrollController _verticalController = ScrollController();

  static const columns = <(String, String)>[
    ('READY', 'جاهزة'),
    ('IN_PROGRESS', 'قيد التنفيذ'),
    ('WIP_REMOTE_CHECKPOINTED', 'WIP مرفوع'),
    ('READY_FOR_REVIEW', 'للمراجعة'),
    ('READY_FOR_INTEGRATION', 'للتكامل'),
    ('IN_MERGE_QUEUE', 'طابور الدمج'),
    ('RECONCILIATION_REQUIRED', 'تحتاج تسوية'),
    ('INTEGRATED', 'مدمجة'),
  ];

  @override
  void dispose() {
    _horizontalController.dispose();
    _verticalController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tasks = widget.tasks;
    return SingleChildScrollView(
      key: const ValueKey<String>('engineering-task-board-vertical-scroll'),
      controller: _verticalController,
      scrollDirection: Axis.vertical,
      child: Scrollbar(
        key: const ValueKey<String>(
          'engineering-task-board-horizontal-scrollbar',
        ),
        controller: _horizontalController,
        thumbVisibility: true,
        child: SingleChildScrollView(
          controller: _horizontalController,
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: columns.map((column) {
              final values =
                  tasks.where((task) => task.status == column.$1).toList();
              return Padding(
                padding: const EdgeInsetsDirectional.only(end: 12),
                child: SizedBox(
                  width: 300,
                  child: _TaskColumn(
                    status: column.$1,
                    title: column.$2,
                    tasks: values,
                    canSyncRemoteWip: widget.canSyncRemoteWip,
                    onSyncRemoteWip: widget.onSyncRemoteWip,
                  ),
                ),
              );
            }).toList(growable: false),
          ),
        ),
      ),
    );
  }
}

class _TaskColumn extends StatelessWidget {
  const _TaskColumn({
    required this.status,
    required this.title,
    required this.tasks,
    required this.canSyncRemoteWip,
    required this.onSyncRemoteWip,
  });

  final String status;
  final String title;
  final List<EngineeringTask> tasks;
  final bool canSyncRemoteWip;
  final Future<void> Function(EngineeringTask task) onSyncRemoteWip;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    title,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
                CircleAvatar(radius: 13, child: Text('${tasks.length}')),
              ],
            ),
            const SizedBox(height: 12),
            if (tasks.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 22),
                child: Center(child: Text('لا توجد مهام')),
              )
            else
              ...tasks.map(
                (task) => _TaskCard(
                  task: task,
                  canSyncRemoteWip: canSyncRemoteWip,
                  onSyncRemoteWip: onSyncRemoteWip,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _TaskCard extends StatelessWidget {
  const _TaskCard({
    required this.task,
    required this.canSyncRemoteWip,
    required this.onSyncRemoteWip,
  });

  final EngineeringTask task;
  final bool canSyncRemoteWip;
  final Future<void> Function(EngineeringTask task) onSyncRemoteWip;

  @override
  Widget build(BuildContext context) {
    String shortSha(String? sha) {
      if (sha == null || sha.length < 10) return '—';
      return sha.substring(0, 10);
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Text(
              task.title,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 5),
            SelectableText(
              task.taskId,
              textDirection: TextDirection.ltr,
              style: Theme.of(context).textTheme.labelSmall,
            ),
            const SizedBox(height: 10),
            _Fact(label: 'الفرع', value: task.taskBranch),
            _Fact(label: 'الأساس', value: shortSha(task.baseSha)),
            _Fact(
              label: 'نقطة العمل البعيدة',
              value: shortSha(task.latestRemoteTaskSha),
            ),
            _Fact(
              label: 'المنفذ',
              value:
                  '${task.actorType}: ${task.actorId}${task.providerId == null ? '' : ' / ${task.providerId}'}',
            ),
            _Fact(label: 'الاعتمادية', value: task.dependencyMode),
            const SizedBox(height: 8),
            Wrap(
              spacing: 5,
              runSpacing: 5,
              children: <Widget>[
                Chip(label: Text(task.riskClass)),
                Chip(label: Text(task.wipCheckpointStatus)),
                ...task.scopePatterns
                    .take(2)
                    .map((scope) => Chip(label: Text(scope))),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                OutlinedButton.icon(
                  key: ValueKey<String>(
                    'engineering-task-sync-wip-${task.taskId}',
                  ),
                  onPressed: canSyncRemoteWip
                      ? () => onSyncRemoteWip(task)
                      : null,
                  icon: const Icon(Icons.cloud_sync_outlined, size: 18),
                  label: const Text('مزامنة WIP البعيد'),
                ),
                OutlinedButton.icon(
                  key: ValueKey<String>(
                    'engineering-task-operations-${task.taskId}',
                  ),
                  onPressed: () => context.go(
                    Uri(
                      path: '/operations',
                      queryParameters: <String, String>{
                        'engineeringTaskId': task.taskId,
                      },
                    ).toString(),
                  ),
                  icon: const Icon(Icons.settings_suggest_outlined, size: 18),
                  label: const Text('مركز التشغيل'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Fact extends StatelessWidget {
  const _Fact({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: <Widget>[
          SizedBox(
            width: 78,
            child: Text(label, style: Theme.of(context).textTheme.labelSmall),
          ),
          Expanded(
            child: Text(
              value,
              textDirection: TextDirection.ltr,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyBoard extends StatelessWidget {
  const _EmptyBoard();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(Icons.view_kanban_outlined, size: 48),
          SizedBox(height: 12),
          Text('لا توجد مهام هندسية بعد'),
          SizedBox(height: 6),
          Text('أنشئ أول مهمة؛ ستبدأ من أساس Git موثق وفرع task/* صريح.'),
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
  final key = GlobalKey<FormState>();
  final taskId = TextEditingController(text: 'WM-MEGA-BATCH-NEXT');
  final title = TextEditingController();
  final description = TextEditingController();
  final baseSha = TextEditingController();
  final branch = TextEditingController(text: 'task/WM-MEGA-BATCH-NEXT');
  final owner = TextEditingController(text: 'firas');
  final actor = TextEditingController(text: 'firas');
  final provider = TextEditingController();
  final scopes = TextEditingController(text: 'lib/**,orchestrator/**');
  String actorType = 'HUMAN';

  @override
  void dispose() {
    for (final controller in <TextEditingController>[
      taskId,
      title,
      description,
      baseSha,
      branch,
      owner,
      actor,
      provider,
      scopes,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('مهمة Remote-first جديدة'),
      content: SizedBox(
        width: 620,
        child: Form(
          key: key,
          child: SingleChildScrollView(
            child: Column(
              children: <Widget>[
                _field(taskId, 'Task ID'),
                _field(title, 'العنوان'),
                _field(description, 'الوصف', lines: 3),
                _field(
                  baseSha,
                  'Integrated Base SHA',
                  ltr: true,
                  helperText:
                      'آخر Integrated Accepted Head فقط؛ لا تستخدم Remote WIP HEAD.',
                ),
                _field(branch, 'Remote Task Branch', ltr: true),
                _field(owner, 'Owner'),
                _field(actor, 'Actor'),
                DropdownButtonFormField<String>(
                  initialValue: actorType,
                  decoration: const InputDecoration(labelText: 'Actor Type'),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem(value: 'HUMAN', child: Text('Human')),
                    DropdownMenuItem(value: 'AGENT', child: Text('Agent')),
                    DropdownMenuItem(value: 'LLM', child: Text('LLM')),
                  ],
                  onChanged: (value) =>
                      setState(() => actorType = value ?? 'HUMAN'),
                ),
                const SizedBox(height: 10),
                TextFormField(
                  controller: provider,
                  textDirection: TextDirection.ltr,
                  decoration: const InputDecoration(
                    labelText: 'Provider ID (اختياري)',
                    helperText:
                        'اتركه فارغًا للمهمة البشرية؛ مزود التنفيذ يُختار داخل Execution Run.',
                  ),
                  validator: (value) {
                    if (actorType == 'HUMAN' &&
                        (value ?? '').trim().isNotEmpty) {
                      return 'المهمة البشرية لا ترتبط بمزود؛ اترك الحقل فارغًا.';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 10),
                _field(scopes, 'Scopes مفصولة بفاصلة', ltr: true),
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
        FilledButton(onPressed: _submit, child: const Text('إنشاء')),
      ],
    );
  }

  Widget _field(
    TextEditingController controller,
    String label, {
    int lines = 1,
    bool ltr = false,
    String? helperText,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextFormField(
        controller: controller,
        maxLines: lines,
        textDirection: ltr ? TextDirection.ltr : null,
        decoration: InputDecoration(
          labelText: label,
          helperText: helperText,
        ),
        validator: (value) =>
            (value ?? '').trim().isEmpty && !label.contains('اختياري')
                ? 'مطلوب'
                : null,
      ),
    );
  }

  void _submit() {
    if (!key.currentState!.validate()) return;
    Navigator.pop(
      context,
      NewEngineeringTaskDraft(
        taskId: taskId.text.trim(),
        title: title.text.trim(),
        description: description.text.trim(),
        baseSha: baseSha.text.trim(),
        taskBranch: branch.text.trim(),
        ownerId: owner.text.trim(),
        actorId: actor.text.trim(),
        actorType: actorType,
        providerId: provider.text.trim().isEmpty ? null : provider.text.trim(),
        scopePatterns: scopes.text
            .split(',')
            .map((value) => value.trim())
            .where((value) => value.isNotEmpty)
            .toList(growable: false),
      ),
    );
  }
}
