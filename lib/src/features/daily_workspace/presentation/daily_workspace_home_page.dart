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
  DailyWorkKind _kind = DailyWorkKind.development;

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
    final selected = state.selectedTask;

    return RefreshIndicator(
      onRefresh: () => ref
          .read(dailyWorkspaceControllerProvider.notifier)
          .load(preferTaskId: state.selectedTaskId),
      child: ListView(
        key: const ValueKey<String>('daily-workspace-home'),
        padding: const EdgeInsets.all(24),
        children: <Widget>[
          _WelcomePanel(
            intentController: _intentController,
            selected: selected,
            tasks: state.tasks,
            kind: _kind,
            busy: state.executing,
            onTaskChanged: (taskId) {
              if (taskId != null) {
                ref
                    .read(dailyWorkspaceControllerProvider.notifier)
                    .selectTask(taskId);
              }
            },
            onKindChanged: (kind) {
              if (kind != null) setState(() => _kind = kind);
            },
            onStart: selected == null || state.executing
                ? null
                : () => _confirmAndExecute(selected),
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
          const SizedBox(height: 24),
          _SectionHeader(
            title: 'أعمالك الحالية',
            actionLabel: 'عرض الكل',
            onAction: () => context.go('/work'),
          ),
          const SizedBox(height: 10),
          if (!state.loading && state.tasks.isEmpty)
            _EmptyTasksCard(onAdvanced: () => context.go('/tasks'))
          else
            ...state.tasks.take(4).map(
                  (task) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: _DailyTaskCard(
                      task: task,
                      onUse: () {
                        ref
                            .read(dailyWorkspaceControllerProvider.notifier)
                            .selectTask(task.taskId);
                      },
                    ),
                  ),
                ),
          const SizedBox(height: 12),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextButton.icon(
              onPressed: () => context.go('/advanced'),
              icon: const Icon(Icons.admin_panel_settings_outlined),
              label: const Text('فتح الإدارة المتقدمة'),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmAndExecute(EngineeringTask task) async {
    final prompt = _intentController.text.trim();
    if (prompt.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('اكتب ما تريد إنجازه أولًا.')),
      );
      return;
    }

    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('اعتماد وبدء التنفيذ'),
        content: Text(
          _kind.mutating
              ? 'سيعمل النظام داخل نطاق المهمة «${task.title}» فقط. '
                  'لن يتم الدمج إلى main أو النشر أو تعديل قاعدة البيانات.'
              : 'سيجري النظام ${_kind.arabicLabel} ضمن نطاق المهمة '
                  '«${task.title}» دون تعديل الإنتاج أو قاعدة البيانات.',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            key: const ValueKey<String>('daily-confirm-execution'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('اعتماد وبدء التنفيذ'),
          ),
        ],
      ),
    );

    if (accepted != true || !mounted) return;
    await ref.read(dailyWorkspaceControllerProvider.notifier).execute(
          prompt: prompt,
          kind: _kind,
        );
  }
}

class _WelcomePanel extends StatelessWidget {
  const _WelcomePanel({
    required this.intentController,
    required this.selected,
    required this.tasks,
    required this.kind,
    required this.busy,
    required this.onTaskChanged,
    required this.onKindChanged,
    required this.onStart,
  });

