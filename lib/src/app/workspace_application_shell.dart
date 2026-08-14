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
    final selectedIndex = _selectedIndex(location);
    final connection =
        ref.watch(dashboardControllerProvider).summary?.connection;
    final hasToken =
        (ref.watch(orchestratorTokenProvider) ?? '').trim().isNotEmpty;
    final previewMode = PreviewModeUi.isVisualPreview;
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
                  'PalWakf Workspace Manager',
                  textDirection: TextDirection.ltr,
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
                          ? 'معاينة بصرية'
                          : connection?.ready ?? false
                              ? connection!.localSecure
                                  ? 'محلي آمن'
                                  : 'متصل'
                              : 'غير متصل',
                    ),
                  ),
                ),
              if (!previewMode)
                IconButton(
                  tooltip: hasToken
                      ? 'مصادقة الخدمة مهيأة في هذه الجلسة'
                      : 'إعداد مصادقة الخدمة',
                  onPressed: () => showServiceAuthDialog(context, ref),
                  icon: Icon(hasToken ? Icons.lock : Icons.lock_open_outlined),
                ),
              IconButton(
                tooltip: 'تحديث الحالة الموثقة',
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
                        context.go(destinations[index].route);
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
                    minExtendedWidth: 232,
                    selectedIndex: selectedIndex,
                    labelType: desktop && extended
                        ? NavigationRailLabelType.none
                        : NavigationRailLabelType.all,
                    onDestinationSelected: (index) =>
                        context.go(destinations[index].route),
                    leading: const Padding(
                      padding: EdgeInsets.only(bottom: 14),
                      child: Icon(Icons.account_balance_outlined),
                    ),
                    destinations: destinations
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
                  selectedIndex: selectedIndex <= 3 ? selectedIndex : 0,
                  onDestinationSelected: (index) =>
                      context.go(destinations[index].route),
                  destinations: destinations
                      .take(4)
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

  int _selectedIndex(String path) {
    final index = destinations.indexWhere(
      (destination) =>
          path == destination.route || path.startsWith('${destination.route}/'),
    );
    return index < 0 ? 0 : index;
  }

  static String _pageTitle(String path) {
    if (path.startsWith('/projects/')) return 'تفاصيل المشروع';
    if (path.startsWith('/tools/')) return 'تفاصيل الأداة';
    return destinations
        .firstWhere(
          (item) => path == item.route || path.startsWith('${item.route}/'),
          orElse: () => destinations.first,
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
            itemCount: WorkspaceApplicationShell.destinations.length,
            itemBuilder: (context, index) {
              final destination = WorkspaceApplicationShell.destinations[index];
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
