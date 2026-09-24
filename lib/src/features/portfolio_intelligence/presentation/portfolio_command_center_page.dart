import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../application/portfolio_intelligence_controller.dart';
import '../domain/portfolio_intelligence_models.dart';

const _ccBg = Color(0xFF03101C);
const _ccPanel = Color(0xFF071B2C);
const _ccPanelHigh = Color(0xFF0A2238);
const _ccBorder = Color(0xFF123A59);
const _ccText = Color(0xFFF3F8FC);
const _ccMuted = Color(0xFF8EA9C1);
const _ccCyan = Color(0xFF00C8FF);
const _ccTeal = Color(0xFF00E3B2);
const _ccGreen = Color(0xFF24E59A);
const _ccBlue = Color(0xFF2F82FF);
const _ccPurple = Color(0xFF8E5CFF);
const _ccOrange = Color(0xFFFFA726);
const _ccRed = Color(0xFFFF4D67);

class PortfolioCommandCenterPage extends ConsumerStatefulWidget {
  const PortfolioCommandCenterPage({super.key});

  @override
  ConsumerState<PortfolioCommandCenterPage> createState() =>
      _PortfolioCommandCenterPageState();
}

class _PortfolioCommandCenterPageState
    extends ConsumerState<PortfolioCommandCenterPage> {
  String _query = '';

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

    final query = _query.trim().toLowerCase();
    final visibleProjects = query.isEmpty
        ? snapshot.projects
        : snapshot.projects
            .where(
              (project) =>
                  project.displayName.toLowerCase().contains(query) ||
                  project.projectId.toLowerCase().contains(query) ||
                  project.repositoryFullName.toLowerCase().contains(query),
            )
            .toList(growable: false);

    return Theme(
      data: _commandCenterTheme(),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final desktop = constraints.maxWidth >= 1080;
          return Material(
            color: _ccBg,
            child: Row(
              textDirection: TextDirection.ltr,
              children: <Widget>[
                if (desktop) const _VisualSidebar(),
                Expanded(
                  child: Directionality(
                    textDirection: TextDirection.rtl,
                    child: RefreshIndicator(
                      color: _ccTeal,
                      backgroundColor: _ccPanelHigh,
                      onRefresh: () => ref
                          .read(
                            portfolioIntelligenceControllerProvider.notifier,
                          )
                          .load(),
                      child: SingleChildScrollView(
                        key: const ValueKey<String>(
                          'portfolio-command-center-scroll',
                        ),
                        physics: const AlwaysScrollableScrollPhysics(),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: <Widget>[
                            _VisualCommandHeader(
                              snapshot: snapshot,
                              compact: !desktop,
                              loading: state.loading,
                              query: _query,
                              onQueryChanged: (value) =>
                                  setState(() => _query = value),
                              onRefresh: () => ref
                                  .read(
                                    portfolioIntelligenceControllerProvider
                                        .notifier,
                                  )
                                  .load(),
                            ),
                            if (state.error != null)
                              Padding(
                                padding:
                                    const EdgeInsets.fromLTRB(14, 10, 14, 0),
                                child: _InlineWarning(message: state.error!),
                              ),
                            Padding(
                              padding: EdgeInsets.fromLTRB(
                                desktop ? 14 : 10,
                                12,
                                desktop ? 14 : 10,
                                28,
                              ),
                              child: Center(
                                child: ConstrainedBox(
                                  constraints:
                                      const BoxConstraints(maxWidth: 1780),
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.stretch,
                                    children: <Widget>[
                                      _CommandStatusStrip(
                                        snapshot: snapshot,
                                      ),
                                      const SizedBox(height: 10),
                                      _KpiGrid(items: snapshot.kpis),
                                      const SizedBox(height: 10),
                                      _CommandCenterCore(
                                        snapshot: snapshot,
                                        projects: visibleProjects,
                                      ),
                                      const SizedBox(height: 10),
                                      _RegistrySection(
                                        capabilities: snapshot.capabilities,
                                        skills: snapshot.skills,
                                        tools: snapshot.tools,
                                        agents: snapshot.agents,
                                        providers: snapshot.providers,
                                      ),
                                      const SizedBox(height: 10),
                                      _CommandCenterBottom(
                                        snapshot: snapshot,
                                      ),
                                      const SizedBox(height: 10),
                                      _AuthorityFooter(
                                        notes: snapshot.authorityNotes,
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

ThemeData _commandCenterTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: _ccTeal,
    brightness: Brightness.dark,
  ).copyWith(
    primary: _ccTeal,
    secondary: _ccCyan,
    error: _ccRed,
    surface: _ccPanel,
    onSurface: _ccText,
    onSurfaceVariant: _ccMuted,
    outline: _ccBorder,
    outlineVariant: _ccBorder,
  );
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: scheme,
    scaffoldBackgroundColor: _ccBg,
    canvasColor: _ccBg,
    dividerColor: _ccBorder,
    cardTheme: CardThemeData(
      elevation: 0,
      margin: EdgeInsets.zero,
      color: _ccPanel,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: _ccBorder),
      ),
    ),
  );
}

class _VisualSidebar extends StatelessWidget {
  const _VisualSidebar();

  static const _items = <(String, String, IconData)>[
    ('الرئيسية', '/home', Icons.home_rounded),
    ('مركز القيادة', '/dashboard', Icons.space_dashboard_rounded),
    ('المشاريع', '/projects', Icons.folder_copy_rounded),
    ('أعمالي', '/work', Icons.checklist_rounded),
    ('التشغيل', '/operations', Icons.settings_suggest_rounded),
    ('الأدوات', '/tools', Icons.build_circle_rounded),
    ('التنبيهات والمخاطر', '/alerts', Icons.warning_amber_rounded),
    ('الأدلة والمعرفة', '/evidence', Icons.fact_check_rounded),
    ('التوسعات', '/extensions', Icons.extension_rounded),
    ('الاتصالات', '/settings/connections', Icons.cable_rounded),
    ('الإدارة المتقدمة', '/advanced', Icons.admin_panel_settings_rounded),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 205,
      decoration: const BoxDecoration(
        color: Color(0xFF020D17),
        border: Border(right: BorderSide(color: _ccBorder)),
      ),
      child: Directionality(
        textDirection: TextDirection.rtl,
        child: SafeArea(
          child: Column(
            children: <Widget>[
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 18, 14, 10),
                child: Row(
                  children: <Widget>[
                    Container(
                      width: 42,
                      height: 42,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: const LinearGradient(
                          colors: <Color>[_ccTeal, _ccBlue],
                        ),
                        boxShadow: <BoxShadow>[
                          BoxShadow(
                            color: _ccTeal.withValues(alpha: .25),
                            blurRadius: 18,
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.account_balance_rounded,
                        color: Colors.white,
                        size: 23,
                      ),
                    ),
                    const SizedBox(width: 9),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                            'PalWakf',
                            textDirection: TextDirection.ltr,
                            style: TextStyle(
                              color: _ccText,
                              fontSize: 22,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                          Text(
                            'معًا لوقف مستدام',
                            style: TextStyle(
                              color: Color(0xFFE8B957),
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: ListView.separated(
                  padding: const EdgeInsets.fromLTRB(10, 12, 10, 6),
                  itemCount: _items.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 3),
                  itemBuilder: (context, index) {
                    final item = _items[index];
                    final selected = item.$2 == '/dashboard';
                    return Material(
                      color: selected
                          ? _ccBlue.withValues(alpha: .20)
                          : Colors.transparent,
                      borderRadius: BorderRadius.circular(9),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(9),
                        onTap: () => context.go(item.$2),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 9,
                          ),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(9),
                            border: selected
                                ? Border.all(
                                    color: _ccCyan.withValues(alpha: .38),
                                  )
                                : null,
                          ),
                          child: Row(
                            children: <Widget>[
                              Icon(
                                item.$3,
                                size: 19,
                                color: selected ? _ccCyan : _ccMuted,
                              ),
                              const SizedBox(width: 9),
                              Expanded(
                                child: Text(
                                  item.$1,
                                  style: TextStyle(
                                    color: selected ? _ccText : _ccMuted,
                                    fontSize: 12,
                                    fontWeight: selected
                                        ? FontWeight.w800
                                        : FontWeight.w600,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(11),
                child: Container(
                  padding: const EdgeInsets.all(11),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: <Color>[
                        _ccPurple.withValues(alpha: .20),
                        _ccBlue.withValues(alpha: .12),
                      ],
                    ),
                    borderRadius: BorderRadius.circular(13),
                    border: Border.all(
                      color: _ccPurple.withValues(alpha: .28),
                    ),
                  ),
                  child: const Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      Icon(
                        Icons.mosque_rounded,
                        color: Color(0xFFE8B957),
                        size: 28,
                      ),
                      SizedBox(height: 7),
                      Text(
                        'وقفٌ يصنع أثرًا أبقى',
                        style: TextStyle(
                          color: _ccText,
                          fontSize: 12,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      Text(
                        'قيادة موحّدة للمشاريع والقدرات',
                        style: TextStyle(color: _ccMuted, fontSize: 9),
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

class _VisualCommandHeader extends StatelessWidget {
  const _VisualCommandHeader({
    required this.snapshot,
    required this.compact,
    required this.loading,
    required this.query,
    required this.onQueryChanged,
    required this.onRefresh,
  });

  final PortfolioCommandCenterSnapshot snapshot;
  final bool compact;
  final bool loading;
  final String query;
  final ValueChanged<String> onQueryChanged;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    final title = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        const Text(
          'مركز قيادة المشاريع والقدرات',
          style: TextStyle(
            color: _ccText,
            fontSize: 22,
            fontWeight: FontWeight.w900,
            height: 1,
          ),
        ),
        const SizedBox(height: 5),
        Row(
          children: <Widget>[
            const Flexible(
              child: Text(
                'Portfolio Intelligence & Command Center',
                textDirection: TextDirection.ltr,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: _ccMuted, fontSize: 11),
              ),
            ),
            const SizedBox(width: 8),
            _StateChip(
              label: 'التصميم التنفيذي',
              state: 'VERIFIED',
            ),
          ],
        ),
      ],
    );
    final search = SizedBox(
      height: 42,
      child: TextField(
        key: const ValueKey<String>('command-center-search'),
        onChanged: onQueryChanged,
        style: const TextStyle(color: _ccText, fontSize: 12),
        decoration: InputDecoration(
          isDense: true,
          filled: true,
          fillColor: _ccPanelHigh,
          prefixIcon:
              const Icon(Icons.search_rounded, color: _ccMuted, size: 19),
          hintText: 'ابحث في المشاريع والقدرات...',
          hintStyle: const TextStyle(color: _ccMuted, fontSize: 11),
          suffixIcon: query.isEmpty
              ? const Center(
                  widthFactor: 1,
                  child: Text(
                    'Ctrl + K',
                    style: TextStyle(color: _ccMuted, fontSize: 9),
                  ),
                )
              : IconButton(
                  tooltip: 'مسح البحث',
                  onPressed: () => onQueryChanged(''),
                  icon: const Icon(Icons.close_rounded, size: 17),
                ),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: const BorderSide(color: _ccBorder),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: const BorderSide(color: _ccBorder),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: const BorderSide(color: _ccCyan),
          ),
        ),
      ),
    );
    final actions = Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        IconButton(
          tooltip: 'تحديث',
          onPressed: loading ? null : onRefresh,
          icon: Icon(
            loading ? Icons.hourglass_top_rounded : Icons.sync_rounded,
            color: _ccCyan,
          ),
        ),
        Stack(
          clipBehavior: Clip.none,
          children: <Widget>[
            const Icon(
              Icons.notifications_none_rounded,
              color: _ccMuted,
              size: 24,
            ),
            if (snapshot.risks.isNotEmpty)
              PositionedDirectional(
                end: -6,
                top: -6,
                child: Container(
                  width: 17,
                  height: 17,
                  alignment: Alignment.center,
                  decoration: const BoxDecoration(
                    color: _ccRed,
                    shape: BoxShape.circle,
                  ),
                  child: Text(
                    '${snapshot.risks.length}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 8,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(width: 13),
        Container(
          width: 36,
          height: 36,
          alignment: Alignment.center,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            gradient: LinearGradient(colors: <Color>[_ccBlue, _ccPurple]),
          ),
          child: const Text(
            'AA',
            style: TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
        const SizedBox(width: 8),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const Text(
              'المشرف العام',
              style: TextStyle(
                color: _ccText,
                fontSize: 11,
                fontWeight: FontWeight.w800,
              ),
            ),
            Text(
              _formatDateTime(snapshot.generatedAt),
              style: const TextStyle(color: _ccMuted, fontSize: 9),
            ),
          ],
        ),
      ],
    );

    return Container(
      key: const ValueKey<String>('portfolio-command-header'),
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 12 : 18,
        vertical: 12,
      ),
      decoration: const BoxDecoration(
        color: Color(0xFF05192A),
        border: Border(bottom: BorderSide(color: _ccBorder)),
      ),
      child: compact
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                title,
                const SizedBox(height: 8),
                Align(
                  alignment: AlignmentDirectional.centerStart,
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: actions,
                  ),
                ),
                const SizedBox(height: 10),
                search,
              ],
            )
          : Row(
              children: <Widget>[
                Expanded(flex: 5, child: title),
                const SizedBox(width: 16),
                Expanded(flex: 5, child: search),
                const SizedBox(width: 16),
                actions,
              ],
            ),
    );
  }
}

class _CommandStatusStrip extends StatelessWidget {
  const _CommandStatusStrip({required this.snapshot});

  final PortfolioCommandCenterSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 920;
        final sources = _SourceHealthSection(items: snapshot.sourceHealth);
        final gauge = _PortfolioGauge(snapshot: snapshot);
        if (!wide) {
          return Column(
            children: <Widget>[
              sources,
              const SizedBox(height: 10),
              gauge,
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(flex: 72, child: sources),
            const SizedBox(width: 10),
            Expanded(flex: 28, child: gauge),
          ],
        );
      },
    );
  }
}

class _PortfolioGauge extends StatelessWidget {
  const _PortfolioGauge({required this.snapshot});

  final PortfolioCommandCenterSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final confidence = snapshot.truthConfidence.clamp(0, 100);
    final healthy = snapshot.sourceHealth
        .where((item) => item.state.toUpperCase() == 'HEALTHY')
        .length;
    return _Section(
      title: 'مؤشر الثقة والجاهزية',
      subtitle: 'مؤشر شفاف مشتق من صحة المصادر والقراءة الحالية.',
      child: SizedBox(
        height: 150,
        child: Row(
          children: <Widget>[
            Expanded(
              child: CustomPaint(
                painter: _GaugePainter(value: confidence / 100),
                child: Center(
                  child: Padding(
                    padding: const EdgeInsets.only(top: 20),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Text(
                          '$confidence%',
                          style: const TextStyle(
                            color: _ccText,
                            fontSize: 29,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        Text(
                          snapshot.truthState,
                          style: TextStyle(
                            color: _statusColor(context, snapshot.truthState),
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: <Widget>[
                  _MetricLine(
                    label: 'مصادر صحية',
                    value: '$healthy/${snapshot.sourceHealth.length}',
                    ok: healthy > 0,
                  ),
                  _MetricLine(
                    label: 'المشاريع',
                    value: '${snapshot.projects.length}',
                    ok: snapshot.projects.isNotEmpty,
                  ),
                  _MetricLine(
                    label: 'التوصيات',
                    value: '${snapshot.recommendations.length}',
                    ok: true,
                  ),
                  _MetricLine(
                    label: 'قرارات بشرية',
                    value: '${snapshot.decisions.length}',
                    ok: snapshot.decisions.isEmpty,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetricLine extends StatelessWidget {
  const _MetricLine({
    required this.label,
    required this.value,
    required this.ok,
  });

  final String label;
  final String value;
  final bool ok;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: <Widget>[
          Icon(
            ok ? Icons.check_circle_rounded : Icons.info_rounded,
            color: ok ? _ccGreen : _ccOrange,
            size: 13,
          ),
          const SizedBox(width: 5),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(color: _ccMuted, fontSize: 9),
            ),
          ),
          Text(
            value,
            style: const TextStyle(
              color: _ccText,
              fontSize: 9,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _CommandCenterCore extends StatelessWidget {
  const _CommandCenterCore({
    required this.snapshot,
    required this.projects,
  });

  final PortfolioCommandCenterSnapshot snapshot;
  final List<ProjectIntelligence> projects;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final recommendations = _RecommendationsPanel(
          recommendations: snapshot.recommendations,
        );
        final risks = _RisksPanel(risks: snapshot.risks);
        if (constraints.maxWidth < 1050) {
          return Column(
            children: <Widget>[
              _ProjectsSection(projects: projects),
              const SizedBox(height: 10),
              _StrategicNetworkPanel(snapshot: snapshot),
              const SizedBox(height: 10),
              recommendations,
              const SizedBox(height: 10),
              risks,
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(flex: 43, child: _ProjectsSection(projects: projects)),
            const SizedBox(width: 10),
            Expanded(
              flex: 31,
              child: _StrategicNetworkPanel(snapshot: snapshot),
            ),
            const SizedBox(width: 10),
            Expanded(
              flex: 26,
              child: Column(
                children: <Widget>[
                  recommendations,
                  const SizedBox(height: 10),
                  risks,
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

class _StrategicNetworkPanel extends StatelessWidget {
  const _StrategicNetworkPanel({required this.snapshot});

  final PortfolioCommandCenterSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final nodes = <_NetworkNodeData>[
      ...snapshot.projects.map(
        (item) => _NetworkNodeData(
          item.displayName,
          Icons.hub_rounded,
          _ccBlue,
        ),
      ),
      ...snapshot.capabilities.map(
        (item) => _NetworkNodeData(
          item.nameAr,
          Icons.psychology_rounded,
          _ccTeal,
        ),
      ),
      ...snapshot.tools.map(
        (item) => _NetworkNodeData(
          item.nameAr,
          Icons.build_circle_rounded,
          _ccPurple,
        ),
      ),
    ].take(7).toList(growable: false);

    return _Section(
      title: 'الخريطة الاستراتيجية للمشاريع والقدرات',
      subtitle: 'ترابط مرئي من العناصر المرصودة فعليًا، دون اختلاق عقد.',
      child: SizedBox(
        height: 405,
        child: nodes.isEmpty
            ? const _EmptyState(message: 'لا توجد عقد مرصودة لرسم الخريطة.')
            : LayoutBuilder(
                builder: (context, constraints) {
                  final positions = _networkPositions(
                    constraints.maxWidth,
                    constraints.maxHeight - 34,
                    nodes.length,
                  );
                  return Stack(
                    children: <Widget>[
                      Positioned.fill(
                        child: CustomPaint(
                          painter: _NetworkPainter(nodeCount: nodes.length),
                        ),
                      ),
                      ...positions.asMap().entries.map((entry) {
                        final node = nodes[entry.key];
                        final center = entry.key == 0;
                        final size = center ? 92.0 : 72.0;
                        return Positioned(
                          left: entry.value.dx - size / 2,
                          top: entry.value.dy - size / 2,
                          child: _NetworkNode(
                            data: node,
                            center: center,
                          ),
                        );
                      }),
                      PositionedDirectional(
                        start: 0,
                        end: 0,
                        bottom: 0,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 7,
                          ),
                          decoration: BoxDecoration(
                            color: _ccTeal.withValues(alpha: .07),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: _ccTeal.withValues(alpha: .25),
                            ),
                          ),
                          child: const Text(
                            'بيانات موحّدة · قدرات مترابطة · قرار أوضح',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: _ccTeal,
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ),
                    ],
                  );
                },
              ),
      ),
    );
  }
}

class _NetworkNodeData {
  const _NetworkNodeData(this.label, this.icon, this.color);

  final String label;
  final IconData icon;
  final Color color;
}

class _NetworkNode extends StatelessWidget {
  const _NetworkNode({
    required this.data,
    required this.center,
  });

  final _NetworkNodeData data;
  final bool center;

  @override
  Widget build(BuildContext context) {
    final size = center ? 92.0 : 72.0;
    return SizedBox(
      width: size,
      child: Column(
        children: <Widget>[
          Container(
            width: center ? 56 : 44,
            height: center ? 56 : 44,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: const Color(0xFF061A2B),
              border: Border.all(
                color: data.color,
                width: center ? 2.2 : 1.6,
              ),
              boxShadow: <BoxShadow>[
                BoxShadow(
                  color: data.color.withValues(alpha: .32),
                  blurRadius: center ? 22 : 15,
                ),
              ],
            ),
            child: Icon(
              data.icon,
              color: data.color,
              size: center ? 28 : 22,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            data.label,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: _ccText,
              fontSize: center ? 9 : 7.5,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _CommandCenterBottom extends StatelessWidget {
  const _CommandCenterBottom({required this.snapshot});

  final PortfolioCommandCenterSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final activity = _ActivityEvidenceSection(snapshot: snapshot);
        final decisions = _DecisionsPanel(decisions: snapshot.decisions);
        final critical = _CriticalPathPanel(
          criticalPath: snapshot.criticalPath,
          dependencies: snapshot.dependencies,
        );
        if (constraints.maxWidth < 980) {
          return Column(
            children: <Widget>[
              activity,
              const SizedBox(height: 10),
              decisions,
              const SizedBox(height: 10),
              critical,
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(flex: 48, child: activity),
            const SizedBox(width: 10),
            Expanded(flex: 24, child: decisions),
            const SizedBox(width: 10),
            Expanded(flex: 28, child: critical),
          ],
        );
      },
    );
  }
}

class _GaugePainter extends CustomPainter {
  const _GaugePainter({required this.value});

  final double value;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Rect.fromLTWH(7, 18, size.width - 14, size.height - 24);
    final base = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 11
      ..strokeCap = StrokeCap.round
      ..color = const Color(0xFF17334C);
    final active = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 11
      ..strokeCap = StrokeCap.round
      ..shader = const LinearGradient(
        colors: <Color>[_ccBlue, _ccCyan, _ccTeal],
      ).createShader(rect);
    canvas.drawArc(rect, math.pi, math.pi, false, base);
    canvas.drawArc(
      rect,
      math.pi,
      math.pi * value.clamp(0, 1),
      false,
      active,
    );
  }

  @override
  bool shouldRepaint(covariant _GaugePainter oldDelegate) =>
      oldDelegate.value != value;
}

class _NetworkPainter extends CustomPainter {
  const _NetworkPainter({required this.nodeCount});

  final int nodeCount;

  @override
  void paint(Canvas canvas, Size size) {
    final grid = Paint()
      ..color = _ccCyan.withValues(alpha: .045)
      ..strokeWidth = 1;
    for (double x = 0; x < size.width; x += 26) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), grid);
    }
    for (double y = 0; y < size.height; y += 26) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }
    if (nodeCount <= 1) return;
    final positions =
        _networkPositions(size.width, size.height - 34, nodeCount);
    final center = positions.first;
    for (var i = 1; i < positions.length; i++) {
      final paint = Paint()
        ..color = (i.isEven ? _ccCyan : _ccPurple).withValues(alpha: .42)
        ..strokeWidth = 1.3;
      _drawDashed(canvas, center, positions[i], paint);
    }
    final glow = Paint()
      ..shader = RadialGradient(
        colors: <Color>[
          _ccTeal.withValues(alpha: .14),
          Colors.transparent,
        ],
      ).createShader(
        Rect.fromCircle(
          center: center,
          radius: math.min(size.width, size.height) * .38,
        ),
      );
    canvas.drawCircle(
      center,
      math.min(size.width, size.height) * .38,
      glow,
    );
  }

  void _drawDashed(
    Canvas canvas,
    Offset a,
    Offset b,
    Paint paint,
  ) {
    final distance = (b - a).distance;
    if (distance == 0) return;
    final direction = (b - a) / distance;
    var current = 0.0;
    while (current < distance) {
      final end = math.min(current + 5, distance);
      canvas.drawLine(
        a + direction * current,
        a + direction * end,
        paint,
      );
      current += 10;
    }
  }

  @override
  bool shouldRepaint(covariant _NetworkPainter oldDelegate) =>
      oldDelegate.nodeCount != nodeCount;
}

List<Offset> _networkPositions(
  double width,
  double height,
  int count,
) {
  if (count <= 0) return const <Offset>[];
  final center = Offset(width / 2, height / 2);
  final values = <Offset>[center];
  final radiusX = width * .34;
  final radiusY = height * .30;
  for (var i = 1; i < count; i++) {
    final angle =
        -math.pi / 2 + (2 * math.pi * (i - 1) / math.max(1, count - 1));
    values.add(
      Offset(
        center.dx + math.cos(angle) * radiusX,
        center.dy + math.sin(angle) * radiusY,
      ),
    );
  }
  return values;
}

class _SourceHealthSection extends StatelessWidget {
  const _SourceHealthSection({required this.items});

  final List<SourceHealthItem> items;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title: 'حالة مصادر البيانات والأنظمة',
      subtitle:
          'الحالة الحية للمصادر؛ UNKNOWN يبقى صريحًا ولا يُحوّل إلى غياب.',
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
      title: 'المؤشرات التنفيذية للمحفظة',
      subtitle: 'مؤشرات حقيقية من snapshot الحالي؛ لا نسب تقدم أو ETA مصطنعة.',
      child: LayoutBuilder(
        builder: (context, constraints) {
          final width = constraints.maxWidth;
          final columns = width >= 1380
              ? math.min(8, items.length)
              : width >= 900
                  ? math.min(4, items.length)
                  : width >= 560
                      ? math.min(2, items.length)
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
      title: 'أهم المشاريع الاستراتيجية',
      subtitle: 'الحالة والجاهزية والأولوية والإجراء التالي من الواقع المرصود.',
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
              Expanded(
                child: Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
              ),
              const SizedBox(width: 8),
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
            style: const TextStyle(
              color: _ccText,
              fontSize: 13,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            subtitle,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: _ccMuted, fontSize: 9),
          ),
          const SizedBox(height: 10),
          child,
        ],
      ),
    );
  }
}

class _Panel extends StatelessWidget {
  const _Panel({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: _ccPanel,
        borderRadius: BorderRadius.circular(13),
        border: Border.all(color: _ccBorder),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: _ccCyan.withValues(alpha: .025),
            blurRadius: 18,
            spreadRadius: 1,
          ),
        ],
      ),
      child: child,
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
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
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
