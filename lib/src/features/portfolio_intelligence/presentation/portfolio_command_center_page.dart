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
          final desktop = constraints.maxWidth >= 1180;
          return Material(
            color: _ccBg,
            child: Row(
              textDirection: TextDirection.rtl,
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
                                      const BoxConstraints(maxWidth: 1920),
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
                                      _ExecutiveLowerDeck(
                                        snapshot: snapshot,
                                      ),
                                      const SizedBox(height: 10),
                                      _ExecutiveSummaryStrip(
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
    (
      '\u0627\u0644\u0631\u0626\u064a\u0633\u064a\u0629',
      '/dashboard',
      Icons.home_rounded
    ),
    (
      '\u0627\u0644\u0645\u0634\u0627\u0631\u064a\u0639',
      '/projects',
      Icons.folder_copy_rounded
    ),
    (
      '\u0627\u0644\u0645\u062e\u0637\u0637 \u0627\u0644\u0632\u0645\u0646\u064a',
      '',
      Icons.calendar_month_rounded
    ),
    (
      '\u0627\u0644\u0645\u062d\u0641\u0638\u0629 \u0648\u0627\u0644\u0628\u0631\u0627\u0645\u062c',
      '',
      Icons.hub_rounded
    ),
    (
      '\u0627\u0644\u0627\u0639\u062a\u0645\u0627\u062f\u0627\u062a \u0648\u0627\u0644\u062a\u0643\u0627\u0645\u0644',
      '',
      Icons.account_tree_rounded
    ),
    (
      '\u0627\u0644\u0645\u0647\u0627\u0631\u0627\u062a \u0648\u0627\u0644\u0642\u062f\u0631\u0627\u062a',
      '',
      Icons.psychology_rounded
    ),
    (
      '\u0627\u0644\u0623\u062f\u0648\u0627\u062a',
      '/tools',
      Icons.build_circle_rounded
    ),
    ('\u0627\u0644\u0648\u0643\u0644\u0627\u0621', '', Icons.smart_toy_rounded),
    (
      '\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0648\u0627\u0644\u0645\u0639\u0631\u0641\u0629',
      '/evidence',
      Icons.layers_rounded
    ),
    (
      '\u0627\u0644\u0628\u062d\u062b \u0648\u0627\u0644\u0630\u0643\u0627\u0621',
      '',
      Icons.manage_search_rounded
    ),
    (
      '\u0627\u0644\u0623\u0648\u0642\u0627\u0641 \u0648\u0627\u0644\u0623\u0646\u0638\u0645\u0629',
      '',
      Icons.account_balance_rounded
    ),
    (
      '\u0627\u0644\u062d\u062c \u0648\u0627\u0644\u0639\u0645\u0631\u0629',
      '',
      Icons.mosque_rounded
    ),
    (
      '\u0627\u0644\u062e\u0631\u0627\u0626\u0637 \u0627\u0644\u0645\u0643\u0627\u0646\u064a\u0629 GIS',
      '',
      Icons.location_on_rounded
    ),
    (
      '\u0627\u0644\u062a\u0642\u0627\u0631\u064a\u0631 \u0648\u0627\u0644\u062a\u062d\u0644\u064a\u0644\u0627\u062a',
      '',
      Icons.analytics_rounded
    ),
    (
      '\u0627\u0644\u062a\u0648\u0635\u064a\u0627\u062a \u0627\u0644\u0630\u0643\u064a\u0629',
      '',
      Icons.auto_awesome_rounded
    ),
    (
      '\u0627\u0644\u0645\u062e\u0627\u0637\u0631 \u0648\u0627\u0644\u0645\u0639\u0648\u0642\u0627\u062a',
      '/alerts',
      Icons.warning_amber_rounded
    ),
    (
      '\u0633\u062c\u0644 \u0627\u0644\u0623\u062d\u062f\u0627\u062b',
      '',
      Icons.history_rounded
    ),
    (
      '\u0625\u0639\u062f\u0627\u062f\u0627\u062a \u0627\u0644\u0646\u0638\u0627\u0645',
      '/settings/connections',
      Icons.settings_rounded
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const ValueKey<String>('portfolio-rtl-sidebar'),
      width: 190,
      decoration: const BoxDecoration(
        color: Color(0xFF020D17),
        border: Border(left: BorderSide(color: _ccBorder)),
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
                    final selected = index == 0;
                    return Material(
                      color: selected
                          ? _ccBlue.withValues(alpha: .20)
                          : Colors.transparent,
                      borderRadius: BorderRadius.circular(9),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(9),
                        onTap:
                            item.$2.isEmpty ? null : () => context.go(item.$2),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 9,
                          ),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(9),
                            border: selected
                                ? BorderDirectional(
                                    start: BorderSide(
                                      color: _ccCyan.withValues(alpha: .72),
                                      width: 2,
                                    ),
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
                                  textAlign: TextAlign.right,
                                  style: TextStyle(
                                    color: selected ? _ccText : _ccMuted,
                                    fontSize: 11,
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
                padding: const EdgeInsets.all(8),
                child: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: <Color>[
                        _ccPurple.withValues(alpha: .20),
                        _ccBlue.withValues(alpha: .12),
                      ],
                    ),
                    borderRadius: BorderRadius.circular(10),
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
                        size: 22,
                      ),
                      SizedBox(height: 4),
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
              label: 'التصميم المعتمد',
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
          hintText: 'ابحث في المشاريع والبيانات والأدوات والقدرات...',
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
        const Icon(
          Icons.light_mode_outlined,
          color: _ccMuted,
          size: 21,
        ),
        const SizedBox(width: 12),
        const Icon(
          Icons.mail_outline_rounded,
          color: _ccMuted,
          size: 21,
        ),
        const SizedBox(width: 12),
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
              textDirection: TextDirection.ltr,
              children: <Widget>[
                Expanded(flex: 5, child: title),
                const SizedBox(width: 16),
                Expanded(flex: 5, child: search),
                const SizedBox(width: 16),
                actions,
                const SizedBox(width: 12),
                _HeaderHeroTile(snapshot: snapshot),
              ],
            ),
    );
  }
}

// FINAL_LITERAL_RTL_VISUAL_FIDELITY_V3
// FINAL_LITERAL_RTL_VISUAL_FIDELITY_V4
// FINAL_LITERAL_RTL_VISUAL_FIDELITY_V5

class _HeaderHeroTile extends StatelessWidget {
  const _HeaderHeroTile({required this.snapshot});

  final PortfolioCommandCenterSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final healthy = snapshot.sourceHealth
        .where((item) => item.state.toUpperCase() == 'HEALTHY')
        .length;

    final truthColor = _statusColor(
      context,
      snapshot.truthState,
    );

    return Container(
      key: const ValueKey<String>('header-hero-tile'),
      width: 220,
      height: 82,
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(11),
        gradient: LinearGradient(
          begin: AlignmentDirectional.topStart,
          end: AlignmentDirectional.bottomEnd,
          colors: <Color>[
            _ccBlue.withValues(alpha: .30),
            _ccPanelHigh,
            _ccTeal.withValues(alpha: .16),
          ],
        ),
        border: Border.all(
          color: _ccCyan.withValues(alpha: .34),
        ),
      ),
      child: Row(
        children: <Widget>[
          Container(
            width: 52,
            height: 64,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(9),
              gradient: const LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: <Color>[
                  Color(0xFF155CA8),
                  Color(0xFF073558),
                ],
              ),
              border: Border.all(
                color: Color(0x335DEBFF),
              ),
            ),
            child: const Icon(
              Icons.account_balance_rounded,
              color: Color(0xFFE8C66B),
              size: 30,
            ),
          ),
          const SizedBox(width: 9),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const Text(
                  '\u0622\u062e\u0631 \u0644\u0642\u0637\u0629 \u0645\u0648\u062b\u0642\u0629',
                  style: TextStyle(
                    color: _ccMuted,
                    fontSize: 8,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  _formatDateTime(snapshot.generatedAt),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: _ccText,
                    fontSize: 10,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  children: <Widget>[
                    Container(
                      width: 7,
                      height: 7,
                      decoration: BoxDecoration(
                        color: truthColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 5),
                    Expanded(
                      child: Text(
                        snapshot.truthState,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: truthColor,
                          fontSize: 8,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                  ],
                ),
                Text(
                  '$healthy/${snapshot.sourceHealth.length} '
                  '\u0645\u0635\u0627\u062f\u0631 \u0635\u062d\u064a\u0629',
                  style: const TextStyle(
                    color: _ccMuted,
                    fontSize: 8,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ExecutiveLowerDeck extends StatelessWidget {
  const _ExecutiveLowerDeck({required this.snapshot});

  final PortfolioCommandCenterSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final capabilities = <RegistryEntity>[
      ...snapshot.capabilities,
      ...snapshot.skills,
    ];

    final timeline = _ExecutiveTimelinePanel(
      snapshot: snapshot,
    );

    final skills = _ExecutiveRegistryPanel(
      title:
          '\u0627\u0644\u0642\u062f\u0631\u0627\u062a \u0648\u0627\u0644\u0645\u0647\u0627\u0631\u0627\u062a',
      icon: Icons.psychology_rounded,
      items: capabilities,
    );

    final tools = _ExecutiveRegistryPanel(
      title:
          '\u0627\u0644\u0623\u062f\u0648\u0627\u062a \u0627\u0644\u0645\u062a\u0635\u0644\u0629',
      icon: Icons.build_circle_rounded,
      items: snapshot.tools,
    );

    final agents = _ExecutiveRegistryPanel(
      title:
          '\u0627\u0644\u0648\u0643\u0644\u0627\u0621 \u0648\u0627\u0644\u0623\u0646\u0638\u0645\u0629 \u0627\u0644\u0630\u0643\u064a\u0629 \u0648\u0627\u0644\u0645\u0632\u0648\u062f\u0648\u0646',
      icon: Icons.smart_toy_rounded,
      items: <RegistryEntity>[
        ...snapshot.providers,
        ...snapshot.agents,
      ],
    );

    final activity = _ExecutiveActivityPanel(
      snapshot: snapshot,
    );

    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 1050) {
          return Column(
            children: <Widget>[
              timeline,
              const SizedBox(height: 10),
              skills,
              const SizedBox(height: 10),
              tools,
              const SizedBox(height: 10),
              agents,
              const SizedBox(height: 10),
              activity,
            ],
          );
        }

        return Column(
          key: const ValueKey<String>(
            'executive-lower-deck-v5',
          ),
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            timeline,
            const SizedBox(height: 10),
            IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  Expanded(
                    flex: 23,
                    child: skills,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    flex: 17,
                    child: tools,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    flex: 22,
                    child: agents,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    flex: 38,
                    child: activity,
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

class _ExecutiveTimelinePanel extends StatelessWidget {
  const _ExecutiveTimelinePanel({required this.snapshot});

  final PortfolioCommandCenterSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    return _Section(
      title:
          '\u0627\u0644\u0645\u062e\u0637\u0637 \u0627\u0644\u0632\u0645\u0646\u064a \u0644\u0644\u0645\u062d\u0641\u0638\u0629',
      subtitle:
          '\u064a\u0639\u0631\u0636 \u0641\u0642\u0637 \u0627\u0644\u062a\u0642\u062f\u0645 \u0627\u0644\u0645\u062b\u0628\u062a\u061b \u0648\u0639\u0646\u062f \u063a\u064a\u0627\u0628 \u0627\u0644\u0646\u0633\u0628\u0629 \u062a\u0638\u0647\u0631 \u062d\u0627\u0644\u0629 \u0627\u0644\u062c\u0627\u0647\u0632\u064a\u0629 \u0628\u062f\u0644\u064b\u0627 \u0645\u0646 \u0627\u062e\u062a\u0644\u0627\u0642 \u062a\u0642\u062f\u0645.',
      child: Container(
        key: const ValueKey<String>(
          'portfolio-executive-timeline',
        ),
        child: Column(
          children: <Widget>[
            const Padding(
              padding: EdgeInsetsDirectional.only(
                start: 154,
                end: 82,
              ),
              child: Row(
                textDirection: TextDirection.ltr,
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: <Widget>[
                  Text(
                    '0%',
                    style: TextStyle(
                      color: _ccMuted,
                      fontSize: 7,
                    ),
                  ),
                  Text(
                    '25%',
                    style: TextStyle(
                      color: _ccMuted,
                      fontSize: 7,
                    ),
                  ),
                  Text(
                    '50%',
                    style: TextStyle(
                      color: _ccMuted,
                      fontSize: 7,
                    ),
                  ),
                  Text(
                    '75%',
                    style: TextStyle(
                      color: _ccMuted,
                      fontSize: 7,
                    ),
                  ),
                  Text(
                    '100%',
                    style: TextStyle(
                      color: _ccMuted,
                      fontSize: 7,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 6),
            ...snapshot.projects.take(8).map((project) {
              final progress = project.scopeProgressPercent;
              final color = _statusColor(
                context,
                project.readiness,
              );

              return Padding(
                padding: const EdgeInsets.only(bottom: 7),
                child: Row(
                  children: <Widget>[
                    SizedBox(
                      width: 145,
                      child: Text(
                        project.displayName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: _ccText,
                          fontSize: 8,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: progress == null
                          ? Container(
                              height: 22,
                              alignment: Alignment.center,
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(5),
                                gradient: LinearGradient(
                                  colors: <Color>[
                                    color.withValues(
                                      alpha: .15,
                                    ),
                                    _ccPanelHigh,
                                  ],
                                ),
                                border: Border.all(
                                  color: color.withValues(
                                    alpha: .42,
                                  ),
                                ),
                              ),
                              child: Text(
                                '${project.readiness} ? '
                                '\u0627\u0644\u062a\u0642\u062f\u0645 \u063a\u064a\u0631 \u0645\u062a\u0627\u062d',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  color: color,
                                  fontSize: 7,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            )
                          : ClipRRect(
                              borderRadius: BorderRadius.circular(5),
                              child: Stack(
                                alignment: Alignment.center,
                                children: <Widget>[
                                  LinearProgressIndicator(
                                    minHeight: 22,
                                    value:
                                        progress.clamp(0, 100).toDouble() / 100,
                                    backgroundColor: _ccPanelHigh,
                                    valueColor: AlwaysStoppedAnimation<Color>(
                                      color,
                                    ),
                                  ),
                                  Text(
                                    '${progress.round()}%',
                                    style: const TextStyle(
                                      color: _ccText,
                                      fontSize: 7,
                                      fontWeight: FontWeight.w900,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                    ),
                    const SizedBox(width: 8),
                    SizedBox(
                      width: 72,
                      child: Text(
                        project.readiness,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        textAlign: TextAlign.end,
                        style: TextStyle(
                          color: color,
                          fontSize: 7,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }
}

class _ExecutiveRegistryPanel extends StatelessWidget {
  const _ExecutiveRegistryPanel({
    required this.title,
    required this.icon,
    required this.items,
  });

  final String title;
  final IconData icon;
  final List<RegistryEntity> items;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(icon, color: _ccCyan, size: 17),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: _ccText,
                    fontSize: 10,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              Text(
                '${items.length}',
                style: const TextStyle(
                  color: _ccCyan,
                  fontSize: 9,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          const Divider(height: 14),
          if (items.isEmpty)
            const _EmptyState(message: 'No observed entries.')
          else
            ...items.take(6).map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      children: <Widget>[
                        Container(
                          width: 7,
                          height: 7,
                          decoration: BoxDecoration(
                            color: _statusColor(context, item.status),
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            item.nameAr,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: _ccText,
                              fontSize: 8,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        const SizedBox(width: 4),
                        SizedBox(
                          width: 58,
                          child: Text(
                            item.status,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            textAlign: TextAlign.end,
                            style: TextStyle(
                              color: _statusColor(context, item.status),
                              fontSize: 7,
                              fontWeight: FontWeight.w800,
                            ),
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

class _ExecutiveActivityPanel extends StatelessWidget {
  const _ExecutiveActivityPanel({required this.snapshot});

  final PortfolioCommandCenterSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final hasContent =
        snapshot.recentChanges.isNotEmpty || snapshot.decisions.isNotEmpty;

    return _Panel(
      child: Column(
        key: const ValueKey<String>('executive-activity-panel'),
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          const Row(
            children: <Widget>[
              Icon(
                Icons.history_rounded,
                color: _ccCyan,
                size: 17,
              ),
              SizedBox(width: 6),
              Expanded(
                child: Text(
                  '\u0622\u062e\u0631 \u0627\u0644\u0623\u0646\u0634\u0637\u0629 \u0648\u0627\u0644\u0642\u0631\u0627\u0631\u0627\u062a',
                  style: TextStyle(
                    color: _ccText,
                    fontSize: 10,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
          const Divider(height: 14),
          if (!hasContent)
            const _EmptyState(
              message:
                  '\u0644\u0627 \u062a\u0648\u062c\u062f \u0623\u0646\u0634\u0637\u0629 \u0623\u0648 \u0642\u0631\u0627\u0631\u0627\u062a \u0645\u0631\u0635\u0648\u062f\u0629.',
            )
          else ...<Widget>[
            ...snapshot.recentChanges.take(4).map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      children: <Widget>[
                        const Icon(
                          Icons.check_circle_rounded,
                          color: _ccTeal,
                          size: 12,
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            item.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: _ccText,
                              fontSize: 8,
                            ),
                          ),
                        ),
                        const SizedBox(width: 5),
                        Text(
                          _formatDateTime(item.occurredAt),
                          style: const TextStyle(
                            color: _ccMuted,
                            fontSize: 7,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            if (snapshot.recentChanges.isNotEmpty &&
                snapshot.decisions.isNotEmpty)
              const Divider(height: 12),
            ...snapshot.decisions.take(2).map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      children: <Widget>[
                        const Icon(
                          Icons.gavel_rounded,
                          color: _ccOrange,
                          size: 12,
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            item.summaryAr,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: _ccText,
                              fontSize: 8,
                            ),
                          ),
                        ),
                        const SizedBox(width: 5),
                        _StateChip(
                          label: item.status,
                          state: item.status,
                        ),
                      ],
                    ),
                  ),
                ),
          ],
        ],
      ),
    );
  }
}

class _ExecutiveSummaryStrip extends StatelessWidget {
  const _ExecutiveSummaryStrip({required this.snapshot});

  final PortfolioCommandCenterSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final healthy = snapshot.sourceHealth
        .where((item) => item.state.toUpperCase() == 'HEALTHY')
        .length;

    final metrics = <(IconData, String, String, Color)>[
      (
        Icons.folder_copy_rounded,
        '${snapshot.projects.length}',
        '\u0627\u0644\u0645\u0634\u0627\u0631\u064a\u0639',
        _ccPurple,
      ),
      (
        Icons.psychology_rounded,
        '${snapshot.capabilities.length + snapshot.skills.length}',
        '\u0627\u0644\u0642\u062f\u0631\u0627\u062a \u0648\u0627\u0644\u0645\u0647\u0627\u0631\u0627\u062a',
        _ccBlue,
      ),
      (
        Icons.build_circle_rounded,
        '${snapshot.tools.length}',
        '\u0627\u0644\u0623\u062f\u0648\u0627\u062a \u0627\u0644\u0645\u062a\u0635\u0644\u0629',
        _ccTeal,
      ),
      (
        Icons.smart_toy_rounded,
        '${snapshot.agents.length}',
        '\u0627\u0644\u0648\u0643\u0644\u0627\u0621',
        _ccCyan,
      ),
      (
        Icons.warning_amber_rounded,
        '${snapshot.risks.length}',
        '\u0627\u0644\u0645\u062e\u0627\u0637\u0631 \u0627\u0644\u0645\u0641\u062a\u0648\u062d\u0629',
        _ccRed,
      ),
      (
        Icons.gavel_rounded,
        '${snapshot.decisions.length}',
        '\u0627\u0644\u0642\u0631\u0627\u0631\u0627\u062a \u0627\u0644\u0645\u0637\u0644\u0648\u0628\u0629',
        _ccOrange,
      ),
      (
        Icons.fact_check_rounded,
        '${snapshot.evidenceRefs.length}',
        '\u0645\u0631\u0627\u062c\u0639 \u0627\u0644\u0623\u062f\u0644\u0629',
        _ccBlue,
      ),
      (
        Icons.health_and_safety_rounded,
        '$healthy/${snapshot.sourceHealth.length}',
        '\u0645\u0635\u0627\u062f\u0631 \u0635\u062d\u064a\u0629',
        _ccGreen,
      ),
    ];

    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final columns = width >= 1200
            ? 8
            : width >= 700
                ? 4
                : 2;

        final itemWidth = (width - (columns - 1) * 8) / columns;

        return Container(
          key: const ValueKey<String>('executive-summary-strip'),
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            children: metrics
                .map(
                  (metric) => SizedBox(
                    width: itemWidth,
                    child: Container(
                      height: 58,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 8,
                      ),
                      decoration: BoxDecoration(
                        color: _ccPanel,
                        borderRadius: BorderRadius.circular(9),
                        border: Border.all(
                          color: metric.$4.withValues(alpha: .36),
                        ),
                        gradient: LinearGradient(
                          colors: <Color>[
                            metric.$4.withValues(alpha: .14),
                            _ccPanel,
                          ],
                        ),
                      ),
                      child: Row(
                        children: <Widget>[
                          Icon(
                            metric.$1,
                            color: metric.$4,
                            size: 18,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Text(
                                  metric.$2,
                                  style: const TextStyle(
                                    color: _ccText,
                                    fontSize: 14,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                                Text(
                                  metric.$3,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    color: _ccMuted,
                                    fontSize: 7,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                )
                .toList(growable: false),
          ),
        );
      },
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
    final recommendations = _RecommendationsPanel(
      recommendations: snapshot.recommendations,
    );

    final risks = _RisksPanel(risks: snapshot.risks);

    return LayoutBuilder(
      builder: (context, constraints) {
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

        return Container(
          key: const ValueKey<String>('executive-core-grid-v4'),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Expanded(
                flex: 44,
                child: _ProjectsSection(projects: projects),
              ),
              const SizedBox(width: 10),
              Expanded(
                flex: 34,
                child: _StrategicNetworkPanel(snapshot: snapshot),
              ),
              const SizedBox(width: 10),
              Expanded(
                flex: 22,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    recommendations,
                    const SizedBox(height: 8),
                    risks,
                  ],
                ),
              ),
            ],
          ),
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

    Widget legendItem(
      Color color,
      String label,
    ) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 5),
          Text(
            label,
            style: const TextStyle(
              color: _ccMuted,
              fontSize: 8,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      );
    }

    return _Section(
      title:
          '\u0627\u0644\u062e\u0631\u064a\u0637\u0629 \u0627\u0644\u0627\u0633\u062a\u0631\u0627\u062a\u064a\u062c\u064a\u0629 \u0644\u0644\u0645\u0634\u0627\u0631\u064a\u0639 \u0648\u0627\u0644\u0642\u062f\u0631\u0627\u062a',
      subtitle:
          '\u062a\u0631\u0627\u0628\u0637 \u0645\u0631\u0626\u064a \u0645\u0646 \u0627\u0644\u0639\u0646\u0627\u0635\u0631 \u0627\u0644\u0645\u0631\u0635\u0648\u062f\u0629 \u0641\u0639\u0644\u064a\u064b\u0627 \u062f\u0648\u0646 \u0627\u062e\u062a\u0644\u0627\u0642 \u0646\u0648\u0639 \u0639\u0644\u0627\u0642\u0629.',
      child: SizedBox(
        height: 335,
        child: nodes.isEmpty
            ? const _EmptyState(
                message:
                    '\u0644\u0627 \u062a\u0648\u062c\u062f \u0639\u0642\u062f \u0645\u0631\u0635\u0648\u062f\u0629 \u0644\u0631\u0633\u0645 \u0627\u0644\u062e\u0631\u064a\u0637\u0629.',
              )
            : LayoutBuilder(
                builder: (context, constraints) {
                  final positions = _networkPositions(
                    constraints.maxWidth,
                    constraints.maxHeight - 52,
                    nodes.length,
                  );

                  return Stack(
                    children: <Widget>[
                      Positioned.fill(
                        child: CustomPaint(
                          painter: _NetworkPainter(
                            nodeCount: nodes.length,
                          ),
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
                            horizontal: 9,
                            vertical: 6,
                          ),
                          decoration: BoxDecoration(
                            color: _ccPanelHigh.withValues(alpha: .88),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: _ccBorder,
                            ),
                          ),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              Wrap(
                                alignment: WrapAlignment.center,
                                spacing: 15,
                                runSpacing: 4,
                                children: <Widget>[
                                  legendItem(
                                    _ccBlue,
                                    '\u0645\u0634\u0631\u0648\u0639',
                                  ),
                                  legendItem(
                                    _ccTeal,
                                    '\u0642\u062f\u0631\u0629',
                                  ),
                                  legendItem(
                                    _ccPurple,
                                    '\u0623\u062f\u0627\u0629',
                                  ),
                                ],
                              ),
                              const SizedBox(height: 3),
                              const Text(
                                '\u0627\u0644\u0623\u0644\u0648\u0627\u0646 \u062a\u0645\u062b\u0644 \u0646\u0648\u0639 \u0627\u0644\u0639\u0642\u062f\u0629\u061b \u0644\u0627 \u064a\u064f\u0633\u062a\u0646\u062a\u062c \u0646\u0648\u0639 \u0631\u0627\u0628\u0637 \u063a\u064a\u0631 \u0645\u062b\u0628\u062a.',
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                  color: _ccMuted,
                                  fontSize: 7,
                                ),
                              ),
                            ],
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
      title:
          '\u062d\u0627\u0644\u0629 \u0645\u0635\u0627\u062f\u0631 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0648\u0627\u0644\u0623\u0646\u0638\u0645\u0629',
      subtitle:
          '\u0627\u0644\u062d\u0627\u0644\u0629 \u0627\u0644\u062d\u064a\u0629 \u0644\u0644\u0645\u0635\u0627\u062f\u0631\u061b UNKNOWN \u064a\u0628\u0642\u0649 \u0635\u0631\u064a\u062d\u064b\u0627 \u0648\u0644\u0627 \u064a\u064f\u062d\u0648\u0651\u0644 \u0625\u0644\u0649 \u063a\u064a\u0627\u0628.',
      child: items.isEmpty
          ? const _EmptyState(
              message: 'No source-health entries are available.')
          : LayoutBuilder(
              builder: (context, constraints) {
                final width = constraints.maxWidth;
                final columns = width >= 900
                    ? math.max(1, math.min(7, items.length))
                    : width >= 560
                        ? math.max(1, math.min(3, items.length))
                        : 1;
                final cardWidth = (width - (columns - 1) * 8) / columns;
                return Wrap(
                  spacing: 8,
                  runSpacing: 8,
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
      constraints: const BoxConstraints(minHeight: 78),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(9),
        color: _ccPanelHigh,
        border: Border.all(color: color.withValues(alpha: .42)),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: color.withValues(alpha: .05),
            blurRadius: 12,
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(Icons.sensors_rounded, size: 16, color: color),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  item.labelAr,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            children: <Widget>[
              Container(
                width: 7,
                height: 7,
                decoration: BoxDecoration(
                  color: color,
                  shape: BoxShape.circle,
                  boxShadow: <BoxShadow>[
                    BoxShadow(
                      color: color.withValues(alpha: .45),
                      blurRadius: 8,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 5),
              Expanded(
                child: Text(
                  item.state,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: color,
                    fontSize: 9,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            item.freshness,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: _ccMuted,
              fontSize: 8,
            ),
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
    final color = _statusColor(context, item.status);
    return Container(
      key: ValueKey<String>('kpi-${item.kpiId}'),
      constraints: const BoxConstraints(minHeight: 104),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(10),
        gradient: LinearGradient(
          colors: <Color>[
            color.withValues(alpha: .19),
            _ccPanelHigh,
          ],
        ),
        border: Border.all(color: color.withValues(alpha: .42)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(
                Icons.insights_rounded,
                color: color,
                size: 17,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  item.labelAr,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 7),
          Text(
            item.value,
            style: const TextStyle(
              color: _ccText,
              fontSize: 22,
              fontWeight: FontWeight.w900,
              height: 1,
            ),
          ),
          const SizedBox(height: 5),
          Text(
            item.explanationAr,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: _ccMuted,
              fontSize: 8,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            '${(item.confidence * 100).round()}% confidence',
            style: TextStyle(
              color: color,
              fontSize: 8,
              fontWeight: FontWeight.w700,
            ),
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
      title:
          '\u0623\u0647\u0645 \u0627\u0644\u0645\u0634\u0627\u0631\u064a\u0639 \u0627\u0644\u0627\u0633\u062a\u0631\u0627\u062a\u064a\u062c\u064a\u0629',
      subtitle:
          '\u0627\u0644\u062d\u0627\u0644\u0629 \u0648\u0627\u0644\u062c\u0627\u0647\u0632\u064a\u0629 \u0648\u0627\u0644\u0623\u0648\u0644\u0648\u064a\u0629 \u0648\u0627\u0644\u062a\u0642\u062f\u0645 \u0648\u0627\u0644\u0645\u0639\u064a\u0642\u0627\u062a \u0645\u0646 \u0627\u0644\u0648\u0627\u0642\u0639 \u0627\u0644\u0645\u0631\u0635\u0648\u062f.',
      child: LayoutBuilder(
        builder: (context, constraints) {
          if (constraints.maxWidth < 420) {
            return Column(
              children: projects
                  .map(
                    (project) => Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: _ProjectCard(project: project),
                    ),
                  )
                  .toList(growable: false),
            );
          }

          return ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: DataTable(
                key: const ValueKey<String>('portfolio-projects-table'),
                horizontalMargin: 8,
                columnSpacing: 12,
                headingRowHeight: 38,
                dataRowMinHeight: 44,
                dataRowMaxHeight: 52,
                columns: const <DataColumn>[
                  DataColumn(
                      label:
                          Text('\u0627\u0644\u0645\u0634\u0631\u0648\u0639')),
                  DataColumn(
                      label: Text('\u0627\u0644\u062d\u0627\u0644\u0629')),
                  DataColumn(
                      label: Text(
                          '\u0627\u0644\u062c\u0627\u0647\u0632\u064a\u0629')),
                  DataColumn(
                      label: Text('\u0627\u0644\u062a\u0642\u062f\u0645')),
                  DataColumn(
                      label: Text(
                          '\u0627\u0644\u0623\u0648\u0644\u0648\u064a\u0629')),
                  DataColumn(
                      label: Text(
                          '\u0627\u0644\u0645\u0639\u064a\u0642\u0627\u062a')),
                  DataColumn(
                      label: Text(
                          '\u0627\u0644\u0625\u062c\u0631\u0627\u0621 \u0627\u0644\u062a\u0627\u0644\u064a')),
                ],
                rows: projects.take(8).map((project) {
                  return DataRow(
                    cells: <DataCell>[
                      DataCell(
                        SizedBox(
                          width: 135,
                          child: Text(
                            project.displayName,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ),
                      DataCell(
                        _StateChip(
                          label: project.truthState,
                          state: project.truthState,
                        ),
                      ),
                      DataCell(
                        _StateChip(
                          label: project.readiness,
                          state: project.readiness,
                        ),
                      ),
                      DataCell(
                        Text(
                          project.scopeProgressPercent == null
                              ? '\u063a\u064a\u0631 \u0645\u062a\u0627\u062d'
                              : '${project.scopeProgressPercent!.round()}%',
                        ),
                      ),
                      DataCell(Text('${project.priorityScore}/100')),
                      DataCell(Text('${project.blockers.length}')),
                      DataCell(
                        SizedBox(
                          width: 165,
                          child: Text(
                            project.nextActionAr,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 8),
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
    final visible = recommendations.take(2).toList(growable: false);

    return _Panel(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Row(
            children: <Widget>[
              const Icon(
                Icons.auto_awesome_rounded,
                size: 17,
                color: _ccCyan,
              ),
              const SizedBox(width: 6),
              const Expanded(
                child: Text(
                  '\u0627\u0644\u062a\u0648\u0635\u064a\u0627\u062a \u0627\u0644\u0630\u0643\u064a\u0629',
                  style: TextStyle(
                    color: _ccText,
                    fontSize: 11,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              Text(
                '${recommendations.length}',
                style: const TextStyle(
                  color: _ccCyan,
                  fontSize: 10,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          const SizedBox(height: 3),
          const Text(
            '\u0627\u0633\u062a\u0634\u0627\u0631\u064a\u0629 \u0641\u0642\u0637 \u0648\u0644\u0627 \u062a\u0645\u0646\u062d \u0633\u0644\u0637\u0629 \u062a\u0646\u0641\u064a\u0630.',
            style: TextStyle(
              color: _ccMuted,
              fontSize: 8,
            ),
          ),
          const Divider(height: 14),
          if (visible.isEmpty)
            const _EmptyState(
              message:
                  '\u0644\u0627 \u062a\u0648\u062c\u062f \u062a\u0648\u0635\u064a\u0627\u062a \u0630\u0627\u062a \u0623\u0648\u0644\u0648\u064a\u0629.',
            )
          else
            ...visible.map(
              (item) => Container(
                key: ValueKey<String>(item.recommendationId),
                margin: const EdgeInsets.only(bottom: 7),
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: _ccPanelHigh,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: _ccCyan.withValues(alpha: .22),
                  ),
                ),
                child: Row(
                  children: <Widget>[
                    CircleAvatar(
                      radius: 15,
                      backgroundColor: _ccTeal.withValues(alpha: .18),
                      child: Text(
                        '${(item.confidence * 100).round()}',
                        style: const TextStyle(
                          color: _ccTeal,
                          fontSize: 8,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                    const SizedBox(width: 7),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                            item.type,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: _ccText,
                              fontSize: 10,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            item.reasonAr,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: _ccMuted,
                              fontSize: 8,
                              height: 1.2,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 5),
                    _StateChip(
                      label: item.authority,
                      state: item.authority,
                    ),
                  ],
                ),
              ),
            ),
          if (recommendations.length > visible.length)
            Text(
              '+${recommendations.length - visible.length} '
              '\u062a\u0648\u0635\u064a\u0627\u062a \u0625\u0636\u0627\u0641\u064a\u0629',
              style: const TextStyle(
                color: _ccMuted,
                fontSize: 8,
              ),
            ),
        ],
      ),
    );
  }
}

class _RisksPanel extends StatelessWidget {
  const _RisksPanel({required this.risks});

  final List<PortfolioRisk> risks;

  @override
  Widget build(BuildContext context) {
    final visible = risks.take(3).toList(growable: false);

    return _Panel(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Row(
            children: <Widget>[
              const Icon(
                Icons.warning_amber_rounded,
                size: 17,
                color: _ccOrange,
              ),
              const SizedBox(width: 6),
              const Expanded(
                child: Text(
                  '\u0627\u0644\u0645\u062e\u0627\u0637\u0631 \u0648\u0627\u0644\u0645\u0639\u0648\u0642\u0627\u062a',
                  style: TextStyle(
                    color: _ccText,
                    fontSize: 11,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              Text(
                '${risks.length}',
                style: const TextStyle(
                  color: _ccOrange,
                  fontSize: 10,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          const SizedBox(height: 3),
          const Text(
            '\u0623\u0639\u0644\u0649 \u0627\u0644\u0645\u062e\u0627\u0637\u0631 \u0627\u0644\u0645\u0631\u0635\u0648\u062f\u0629 \u0648\u0627\u0644\u0625\u062c\u0631\u0627\u0621 \u0627\u0644\u0645\u0637\u0644\u0648\u0628.',
            style: TextStyle(
              color: _ccMuted,
              fontSize: 8,
            ),
          ),
          const Divider(height: 14),
          if (visible.isEmpty)
            const _EmptyState(
              message:
                  '\u0644\u0627 \u062a\u0648\u062c\u062f \u0645\u062e\u0627\u0637\u0631 \u062a\u0634\u063a\u064a\u0644\u064a\u0629 \u0645\u0631\u0635\u0648\u062f\u0629.',
            )
          else
            ...visible.map(
              (item) => Container(
                margin: const EdgeInsets.only(bottom: 6),
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: _ccPanelHigh,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: _statusColor(
                      context,
                      item.severity,
                    ).withValues(alpha: .28),
                  ),
                ),
                child: Row(
                  children: <Widget>[
                    Icon(
                      Icons.warning_amber_rounded,
                      size: 15,
                      color: _statusColor(
                        context,
                        item.severity,
                      ),
                    ),
                    const SizedBox(width: 7),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                            item.summaryAr,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: _ccText,
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            item.requiredActionAr,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: _ccMuted,
                              fontSize: 8,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 5),
                    _StateChip(
                      label: item.severity,
                      state: item.severity,
                    ),
                  ],
                ),
              ),
            ),
          if (risks.length > visible.length)
            Text(
              '+${risks.length - visible.length} '
              '\u0645\u062e\u0627\u0637\u0631 \u0625\u0636\u0627\u0641\u064a\u0629',
              style: const TextStyle(
                color: _ccMuted,
                fontSize: 8,
              ),
            ),
        ],
      ),
    );
  }
}

class _AuthorityFooter extends StatelessWidget {
  const _AuthorityFooter({required this.notes});

  final List<String> notes;

  @override
  Widget build(BuildContext context) {
    String localized(String note) {
      switch (note) {
        case 'SOURCE_FAILURE_DOES_NOT_ERASE_LAST_VERIFIED_STATE':
          return '\u0641\u0634\u0644 \u0627\u0644\u0645\u0635\u062f\u0631 \u0644\u0627 \u064a\u0645\u062d\u0648 \u0622\u062e\u0631 \u062d\u0627\u0644\u0629 \u0645\u062a\u062d\u0642\u0642\u0629';
        case 'UNKNOWN_IS_NOT_FALSE':
          return '\u063a\u064a\u0631 \u0645\u0639\u0631\u0648\u0641 \u0644\u0627 \u064a\u0639\u0646\u064a \u062e\u0637\u0623';
        case 'CAPABILITY_IS_NOT_AUTHORITY':
          return '\u0627\u0644\u0642\u062f\u0631\u0629 \u0644\u0627 \u062a\u0639\u0646\u064a \u0627\u0644\u062a\u0641\u0648\u064a\u0636';
        case 'RECOMMENDATIONS_DO_NOT_AUTHORIZE_EXECUTION':
          return '\u0627\u0644\u062a\u0648\u0635\u064a\u0627\u062a \u0644\u0627 \u062a\u0645\u0646\u062d \u0633\u0644\u0637\u0629 \u0627\u0644\u062a\u0646\u0641\u064a\u0630';
        default:
          return note;
      }
    }

    return Container(
      key: const ValueKey<String>(
        'compact-authority-footer-v5',
      ),
      padding: const EdgeInsets.symmetric(
        horizontal: 8,
        vertical: 6,
      ),
      decoration: BoxDecoration(
        color: _ccPanel.withValues(alpha: .72),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: _ccBorder,
        ),
      ),
      child: Wrap(
        alignment: WrapAlignment.center,
        spacing: 7,
        runSpacing: 5,
        children: notes
            .map(
              (note) => Tooltip(
                message: note,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: _ccPanelHigh.withValues(alpha: .82),
                    borderRadius: BorderRadius.circular(7),
                    border: Border.all(
                      color: _ccTeal.withValues(
                        alpha: .22,
                      ),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      const Icon(
                        Icons.shield_outlined,
                        size: 12,
                        color: _ccTeal,
                      ),
                      const SizedBox(width: 5),
                      Text(
                        localized(note),
                        style: const TextStyle(
                          color: _ccMuted,
                          fontSize: 8,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            )
            .toList(growable: false),
      ),
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
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: _ccPanel,
        borderRadius: BorderRadius.circular(10),
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
