import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/portfolio_intelligence_controller.dart';
import '../domain/portfolio_intelligence_models.dart';

class PortfolioCommandCenterPage extends ConsumerStatefulWidget {
  const PortfolioCommandCenterPage({super.key});

  @override
  ConsumerState<PortfolioCommandCenterPage> createState() =>
      _PortfolioCommandCenterPageState();
}

class _PortfolioCommandCenterPageState
    extends ConsumerState<PortfolioCommandCenterPage> {
  @override
  void initState() {
    super.initState();
    Future<void>.microtask(
      () => ref.read(portfolioIntelligenceControllerProvider.notifier).load(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(portfolioIntelligenceControllerProvider);
    final snapshot = state.snapshot;

    if (snapshot == null && state.loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (snapshot == null) {
      return _FailureState(
        message: state.error ?? 'لا توجد لقطة Portfolio Intelligence متاحة.',
        onRetry: () =>
            ref.read(portfolioIntelligenceControllerProvider.notifier).load(),
      );
    }

    return RefreshIndicator(
      onRefresh: () =>
          ref.read(portfolioIntelligenceControllerProvider.notifier).load(),
      child: SingleChildScrollView(
        key: const ValueKey<String>('portfolio-command-center-scroll'),
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(18),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1720),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                _CommandHeader(
                  snapshot: snapshot,
                  loading: state.loading,
                  onRefresh: () => ref
                      .read(portfolioIntelligenceControllerProvider.notifier)
                      .load(),
                ),
                if (state.error != null) ...<Widget>[
                  const SizedBox(height: 12),
                  _InlineWarning(message: state.error!),
                ],
                const SizedBox(height: 16),
                _SourceHealthSection(items: snapshot.sourceHealth),
                const SizedBox(height: 16),
                _KpiGrid(items: snapshot.kpis),
                const SizedBox(height: 16),
                _ProjectsSection(projects: snapshot.projects),
                const SizedBox(height: 16),
                _ResponsivePair(
                  first: _RecommendationsPanel(
                    recommendations: snapshot.recommendations,
                  ),
                  second: _CriticalPathPanel(
                    criticalPath: snapshot.criticalPath,
                    dependencies: snapshot.dependencies,
                  ),
                ),
                const SizedBox(height: 16),
                _RegistrySection(
                  capabilities: snapshot.capabilities,
                  skills: snapshot.skills,
                  tools: snapshot.tools,
                  agents: snapshot.agents,
                  providers: snapshot.providers,
                ),
                const SizedBox(height: 16),
                _ResponsivePair(
                  first: _DecisionsPanel(decisions: snapshot.decisions),
                  second: _RisksPanel(risks: snapshot.risks),
                ),
                const SizedBox(height: 16),
                _ActivityEvidenceSection(snapshot: snapshot),
                const SizedBox(height: 12),
                _AuthorityFooter(notes: snapshot.authorityNotes),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _CommandHeader extends StatelessWidget {
  const _CommandHeader({
    required this.snapshot,
    required this.loading,
    required this.onRefresh,
  });

  final PortfolioCommandCenterSnapshot snapshot;
  final bool loading;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      key: const ValueKey<String>('portfolio-command-header'),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 760;
          final title = Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'مركز قيادة وذكاء المحفظة',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
              ),
              const SizedBox(height: 5),
              Text(
                'Portfolio Intelligence & Command Center · '
                'لقطة ${snapshot.snapshotId}',
                textDirection: TextDirection.rtl,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          );
          final controls = Wrap(
            spacing: 8,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: <Widget>[
              _StateChip(
                label: 'Truth ${snapshot.truthConfidence}%',
                state: snapshot.truthState,
              ),
              _StateChip(
                label: snapshot.truthState,
                state: snapshot.truthState,
              ),
              Text(
                _formatDateTime(snapshot.generatedAt),
                style: Theme.of(context).textTheme.labelSmall,
              ),
              IconButton.filledTonal(
                key: const ValueKey<String>('portfolio-refresh'),
                tooltip: 'تحديث الحقيقة الحالية',
                onPressed: loading ? null : onRefresh,
                icon: loading
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.sync),
              ),
            ],
          );
          if (compact) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                title,
                const SizedBox(height: 12),
                controls,
              ],
            );
          }
          return Row(
            children: <Widget>[
              Expanded(child: title),
              const SizedBox(width: 16),
              controls,
            ],
          );
        },
      ),
    );
  }
}

