import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart' hide TextDirection;

import '../../../core/theme/palwakf_theme.dart';
import '../application/dashboard_controller.dart';
import '../domain/dashboard_models.dart';

class WorkspaceDashboardPage extends ConsumerStatefulWidget {
  const WorkspaceDashboardPage({super.key});

  @override
  ConsumerState<WorkspaceDashboardPage> createState() =>
      _WorkspaceDashboardPageState();
}

class _WorkspaceDashboardPageState
    extends ConsumerState<WorkspaceDashboardPage> {
  @override
  void initState() {
    super.initState();
    Future<void>.microtask(
      () => ref.read(dashboardControllerProvider.notifier).load(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(dashboardControllerProvider);
    if (state.summary == null && state.loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.summary == null) {
      return _DisconnectedState(
        message: state.error,
        onRetry: ref.read(dashboardControllerProvider.notifier).load,
      );
    }
    final summary = state.summary!;
    return Column(
      children: <Widget>[
        if (state.loading) const LinearProgressIndicator(minHeight: 2),
        if (state.error != null)
          _ErrorBand(
            message: state.error!,
            onRetry: ref.read(dashboardControllerProvider.notifier).load,
          ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: ref.read(dashboardControllerProvider.notifier).load,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 40),
              children: <Widget>[
                _DashboardHeader(summary: summary),
                if (summary.managedWorkspace != null) ...<Widget>[
                  const SizedBox(height: 14),
                  _ManagedWorkspaceBand(status: summary.managedWorkspace!),
                ],
                const SizedBox(height: 18),
                _MetricGrid(summary: summary),
                const SizedBox(height: 26),
                _SectionTitle(
                  title: 'محفظة المشاريع',
                  actionLabel: 'كل المشاريع',
                  onPressed: () => context.go('/projects'),
                ),
                const SizedBox(height: 10),
                _ProjectTable(projects: summary.projects),
                const SizedBox(height: 26),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final narrow = constraints.maxWidth < 900;
                    final children = <Widget>[
                      _OperationsPanel(summary: summary),
                      _ConnectionPanel(connection: summary.connection),
                    ];
                    if (narrow) {
                      return Column(
                        children: children
                            .expand(
                              (child) => <Widget>[
                                child,
                                const SizedBox(height: 16),
                              ],
                            )
                            .toList(growable: false),
                      );
                    }
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: children[0]),
                        const SizedBox(width: 16),
                        Expanded(child: children[1]),
                      ],
                    );
                  },
                ),
                const SizedBox(height: 10),
                _SectionTitle(
                  title: 'مركز الإجراء المصرح',
                  actionLabel: 'التنبيهات',
                  onPressed: () => context.go('/alerts'),
                ),
                const SizedBox(height: 10),
                _ActionCenter(actions: summary.actions),
                const SizedBox(height: 26),
                _SectionTitle(
                  title: 'النشاط ونقاط الاستئناف',
                  actionLabel: 'الأدلة',
                  onPressed: () => context.go('/evidence'),
                ),
                const SizedBox(height: 10),
                _ActivityAndCheckpoints(
                  activity: state.activity,
                  checkpoints: summary.checkpoints,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _ManagedWorkspaceBand extends StatelessWidget {
  const _ManagedWorkspaceBand({required this.status});

  final ManagedWorkspaceStatus status;

  @override
  Widget build(BuildContext context) {
    String head(String? value) {
      if (value == null || value.length < 8) return 'UNKNOWN';
      return value.substring(0, 8);
    }

    final capabilities = <String, CapabilityState>{
      'Orchestrator': status.orchestrator,
      'المصادقة': status.authentication,
      'GitHub': status.github,
      'Agents SDK': status.agentsSdk,
      'Codex': status.codex,
    };
    return _Panel(
      title: 'مساحة العمل الأساسية',
      icon: Icons.dns_outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            status.repository,
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: capabilities.entries
                .map(
                  (entry) => _StateChip(
                    label: '${entry.key}: ${entry.value.status}',
                    warning: entry.value.status == 'BLOCKED',
                  ),
                )
                .toList(growable: false),
          ),
          const SizedBox(height: 12),
          _FactRow(
            label: 'الرؤوس local / remote / PR',
            value:
                '${head(status.localHead)} / ${head(status.remoteHead)} / ${head(status.pullRequestHead)}',
          ),
          _FactRow(
            label: 'PR #${status.pullRequestNumber}',
            value: '${status.pullRequestState} · CI ${status.ciStatus}',
          ),
          _FactRow(
            label: 'الشجرة والكاتب',
            value:
                '${status.worktreeClean == true ? 'نظيفة' : 'غير نظيفة'} · ${status.activeWriterTaskId ?? 'لا يوجد كاتب نشط'}',
          ),
          _FactRow(
            label: 'المهمة الحالية',
            value: status.currentTaskId ?? 'لا توجد مهمة نشطة',
          ),
        ],
      ),
    );
  }
}

