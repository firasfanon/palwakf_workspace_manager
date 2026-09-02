import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../engineering_os/domain/engineering_os_models.dart';
import '../../workspace_catalog/application/workspace_catalog_controller.dart';
import '../application/daily_workspace_controller.dart';
import '../domain/user_workspace_insights.dart';

class UserWorkspaceDashboardPage extends ConsumerStatefulWidget {
  const UserWorkspaceDashboardPage({super.key});

  @override
  ConsumerState<UserWorkspaceDashboardPage> createState() =>
      _UserWorkspaceDashboardPageState();
}

class _UserWorkspaceDashboardPageState
    extends ConsumerState<UserWorkspaceDashboardPage> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final current = ref.read(dailyWorkspaceControllerProvider);
      if (current.tasks.isEmpty && !current.loading) {
        ref.read(dailyWorkspaceControllerProvider.notifier).load();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(dailyWorkspaceControllerProvider);
    final catalog = ref.watch(workspaceCatalogProvider);
    final insights = UserWorkspaceInsights.fromTasks(state.tasks);
    final scheme = Theme.of(context).colorScheme;

    return RefreshIndicator(
      onRefresh: () =>
          ref.read(dailyWorkspaceControllerProvider.notifier).load(),
      child: ListView(
        key: const ValueKey<String>('user-workspace-dashboard'),
        padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 28),
        children: <Widget>[
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1480),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  _DashboardHeader(
                    onNewWork: () => context.go('/home'),
                    onProjects: () => context.go('/projects'),
                  ),
                  const SizedBox(height: 18),
                  _WorkspaceCatalogSummary(catalog: catalog),
                  if (state.loading) ...<Widget>[
                    const SizedBox(height: 14),
                    const LinearProgressIndicator(),
                  ],
                  const SizedBox(height: 20),
                  _MetricGrid(insights: insights),
                  const SizedBox(height: 22),
                  LayoutBuilder(
                    builder: (context, constraints) {
                      final projectPanel = _ProjectActivityPanel(
                        summaries: insights.projectSummaries,
                        onProjects: () => context.go('/projects'),
                      );
                      final attentionPanel = _AttentionPanel(
                        tasks: insights.attentionTasks,
                        onOpen: (task) => context.go(
                          '/home?taskId=${Uri.encodeComponent(task.taskId)}',
                        ),
                      );
                      if (constraints.maxWidth < 960) {
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: <Widget>[
                            projectPanel,
                            const SizedBox(height: 16),
                            attentionPanel,
                          ],
                        );
                      }
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(flex: 6, child: projectPanel),
                          const SizedBox(width: 16),
                          Expanded(flex: 4, child: attentionPanel),
                        ],
                      );
                    },
                  ),
                  const SizedBox(height: 16),
                  LayoutBuilder(
                    builder: (context, constraints) {
                      final activePanel = _ActiveWorkPanel(
                        tasks: insights.activeTasks,
                        onOpen: (task) => context.go(
                          '/home?taskId=${Uri.encodeComponent(task.taskId)}',
                        ),
                        onAll: () => context.go('/work'),
                      );
                      final suggestionPanel = _SuggestionPanel(
                        suggestion: insights.primarySuggestion,
                        onOpen: (task) => context.go(
                          '/home?taskId=${Uri.encodeComponent(task.taskId)}',
                        ),
                      );
                      if (constraints.maxWidth < 960) {
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: <Widget>[
                            activePanel,
                            const SizedBox(height: 16),
                            suggestionPanel,
                          ],
                        );
                      }
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(flex: 6, child: activePanel),
                          const SizedBox(width: 16),
                          Expanded(flex: 4, child: suggestionPanel),
                        ],
                      );
                    },
                  ),
                  const SizedBox(height: 16),
                  _CurrentActivityPanel(
                    tasks: insights.continuationTasks,
                    onOpen: (task) => context.go(
                      '/home?taskId=${Uri.encodeComponent(task.taskId)}',
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'تعرض هذه اللوحة الحالة المسجلة فعليًا فقط؛ لا تعرض نسب تقدم تقديرية أو تواريخ غير موجودة في المصدر.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _WorkspaceCatalogSummary extends StatelessWidget {
  const _WorkspaceCatalogSummary({required this.catalog});

  final WorkspaceCatalogState catalog;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final values = <({IconData icon, String label, int value})>[
          (
            icon: Icons.grid_view_outlined,
            label: 'إجمالي مساحة العمل',
            value: catalog.totalCount,
          ),
          (
            icon: Icons.account_balance_outlined,
            label: 'مشاريع PalWakf',
            value: catalog.governedCount,
          ),
          (
            icon: Icons.menu_book_outlined,
            label: 'الأبحاث',
            value: catalog.researchCount,
          ),
          (
            icon: Icons.person_outline,
            label: 'المشاريع الخاصة',
            value: catalog.privateCount,
          ),
        ];
        final columns = constraints.maxWidth >= 900
            ? 4
            : constraints.maxWidth >= 520
                ? 2
                : 1;
        const gap = 10.0;
        final width = (constraints.maxWidth - gap * (columns - 1)) / columns;
        return Wrap(
          spacing: gap,
          runSpacing: gap,
          children: values
              .map(
                (entry) => SizedBox(
                  width: width,
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Row(
                        children: <Widget>[
                          Icon(entry.icon),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Text(
                                  '${entry.value}',
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleLarge
                                      ?.copyWith(
                                        fontWeight: FontWeight.w900,
                                      ),
                                ),
                                Text(entry.label),
                              ],
                            ),
                          ),
                        ],
                      ),
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

class _DashboardHeader extends StatelessWidget {
  const _DashboardHeader({required this.onNewWork, required this.onProjects});

  final VoidCallback onNewWork;
  final VoidCallback onProjects;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return LayoutBuilder(
      builder: (context, constraints) {
        final title = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'لوحة التحكم',
              style: theme.textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'نظرة موحدة على مشاريع PalWakf والأبحاث والمشاريع الخاصة وأعمالك الحالية.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        );
        final actions = Wrap(
          spacing: 8,
          runSpacing: 8,
          children: <Widget>[
            OutlinedButton.icon(
              onPressed: onProjects,
              icon: const Icon(Icons.folder_open_outlined),
              label: const Text('مشاريعي'),
            ),
            FilledButton.icon(
              onPressed: onNewWork,
              icon: const Icon(Icons.add),
              label: const Text('عمل جديد'),
            ),
          ],
        );

        if (constraints.maxWidth < 700) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              title,
              const SizedBox(height: 14),
              actions,
            ],
          );
        }
        return Row(children: <Widget>[Expanded(child: title), actions]);
      },
    );
  }
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({required this.insights});

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
              value: insights.projectCount,
              label: 'المشاريع',
              helper: 'مشروعات مرتبطة',
            ),
            _MetricCard(
              width: itemWidth,
              icon: Icons.play_circle_outline,
              value: insights.activeWorkCount,
              label: 'قيد العمل',
              helper: 'أعمال قابلة للمتابعة',
            ),
            _MetricCard(
              width: itemWidth,
              icon: Icons.priority_high_rounded,
              value: insights.attentionCount,
              label: 'تحتاجك',
              helper: 'قرار أو مراجعة مطلوبة',
            ),
            _MetricCard(
              width: itemWidth,
              icon: Icons.task_alt,
              value: insights.completedCount,
              label: 'مكتمل',
              helper: 'أعمال منتهية',
            ),
          ],
        );
      },
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.width,
    required this.icon,
    required this.value,
    required this.label,
    required this.helper,
  });

  final double width;
  final IconData icon;
  final int value;
  final String label;
  final String helper;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return SizedBox(
      width: width,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(
            children: <Widget>[
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: scheme.primary.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: scheme.primary),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      '$value',
                      style: theme.textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    Text(
                      label,
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      helper,
                      style: theme.textTheme.bodySmall?.copyWith(
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
    );
  }
}

class _ProjectActivityPanel extends StatelessWidget {
  const _ProjectActivityPanel(
      {required this.summaries, required this.onProjects});

  final List<UserProjectSummary> summaries;
  final VoidCallback onProjects;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'نشاط المشاريع',
      subtitle: 'حالة مباشرة مشتقة من الأعمال المسجلة لكل مشروع.',
      trailing: TextButton(
        onPressed: onProjects,
        child: const Text('عرض المشاريع'),
      ),
      child: summaries.isEmpty
          ? const _Empty(message: 'لا توجد مشاريع مسجلة بعد.')
          : Column(
              children: summaries.take(5).map((summary) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: _ProjectRow(summary: summary),
                );
              }).toList(growable: false),
            ),
    );
  }
}