class _SourceHealthSection extends StatelessWidget {
  const _SourceHealthSection({required this.items});

  final List<SourceHealthItem> items;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'صحة مصادر الحقيقة',
      subtitle: 'تعطل المصدر يخفض الثقة ولا يتحول إلى ادعاء بغياب البيانات.',
      child: LayoutBuilder(
        builder: (context, constraints) {
          final width = constraints.maxWidth;
          final columns = width >= 1280
              ? 3
              : width >= 720
                  ? 2
                  : 1;
          final cardWidth = (width - (columns - 1) * 12) / columns;
          return Wrap(
            spacing: 12,
            runSpacing: 12,
            children: items
                .map(
                  (item) => SizedBox(
                    width: cardWidth,
                    child: _SourceCard(item: item),
                  ),
                )
                .toList(growable: false),
          );
        },
      ),
    );
  }
}

class _SourceCard extends StatelessWidget {
  const _SourceCard({required this.item});

  final SourceHealthItem item;

  @override
  Widget build(BuildContext context) {
    final color = _statusColor(context, item.state);
    return Container(
      key: ValueKey<String>('source-${item.sourceId}'),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border.all(color: color.withValues(alpha: .42)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(Icons.sensors, size: 18, color: color),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  item.labelAr,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
              _StateChip(label: item.state, state: item.state),
            ],
          ),
          const SizedBox(height: 8),
          Text(item.detailAr, maxLines: 3, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 8),
          Text(
            '${item.freshness} · ${item.authority}',
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
    );
  }
}

class _KpiGrid extends StatelessWidget {
  const _KpiGrid({required this.items});

  final List<PortfolioKpi> items;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'المؤشرات التنفيذية',
      subtitle: 'كل مؤشر يحمل تفسيرًا وثقة؛ لا توجد نسب تقدم مصطنعة.',
      child: LayoutBuilder(
        builder: (context, constraints) {
          final width = constraints.maxWidth;
          final columns = width >= 1400
              ? 4
              : width >= 900
                  ? 3
                  : width >= 560
                      ? 2
                      : 1;
          final itemWidth = (width - (columns - 1) * 12) / columns;
          return Wrap(
            spacing: 12,
            runSpacing: 12,
            children: items
                .map(
                  (item) => SizedBox(
                    width: itemWidth,
                    child: _KpiCard(item: item),
                  ),
                )
                .toList(growable: false),
          );
        },
      ),
    );
  }
}

class _KpiCard extends StatelessWidget {
  const _KpiCard({required this.item});

  final PortfolioKpi item;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: ValueKey<String>('kpi-${item.kpiId}'),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(child: Text(item.labelAr)),
              _StateChip(label: item.status, state: item.status),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            item.value,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 6),
          Text(
            item.explanationAr,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 6),
          Text(
            'ثقة ${(item.confidence * 100).round()}%',
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
    );
  }
}

class _ProjectsSection extends StatelessWidget {
  const _ProjectsSection({required this.projects});

