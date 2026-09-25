import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/presentation/preview_mode_ui.dart';
import '../core/theme/palwakf_theme.dart';
import '../features/dashboard/application/dashboard_controller.dart';
import '../features/orchestrator/application/orchestrator_controller.dart';
import '../features/orchestrator/presentation/service_auth_dialog.dart';
import '../features/portfolio_intelligence/application/portfolio_intelligence_controller.dart';
import '../features/projects/application/external_projects_controller.dart';

class WorkspaceApplicationShell extends ConsumerWidget {
  const WorkspaceApplicationShell({
    required this.location,
    required this.child,
    super.key,
  });

  final String location;
  final Widget child;

  static const dailyDestinations = <ShellDestination>[
    ShellDestination('/home', 'الرئيسية', Icons.home_outlined, Icons.home),
    ShellDestination(
      '/overview',
      'لوحة التحكم',
      Icons.space_dashboard_outlined,
      Icons.space_dashboard,
    ),
    ShellDestination(
      '/projects',
      'مشاريعي',
      Icons.folder_outlined,
      Icons.folder,
    ),
    ShellDestination(
      '/work',
      'أعمالي',
      Icons.checklist_outlined,
      Icons.checklist,
    ),
  ];

  static const destinations = <ShellDestination>[
    ShellDestination(
      '/dashboard',
      'لوحة العمليات',
      Icons.dashboard_outlined,
      Icons.dashboard,
    ),
    ShellDestination('/projects', 'المشاريع', Icons.hub_outlined, Icons.hub),
    ShellDestination(
      '/tasks',
      'المهام',
      Icons.task_alt_outlined,
      Icons.task_alt,
    ),
    ShellDestination(
      '/extensions',
      'التوسعات',
      Icons.extension_outlined,
      Icons.extension,
    ),
    ShellDestination(
      '/operations',
      'التشغيل',
      Icons.settings_suggest_outlined,
      Icons.settings_suggest,
    ),
    ShellDestination('/tools', 'الأدوات', Icons.build_outlined, Icons.build),
    ShellDestination(
      '/alerts',
      'التنبيهات',
      Icons.notifications_outlined,
      Icons.notifications,
    ),
    ShellDestination(
      '/evidence',
      'الأدلة',
      Icons.fact_check_outlined,
      Icons.fact_check,
    ),
    ShellDestination(
      '/settings/connections',
      'الاتصالات',
      Icons.cable_outlined,
      Icons.cable,
    ),
  ];

  static const portfolioDestinations = <ShellDestination>[
    ShellDestination(
      '/dashboard',
      'مركز القيادة',
      Icons.home_rounded,
      Icons.home_rounded,
    ),
    ShellDestination(
      '/portfolio/projects',
      'المشاريع الاستراتيجية',
      Icons.folder_copy_outlined,
      Icons.folder_copy_rounded,
    ),
    ShellDestination(
      '/portfolio/timeline',
      'المخطط الزمني',
      Icons.calendar_month_outlined,
      Icons.calendar_month_rounded,
    ),
    ShellDestination(
      '/portfolio/programs',
      'المحفظة والبرامج',
      Icons.hub_outlined,
      Icons.hub_rounded,
    ),
    ShellDestination(
      '/portfolio/dependencies',
      'الاعتمادات والتكامل',
      Icons.account_tree_outlined,
      Icons.account_tree_rounded,
    ),
    ShellDestination(
      '/portfolio/capabilities',
      'المهارات والقدرات',
      Icons.psychology_outlined,
      Icons.psychology_rounded,
    ),
    ShellDestination(
      '/portfolio/agents',
      'الوكلاء',
      Icons.smart_toy_outlined,
      Icons.smart_toy_rounded,
    ),
    ShellDestination(
      '/portfolio/intelligence',
      'البحث والذكاء',
      Icons.manage_search_outlined,
      Icons.manage_search_rounded,
    ),
    ShellDestination(
      '/portfolio/waqf',
      'الأوقاف والأنظمة',
      Icons.account_balance_outlined,
      Icons.account_balance_rounded,
    ),
    ShellDestination(
      '/portfolio/hajj-umrah',
      'الحج والعمرة',
      Icons.mosque_outlined,
      Icons.mosque_rounded,
    ),
    ShellDestination(
      '/portfolio/gis',
      'الخرائط المكانية GIS',
      Icons.location_on_outlined,
      Icons.location_on_rounded,
    ),
    ShellDestination(
      '/portfolio/reports',
      'التقارير والتحليلات',
      Icons.analytics_outlined,
      Icons.analytics_rounded,
    ),
    ShellDestination(
      '/portfolio/recommendations',
      'التوصيات الذكية',
      Icons.auto_awesome_outlined,
      Icons.auto_awesome_rounded,
    ),
    ShellDestination(
      '/portfolio/decisions',
      'القرارات',
      Icons.gavel_outlined,
      Icons.gavel_rounded,
    ),
    ShellDestination(
      '/portfolio/activity',
      'سجل الأحداث',
      Icons.history_outlined,
      Icons.history_rounded,
    ),
  ];

