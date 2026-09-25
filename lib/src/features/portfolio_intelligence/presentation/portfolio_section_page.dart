import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../application/portfolio_intelligence_controller.dart';
import '../domain/portfolio_intelligence_models.dart';

class PortfolioSectionPage extends ConsumerStatefulWidget {
  const PortfolioSectionPage({
    required this.section,
    required this.title,
    super.key,
  });

  final String section;
  final String title;

  @override
  ConsumerState<PortfolioSectionPage> createState() =>
      _PortfolioSectionPageState();
}

class _PortfolioSectionPageState extends ConsumerState<PortfolioSectionPage> {
  late final PortfolioIntelligenceController _portfolioController;

  @override
  void initState() {
    super.initState();

    _portfolioController = ref.read(
      portfolioIntelligenceControllerProvider.notifier,
    );

    Future<void>.microtask(() async {
      if (!mounted) {
        return;
      }

      _portfolioController.startAutoRefresh();
      await _portfolioController.load();
    });
  }

  @override
  void dispose() {
    _portfolioController.stopAutoRefresh();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(portfolioIntelligenceControllerProvider);

    final snapshot = state.snapshot;

    if (snapshot == null && state.loading) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    if (snapshot == null) {
      return Center(
        child: FilledButton.icon(
          onPressed: () => ref
              .read(
                portfolioIntelligenceControllerProvider.notifier,
              )
              .load(),
          icon: const Icon(Icons.refresh),
          label: Text(
            state.error ?? 'إعادة تحميل بيانات المحفظة',
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () => ref
          .read(
            portfolioIntelligenceControllerProvider.notifier,
          )
          .load(),
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: <Widget>[
          Row(
            children: <Widget>[
              IconButton(
                tooltip: 'العودة إلى مركز القيادة',
                onPressed: () => context.go('/dashboard'),
                icon: const Icon(Icons.arrow_forward),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  widget.title,
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              IconButton(
                tooltip: 'تحديث',
                onPressed: state.loading
                    ? null
                    : () => ref
                        .read(
                          portfolioIntelligenceControllerProvider.notifier,
                        )
                        .load(),
                icon: const Icon(Icons.sync),
              ),
            ],
          ),
          if (state.error != null) ...<Widget>[
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  'تعذر تحديث أحد المصادر؛ '
                  'تُعرض آخر لقطة موثقة: ${state.error}',
                ),
              ),
            ),
          ],
          const SizedBox(height: 18),
          ..._sectionWidgets(context, snapshot),
        ],
      ),
    );
  }