  final List<ProjectIntelligence> projects;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'المشاريع وترتيب الانتباه',
      subtitle:
          'Priority score يعبّر عن الحاجة للانتباه وفق عوامل معلنة، وليس سلطة تنفيذ.',
      child: LayoutBuilder(
        builder: (context, constraints) {
          if (constraints.maxWidth < 860) {
            return Column(
              children: projects
                  .map(
                    (project) => Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: _ProjectCard(project: project),
                    ),
                  )
                  .toList(growable: false),
            );
          }
          return ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: DataTable(
                key: const ValueKey<String>('portfolio-projects-table'),
                headingRowHeight: 44,
                dataRowMinHeight: 62,
                dataRowMaxHeight: 84,
                columns: const <DataColumn>[
                  DataColumn(label: Text('المشروع')),
                  DataColumn(label: Text('الحقيقة')),
                  DataColumn(label: Text('الجاهزية')),
                  DataColumn(label: Text('الأولوية')),
                  DataColumn(label: Text('CI')),
                  DataColumn(label: Text('الانحراف')),
                  DataColumn(label: Text('التقدم')),
                  DataColumn(label: Text('الإجراء التالي')),
                ],
                rows: projects.map((project) {
                  return DataRow(
                    cells: <DataCell>[
                      DataCell(
                        SizedBox(
                          width: 210,
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Text(
                                project.displayName,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                    fontWeight: FontWeight.w800),
                              ),
                              Text(
                                project.projectId,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: Theme.of(context).textTheme.labelSmall,
                              ),
                            ],
                          ),
                        ),
                      ),
                      DataCell(_StateChip(
                        label: project.truthState,
                        state: project.truthState,
                      )),
                      DataCell(_StateChip(
                        label: project.readiness,
                        state: project.readiness,
                      )),
                      DataCell(Text('${project.priorityScore}/100')),
                      DataCell(Text(project.ciStatus)),
                      DataCell(Text(project.driftStatus)),
                      DataCell(
                        Text(
                          project.scopeProgressPercent == null
                              ? 'غير متاح'
                              : '${project.scopeProgressPercent!.round()}%',
                        ),
                      ),
                      DataCell(
                        SizedBox(
                          width: 300,
                          child: Text(
                            project.nextActionAr,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                    ],
                  );
                }).toList(growable: false),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _ProjectCard extends StatelessWidget {
  const _ProjectCard({required this.project});

  final ProjectIntelligence project;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: ValueKey<String>('project-${project.projectId}'),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  project.displayName,
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
              ),
              Text('${project.priorityScore}/100'),
            ],
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 7,
            runSpacing: 7,
            children: <Widget>[
              _StateChip(label: project.truthState, state: project.truthState),
              _StateChip(label: project.readiness, state: project.readiness),
              _StateChip(label: project.ciStatus, state: project.ciStatus),
            ],
          ),
          const SizedBox(height: 9),
          Text(project.nextActionAr),
          const SizedBox(height: 7),
          Text(
            project.scopeProgressPercent == null
                ? 'التقدم: غير متاح — ${project.scopeProgressBasis}'
                : 'التقدم: ${project.scopeProgressPercent!.round()}%',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _RecommendationsPanel extends StatelessWidget {
  const _RecommendationsPanel({required this.recommendations});

  final List<PortfolioRecommendation> recommendations;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'التوصيات الذكية',
      subtitle: 'استشارية فقط؛ لا تمنح تفويضًا ولا توسّع سلطة.',
      child: recommendations.isEmpty
          ? const _EmptyState(
              message: 'لا توجد توصية تشغيلية ذات أولوية حاليًا.')
          : Column(
              children: recommendations.take(8).map((item) {
                return ListTile(
                  key: ValueKey<String>(item.recommendationId),
                  contentPadding: EdgeInsets.zero,
                  leading: CircleAvatar(
                    child: Text('${(item.confidence * 100).round()}'),
                  ),
                  title: Text(
                    item.type,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  subtitle: Text(item.reasonAr),
                  trailing: _StateChip(
                    label: item.authority,
                    state: item.authority,
                  ),
                );
              }).toList(growable: false),
            ),
    );
  }
}

class _CriticalPathPanel extends StatelessWidget {
  const _CriticalPathPanel({
    required this.criticalPath,
    required this.dependencies,
  });

  final CriticalPathView criticalPath;
  final List<DependencyView> dependencies;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'المسار الحرج والتبعيات',
      subtitle: criticalPath.reasonAr,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Row(
            children: <Widget>[
              _StateChip(
                label: criticalPath.status,
                state: criticalPath.status,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  criticalPath.mostBlockingProjectId == null
                      ? 'لا يوجد Most Blocking Project مثبت.'
                      : 'الأكثر حجبًا: ${criticalPath.mostBlockingProjectId}',
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          if (criticalPath.projectIds.isNotEmpty)
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: criticalPath.projectIds
                  .map((id) => Chip(label: Text(id)))
                  .toList(growable: false),
            )
          else
            const _EmptyState(
              message:
                  'لا يتم اختلاق dependency graph عند غياب المصدر المعتمد.',
            ),
          if (dependencies.isNotEmpty) ...<Widget>[
            const Divider(height: 24),
            ...dependencies.take(6).map(
                  (edge) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      '${edge.producerProjectId} → ${edge.consumerProjectId} '
                      '· ${edge.kind} · ${edge.contractId}',
                    ),
                  ),
                ),
          ],
        ],
      ),
    );
  }
}

class _RegistrySection extends StatelessWidget {
  const _RegistrySection({
    required this.capabilities,
    required this.skills,
    required this.tools,
    required this.agents,
    required this.providers,
  });

  final List<RegistryEntity> capabilities;
  final List<RegistryEntity> skills;
  final List<RegistryEntity> tools;
  final List<RegistryEntity> agents;
  final List<RegistryEntity> providers;