class _DashboardHeader extends StatelessWidget {
  const _DashboardHeader({required this.summary});

  final DashboardSummary summary;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      alignment: WrapAlignment.spaceBetween,
      crossAxisAlignment: WrapCrossAlignment.end,
      spacing: 16,
      runSpacing: 8,
      children: <Widget>[
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'لوحة العمليات',
              style: Theme.of(context)
                  .textTheme
                  .headlineSmall
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 4),
            const Text('حالة موحدة من مخازن التشغيل الموثقة'),
          ],
        ),
        Text(
          'آخر تجميع ${DateFormat('yyyy/MM/dd  HH:mm', 'ar').format(summary.generatedAt.toLocal())}',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({required this.summary});

  final DashboardSummary summary;

  @override
  Widget build(BuildContext context) {
    final metrics =
        <({String label, String value, String detail, IconData icon})>[
      (
        label: 'المشاريع الجاهزة',
        value: '${summary.portfolioReady}/${summary.portfolioTotal}',
        detail: '${summary.portfolioAttentionRequired} تحتاج مراجعة',
        icon: Icons.hub_outlined,
      ),
      (
        label: 'المهام النشطة',
        value: '${summary.tasks.activeTaskIds.length}',
        detail: '${summary.tasks.verified} موثقة',
        icon: Icons.task_alt_outlined,
      ),
      (
        label: 'صحة الأدوات',
        value: '${summary.tools.healthy}/${summary.tools.total}',
        detail: '${summary.tools.requiredAttention} تحتاج انتباهًا',
        icon: Icons.health_and_safety_outlined,
      ),
      (
        label: 'إجراء بشري',
        value: '${summary.humanActionRequired}',
        detail: '${summary.criticalAlertCount} حرج',
        icon: Icons.notification_important_outlined,
      ),
      (
        label: 'كتّاب المستودعات',
        value: '${summary.activeRepositoryWriters}',
        detail: 'كاتب واحد كحد أقصى لكل مستودع',
        icon: Icons.edit_note_outlined,
      ),
    ];
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth >= 1200
            ? 5
            : constraints.maxWidth >= 760
                ? 3
                : constraints.maxWidth >= 520
                    ? 2
                    : 1;
        final width = (constraints.maxWidth - (columns - 1) * 12) / columns;
        return Wrap(
          spacing: 12,
          runSpacing: 12,
          children: metrics
              .map(
                (metric) => SizedBox(
                  width: width,
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        children: <Widget>[
                          Icon(metric.icon, size: 22),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Text(metric.label),
                                const SizedBox(height: 4),
                                Text(
                                  metric.value,
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleLarge
                                      ?.copyWith(fontWeight: FontWeight.w800),
                                ),
                                Text(
                                  metric.detail,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
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

class _ProjectTable extends StatelessWidget {
  const _ProjectTable({required this.projects});

  final List<PortfolioProjectSummary> projects;

  @override
  Widget build(BuildContext context) {
    if (projects.isEmpty) {
      return const _EmptyBand(
        icon: Icons.hub_outlined,
        message: 'لا توجد مشاريع مسجلة في سجل المشاريع.',
      );
    }
    return Column(
      children: projects
          .map(
            (project) => Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: InkWell(
                onTap: () => context.go('/projects/${project.projectId}'),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: LayoutBuilder(
                    builder: (context, constraints) {
                      final compact = constraints.maxWidth < 720;
                      final identity = Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                            project.displayName,
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            project.repositoryFullName,
                            textDirection: TextDirection.ltr,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          if (project.observedHead != null) ...<Widget>[
                            const SizedBox(height: 6),
                            Text(
                              '${project.observedBranch ?? 'UNKNOWN'} · ${project.observedHead!.substring(0, 10)}',
                              textDirection: TextDirection.ltr,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ],
                      );
                      final facts = Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: <Widget>[
                          _StateChip(
                            label: project.readiness,
                            warning: project.attentionRequired,
                          ),
                          _StateChip(label: 'CI ${project.ciStatus}'),
                          _StateChip(
                            label: 'نشر ${project.deploymentStatus}',
                          ),
                          _StateChip(label: project.freshness),
                          _StateChip(label: '${project.taskCount} مهام'),
                          if (project.activeWriter)
                            const _StateChip(label: 'كاتب نشط', warning: true),
                        ],
                      );
                      if (compact) {
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: <Widget>[
                            identity,
                            const SizedBox(height: 12),
                            facts,
                            if (project.topCandidateTitle != null) ...<Widget>[
                              const SizedBox(height: 10),
                              Text(
                                'المرشح الأعلى: ${project.topCandidateTitle}',
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ],
                        );
                      }
                      return Row(
                        children: <Widget>[
                          Expanded(flex: 3, child: identity),
                          const SizedBox(width: 16),
                          Expanded(flex: 4, child: facts),
                          const Icon(Icons.chevron_left),
                        ],
                      );
                    },
                  ),
                ),
              ),
            ),
          )
          .toList(growable: false),
    );
  }
}

class _OperationsPanel extends StatelessWidget {
  const _OperationsPanel({required this.summary});

  final DashboardSummary summary;

  @override
  Widget build(BuildContext context) {
    final facts = <(String, String)>[
      ('إجمالي المهام', '${summary.tasks.total}'),
      ('قيد التنفيذ', '${summary.tasks.running}'),
      ('في الانتظار', '${summary.tasks.queued}'),
      ('بانتظار التحقق', '${summary.tasks.pendingVerification}'),
      ('قديمة', '${summary.tasks.stale}'),
      ('فاشلة', '${summary.tasks.failed}'),
    ];
    return _Panel(
      title: 'تشغيل المهام',
      icon: Icons.task_alt_outlined,
      child: Wrap(
        spacing: 12,
        runSpacing: 12,
        children: facts
            .map(
              (fact) => SizedBox(
                width: 140,
                child: ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: Text(fact.$1),
                  trailing: Text(
                    fact.$2,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
              ),
            )
            .toList(growable: false),
      ),
    );
  }
}

class _ConnectionPanel extends StatelessWidget {
  const _ConnectionPanel({required this.connection});

  final ConnectionReadinessSummary connection;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'جاهزية الاتصال',
      icon: Icons.cable_outlined,
      child: Column(
        children: <Widget>[
          _FactRow(
            label: 'الوضع المحلي الآمن',
            value: connection.localSecure ? 'مفعل' : 'غير مفعل',
          ),
          _FactRow(
            label: 'مصادقة الخدمة',
            value: connection.authenticationConfigured ? 'مهيأة' : 'غير مهيأة',
          ),
          _FactRow(
            label: 'المخزن والعمّال',
            value: connection.storeHealthy && connection.workersStarted
                ? 'جاهز'
                : 'غير جاهز',
          ),
          _FactRow(
            label: 'ChatGPT المباشر',
            value: connection.chatgptLiveState,
          ),
          _FactRow(
            label: 'توافق الاستئناف',
            value: connection.executionHostCompatibility,
          ),
        ],
      ),
    );
  }
}

class _ActionCenter extends StatelessWidget {
  const _ActionCenter({required this.actions});

  final List<DashboardAction> actions;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      children: actions
          .map(
            (action) => Tooltip(
              message: action.enabled
                  ? action.authority
                  : action.disabledReason ?? 'غير متاح',
              child: OutlinedButton.icon(
                onPressed:
                    action.enabled ? () => context.go(action.route) : null,
                icon: const Icon(Icons.arrow_back),
                label: Text(action.label),
              ),
            ),
          )
          .toList(growable: false),
    );
  }
}

class _ActivityAndCheckpoints extends StatelessWidget {
  const _ActivityAndCheckpoints({
    required this.activity,
    required this.checkpoints,
  });

  final List<RecentActivity> activity;
  final List<ResumeCheckpointSummary> checkpoints;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final activityPanel = _Panel(
          title: 'آخر النشاط',
          icon: Icons.timeline_outlined,
          child: activity.isEmpty
              ? const Text('لا يوجد نشاط مسجل.')
              : Column(
                  children: activity
                      .take(6)
                      .map(
                        (item) => _FactRow(
                          label: item.title,
                          value: '${item.subjectId} · ${item.status}',
                        ),
                      )
                      .toList(growable: false),
                ),
        );
        final checkpointPanel = _Panel(
          title: 'نقاط الاستئناف',
          icon: Icons.bookmark_outline,
          child: checkpoints.isEmpty
              ? const Text('لا توجد مهمة نشطة قابلة للاستئناف.')
              : Column(
                  children: checkpoints
                      .take(6)
                      .map(
                        (item) => ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(
                            item.taskId,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          subtitle: Text(item.nextAction),
                          trailing: Text(item.status),
                          onTap: () => context.go('/tasks'),
                        ),
                      )
                      .toList(growable: false),
                ),
        );
        if (constraints.maxWidth < 900) {
          return Column(
            children: <Widget>[
              activityPanel,
              const SizedBox(height: 16),
              checkpointPanel,
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(child: activityPanel),
            const SizedBox(width: 16),
            Expanded(child: checkpointPanel),
          ],
        );
      },
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({
    required this.title,
    required this.actionLabel,
    required this.onPressed,
  });

  final String title;
  final String actionLabel;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Expanded(
          child: Text(
            title,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
        ),
        TextButton(onPressed: onPressed, child: Text(actionLabel)),
      ],
    );
  }
}