class _ProjectRow extends StatelessWidget {
  const _ProjectRow({required this.summary});

  final UserProjectSummary summary;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final attention = summary.attentionCount > 0;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                summary.label,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            const SizedBox(width: 10),
            _StatusChip(label: summary.stageLabel, attention: attention),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          '${summary.activeCount} قيد المتابعة · ${summary.completedCount} مكتمل'
          '${attention ? ' · ${summary.attentionCount} تحتاج انتباهًا' : ''}',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: attention ? scheme.error : scheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}

class _AttentionPanel extends StatelessWidget {
  const _AttentionPanel({required this.tasks, required this.onOpen});

  final List<EngineeringTask> tasks;
  final ValueChanged<EngineeringTask> onOpen;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return _Panel(
      title: 'تحتاج انتباهك',
      subtitle: 'الأعمال التي تستحق قرارك أو مراجعتك أولًا.',
      child: tasks.isEmpty
          ? const _Empty(
              icon: Icons.check_circle_outline,
              message: 'لا توجد قرارات معلقة الآن.',
            )
          : Column(
              children: tasks.take(4).map((task) {
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: CircleAvatar(
                    backgroundColor: scheme.error.withValues(alpha: 0.12),
                    child:
                        Icon(Icons.priority_high_rounded, color: scheme.error),
                  ),
                  title: Text(
                    DailyWorkspaceController.friendlyTaskTitle(task),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Text(UserWorkspaceInsights.activityLabel(task)),
                  trailing: IconButton(
                    tooltip: 'فتح',
                    onPressed: () => onOpen(task),
                    icon: const Icon(Icons.arrow_back),
                  ),
                );
              }).toList(growable: false),
            ),
    );
  }
}

