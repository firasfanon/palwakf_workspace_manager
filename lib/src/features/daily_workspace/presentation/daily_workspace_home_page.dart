import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../engineering_os/domain/engineering_os_models.dart';
import '../application/daily_workspace_controller.dart';
import '../domain/user_workspace_insights.dart';

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
  final _intentFocus = FocusNode();

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
    _intentFocus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(dailyWorkspaceControllerProvider);
    final insights = UserWorkspaceInsights.fromTasks(state.tasks);

    return RefreshIndicator(
      onRefresh: () => ref
          .read(dailyWorkspaceControllerProvider.notifier)
          .load(preferTaskId: state.selectedTaskId),
      child: ListView(
        key: const ValueKey<String>('daily-workspace-home'),
        padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 28),
        children: <Widget>[
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1480),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  _WelcomeStrip(state: state, insights: insights),
                  const SizedBox(height: 18),
                  _CommandCenter(
                    intentController: _intentController,
                    intentFocus: _intentFocus,
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
                    onQuickAction: _applyQuickAction,
                    onStart: state.tasks.isEmpty || state.executing
                        ? null
                        : _confirmAndExecute,
                  ),
                  if (state.loading) ...<Widget>[
                    const SizedBox(height: 14),
                    const LinearProgressIndicator(),
                  ],
                  if (state.phase != DailyExecutionPhase.idle) ...<Widget>[
                    const SizedBox(height: 18),
                    _ExecutionProgressCard(state: state),
                  ],
                  if (state.error != null) ...<Widget>[
                    const SizedBox(height: 14),
                    _FriendlyErrorCard(
                      message: state.error!,
                      technicalError: state.technicalError,
                    ),
                  ],
                  const SizedBox(height: 24),
                  _HomeMetricGrid(insights: insights),
                  const SizedBox(height: 28),
                  LayoutBuilder(
                    builder: (context, constraints) {
                      final wide = constraints.maxWidth >= 980;
                      final work = _ContinuationSection(
                        tasks: insights.continuationTasks,
                        selectedTaskId: state.selectedTaskId,
                        loading: state.loading,
                        onResume: _resumeTask,
                        onAll: () => context.go('/work'),
                        onProjects: () => context.go('/projects'),
                      );
                      final suggestion = _SuggestionPanel(
                        suggestion: insights.primarySuggestion,
                        onOpenSuggestion: (task) => _resumeTask(task.taskId),
                        onDashboard: () => context.go('/overview'),
                      );

                      if (!wide) {
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: <Widget>[
                            work,
                            const SizedBox(height: 18),
                            suggestion,
                          ],
                        );
                      }

                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(flex: 7, child: work),
                          const SizedBox(width: 18),
                          Expanded(flex: 3, child: suggestion),
                        ],
                      );
                    },
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _applyQuickAction(String text) {
    _intentController.text = text;
    _intentController.selection = TextSelection.collapsed(offset: text.length);
    _intentFocus.requestFocus();
  }

  void _resumeTask(String taskId) {
    ref.read(dailyWorkspaceControllerProvider.notifier).selectTask(taskId);
    _intentController.clear();
    _intentFocus.requestFocus();
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

class _WelcomeStrip extends StatelessWidget {
  const _WelcomeStrip({required this.state, required this.insights});

  final DailyWorkspaceState state;
  final UserWorkspaceInsights insights;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final greeting = DateTime.now().hour < 12 ? 'صباح الخير' : 'مساء الخير';
    final dataReady = !state.loading && state.error == null;

    return Wrap(
      alignment: WrapAlignment.spaceBetween,
      crossAxisAlignment: WrapCrossAlignment.center,
      runSpacing: 10,
      children: <Widget>[
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              greeting,
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              insights.activeWorkCount == 0
                  ? 'ابدأ عملًا جديدًا أو تابع مشروعًا مسجلًا من هنا.'
                  : 'لديك ${insights.activeWorkCount} أعمال يمكنك متابعتها الآن.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
        Chip(
          avatar: Icon(
            dataReady ? Icons.check_circle_outline : Icons.sync,
            size: 17,
          ),
          label: Text(dataReady ? 'البيانات محدثة' : 'جاري تحديث البيانات'),
        ),
      ],
    );
  }
}

