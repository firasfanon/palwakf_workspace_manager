import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/theme/palwakf_theme.dart';
import '../features/dashboard/presentation/operational_list_pages.dart';
import '../features/dashboard/presentation/workspace_dashboard_page.dart';
import '../features/engineering_os/presentation/extensions_center_page.dart';
import '../features/engineering_os/presentation/task_board_page.dart';
import '../features/orchestrator/presentation/orchestrator_workspace_page.dart';
import '../features/orchestrator/presentation/tool_health_page.dart';
import '../features/projects/presentation/external_projects_page.dart';
import '../features/projects/presentation/project_reality_page.dart';
import 'workspace_application_shell.dart';

final workspaceRouterProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    initialLocation: '/dashboard',
    routes: <RouteBase>[
      GoRoute(path: '/', redirect: (_, __) => '/dashboard'),
      ShellRoute(
        builder: (context, state, child) =>
            WorkspaceApplicationShell(location: state.uri.path, child: child),
        routes: <RouteBase>[
          GoRoute(
            path: '/dashboard',
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
            builder: (context, state) => const OrchestratorWorkspacePage(),
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
            builder: (context, state) => const ExternalProjectsPage(),
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