  static const advancedDestinations = <ShellDestination>[
    ShellDestination(
      '/advanced',
      'الإدارة المتقدمة',
      Icons.admin_panel_settings_outlined,
      Icons.admin_panel_settings,
    ),
    ShellDestination(
      '/advanced/projects-registry',
      'سجل المشاريع المحكوم',
      Icons.radar_outlined,
      Icons.radar,
    ),
    ShellDestination(
      '/advanced/operations-dashboard',
      'لوحة العمليات التقنية',
      Icons.monitor_heart_outlined,
      Icons.monitor_heart,
    ),
    ShellDestination(
      '/tasks',
      'المهام الهندسية',
      Icons.task_alt_outlined,
      Icons.task_alt,
    ),
    ShellDestination(
      '/extensions',
      'التوسعات',
      Icons.extension_outlined,
      Icons.extension,
    ),
    ShellDestination(
      '/operations',
      'التشغيل',
      Icons.settings_suggest_outlined,
      Icons.settings_suggest,
    ),
    ShellDestination('/tools', 'الأدوات', Icons.build_outlined, Icons.build),
    ShellDestination(
      '/alerts',
      'التنبيهات والمخاطر',
      Icons.warning_amber_outlined,
      Icons.warning_amber_rounded,
    ),
    ShellDestination(
      '/evidence',
      'الأدلة والمعرفة',
      Icons.fact_check_outlined,
      Icons.fact_check,
    ),
    ShellDestination(
      '/settings/connections',
      'الاتصالات',
      Icons.cable_outlined,
      Icons.cable,
    ),
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final connection =
        ref.watch(dashboardControllerProvider).summary?.connection;
    final hasToken =
        (ref.watch(orchestratorTokenProvider) ?? '').trim().isNotEmpty;
    final previewMode = PreviewModeUi.isVisualPreview;
    final advanced = _isAdvancedPath(location);
    final commandCenter = location == '/dashboard';

    final connectionLabel = previewMode
        ? 'معاينة'
        : connection == null
            ? 'الحالة غير متاحة'
            : connection.ready
                ? 'الخدمة متصلة'
                : 'الخدمة غير متصلة';
    final connectionIcon = previewMode
        ? Icons.visibility_outlined
        : connection == null
            ? Icons.help_outline_rounded
            : connection.ready
                ? Icons.check_circle_outline_rounded
                : Icons.link_off_rounded;
    final connectionColor = previewMode
        ? PalWakfTheme.workspacePurple
        : connection == null
            ? PalWakfTheme.workspaceMuted
            : connection.ready
                ? PalWakfTheme.workspaceGreen
                : PalWakfTheme.workspaceRed;

    return Theme(
      data: PalWakfTheme.dark(),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final desktop = constraints.maxWidth >= 1024;

          final sidebar = _WorkspaceSidebar(
            location: location,
            onNavigate: (route) => context.go(route),
          );

          return Scaffold(
            backgroundColor: PalWakfTheme.workspaceBg,
            appBar: !desktop && !commandCenter
                ? AppBar(
                    titleSpacing: 10,
                    title: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          _pageTitle(location),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        const Text(
                          'PalWakf Workspace',
                          style: TextStyle(
                            color: PalWakfTheme.workspaceMuted,
                            fontSize: 9,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                    actions: <Widget>[
                      _ConnectionIcon(
                        label: connectionLabel,
                        icon: connectionIcon,
                        color: connectionColor,
                      ),
                      IconButton(
                        tooltip: 'تحديث',
                        onPressed: () => _refresh(ref),
                        icon: const Icon(Icons.refresh_rounded),
                      ),
                      const SizedBox(width: 4),
                    ],
                  )
                : null,
            drawer: !desktop
                ? Drawer(
                    child: SafeArea(
                      child: sidebar,
                    ),
                  )
                : null,
            body: SafeArea(
              top: desktop,
              child: Row(
                textDirection: TextDirection.rtl,
                children: <Widget>[
                  if (desktop)
                    SizedBox(
                      width: 232,
                      child: sidebar,
                    ),
                  if (desktop)
                    const VerticalDivider(
                      width: 1,
                      thickness: 1,
                      color: PalWakfTheme.workspaceBorder,
                    ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: <Widget>[
                        if (desktop && !commandCenter)
                          _WorkspaceCommandHeader(
                            title: _pageTitle(location),
                            advanced: advanced,
                            previewMode: previewMode,
                            connectionLabel: connectionLabel,
                            connectionIcon: connectionIcon,
                            connectionColor: connectionColor,
                            hasToken: hasToken,
                            onAuthenticate: advanced && !previewMode
                                ? () => showServiceAuthDialog(context, ref)
                                : null,
                            onRefresh: () => _refresh(ref),
                          ),
                        Expanded(
                          child: DecoratedBox(
                            decoration: const BoxDecoration(
                              color: PalWakfTheme.workspaceBg,
                            ),
                            child: child,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  static bool _isAdvancedPath(String path) {
    if (path == '/advanced' || path.startsWith('/advanced/')) {
      return true;
    }
    return destinations.any(
      (item) =>
          item.route != '/projects' &&
          (path == item.route || path.startsWith('${item.route}/')),
    );
  }

  static bool _matches(String path, String route) {
    if (path == route) {
      return true;
    }
    return switch (route) {
      '/projects' ||
      '/tools' ||
      '/portfolio/projects' =>
        path.startsWith('$route/'),
      _ => false,
    };
  }

  static String _pageTitle(String path) {
    final all = <ShellDestination>[
      ...portfolioDestinations,
      ...dailyDestinations,
      ...advancedDestinations,
    ];
    for (final destination in all) {
      if (_matches(path, destination.route)) {
        return destination.label;
      }
    }
    return 'PalWakf Workspace';
  }

  Future<void> _refresh(WidgetRef ref) async {
    await Future.wait<void>(<Future<void>>[
      ref.read(dashboardControllerProvider.notifier).load(),
      ref.read(orchestratorControllerProvider.notifier).load(),
      ref.read(externalProjectsControllerProvider.notifier).load(),
      ref.read(portfolioIntelligenceControllerProvider.notifier).load(),
    ]);
  }
}

class _WorkspaceCommandHeader extends StatelessWidget {
  const _WorkspaceCommandHeader({
    required this.title,
    required this.advanced,
    required this.previewMode,
    required this.connectionLabel,
    required this.connectionIcon,
    required this.connectionColor,
    required this.hasToken,
    required this.onRefresh,
    this.onAuthenticate,
  });

  final String title;
  final bool advanced;
  final bool previewMode;
  final String connectionLabel;
  final IconData connectionIcon;
  final Color connectionColor;
  final bool hasToken;
  final VoidCallback onRefresh;
  final VoidCallback? onAuthenticate;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const ValueKey<String>('palwakf-unified-command-header'),
      constraints: const BoxConstraints(minHeight: 72),
      padding: const EdgeInsetsDirectional.fromSTEB(18, 10, 18, 10),
      decoration: const BoxDecoration(
        color: PalWakfTheme.workspaceBg,
        border: Border(
          bottom: BorderSide(color: PalWakfTheme.workspaceBorder),
        ),
      ),
      child: Row(
        children: <Widget>[
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: <Widget>[
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: PalWakfTheme.workspaceText,
                    fontSize: 18,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  advanced
                      ? 'PalWakf Workspace · الإدارة المتقدمة'
                      : 'PalWakf Workspace · مساحة القيادة والتنفيذ',
                  style: const TextStyle(
                    color: PalWakfTheme.workspaceMuted,
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          _ConnectionChip(
            label: connectionLabel,
            icon: connectionIcon,
            color: connectionColor,
          ),
          if (onAuthenticate != null) ...<Widget>[
            const SizedBox(width: 8),
            IconButton.filledTonal(
              tooltip: hasToken
                  ? 'مصادقة الخدمة مهيأة في هذه الجلسة'
                  : 'إعداد مصادقة الخدمة',
              onPressed: onAuthenticate,
              icon: Icon(
                hasToken ? Icons.lock_rounded : Icons.lock_open_rounded,
                size: 19,
              ),
            ),
          ],
          const SizedBox(width: 8),
          IconButton.filledTonal(
            tooltip: 'تحديث المصادر',
            onPressed: onRefresh,
            icon: const Icon(Icons.refresh_rounded, size: 19),
          ),
        ],
      ),
    );
  }
}

class _ConnectionChip extends StatelessWidget {
  const _ConnectionChip({
    required this.label,
    required this.icon,
    required this.color,
  });

  final String label;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsetsDirectional.fromSTEB(10, 7, 10, 7),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        border: Border.all(color: color.withValues(alpha: 0.36)),
        borderRadius: BorderRadius.circular(9),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 10,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _ConnectionIcon extends StatelessWidget {
  const _ConnectionIcon({
    required this.label,
    required this.icon,
    required this.color,
  });

  final String label;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: label,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 5),
        child: Icon(icon, color: color, size: 19),
      ),
    );
  }
}

class _WorkspaceSidebar extends StatelessWidget {
  const _WorkspaceSidebar({
    required this.location,
    required this.onNavigate,
  });

  final String location;
  final ValueChanged<String> onNavigate;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const ValueKey<String>('palwakf-unified-rtl-sidebar'),
      color: PalWakfTheme.workspaceSidebar,
      child: Column(
        children: <Widget>[
          const _WorkspaceBrand(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(9, 4, 9, 18),
              children: <Widget>[
                _NavigationSection(
                  title: 'القيادة والمحفظة',
                  destinations: WorkspaceApplicationShell.portfolioDestinations,
                  location: location,
                  onNavigate: onNavigate,
                ),
                const SizedBox(height: 10),
                _NavigationSection(
                  title: 'مساحة العمل',
                  destinations: WorkspaceApplicationShell.dailyDestinations,
                  location: location,
                  onNavigate: onNavigate,
                ),
                const SizedBox(height: 10),
                _NavigationSection(
                  title: 'التشغيل والحوكمة',
                  destinations: WorkspaceApplicationShell.advancedDestinations,
                  location: location,
                  onNavigate: onNavigate,
                ),
              ],
            ),
          ),
          const _SidebarAuthorityFooter(),
        ],
      ),
    );
  }
}

class _WorkspaceBrand extends StatelessWidget {
  const _WorkspaceBrand();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsetsDirectional.fromSTEB(12, 18, 12, 12),
      child: Row(
        children: <Widget>[
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: <Color>[
                  PalWakfTheme.workspaceTeal,
                  PalWakfTheme.workspaceBlue,
                ],
              ),
              borderRadius: BorderRadius.circular(11),
              boxShadow: <BoxShadow>[
                BoxShadow(
                  color: PalWakfTheme.workspaceTeal.withValues(alpha: 0.20),
                  blurRadius: 16,
                ),
              ],
            ),
            child: const Icon(
              Icons.account_balance_rounded,
              color: Color(0xFF001A19),
              size: 21,
            ),
          ),
          const SizedBox(width: 9),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'PalWakf',
                  style: TextStyle(
                    color: PalWakfTheme.workspaceText,
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                    letterSpacing: .2,
                  ),
                ),
                Text(
                  'Workspace Manager',
                  style: TextStyle(
                    color: PalWakfTheme.workspaceMuted,
                    fontSize: 9,
                    fontWeight: FontWeight.w700,
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

class _NavigationSection extends StatelessWidget {
  const _NavigationSection({
    required this.title,
    required this.destinations,
    required this.location,
    required this.onNavigate,
  });

  final String title;
  final List<ShellDestination> destinations;
  final String location;
  final ValueChanged<String> onNavigate;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Padding(
          padding: const EdgeInsetsDirectional.fromSTEB(9, 6, 9, 6),
          child: Text(
            title,
            style: const TextStyle(
              color: PalWakfTheme.workspaceMuted,
              fontSize: 9,
              fontWeight: FontWeight.w900,
              letterSpacing: .2,
            ),
          ),
        ),
        ...destinations.map((destination) {
          final selected = WorkspaceApplicationShell._matches(
            location,
            destination.route,
          );
          return Padding(
            padding: const EdgeInsets.only(bottom: 3),
            child: Material(
              color: selected
                  ? PalWakfTheme.workspaceBlue.withValues(alpha: 0.18)
                  : Colors.transparent,
              borderRadius: BorderRadius.circular(9),
              child: InkWell(
                key: ValueKey<String>('workspace-nav-${destination.route}'),
                borderRadius: BorderRadius.circular(9),
                onTap: () => onNavigate(destination.route),
                child: Container(
                  constraints: const BoxConstraints(minHeight: 38),
                  padding: const EdgeInsetsDirectional.fromSTEB(10, 7, 9, 7),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(9),
                    border: Border.all(
                      color: selected
                          ? PalWakfTheme.workspaceCyan.withValues(alpha: 0.20)
                          : Colors.transparent,
                    ),
                  ),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        selected ? destination.selectedIcon : destination.icon,
                        size: 17,
                        color: selected
                            ? PalWakfTheme.workspaceCyan
                            : PalWakfTheme.workspaceMuted,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          destination.label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: selected
                                ? PalWakfTheme.workspaceText
                                : PalWakfTheme.workspaceMuted,
                            fontSize: 10.5,
                            fontWeight:
                                selected ? FontWeight.w900 : FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        }),
      ],
    );
  }
}

class _SidebarAuthorityFooter extends StatelessWidget {
  const _SidebarAuthorityFooter();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsetsDirectional.fromSTEB(12, 10, 12, 12),
      decoration: const BoxDecoration(
        border: Border(
          top: BorderSide(color: PalWakfTheme.workspaceBorder),
        ),
      ),
      child: const Row(
        children: <Widget>[
          Icon(
            Icons.verified_user_outlined,
            size: 15,
            color: PalWakfTheme.workspaceTeal,
          ),
          SizedBox(width: 7),
          Expanded(
            child: Text(
              'الحقيقة قبل التعديل · السلطة لا تُفترض',
              style: TextStyle(
                color: PalWakfTheme.workspaceMuted,
                fontSize: 8.5,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class ShellDestination {
  const ShellDestination(this.route, this.label, this.icon, this.selectedIcon);

  final String route;
  final String label;
  final IconData icon;
  final IconData selectedIcon;
}