class _Panel extends StatelessWidget {
  const _Panel({
    required this.title,
    required this.icon,
    required this.child,
  });

  final String title;
  final IconData icon;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).dividerColor),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(icon, size: 20),
                const SizedBox(width: 8),
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ],
            ),
            const Divider(height: 24),
            child,
          ],
        ),
      ),
    );
  }
}

class _FactRow extends StatelessWidget {
  const _FactRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: <Widget>[
          Expanded(child: Text(label)),
          const SizedBox(width: 12),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.end,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

class _StateChip extends StatelessWidget {
  const _StateChip({required this.label, this.warning = false});

  final String label;
  final bool warning;

  @override
  Widget build(BuildContext context) {
    return Chip(
      avatar: Icon(
        warning ? Icons.warning_amber : Icons.check_circle_outline,
        size: 16,
        color: warning ? PalWakfTheme.royalRed : PalWakfTheme.successGreen,
      ),
      label: Text(label, overflow: TextOverflow.ellipsis),
    );
  }
}

class _EmptyBand extends StatelessWidget {
  const _EmptyBand({required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 40),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(icon, size: 36),
            const SizedBox(height: 10),
            Text(message, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}

class _DisconnectedState extends StatelessWidget {
  const _DisconnectedState({required this.message, required this.onRetry});

  final String? message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Icon(Icons.link_off_outlined, size: 42),
              const SizedBox(height: 12),
              Text(
                'خدمة العمليات غير متصلة',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              Text(
                message ?? 'لم تصل بيانات موثقة من Orchestrator.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 18),
              FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('إعادة المحاولة'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ErrorBand extends StatelessWidget {
  const _ErrorBand({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
        child: Row(
          children: <Widget>[
            const Icon(Icons.error_outline),
            const SizedBox(width: 10),
            Expanded(child: Text(message)),
            IconButton(
              tooltip: 'إعادة المحاولة',
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
      ),
    );
  }
}