  @override
  Widget build(BuildContext context) {
    final groups = <(String, IconData, List<RegistryEntity>)>[
      ('القدرات', Icons.account_tree_outlined, capabilities),
      ('المهارات', Icons.psychology_outlined, skills),
      ('الأدوات', Icons.build_outlined, tools),
      ('الوكلاء', Icons.smart_toy_outlined, agents),
      ('المزودون', Icons.cloud_outlined, providers),
    ];
    return _Section(
      title: 'القدرات · المهارات · الأدوات · الوكلاء · المزودون',
      subtitle:
          'Capability ≠ Authority، وحالة UNKNOWN لا تُحوّل إلى حقيقة مفترضة.',
      child: LayoutBuilder(
        builder: (context, constraints) {
          final width = constraints.maxWidth;
          final columns = width >= 1280
              ? 3
              : width >= 720
                  ? 2
                  : 1;
          final itemWidth = (width - (columns - 1) * 12) / columns;
          return Wrap(
            spacing: 12,
            runSpacing: 12,
            children: groups
                .map(
                  (group) => SizedBox(
                    width: itemWidth,
                    child: _RegistryPanel(
                      title: group.$1,
                      icon: group.$2,
                      items: group.$3,
                    ),
                  ),
                )
                .toList(growable: false),
          );
        },
      ),
    );
  }
}

class _RegistryPanel extends StatelessWidget {
  const _RegistryPanel({
    required this.title,
    required this.icon,
    required this.items,
  });

  final String title;
  final IconData icon;
  final List<RegistryEntity> items;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(icon, size: 19),
              const SizedBox(width: 8),
              Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
              const Spacer(),
              Text('${items.length}'),
            ],
          ),
          const Divider(height: 20),
          if (items.isEmpty)
            const Text('لا توجد عناصر مرصودة.')
          else
            ...items.take(6).map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Row(
                          children: <Widget>[
                            Expanded(
                              child: Text(
                                item.nameAr,
                                style: const TextStyle(
                                    fontWeight: FontWeight.w700),
                              ),
                            ),
                            _StateChip(label: item.status, state: item.status),
                          ],
                        ),
                        const SizedBox(height: 3),
                        Text(
                          item.descriptionAr,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.bodySmall,
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

class _DecisionsPanel extends StatelessWidget {
  const _DecisionsPanel({required this.decisions});

  final List<PortfolioDecision> decisions;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'القرارات المطلوبة',
      subtitle: 'الفصل بين القرار البشري والعمل الهندسي محفوظ.',
      child: decisions.isEmpty
          ? const _EmptyState(message: 'لا توجد قرارات في صندوق القرار الحالي.')
          : Column(
              children: decisions.take(8).map((item) {
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                    item.requiresHumanAction
                        ? Icons.how_to_reg_outlined
                        : Icons.rule_outlined,
                  ),
                  title: Text(item.summaryAr),
                  subtitle: Text('${item.kind} · ${item.decisionId}'),
                  trailing: _StateChip(label: item.status, state: item.status),
                );
              }).toList(growable: false),
            ),
    );
  }
}

class _RisksPanel extends StatelessWidget {
  const _RisksPanel({required this.risks});

  final List<PortfolioRisk> risks;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'المخاطر والمعيقات',
      subtitle: 'تنبيهات مبنية على الواقع المرصود، مع الإجراء المطلوب.',
      child: risks.isEmpty
          ? const _EmptyState(message: 'لا توجد مخاطر تشغيلية مرصودة حاليًا.')
          : Column(
              children: risks.take(8).map((item) {
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                    Icons.warning_amber_rounded,
                    color: _statusColor(context, item.severity),
                  ),
                  title: Text(item.summaryAr),
                  subtitle: Text(item.requiredActionAr),
                  trailing:
                      _StateChip(label: item.severity, state: item.severity),
                );
              }).toList(growable: false),
            ),
    );
  }
}

class _ActivityEvidenceSection extends StatelessWidget {
  const _ActivityEvidenceSection({required this.snapshot});