  final TextEditingController intentController;
  final EngineeringTask? selected;
  final List<EngineeringTask> tasks;
  final DailyWorkKind kind;
  final bool busy;
  final ValueChanged<String?> onTaskChanged;
  final ValueChanged<DailyWorkKind?> onKindChanged;
  final VoidCallback? onStart;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(22),
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
                        'اكتب المطلوب، وسيتولى النظام خطوات التنفيذ الداخلية.',
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
                    'مثال: أصلح المشكلة الحالية في المهمة، ثم شغّل الاختبارات وتحقق من النتيجة.',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 14),
            LayoutBuilder(
              builder: (context, constraints) {
                final narrow = constraints.maxWidth < 680;
                final taskField = DropdownButtonFormField<String>(
                  key: const ValueKey<String>('daily-task-selector'),
                  initialValue: selected?.taskId,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'المشروع / المهمة',
                    border: OutlineInputBorder(),
                  ),
                  items: tasks
                      .map(
                        (task) => DropdownMenuItem<String>(
                          value: task.taskId,
                          child: Text(
                            task.title,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      )
                      .toList(growable: false),
                  onChanged: busy ? null : onTaskChanged,
                );
                final kindField = DropdownButtonFormField<DailyWorkKind>(
                  key: const ValueKey<String>('daily-work-kind'),
                  initialValue: kind,
                  decoration: const InputDecoration(
                    labelText: 'نوع العمل',
                    border: OutlineInputBorder(),
                  ),
                  items: DailyWorkKind.values
                      .map(
                        (value) => DropdownMenuItem<DailyWorkKind>(
                          value: value,
                          child: Text(value.arabicLabel),
                        ),
                      )
                      .toList(growable: false),
                  onChanged: busy ? null : onKindChanged,
                );
                if (narrow) {
                  return Column(
                    children: <Widget>[
                      taskField,
                      const SizedBox(height: 12),
                      kindField,
                    ],
                  );
                }
                return Row(
                  children: <Widget>[
                    Expanded(flex: 2, child: taskField),
                    const SizedBox(width: 12),
                    Expanded(child: kindField),
                  ],
                );
              },
            ),
            if (selected != null) ...<Widget>[
              const SizedBox(height: 10),
              Text(
                'المشروع: ${selected!.projectId} · '
                '${_friendlyTaskStatus(selected!.status)}',
                style: theme.textTheme.bodySmall,
              ),
            ],
            const SizedBox(height: 16),
            FilledButton.icon(
              key: const ValueKey<String>('daily-start-work'),
              onPressed: onStart,
              icon: Icon(busy ? Icons.hourglass_top : Icons.play_arrow),
              label: Text(busy ? 'جاري التنفيذ…' : 'اعتماد وبدء التنفيذ'),
            ),
            const SizedBox(height: 6),
            Text(
              'التفاصيل التقنية وخطة الأدوات والتفويضات تُدار في الخلفية. '
              'سيظهر لك فقط ما يحتاج قرارًا حقيقيًا منك.',
              style: theme.textTheme.bodySmall,
            ),
          ],
        ),
      ),
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
                          ? 'تم إنجاز مرحلة التنفيذ'
                          : failed
                              ? 'توقف التنفيذ بأمان'
                              : 'جاري تنفيذ المهمة',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(state.message ?? 'أتابع حالة المهمة…'),
              const SizedBox(height: 14),
              _ProgressSteps(phase: state.phase),
              if (state.changedFiles.isNotEmpty) ...<Widget>[
                const SizedBox(height: 12),
                Text('تم تعديل ${state.changedFiles.length} ملف/ملفات.'),
              ],
              if (state.activeRunId != null)
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('تفاصيل تقنية متقدمة'),
                  children: <Widget>[
                    Align(
                      alignment: AlignmentDirectional.centerStart,
                      child: SelectableText(
                        'Run: ${state.activeRunId}',
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

  @override
  Widget build(BuildContext context) {
    final current = phase.index;
    const labels = <String>[
      'التحقق من المشروع',
      'تجهيز التنفيذ',
      'تثبيت الموافقة',
      'تجهيز الأدوات',
      'بدء التنفيذ',
      'تنفيذ المهمة',
    ];
    final indexes = <int>[
      DailyExecutionPhase.syncing.index,
      DailyExecutionPhase.preparing.index,
      DailyExecutionPhase.authorizing.index,
      DailyExecutionPhase.planning.index,
      DailyExecutionPhase.dispatching.index,
      DailyExecutionPhase.running.index,
    ];

    return Column(
      children: List<Widget>.generate(labels.length, (index) {
        final reached =
            current > indexes[index] || phase == DailyExecutionPhase.completed;
        final active = current == indexes[index] &&
            phase != DailyExecutionPhase.completed &&
            phase != DailyExecutionPhase.failed;
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
                  'لم تكتمل المهمة',
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
  const _DailyTaskCard({required this.task, required this.onUse});

  final EngineeringTask task;
  final VoidCallback onUse;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: const CircleAvatar(child: Icon(Icons.assignment_outlined)),
        title: Text(task.title),
        subtitle: Text(
          task.description.trim().isEmpty
              ? _friendlyTaskStatus(task.status)
              : '${_friendlyTaskStatus(task.status)} · ${task.description}',
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        trailing: TextButton(
          onPressed: onUse,
          child: const Text('اختيار'),
        ),
      ),
    );
  }
}

class _EmptyTasksCard extends StatelessWidget {
  const _EmptyTasksCard({required this.onAdvanced});

  final VoidCallback onAdvanced;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: <Widget>[
            const Icon(Icons.inbox_outlined, size: 36),
            const SizedBox(height: 8),
            const Text('لا توجد مهمة مسجلة وجاهزة للعمل الآن.'),
            const SizedBox(height: 10),
            OutlinedButton(
              onPressed: onAdvanced,
              child: const Text('إعداد مهمة جديدة'),
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
        const Text('المهام المسجلة التي يمكنك العمل عليها من الواجهة اليومية.'),
        const SizedBox(height: 18),
        if (state.loading) const LinearProgressIndicator(),
        if (!state.loading && state.tasks.isEmpty)
          _EmptyTasksCard(onAdvanced: () => context.go('/tasks')),
        ...state.tasks.map(
          (task) => Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Card(
              child: ListTile(
                title: Text(task.title),
                subtitle: Text(_friendlyTaskStatus(task.status)),
                trailing: FilledButton.tonal(
                  onPressed: () => context.go(
                    '/home?taskId=${Uri.encodeComponent(task.taskId)}',
                  ),
                  child: const Text('العمل عليها'),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

String _friendlyTaskStatus(String status) {
  return switch (status) {
    'READY' => 'جاهزة',
    'WIP_REMOTE_CHECKPOINTED' => 'قيد العمل ومحفوظة',
    'IN_REVIEW' => 'بانتظار المراجعة',
    'INTEGRATED' => 'مكتملة',
    'BLOCKED' => 'تحتاج إجراء',
    'CANCELLED' => 'ملغاة',
    _ => 'مسجلة',
  };
}
