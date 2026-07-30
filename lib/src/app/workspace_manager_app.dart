import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/theme/palwakf_theme.dart';
import '../features/orchestrator/presentation/orchestrator_workspace_page.dart';
import '../features/orchestrator/presentation/tool_health_page.dart';
import '../features/projects/presentation/external_projects_page.dart';
import '../features/projects/presentation/project_reality_page.dart';

final workspaceRouterProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    initialLocation: '/',
    routes: <RouteBase>[
      GoRoute(
        path: '/',
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
      supportedLocales: const <Locale>[
        Locale('ar', 'PS'),
        Locale('en', 'US'),
      ],
      localizationsDelegates: const <LocalizationsDelegate<dynamic>>[
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: PalWakfTheme.light(),
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
