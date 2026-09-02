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

  static const dailyDestinations = <ShellDestination>[
    ShellDestination('/home', 'الرئيسية', Icons.home_outlined, Icons.home),
    ShellDestination(
      '/overview',
      'لوحة التحكم',
      Icons.space_dashboard_outlined,
      Icons.space_dashboard,
    ),
    ShellDestination(
        '/projects', 'مشاريعي', Icons.folder_outlined, Icons.folder),
    ShellDestination(
        '/work', 'أعمالي', Icons.checklist_outlined, Icons.checklist),
  ];

  static const destinations = <ShellDestination>[
    ShellDestination('/dashboard', 'لوحة العمليات', Icons.dashboard_outlined,
        Icons.dashboard),
    ShellDestination('/projects', 'المشاريع', Icons.hub_outlined, Icons.hub),
    ShellDestination(
        '/tasks', 'المهام', Icons.task_alt_outlined, Icons.task_alt),
    ShellDestination(
        '/extensions', 'التوسعات', Icons.extension_outlined, Icons.extension),
    ShellDestination('/operations', 'التشغيل', Icons.settings_suggest_outlined,
        Icons.settings_suggest),
    ShellDestination('/tools', 'الأدوات', Icons.build_outlined, Icons.build),
    ShellDestination('/alerts', 'التنبيهات', Icons.notifications_outlined,
        Icons.notifications),
    ShellDestination(
        '/evidence', 'الأدلة', Icons.fact_check_outlined, Icons.fact_check),
    ShellDestination('/settings/connections', 'الاتصالات', Icons.cable_outlined,
        Icons.cable),
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
        final extended = constraints.maxWidth >= 1320;
        final mobile = constraints.maxWidth < 760;

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
                      advancedSelected: advanced,
                      onSelected: (index) {
                        Navigator.of(context).pop();
                        context.go(dailyDestinations[index].route);
                      },
                      onAdvanced: () {
                        Navigator.of(context).pop();
                        context.go('/advanced');
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
                    minExtendedWidth: 230,
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
                    trailing: Padding(
                      padding: const EdgeInsets.only(top: 18),
                      child: SizedBox(
                        width: extended ? 190 : 76,
                        child: TextButton(
                          key: const ValueKey<String>('advanced-secondary-nav'),
                          onPressed: () => context.go('/advanced'),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: <Widget>[
                              Icon(
                                advanced
                                    ? Icons.admin_panel_settings
                                    : Icons.admin_panel_settings_outlined,
                              ),
                              const SizedBox(height: 3),
                              const FittedBox(
                                fit: BoxFit.scaleDown,
                                child: Text('الإدارة المتقدمة'),
                              ),
                            ],
                          ),
                        ),
                      ),
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
          bottomNavigationBar: mobile && !advanced
              ? NavigationBar(
                  selectedIndex: selectedIndex ?? 0,
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

  int? _selectedDailyIndex(String path) {
    if (path == '/home' || path == '/') {
      return 0;
    }
    if (path == '/overview' || path.startsWith('/overview/')) {
      return 1;
    }
    if (path == '/projects' || path.startsWith('/projects/')) {
      return 2;
    }
    if (path == '/work' || path.startsWith('/work/')) {
      return 3;
    }
    return null;
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

  static String _pageTitle(String path) {
    if (path == '/home' || path == '/') {
      return 'الرئيسية';
    }
    if (path == '/overview' || path.startsWith('/overview/')) {
      return 'لوحة التحكم';
    }
    if (path == '/work' || path.startsWith('/work/')) {
      return 'أعمالي';
    }
    if (path == '/projects') {
      return 'مشاريعي';
    }
    if (path.startsWith('/projects/')) {
      return 'تفاصيل المشروع';
    }
    if (path == '/advanced') {
      return 'الإدارة المتقدمة';
    }
    if (path.startsWith('/tools/')) {
      return 'تفاصيل الأداة';
    }

    return destinations
        .firstWhere(
          (item) => path == item.route || path.startsWith('${item.route}/'),
          orElse: () => const ShellDestination(
            '/advanced',
            'الإدارة المتقدمة',
            Icons.admin_panel_settings_outlined,
            Icons.admin_panel_settings,
          ),
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
    required this.advancedSelected,
    required this.onSelected,
    required this.onAdvanced,
  });

  final int? selectedIndex;
  final bool advancedSelected;
  final ValueChanged<int> onSelected;
  final VoidCallback onAdvanced;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.fromLTRB(18, 20, 18, 14),
          child: Text(
            'مساحة عمل PalWakf',
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
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
        const Divider(height: 1),
        ListTile(
          key: const ValueKey<String>('advanced-secondary-drawer'),
          selected: advancedSelected,
          leading: Icon(
            advancedSelected
                ? Icons.admin_panel_settings
                : Icons.admin_panel_settings_outlined,
          ),
          title: const Text('الإدارة المتقدمة'),
          subtitle: const Text('للتشخيص والتفاصيل التقنية'),
          onTap: onAdvanced,
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
