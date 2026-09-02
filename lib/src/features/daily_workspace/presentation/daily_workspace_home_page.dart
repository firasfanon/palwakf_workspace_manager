import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../engineering_os/domain/engineering_os_models.dart';
import '../application/daily_workspace_controller.dart';

class DailyWorkspaceHomePage extends ConsumerStatefulWidget {
  const DailyWorkspaceHomePage({this.initialTaskId, super.key});

  final String? initialTaskId;

  @override
  ConsumerState<DailyWorkspaceHomePage> createState() =>
      _DailyWorkspaceHomePageState();
}

class _DailyWorkspaceHomePageState
    extends ConsumerState<DailyWorkspaceHomePage> {
  final _intentController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref
          .read(dailyWorkspaceControllerProvider.notifier)
          .load(preferTaskId: widget.initialTaskId);
    });
  }

  @override
  void dispose() {
    _intentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(dailyWorkspaceControllerProvider);

    return RefreshIndicator(
      onRefresh: () => ref
          .read(dailyWorkspaceControllerProvider.notifier)
          .load(preferTaskId: state.selectedTaskId),
      child: ListView(
        key: const ValueKey<String>('daily-workspace-home'),
        padding: const EdgeInsets.all(24),
        children: <Widget>[
          _WorkspaceStartPanel(
            intentController: _intentController,
            selectedProjectId: state.selectedProjectId,
            projectIds: state.projectIds,
            busy: state.executing,
            onProjectChanged: (projectId) {
              if (projectId != null) {
                ref
                    .read(dailyWorkspaceControllerProvider.notifier)
                    .selectProject(projectId);
              }
            },
            onStart: state.tasks.isEmpty || state.executing
                ? null
                : _confirmAndExecute,
          ),
          const SizedBox(height: 18),
          if (state.loading) const LinearProgressIndicator(),
          if (state.phase != DailyExecutionPhase.idle)
            _ExecutionProgressCard(state: state),
          if (state.error != null)
            Padding(
              padding: const EdgeInsets.only(top: 14),
              child: _FriendlyErrorCard(
                message: state.error!,
                technicalError: state.technicalError,
              ),
            ),
          const SizedBox(height: 28),
          _SectionHeader(
            title: 'أعمالك الحالية',
            actionLabel: 'عرض الكل',
            onAction: () => context.go('/work'),
          ),
          const SizedBox(height: 10),
          if (!state.loading && state.tasks.isEmpty)
            _EmptyTasksCard(onProjects: () => context.go('/projects'))
          else
            ...state.tasks.take(4).map(
                  (task) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: _DailyTaskCard(
                      task: task,
                      selected: task.taskId == state.selectedTaskId,
                      onResume: () {
                        ref
                            .read(dailyWorkspaceControllerProvider.notifier)
                            .selectTask(task.taskId);
                        _intentController.clear();
                      },
                    ),
                  ),
                ),
        ],
      ),
    );
  }

  Future<void> _confirmAndExecute() async {
    final prompt = _intentController.text.trim();
    if (prompt.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('اكتب ما تريد إنجازه أولًا.')),
      );
      return;
    }

    final controller = ref.read(dailyWorkspaceControllerProvider.notifier);
    DailyIntentPreview preview;
    try {
      preview = controller.previewIntent(prompt);
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(DailyWorkspaceController.userMessageForFailure(error)),
        ),
      );
      return;
    }

    if (!mounted) return;
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('بدء العمل؟'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Text(preview.confirmationText),
            const SizedBox(height: 12),
            Text(
              'إذا احتاج النظام قرارًا جديدًا خارج حدود العمل الحالية فسيتوقف ويطلب موافقتك.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            key: const ValueKey<String>('daily-confirm-execution'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('ابدأ التنفيذ'),
          ),
        ],
      ),
    );

    if (accepted != true || !mounted) return;
    await controller.execute(prompt: prompt, preview: preview);
  }
}

class _WorkspaceStartPanel extends StatelessWidget {
  const _WorkspaceStartPanel({
    required this.intentController,
    required this.selectedProjectId,
    required this.projectIds,
    required this.busy,
    required this.onProjectChanged,
    required this.onStart,
  });