  final PortfolioCommandCenterSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    return _ResponsivePair(
      first: _Section(
        title: 'ما الذي تغير مؤخرًا؟',
        subtitle: 'Activity projection مع provenance لكل حدث.',
        child: snapshot.recentChanges.isEmpty
            ? const _EmptyState(message: 'لا توجد تغييرات مرصودة.')
            : Column(
                children: snapshot.recentChanges.take(10).map((item) {
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    leading: const Icon(Icons.history, size: 18),
                    title: Text(item.title),
                    subtitle: Text(item.detail),
                    trailing: Text(
                      _formatDateTime(item.occurredAt),
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                  );
                }).toList(growable: false),
              ),
      ),
      second: _Section(
        title: 'Evidence Drill-down',
        subtitle: 'مراجع آمنة فقط؛ لا أسرار ولا مسارات مطلقة.',
        child: snapshot.evidenceRefs.isEmpty
            ? const _EmptyState(
                message: 'لا توجد مراجع أدلة آمنة في هذه اللقطة.')
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: snapshot.evidenceRefs
                    .take(12)
                    .map(
                      (ref) => Padding(
                        padding: const EdgeInsets.only(bottom: 7),
                        child: SelectableText(
                          ref,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ),
                    )
                    .toList(growable: false),
              ),
      ),
    );
  }
}

class _AuthorityFooter extends StatelessWidget {
  const _AuthorityFooter({required this.notes});

  final List<String> notes;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: notes
            .map(
              (note) => Chip(
                avatar: const Icon(Icons.shield_outlined, size: 16),
                label: Text(note),
              ),
            )
            .toList(growable: false),
      ),
    );
  }
}

class _ResponsivePair extends StatelessWidget {
  const _ResponsivePair({required this.first, required this.second});

  final Widget first;
  final Widget second;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 920) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              first,
              const SizedBox(height: 16),
              second,
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(child: first),
            const SizedBox(width: 16),
            Expanded(child: second),
          ],
        );
      },
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    required this.title,
    required this.subtitle,
    required this.child,
  });

  final String title;
  final String subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 4),
          Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

class _Panel extends StatelessWidget {
  const _Panel({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: key,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: child,
      ),
    );
  }
}

class _StateChip extends StatelessWidget {
  const _StateChip({required this.label, required this.state});

  final String label;
  final String state;

  @override
  Widget build(BuildContext context) {
    final color = _statusColor(context, state);
    return Container(
      constraints: const BoxConstraints(maxWidth: 190),
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: .36)),
      ),
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w800,
            ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      alignment: Alignment.center,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(10),
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
      ),
      child: Text(message, textAlign: TextAlign.center),
    );
  }
}

class _InlineWarning extends StatelessWidget {
  const _InlineWarning({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: <Widget>[
          Icon(Icons.warning_amber, color: Theme.of(context).colorScheme.error),
          const SizedBox(width: 8),
          Expanded(child: Text(message)),
        ],
      ),
    );
  }
}

class _FailureState extends StatelessWidget {
  const _FailureState({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: _Panel(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Icon(
                  Icons.cloud_off_outlined,
                  size: 44,
                  color: Theme.of(context).colorScheme.error,
                ),
                const SizedBox(height: 12),
                const Text(
                  'تعذر بناء لقطة المحفظة',
                  style: TextStyle(fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 8),
                Text(message, textAlign: TextAlign.center),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('إعادة المحاولة'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

Color _statusColor(BuildContext context, String state) {
  final normalized = state.toUpperCase();
  if (normalized.contains('FAIL') ||
      normalized.contains('CRITICAL') ||
      normalized.contains('BLOCK') ||
      normalized.contains('DRIFT')) {
    return Theme.of(context).colorScheme.error;
  }
  if (normalized.contains('WARN') ||
      normalized.contains('ATTENTION') ||
      normalized.contains('DEGRADED') ||
      normalized.contains('UNKNOWN') ||
      normalized.contains('UNAVAILABLE') ||
      normalized.contains('HOLD') ||
      normalized.contains('SUSPENDED')) {
    return Colors.amber.shade400;
  }
  if (normalized.contains('PASS') ||
      normalized.contains('READY') ||
      normalized.contains('HEALTHY') ||
      normalized.contains('VERIFIED') ||
      normalized.contains('SUCCESS') ||
      normalized.contains('CLEAR')) {
    return Colors.green.shade400;
  }
  return Theme.of(context).colorScheme.secondary;
}

String _formatDateTime(DateTime value) {
  final local = value.toLocal();
  String two(int number) => number.toString().padLeft(2, '0');
  return '${local.year}-${two(local.month)}-${two(local.day)} '
      '${two(local.hour)}:${two(local.minute)}';
}