class _ActiveWorkPanel extends StatelessWidget {
  const _ActiveWorkPanel({
    required this.tasks,
    required this.onOpen,
    required this.onAll,
  });

  final List<EngineeringTask> tasks;
  final ValueChanged<EngineeringTask> onOpen;
  final VoidCallback onAll;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'أعمال قيد المتابعة',
      subtitle: 'أعمالك النشطة الآن وحالتها المسجلة فعليًا.',
      trailing: TextButton(onPressed: onAll, child: const Text('عرض الكل')),
      child: tasks.isEmpty
          ? const _Empty(message: 'لا توجد أعمال نشطة حاليًا.')
          : Column(
              children: tasks.take(5).map((task) {
                final attention = UserWorkspaceInsights.needsAttention(task);
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(12),
                    onTap: () => onOpen(task),
                    child: Padding(
                      padding: const EdgeInsets.all(10),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          Row(
                            children: <Widget>[
                              Expanded(
                                child: Text(
                                  DailyWorkspaceController.friendlyTaskTitle(
                                    task,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleSmall
                                      ?.copyWith(fontWeight: FontWeight.w800),
                                ),
                              ),
                              const SizedBox(width: 10),
                              _StatusChip(
                                label: UserWorkspaceInsights.stageLabel(task),
                                attention: attention,
                              ),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Text(
                            '${DailyWorkspaceController.friendlyProjectLabel(task.projectId)} · '
                            '${UserWorkspaceInsights.activityLabel(task)}',
                            style:
                                Theme.of(context).textTheme.bodySmall?.copyWith(
                                      color: Theme.of(context)
                                          .colorScheme
                                          .onSurfaceVariant,
                                    ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              }).toList(growable: false),
            ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.attention});

  final String label;
  final bool attention;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final foreground = attention ? scheme.error : scheme.primary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
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
  const _SuggestionPanel({required this.suggestion, required this.onOpen});

  final UserWorkspaceSuggestion? suggestion;
  final ValueChanged<EngineeringTask> onOpen;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return _Panel(
      title: 'يقترح عليك Workspace',
      subtitle: 'اقتراح واحد مبني على الحالة المسجلة حاليًا.',
      child: suggestion == null
          ? const _Empty(
              icon: Icons.lightbulb_outline,
              message: 'لا يوجد اقتراح عاجل الآن.',
            )
          : Container(
              decoration: BoxDecoration(
                color: scheme.secondary.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: scheme.secondary.withValues(alpha: 0.32),
                ),
              ),
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  Text(
                    suggestion!.title,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 7),
                  Text(suggestion!.message),
                  const SizedBox(height: 14),
                  FilledButton.tonal(
                    onPressed: () => onOpen(suggestion!.task),
                    child: Text(suggestion!.actionLabel),
                  ),
                ],
              ),
            ),
    );
  }
}

class _CurrentActivityPanel extends StatelessWidget {
  const _CurrentActivityPanel({required this.tasks, required this.onOpen});

  final List<EngineeringTask> tasks;
  final ValueChanged<EngineeringTask> onOpen;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'النشاط الحالي',
      subtitle:
          'أحدث صورة متاحة من الأعمال المسجلة دون افتراض توقيت غير موجود.',
      child: tasks.isEmpty
          ? const _Empty(message: 'لا يوجد نشاط مسجل حاليًا.')
          : Wrap(
              spacing: 10,
              runSpacing: 10,
              children: tasks.take(6).map((task) {
                return ActionChip(
                  avatar: const Icon(Icons.history, size: 18),
                  label: Text(
                    '${DailyWorkspaceController.friendlyTaskTitle(task)} · '
                    '${UserWorkspaceInsights.activityLabel(task)}',
                  ),
                  onPressed: () => onOpen(task),
                );
              }).toList(growable: false),
            ),
    );
  }
}

class _Panel extends StatelessWidget {
  const _Panel({
    required this.title,
    required this.subtitle,
    required this.child,
    this.trailing,
  });

  final String title;
  final String subtitle;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
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
                              color: scheme.onSurfaceVariant,
                            ),
                      ),
                    ],
                  ),
                ),
                if (trailing != null) trailing!,
              ],
            ),
            const SizedBox(height: 18),
            child,
          ],
        ),
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty({required this.message, this.icon = Icons.inbox_outlined});

  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 20),
      child: Column(
        children: <Widget>[
          Icon(icon, size: 34, color: scheme.onSurfaceVariant),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: TextStyle(color: scheme.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}
