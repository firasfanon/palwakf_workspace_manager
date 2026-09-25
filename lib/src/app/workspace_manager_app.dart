import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/theme/palwakf_theme.dart';
import '../features/daily_workspace/presentation/advanced_operations_hub_page.dart';
import '../features/daily_workspace/presentation/daily_workspace_home_page.dart';
import '../features/daily_workspace/presentation/user_dashboard_page.dart';
import '../features/dashboard/presentation/operational_list_pages.dart';
import '../features/dashboard/presentation/workspace_dashboard_page.dart';
import '../features/engineering_os/presentation/extensions_center_page.dart';
import '../features/engineering_os/presentation/task_board_page.dart';
import '../features/orchestrator/presentation/orchestrator_workspace_page.dart';
import '../features/orchestrator/presentation/tool_health_page.dart';
import '../features/portfolio_intelligence/presentation/portfolio_command_center_page.dart';
import '../features/portfolio_intelligence/presentation/portfolio_section_page.dart';
import '../features/projects/presentation/external_projects_page.dart';
import '../features/projects/presentation/project_reality_page.dart';
import '../features/workspace_catalog/presentation/workspace_catalog_page.dart';
import 'workspace_application_shell.dart';

final workspaceRouterProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    initialLocation: '/home',
    routes: <RouteBase>[
      GoRoute(path: '/', redirect: (_, __) => '/home'),
      ShellRoute(
        builder: (context, state, child) =>
            WorkspaceApplicationShell(location: state.uri.path, child: child),
        routes: <RouteBase>[
          GoRoute(
            path: '/home',
            builder: (context, state) => DailyWorkspaceHomePage(
              initialTaskId: state.uri.queryParameters['taskId'],
              initialWorkspaceItemId: state.uri.queryParameters['itemId'],
            ),
          ),
          GoRoute(
            path: '/overview',
            builder: (context, state) => const UserWorkspaceDashboardPage(),
          ),
          GoRoute(
            path: '/work',
            builder: (context, state) => const DailyWorkspaceTasksPage(),
          ),
          GoRoute(
            path: '/advanced',
            builder: (context, state) => const AdvancedOperationsHubPage(),
          ),
          GoRoute(
            path: '/advanced/projects-registry',
            builder: (context, state) => const ExternalProjectsPage(),
          ),
          GoRoute(
            path: '/dashboard',
            builder: (context, state) =>
                const PortfolioCommandCenterPage(embedded: true),
          ),
          GoRoute(
            path: '/portfolio/projects',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'projects',
              title: 'المشاريع',
            ),
          ),
          GoRoute(
            path: '/portfolio/timeline',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'timeline',
              title: 'المخطط الزمني للمحفظة',
            ),
          ),
          GoRoute(
            path: '/portfolio/programs',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'programs',
              title: 'المحفظة والبرامج',
            ),
          ),
          GoRoute(
            path: '/portfolio/dependencies',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'dependencies',
              title: 'الاعتمادات والتكامل',
            ),
          ),
          GoRoute(
            path: '/portfolio/capabilities',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'capabilities',
              title: 'المهارات والقدرات',
            ),
          ),
          GoRoute(
            path: '/portfolio/agents',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'agents',
              title: 'الوكلاء والأنظمة الذكية',
            ),
          ),
          GoRoute(
            path: '/portfolio/intelligence',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'intelligence',
              title: 'البحث والذكاء',
            ),
          ),
          GoRoute(
            path: '/portfolio/waqf',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'waqf',
              title: 'الأوقاف والأنظمة',
            ),
          ),
          GoRoute(
            path: '/portfolio/hajj-umrah',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'hajj-umrah',
              title: 'الحج والعمرة',
            ),
          ),
          GoRoute(
            path: '/portfolio/gis',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'gis',
              title: 'الخرائط المكانية GIS',
            ),
          ),
          GoRoute(
            path: '/portfolio/reports',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'reports',
              title: 'التقارير والتحليلات',
            ),
          ),
          GoRoute(
            path: '/portfolio/recommendations',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'recommendations',
              title: 'التوصيات الذكية',
            ),
          ),
          GoRoute(
            path: '/portfolio/decisions',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'decisions',
              title: 'القرارات',
            ),
          ),
          GoRoute(
            path: '/portfolio/activity',
            builder: (context, state) => const PortfolioSectionPage(
              section: 'activity',
              title: 'سجل الأحداث',
            ),
          ),
          GoRoute(
            path: '/portfolio/projects/:projectId',
            builder: (context, state) => PortfolioProjectDetailPage(
              projectId: state.pathParameters['projectId']!,
            ),
          ),
          GoRoute(
            path: '/advanced/operations-dashboard',
            builder: (context, state) => const WorkspaceDashboardPage(),
          ),
          GoRoute(
            path: '/tasks',
            builder: (context, state) => const EngineeringTaskBoardPage(),
          ),
          GoRoute(
            path: '/extensions',
            builder: (context, state) => const ExtensionsCenterPage(),
          ),
          GoRoute(
            path: '/operations',
            builder: (context, state) => OrchestratorWorkspacePage(
              engineeringTaskId: state.uri.queryParameters['engineeringTaskId'],
            ),
          ),
          GoRoute(
            path: '/tools',
            builder: (context, state) => const ToolHealthPage(),
            routes: <RouteBase>[
              GoRoute(
                path: ':adapterId',
                builder: (context, state) => ToolHealthPage(
                  adapterId: state.pathParameters['adapterId'],
                ),
              ),
            ],
          ),
          GoRoute(
            path: '/projects',
            builder: (context, state) => const WorkspaceCatalogPage(),
            routes: <RouteBase>[
              GoRoute(
                path: ':projectId',
                builder: (context, state) => ProjectRealityPage(
                  projectId: state.pathParameters['projectId']!,
                ),
              ),
            ],
          ),
          GoRoute(
            path: '/alerts',
            builder: (context, state) => const OperationalAlertsPage(),
          ),
          GoRoute(
            path: '/evidence',
            builder: (context, state) => const EvidenceIndexPage(),
          ),
          GoRoute(
            path: '/settings/connections',
            builder: (context, state) => const ConnectionsPage(),
          ),
        ],
      ),
    ],
  );
  ref.onDispose(router.dispose);
  return router;
});

class WorkspaceManagerApp extends ConsumerWidget {
  const WorkspaceManagerApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'مدير مساحة عمل PalWakf',
      debugShowCheckedModeBanner: false,
      locale: const Locale('ar', 'PS'),
      supportedLocales: const <Locale>[Locale('ar', 'PS'), Locale('en', 'US')],
      localizationsDelegates: const <LocalizationsDelegate<dynamic>>[
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: PalWakfTheme.dark(),
      routerConfig: ref.watch(workspaceRouterProvider),
      builder: (context, child) {
        return Directionality(
          textDirection: TextDirection.rtl,
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}
