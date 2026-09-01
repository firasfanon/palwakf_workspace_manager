import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/presentation/preview_mode_ui.dart';
import '../features/dashboard/application/dashboard_controller.dart';
import '../features/orchestrator/application/orchestrator_controller.dart';
import '../features/orchestrator/presentation/service_auth_dialog.dart';
import '../features/projects/application/external_projects_controller.dart';

class WorkspaceApplicationShell extends ConsumerWidget {
  const WorkspaceApplicationShell({
    required this.location,
    required this.child,
    super.key,
  });

  final String location;
  final Widget child;

  /// Primary destinations shown to ordinary users.
  static const dailyDestinations = <ShellDestination>[
    ShellDestination('/home', 'الرئيسية', Icons.home_outlined, Icons.home),
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
    ShellDestination(
      '/advanced',
      'الإدارة المتقدمة',
      Icons.admin_panel_settings_outlined,
      Icons.admin_panel_settings,
    ),
  ];

  /// Compatibility registry for the advanced control-plane routes.
  ///
  /// These routes remain reachable and testable, but are no longer exposed as
  /// the ordinary user's primary navigation.
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

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selectedIndex = _selectedDailyIndex(location);
    final connection =
        ref.watch(dashboardControllerProvider).summary?.connection;
    final hasToken =
        (ref.watch(orchestratorTokenProvider) ?? '').trim().isNotEmpty;
    final previewMode = PreviewModeUi.isVisualPreview;
    final advanced = _isAdvancedPath(location);

    return LayoutBuilder(
      builder: (context, constraints) {
        final desktop = constraints.maxWidth >= 1024;
        final extended = constraints.maxWidth >= 1280;
        final mobile = constraints.maxWidth < 720;

        return Scaffold(
          appBar: AppBar(
            automaticallyImplyLeading: mobile,
            titleSpacing: mobile ? null : 20,
            title: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(_pageTitle(location)),
                Text(
                  advanced
                      ? 'PalWakf Workspace · الإدارة المتقدمة'
                      : 'PalWakf Workspace',
                  textDirection: TextDirection.rtl,
                  style: Theme.of(context).textTheme.labelSmall,
                ),
              ],
            ),
            actions: <Widget>[
              if (!mobile)
                Padding(
                  padding: const EdgeInsetsDirectional.only(end: 4),
                  child: Chip(
                    avatar: Icon(
                      previewMode
                          ? Icons.visibility_outlined
                          : connection?.ready ?? false
                              ? Icons.check_circle_outline
                              : Icons.link_off_outlined,
                      size: 16,
                    ),
                    label: Text(
                      previewMode
                          ? 'معاينة'
                          : connection?.ready ?? false
                              ? 'جاهز'
                              : 'غير متصل',
                    ),
                  ),
                ),
              if (advanced && !previewMode)
                IconButton(
                  tooltip: hasToken
                      ? 'مصادقة الخدمة مهيأة في هذه الجلسة'
                      : 'إعداد مصادقة الخدمة',
                  onPressed: () => showServiceAuthDialog(context, ref),
                  icon: Icon(hasToken ? Icons.lock : Icons.lock_open_outlined),
                ),
              IconButton(
                tooltip: 'تحديث',
                onPressed: () => _refresh(ref),
                icon: const Icon(Icons.refresh),
              ),
              const SizedBox(width: 6),
            ],
          ),
          drawer: mobile
              ? Drawer(
                  child: SafeArea(
                    child: _DrawerNavigation(
                      selectedIndex: selectedIndex,
                      onSelected: (index) {
                        Navigator.of(context).pop();
                        context.go(dailyDestinations[index].route);
                      },
                    ),
                  ),
                )
              : null,
          body: SafeArea(
            top: false,
            child: Row(
              children: <Widget>[
                if (!mobile)
                  NavigationRail(
                    extended: desktop && extended,
                    minExtendedWidth: 220,
                    selectedIndex: selectedIndex,
                    labelType: desktop && extended
                        ? NavigationRailLabelType.none
                        : NavigationRailLabelType.all,
                    onDestinationSelected: (index) =>
                        context.go(dailyDestinations[index].route),
                    leading: const Padding(
                      padding: EdgeInsets.only(bottom: 14),
                      child: Icon(Icons.account_balance_outlined),
                    ),
                    destinations: dailyDestinations
                        .map(
                          (destination) => NavigationRailDestination(
                            icon: Icon(destination.icon),
                            selectedIcon: Icon(destination.selectedIcon),
                            label: Text(destination.label),
                          ),
                        )
                        .toList(growable: false),
                  ),
                if (!mobile) const VerticalDivider(width: 1),
                Expanded(child: child),
              ],
            ),
          ),
          bottomNavigationBar: mobile
              ? NavigationBar(
                  selectedIndex: selectedIndex,
                  onDestinationSelected: (index) =>
                      context.go(dailyDestinations[index].route),
                  destinations: dailyDestinations
                      .map(
                        (destination) => NavigationDestination(
                          icon: Icon(destination.icon),
                          selectedIcon: Icon(destination.selectedIcon),
                          label: destination.label,
                        ),
                      )
                      .toList(growable: false),
                )
              : null,
        );
      },
    );
  }

  int _selectedDailyIndex(String path) {
    if (path == '/home' || path == '/') return 0;
    if (path == '/projects' || path.startsWith('/projects/')) return 1;
    if (path == '/work' || path.startsWith('/work/')) return 2;
    return 3;
  }

  static bool _isAdvancedPath(String path) {
    if (path == '/advanced' || path.startsWith('/advanced/')) return true;
    return destinations.any(
      (item) =>
          item.route != '/projects' &&
          (path == item.route || path.startsWith('${item.route}/')),
    );
  }

  static String _pageTitle(String path) {
    if (path == '/home' || path == '/') return 'الرئيسية';
    if (path == '/work' || path.startsWith('/work/')) return 'أعمالي';
    if (path == '/projects') return 'مشاريعي';
    if (path.startsWith('/projects/')) return 'تفاصيل المشروع';
    if (path == '/advanced') return 'الإدارة المتقدمة';
    if (path.startsWith('/tools/')) return 'تفاصيل الأداة';

    return destinations
        .firstWhere(
          (item) => path == item.route || path.startsWith('${item.route}/'),
          orElse: () => dailyDestinations.last,
        )
        .label;
  }

  Future<void> _refresh(WidgetRef ref) async {
    await Future.wait<void>(<Future<void>>[
      ref.read(dashboardControllerProvider.notifier).load(),
      ref.read(orchestratorControllerProvider.notifier).load(),
      ref.read(externalProjectsControllerProvider.notifier).load(),
    ]);
  }
}

class _DrawerNavigation extends StatelessWidget {
  const _DrawerNavigation({
    required this.selectedIndex,
    required this.onSelected,
  });

  final int selectedIndex;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.fromLTRB(18, 20, 18, 14),
          child: Text(
            'مساحة عمل PalWakf',
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.symmetric(vertical: 8),
            itemCount: WorkspaceApplicationShell.dailyDestinations.length,
            itemBuilder: (context, index) {
              final destination =
                  WorkspaceApplicationShell.dailyDestinations[index];
              return ListTile(
                selected: index == selectedIndex,
                leading: Icon(
                  index == selectedIndex
                      ? destination.selectedIcon
                      : destination.icon,
                ),
                title: Text(destination.label),
                onTap: () => onSelected(index),
              );
            },
          ),
        ),
      ],
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