class _CommandCenter extends StatelessWidget {
  const _CommandCenter({
    required this.intentController,
    required this.intentFocus,
    required this.selectedProjectId,
    required this.projectIds,
    required this.busy,
    required this.onProjectChanged,
    required this.onQuickAction,
    required this.onStart,
  });

  final TextEditingController intentController;
  final FocusNode intentFocus;
  final String? selectedProjectId;
  final List<String> projectIds;
  final bool busy;
  final ValueChanged<String?> onProjectChanged;
  final ValueChanged<String> onQuickAction;
  final VoidCallback? onStart;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Container(
      key: const ValueKey<String>('workspace-command-center'),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: scheme.outlineVariant),
        gradient: LinearGradient(
          begin: AlignmentDirectional.topStart,
          end: AlignmentDirectional.bottomEnd,
          colors: <Color>[
            scheme.primary.withValues(alpha: 0.13),
            scheme.surface,
            scheme.surfaceContainerHighest.withValues(alpha: 0.75),
          ],
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(30),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              children: <Widget>[
                Container(
                  width: 46,
                  height: 46,
                  decoration: BoxDecoration(
                    color: scheme.primary.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(Icons.auto_awesome, color: scheme.primary),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        'ماذا تريد أن تنجز اليوم؟',
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        'اكتب طلبك بطريقتك. سيحدد Workspace مسار العمل المناسب في الخلفية.',
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            TextField(
              key: const ValueKey<String>('daily-intent-input'),
              controller: intentController,
              focusNode: intentFocus,
              enabled: !busy,
              minLines: 4,
              maxLines: 7,
              decoration: const InputDecoration(
                hintText:
                    'مثال: حسّن الصفحة الرئيسية واجعل متابعة المشاريع أوضح، ثم شغّل الاختبارات وتحقق من النتيجة.',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 14),
            LayoutBuilder(
              builder: (context, constraints) {
                final selector = _ProjectSelector(
                  projectIds: projectIds,
                  selectedProjectId: selectedProjectId,
                  busy: busy,
                  onChanged: onProjectChanged,
                );
                final action = FilledButton.icon(
                  key: const ValueKey<String>('daily-start-work'),
                  onPressed: onStart,
                  icon: Icon(
                    busy ? Icons.hourglass_top : Icons.play_arrow_rounded,
                  ),
                  label: Text(busy ? 'جاري العمل…' : 'ابدأ التنفيذ'),
                );

                if (constraints.maxWidth < 720) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      selector,
                      const SizedBox(height: 12),
                      SizedBox(height: 48, child: action),
                    ],
                  );
                }

                return Row(
                  children: <Widget>[
                    Expanded(child: selector),
                    const SizedBox(width: 12),
                    SizedBox(width: 190, height: 48, child: action),
                  ],
                );
              },
            ),
            const SizedBox(height: 16),
            Text(
              'اقتراحات سريعة',
              style: theme.textTheme.labelLarge?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                ActionChip(
                  avatar: const Icon(Icons.playlist_play, size: 18),
                  label: const Text('تابع آخر عمل'),
                  onPressed: busy
                      ? null
                      : () => onQuickAction(
                            'تابع آخر عمل مسجل، تحقق من حالته وأكمل الخطوة التالية المناسبة.',
                          ),
                ),
                ActionChip(
                  avatar: const Icon(Icons.fact_check_outlined, size: 18),
                  label: const Text('راجع المشروع'),
                  onPressed: busy
                      ? null
                      : () => onQuickAction(
                            'راجع حالة المشروع الحالية وحدد ما يحتاج انتباهًا دون تعديل.',
                          ),
                ),
                ActionChip(
                  avatar: const Icon(Icons.science_outlined, size: 18),
                  label: const Text('اختبر النسخة'),
                  onPressed: busy
                      ? null
                      : () => onQuickAction(
                            'اختبر النسخة الحالية وتحقق من النتائج دون توسيع النطاق.',
                          ),
                ),
                ActionChip(
                  avatar: const Icon(Icons.build_circle_outlined, size: 18),
                  label: const Text('أصلح مشكلة'),
                  onPressed: busy
                      ? null
                      : () => onQuickAction(
                            'أصلح المشكلة الحالية ضمن نطاق العمل المسجل ثم شغّل الاختبارات.',
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

class _HomeMetricGrid extends StatelessWidget {
  const _HomeMetricGrid({required this.insights});

  final UserWorkspaceInsights insights;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final columns = width >= 1080
            ? 4
            : width >= 620
                ? 2
                : 1;
        const gap = 12.0;
        final itemWidth = (width - gap * (columns - 1)) / columns;

        return Wrap(
          spacing: gap,
          runSpacing: gap,
          children: <Widget>[
            _MetricCard(
              width: itemWidth,
              icon: Icons.folder_copy_outlined,
              label: 'مشاريعي',
              value: '${insights.projectCount}',
              helper: 'مشروعات مرتبطة بمساحة العمل',
              onTap: () => context.go('/projects'),
            ),
            _MetricCard(
              width: itemWidth,
              icon: Icons.play_circle_outline,
              label: 'قيد المتابعة',
              value: '${insights.activeWorkCount}',
              helper: 'أعمال يمكن استئنافها الآن',
              onTap: () => context.go('/work'),
            ),
            _MetricCard(
              width: itemWidth,
              icon: Icons.priority_high_rounded,
              label: 'تحتاج انتباهك',
              value: '${insights.attentionCount}',
              helper: insights.attentionCount == 0
                  ? 'لا توجد قرارات معلقة'
                  : 'أعمال تستحق المراجعة أولًا',
              onTap: () => context.go('/overview'),
            ),
            _MetricCard(
              width: itemWidth,
              icon: Icons.task_alt,
              label: 'مكتمل',
              value: '${insights.completedCount}',
              helper: 'أعمال مسجلة كمكتملة',
              onTap: () => context.go('/overview'),
            ),
          ],
        );
      },
    );
  }
}

class _MetricCard extends StatefulWidget {
  const _MetricCard({
    required this.width,
    required this.icon,
    required this.label,
    required this.value,
    required this.helper,
    required this.onTap,
  });

  final double width;
  final IconData icon;
  final String label;
  final String value;
  final String helper;
  final VoidCallback onTap;

  @override
  State<_MetricCard> createState() => _MetricCardState();
}

class _MetricCardState extends State<_MetricCard> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return SizedBox(
      width: widget.width,
      child: MouseRegion(
        onEnter: (_) => setState(() => _hovered = true),
        onExit: (_) => setState(() => _hovered = false),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          decoration: BoxDecoration(
            color: _hovered
                ? scheme.surfaceContainerHighest.withValues(alpha: 0.82)
                : scheme.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: _hovered ? scheme.primary : scheme.outlineVariant,
            ),
          ),
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: widget.onTap,
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Row(
                children: <Widget>[
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: scheme.primary.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(13),
                    ),
                    child: Icon(widget.icon, color: scheme.primary),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          widget.value,
                          style: Theme.of(context)
                              .textTheme
                              .headlineSmall
                              ?.copyWith(fontWeight: FontWeight.w900),
                        ),
                        Text(
                          widget.label,
                          style: Theme.of(context)
                              .textTheme
                              .titleSmall
                              ?.copyWith(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          widget.helper,
                          style:
                              Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: scheme.onSurfaceVariant,
                                  ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ContinuationSection extends StatelessWidget {
  const _ContinuationSection({
    required this.tasks,
    required this.selectedTaskId,
    required this.loading,
    required this.onResume,
    required this.onAll,
    required this.onProjects,
  });

  final List<EngineeringTask> tasks;
  final String? selectedTaskId;
  final bool loading;
  final ValueChanged<String> onResume;
  final VoidCallback onAll;
  final VoidCallback onProjects;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        _SectionTitle(
          title: 'استكمل من حيث توقفت',
          subtitle:
              'أهم الأعمال التي يمكنك متابعتها دون البحث في التفاصيل التقنية.',
          actionLabel: 'عرض جميع الأعمال',
          onAction: onAll,
        ),
        const SizedBox(height: 12),
        if (loading)
          const LinearProgressIndicator()
        else if (tasks.isEmpty)
          _EmptyTasksCard(onProjects: onProjects)
        else
          LayoutBuilder(
            builder: (context, constraints) {
              final twoColumns = constraints.maxWidth >= 720;
              final cardWidth = twoColumns
                  ? (constraints.maxWidth - 12) / 2
                  : constraints.maxWidth;
              return Wrap(
                spacing: 12,
                runSpacing: 12,
                children: tasks.take(4).map((task) {
                  return SizedBox(
                    width: cardWidth,
                    child: _ContinuationCard(
                      task: task,
                      selected: task.taskId == selectedTaskId,
                      onResume: () => onResume(task.taskId),
                    ),
                  );
                }).toList(growable: false),
              );
            },
          ),
      ],
    );
  }
}

class _ContinuationCard extends StatelessWidget {
  const _ContinuationCard({
    required this.task,
    required this.selected,
    required this.onResume,
  });

  final EngineeringTask task;
  final bool selected;
  final VoidCallback onResume;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final attention = UserWorkspaceInsights.needsAttention(task);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              children: <Widget>[
                CircleAvatar(
                  backgroundColor: scheme.primary.withValues(alpha: 0.12),
                  child: Icon(
                    attention
                        ? Icons.priority_high_rounded
                        : Icons.assignment_outlined,
                    color: attention ? scheme.error : scheme.primary,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        DailyWorkspaceController.friendlyTaskTitle(task),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        DailyWorkspaceController.friendlyProjectLabel(
                          task.projectId,
                        ),
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: _WorkStateChip(
                label: UserWorkspaceInsights.stageLabel(task),
                attention: attention,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              UserWorkspaceInsights.activityLabel(task),
              style: theme.textTheme.bodySmall?.copyWith(
                color: attention ? scheme.error : scheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 14),
            Align(
              alignment: AlignmentDirectional.centerEnd,
              child: FilledButton.tonal(
                onPressed: onResume,
                child: Text(selected ? 'محدد للمتابعة' : 'استئناف العمل'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _WorkStateChip extends StatelessWidget {
  const _WorkStateChip({required this.label, required this.attention});

  final String label;
  final bool attention;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final foreground = attention ? scheme.error : scheme.primary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: foreground.withValues(alpha: 0.09),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: foreground.withValues(alpha: 0.32)),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: foreground,
              fontWeight: FontWeight.w800,
            ),
      ),
    );
  }
}

class _SuggestionPanel extends StatelessWidget {
  const _SuggestionPanel({
    required this.suggestion,
    required this.onOpenSuggestion,
    required this.onDashboard,
  });

  final UserWorkspaceSuggestion? suggestion;
  final ValueChanged<EngineeringTask> onOpenSuggestion;
  final VoidCallback onDashboard;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Container(
          key: const ValueKey<String>('workspace-smart-suggestion'),
          decoration: BoxDecoration(
            color: scheme.secondary.withValues(alpha: 0.09),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: scheme.secondary.withValues(alpha: 0.38),
            ),
          ),
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Icon(Icons.lightbulb_outline, color: scheme.secondary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'يقترح عليك Workspace',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              if (suggestion == null)
                Text(
                  'لا يوجد إجراء عاجل الآن. يمكنك بدء طلب جديد من أعلى الصفحة.',
                  style: theme.textTheme.bodyMedium,
                )
              else ...<Widget>[
                Text(
                  suggestion!.title,
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  suggestion!.message,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 14),
                OutlinedButton.icon(
                  onPressed: () => onOpenSuggestion(suggestion!.task),
                  icon: const Icon(Icons.arrow_back),
                  label: Text(suggestion!.actionLabel),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: onDashboard,
          icon: const Icon(Icons.space_dashboard_outlined),
          label: const Text('فتح لوحة التحكم'),
        ),
      ],
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

    return Card(
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

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({
    required this.title,
    required this.subtitle,
    required this.actionLabel,
    required this.onAction,
  });

  final String title;
  final String subtitle;
  final String actionLabel;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: <Widget>[
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                title,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
              ),
              const SizedBox(height: 3),
              Text(
                subtitle,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
            ],
          ),
        ),
        TextButton(onPressed: onAction, child: Text(actionLabel)),
      ],
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
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1180),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Text(
                  'أعمالي',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 4),
                const Text(
                  'الأعمال التي يمكنك استئنافها من مساحة العمل اليومية.',
                ),
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
            ),
          ),
        ),
      ],
    );
  }
}