  final TextEditingController intentController;
  final String? selectedProjectId;
  final List<String> projectIds;
  final bool busy;
  final ValueChanged<String?> onProjectChanged;
  final VoidCallback? onStart;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              children: <Widget>[
                const Icon(Icons.auto_awesome_outlined, size: 30),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        'مساحة عمل PalWakf',
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        'قل ما تريد إنجازه، وسيتولى النظام اختيار مسار العمل المناسب.',
                        style: theme.textTheme.bodyMedium,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 22),
            Text(
              'ماذا تريد أن تنجز؟',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              key: const ValueKey<String>('daily-intent-input'),
              controller: intentController,
              enabled: !busy,
              minLines: 3,
              maxLines: 6,
              decoration: const InputDecoration(
                hintText:
                    'مثال: أصلح مشكلة شاشة المشاريع، ثم شغّل الاختبارات وتحقق من النتيجة.',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 14),
            _ProjectSelector(
              projectIds: projectIds,
              selectedProjectId: selectedProjectId,
              busy: busy,
              onChanged: onProjectChanged,
            ),
            const SizedBox(height: 12),
            Row(
              children: <Widget>[
                const Icon(Icons.auto_fix_high_outlined, size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'سيحدد النظام نوع العمل والمهمة المناسبة تلقائيًا داخل المشروع المختار.',
                    style: theme.textTheme.bodySmall,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            FilledButton.icon(
              key: const ValueKey<String>('daily-start-work'),
              onPressed: onStart,
              icon: Icon(busy ? Icons.hourglass_top : Icons.play_arrow),
              label: Text(busy ? 'جاري العمل…' : 'ابدأ التنفيذ'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ProjectSelector extends StatelessWidget {
  const _ProjectSelector({
    required this.projectIds,
    required this.selectedProjectId,
    required this.busy,
    required this.onChanged,
  });

  final List<String> projectIds;
  final String? selectedProjectId;
  final bool busy;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) {
    if (projectIds.isEmpty) {
      return const InputDecorator(
        decoration: InputDecoration(
          labelText: 'المشروع',
          border: OutlineInputBorder(),
        ),
        child: Text('لا يوجد مشروع جاهز للعمل الآن'),
      );
    }

    if (projectIds.length == 1) {
      return InputDecorator(
        decoration: const InputDecoration(
          labelText: 'المشروع',
          border: OutlineInputBorder(),
        ),
        child: Text(
          DailyWorkspaceController.friendlyProjectLabel(projectIds.first),
        ),
      );
    }

    return DropdownButtonFormField<String>(
      key: const ValueKey<String>('daily-project-selector'),
      initialValue: selectedProjectId ?? projectIds.first,
      isExpanded: true,
      decoration: const InputDecoration(
        labelText: 'المشروع',
        border: OutlineInputBorder(),
      ),
      items: projectIds
          .map(
            (projectId) => DropdownMenuItem<String>(
              value: projectId,
              child: Text(
                DailyWorkspaceController.friendlyProjectLabel(projectId),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          )
          .toList(growable: false),
      onChanged: busy ? null : onChanged,
    );
  }
}

class _ExecutionProgressCard extends StatelessWidget {
  const _ExecutionProgressCard({required this.state});

  final DailyWorkspaceState state;

  @override
  Widget build(BuildContext context) {
    final success = state.phase == DailyExecutionPhase.completed;
    final failed = state.phase == DailyExecutionPhase.failed;
    final icon = success
        ? Icons.check_circle
        : failed
            ? Icons.error_outline
            : Icons.sync;

    return Padding(
      padding: const EdgeInsets.only(top: 18),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Icon(icon),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      success
                          ? 'تم إنجاز العمل'
                          : failed
                              ? 'توقف العمل بأمان'
                              : 'جاري العمل',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(state.message ?? 'أتابع حالة العمل…'),
              const SizedBox(height: 14),
              _ProgressSteps(phase: state.phase),
              if (state.changedFiles.isNotEmpty) ...<Widget>[
                const SizedBox(height: 12),
                const Text('تم حفظ التغييرات المطلوبة على فرع العمل.'),
              ],
              if (state.activeRunId != null)
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('تفاصيل تقنية'),
                  children: <Widget>[
                    Align(
                      alignment: AlignmentDirectional.centerStart,
                      child: SelectableText(
                        'Run: ${state.activeRunId}',
                        textDirection: TextDirection.ltr,
                      ),
                    ),
                    if (state.changedFiles.isNotEmpty)
                      Align(
                        alignment: AlignmentDirectional.centerStart,
                        child: Text(
                          'Changed files: ${state.changedFiles.length}',
                          textDirection: TextDirection.ltr,
                        ),
                      ),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProgressSteps extends StatelessWidget {
  const _ProgressSteps({required this.phase});

  final DailyExecutionPhase phase;

  int get _stage => switch (phase) {
        DailyExecutionPhase.idle => 0,
        DailyExecutionPhase.syncing => 0,
        DailyExecutionPhase.preparing ||
        DailyExecutionPhase.authorizing ||
        DailyExecutionPhase.planning =>
          1,
        DailyExecutionPhase.dispatching || DailyExecutionPhase.running => 2,
        DailyExecutionPhase.completed => 3,
        DailyExecutionPhase.failed => 2,
      };

  @override
  Widget build(BuildContext context) {
    const labels = <String>[
      'فهم الطلب',
      'تجهيز مساحة العمل',
      'تنفيذ العمل',
      'التحقق من النتيجة',
    ];

    return Column(
      children: List<Widget>.generate(labels.length, (index) {
        final reached =
            phase == DailyExecutionPhase.completed || index < _stage;
        final active = phase != DailyExecutionPhase.completed &&
            phase != DailyExecutionPhase.failed &&
            index == _stage;

        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 3),
          child: Row(
            children: <Widget>[
              Icon(
                reached
                    ? Icons.check_circle_outline
                    : active
                        ? Icons.radio_button_checked
                        : Icons.radio_button_unchecked,
                size: 18,
              ),
              const SizedBox(width: 8),
              Text(labels[index]),
            ],
          ),
        );
      }),
    );
  }
}

class _FriendlyErrorCard extends StatelessWidget {
  const _FriendlyErrorCard({
    required this.message,
    required this.technicalError,
  });

  final String message;
  final String? technicalError;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            const Row(
              children: <Widget>[
                Icon(Icons.info_outline),
                SizedBox(width: 8),
                Text(
                  'لم يكتمل العمل',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(message),
            if ((technicalError ?? '').isNotEmpty)
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: const Text('عرض السبب التقني'),
                children: <Widget>[
                  Align(
                    alignment: AlignmentDirectional.centerStart,
                    child: SelectableText(
                      technicalError!,
                      textDirection: TextDirection.ltr,
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
    required this.actionLabel,
    required this.onAction,
  });

  final String title;
  final String actionLabel;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Expanded(
          child: Text(
            title,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
          ),
        ),
        TextButton(onPressed: onAction, child: Text(actionLabel)),
      ],
    );
  }
}

class _DailyTaskCard extends StatelessWidget {
  const _DailyTaskCard({
    required this.task,
    required this.selected,
    required this.onResume,
  });

  final EngineeringTask task;
  final bool selected;
  final VoidCallback onResume;

  @override
  Widget build(BuildContext context) {
    final title = DailyWorkspaceController.friendlyTaskTitle(task);
    final project =
        DailyWorkspaceController.friendlyProjectLabel(task.projectId);
    final status = DailyWorkspaceController.friendlyTaskStatus(task.status);

    return Card(
      child: ListTile(
        selected: selected,
        leading: const CircleAvatar(child: Icon(Icons.assignment_outlined)),
        title: Text(title),
        subtitle: Text('$project · $status'),
        trailing: TextButton(
          onPressed: onResume,
          child: Text(selected ? 'محدد' : 'استئناف'),
        ),
      ),
    );
  }
}

class _EmptyTasksCard extends StatelessWidget {
  const _EmptyTasksCard({required this.onProjects});

  final VoidCallback onProjects;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: <Widget>[
            const Icon(Icons.inbox_outlined, size: 36),
            const SizedBox(height: 8),
            const Text('لا يوجد عمل جاهز للمتابعة الآن.'),
            const SizedBox(height: 10),
            OutlinedButton(
              onPressed: onProjects,
              child: const Text('عرض مشاريعي'),
            ),
          ],
        ),
      ),
    );
  }
}

class DailyWorkspaceTasksPage extends ConsumerStatefulWidget {
  const DailyWorkspaceTasksPage({super.key});

  @override
  ConsumerState<DailyWorkspaceTasksPage> createState() =>
      _DailyWorkspaceTasksPageState();
}

class _DailyWorkspaceTasksPageState
    extends ConsumerState<DailyWorkspaceTasksPage> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(dailyWorkspaceControllerProvider.notifier).load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(dailyWorkspaceControllerProvider);
    return ListView(
      key: const ValueKey<String>('daily-workspace-tasks'),
      padding: const EdgeInsets.all(24),
      children: <Widget>[
        Text(
          'أعمالي',
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 4),
        const Text('الأعمال التي يمكنك استئنافها من مساحة العمل اليومية.'),
        const SizedBox(height: 18),
        if (state.loading) const LinearProgressIndicator(),
        if (!state.loading && state.tasks.isEmpty)
          _EmptyTasksCard(onProjects: () => context.go('/projects')),
        ...state.tasks.map(
          (task) => Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Card(
              child: ListTile(
                leading: const CircleAvatar(
                  child: Icon(Icons.work_outline),
                ),
                title: Text(
                  DailyWorkspaceController.friendlyTaskTitle(task),
                ),
                subtitle: Text(
                  '${DailyWorkspaceController.friendlyProjectLabel(task.projectId)}'
                  ' · ${DailyWorkspaceController.friendlyTaskStatus(task.status)}',
                ),
                trailing: FilledButton.tonal(
                  onPressed: () => context.go(
                    '/home?taskId=${Uri.encodeComponent(task.taskId)}',
                  ),
                  child: const Text('استئناف'),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