  List<Widget> _sectionWidgets(
    BuildContext context,
    PortfolioCommandCenterSnapshot snapshot,
  ) {
    switch (widget.section) {
      case 'projects':
        return <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: FilledButton.icon(
                  onPressed: () => context.go('/advanced/projects-registry'),
                  icon: const Icon(Icons.radar),
                  label: const Text(
                    'سجل الإدخال والفحص المحكوم',
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          ...snapshot.projects.map(
            (project) => _ProjectTile(
              project: project,
              trailing: '${project.readiness} · ${project.truthState}',
            ),
          ),
        ];

      case 'timeline':
        return snapshot.projects
            .map(
              (project) => _ProjectTile(
                project: project,
                trailing: project.scopeProgressPercent == null
                    ? '${project.readiness} · التقدم غير متاح'
                    : '${project.scopeProgressPercent!.round()}%',
              ),
            )
            .toList(growable: false);

      case 'programs':
        return <Widget>[
          FilledButton.icon(
            onPressed: () => context.go('/projects'),
            icon: const Icon(Icons.playlist_add),
            label: const Text(
              'فتح سجل إدخال وفحص المشاريع',
            ),
          ),
          const SizedBox(height: 14),
          ...snapshot.projects.map(
            (project) => _ProjectTile(
              project: project,
              trailing: project.currentStatus,
            ),
          ),
        ];

      case 'dependencies':
        if (snapshot.dependencies.isEmpty) {
          return <Widget>[
            _MessageCard(
              text: snapshot.criticalPath.reasonAr,
            ),
          ];
        }

        return snapshot.dependencies
            .map(
              (edge) => Card(
                child: ListTile(
                  leading: const Icon(Icons.account_tree_outlined),
                  title: Text(
                    '${edge.producerProjectId} ← '
                    '${edge.consumerProjectId}',
                  ),
                  subtitle: Text(
                    '${edge.kind} · ${edge.contractId} · '
                    '${edge.status}',
                  ),
                ),
              ),
            )
            .toList(growable: false);

      case 'capabilities':
        return <Widget>[
          ..._registryGroup(
            'المهارات',
            snapshot.skills,
          ),
          ..._registryGroup(
            'القدرات',
            snapshot.capabilities,
          ),
          ..._registryGroup(
            'الأدوات',
            snapshot.tools,
          ),
        ];

      case 'agents':
        return <Widget>[
          ..._registryGroup(
            'الوكلاء',
            snapshot.agents,
          ),
          ..._registryGroup(
            'المزودون',
            snapshot.providers,
          ),
        ];

      case 'intelligence':
        return <Widget>[
          ...snapshot.sourceHealth.map(
            (item) => Card(
              child: ListTile(
                leading: const Icon(Icons.monitor_heart_outlined),
                title: Text(item.labelAr),
                subtitle: Text(
                  '${item.freshness}\n${item.detailAr}',
                ),
                isThreeLine: true,
                trailing: Chip(
                  label: Text(item.state),
                ),
              ),
            ),
          ),
          const SizedBox(height: 8),
          ...snapshot.recommendations.map(
            (item) => Card(
              child: ListTile(
                leading: const Icon(Icons.auto_awesome_rounded),
                title: Text(item.type),
                subtitle: Text(item.reasonAr),
                onTap: () => _openRecommendation(context, item),
              ),
            ),
          ),
        ];

      case 'reports':
        return snapshot.kpis
            .map(
              (item) => Card(
                child: ListTile(
                  leading: const Icon(Icons.analytics_outlined),
                  title: Text(item.labelAr),
                  subtitle: Text(item.explanationAr),
                  trailing: Text(
                    item.value,
                    style: const TextStyle(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ),
            )
            .toList(growable: false);

      case 'recommendations':
        return snapshot.recommendations
            .map(
              (item) => Card(
                child: ListTile(
                  leading: const Icon(Icons.auto_awesome_rounded),
                  title: Text(item.type),
                  subtitle: Text(item.reasonAr),
                  trailing: Chip(
                    label: Text(item.authority),
                  ),
                  onTap: () => _openRecommendation(context, item),
                ),
              ),
            )
            .toList(growable: false);

      case 'decisions':
        return snapshot.decisions
            .map(
              (item) => Card(
                child: ListTile(
                  leading: const Icon(Icons.gavel_outlined),
                  title: Text(item.summaryAr),
                  subtitle: Text(
                    '${item.kind} · ${item.status}',
                  ),
                  onTap: item.projectId == null
                      ? null
                      : () => context.go(
                            '/portfolio/projects/'
                            '${Uri.encodeComponent(item.projectId!)}',
                          ),
                ),
              ),
            )
            .toList(growable: false);

      case 'activity':
        return snapshot.recentChanges
            .map(
              (item) => Card(
                child: ListTile(
                  leading: const Icon(Icons.history),
                  title: Text(item.title),
                  subtitle: Text(
                    '${item.detail}\n${item.provenance}',
                  ),
                  isThreeLine: true,
                ),
              ),
            )
            .toList(growable: false);

      case 'waqf':
      case 'hajj-umrah':
      case 'gis':
        return <Widget>[
          const _MessageCard(
            text: 'لا يوجد Domain Registry سيادي مستورد '
                'لهذا التصنيف بعد. لن يتم تصنيف المشاريع '
                'من الاسم أو التخمين.',
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: () => context.go('/projects'),
            icon: const Icon(Icons.folder_open),
            label: const Text('فتح سجل المشاريع'),
          ),
        ];

      default:
        return const <Widget>[
          _MessageCard(
            text: 'لا توجد بيانات مرتبطة بهذا القسم '
                'في العقد الحالي.',
          ),
        ];
    }
  }

  List<Widget> _registryGroup(
    String title,
    List<RegistryEntity> items,
  ) {
    return <Widget>[
      Padding(
        padding: const EdgeInsets.only(top: 12, bottom: 6),
        child: Text(
          title,
          style: const TextStyle(
            fontWeight: FontWeight.w900,
          ),
        ),
      ),
      ...items.map(
        (item) => Card(
          child: ListTile(
            leading: const Icon(Icons.circle, size: 10),
            title: Text(item.nameAr),
            subtitle: Text(item.descriptionAr),
            trailing: Chip(
              label: Text(item.status),
            ),
          ),
        ),
      ),
    ];
  }

  void _openRecommendation(
    BuildContext context,
    PortfolioRecommendation item,
  ) {
    if (item.affectedProjects.isNotEmpty) {
      context.go(
        '/portfolio/projects/'
        '${Uri.encodeComponent(item.affectedProjects.first)}',
      );
      return;
    }

    context.go('/portfolio/recommendations');
  }
}

class PortfolioProjectDetailPage extends ConsumerStatefulWidget {
  const PortfolioProjectDetailPage({
    required this.projectId,
    super.key,
  });

  final String projectId;

  @override
  ConsumerState<PortfolioProjectDetailPage> createState() =>
      _PortfolioProjectDetailPageState();
}

class _PortfolioProjectDetailPageState
    extends ConsumerState<PortfolioProjectDetailPage> {
  late final PortfolioIntelligenceController _portfolioController;

  @override
  void initState() {
    super.initState();

    _portfolioController = ref.read(
      portfolioIntelligenceControllerProvider.notifier,
    );

    Future<void>.microtask(() async {
      if (!mounted) {
        return;
      }

      _portfolioController.startAutoRefresh();
      await _portfolioController.load();
    });
  }

  @override
  void dispose() {
    _portfolioController.stopAutoRefresh();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(portfolioIntelligenceControllerProvider);

    final snapshot = state.snapshot;

    if (snapshot == null) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    ProjectIntelligence? project;

    for (final item in snapshot.projects) {
      if (item.projectId == widget.projectId) {
        project = item;
        break;
      }
    }

    if (project == null) {
      return Center(
        child: Text(
          'المشروع غير موجود في لقطة المحفظة الحالية: '
          '${widget.projectId}',
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(24),
      children: <Widget>[
        Row(
          children: <Widget>[
            IconButton(
              tooltip: 'رجوع',
              onPressed: () => context.go('/dashboard'),
              icon: const Icon(Icons.arrow_forward),
            ),
            Expanded(
              child: Text(
                project.displayName,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        _FactCard(
          label: 'المعرف',
          value: project.projectId,
        ),
        _FactCard(
          label: 'مستودع الكود',
          value: project.repositoryFullName,
        ),
        _FactCard(
          label: 'حالة الحقيقة',
          value: project.truthState,
        ),
        _FactCard(
          label: 'الجاهزية',
          value: project.readiness,
        ),
        _FactCard(
          label: 'الحالة',
          value: project.currentStatus,
        ),
        _FactCard(
          label: 'CI',
          value: project.ciStatus,
        ),
        _FactCard(
          label: 'Deployment',
          value: project.deploymentStatus,
        ),
        _FactCard(
          label: 'Drift',
          value: project.driftStatus,
        ),
        _FactCard(
          label: 'Branch',
          value: project.observedBranch ?? 'UNKNOWN',
        ),
        _FactCard(
          label: 'HEAD',
          value: project.observedHead ?? 'UNKNOWN',
        ),
        _FactCard(
          label: 'الإجراء التالي',
          value: project.nextActionAr,
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: () => context.go('/projects'),
          icon: const Icon(Icons.radar),
          label: const Text(
            'فتح سجل الإدخال والفحص المحكوم',
          ),
        ),
      ],
    );
  }
}

class _ProjectTile extends StatelessWidget {
  const _ProjectTile({
    required this.project,
    required this.trailing,
  });

  final ProjectIntelligence project;
  final String trailing;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: const Icon(Icons.folder_copy_outlined),
        title: Text(project.displayName),
        subtitle: Text(
          '${project.projectId}\n${project.nextActionAr}',
        ),
        isThreeLine: true,
        trailing: Text(trailing),
        onTap: () => context.go(
          '/portfolio/projects/'
          '${Uri.encodeComponent(project.projectId)}',
        ),
      ),
    );
  }
}

class _FactCard extends StatelessWidget {
  const _FactCard({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        title: Text(label),
        subtitle: Text(value),
      ),
    );
  }
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({
    required this.text,
  });

  final String text;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Text(text),
      ),
    );
  }
}
