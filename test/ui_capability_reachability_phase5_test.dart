import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:palwakf_workspace_manager/src/app/workspace_application_shell.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/application/engineering_os_controller.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/data/engineering_os_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/domain/engineering_os_models.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/presentation/task_board_page.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/application/operational_authorization.dart';

class FakePhase5EngineeringOsApi extends EngineeringOsApiClient {
  FakePhase5EngineeringOsApi() : super(baseUrl: 'http://127.0.0.1:1');

  @override
  Future<EngineeringOsSummary> summary() async {
    return const EngineeringOsSummary(
      parallelTracks: <String>[],
      tasksByStatus: <String, int>{'READY': 1},
      extensionsByKind: <String, int>{},
      quarantinedExtensions: 0,
      remoteCheckpointedTasks: 0,
    );
  }

  @override
  Future<List<EngineeringTask>> tasks() async {
    return const <EngineeringTask>[
      EngineeringTask(
        taskId: 'WM-PHASE5-UI-REACHABILITY',
        title: 'حفظ الوصول إلى مركز التشغيل',
        projectId: 'PALWAKF_WORKSPACE_MANAGER',
        repository: 'firasfanon/palwakf_workspace_manager',
        baseSha: '569cfea700bb027e9452a84933ad3f5ef101037b',
        taskBranch: 'task/WM-UI-CAPABILITY-REACHABILITY-PRESERVATION-PHASE5-V1',
        ownerId: 'firas',
        actorId: 'firas',
        actorType: 'HUMAN',
        status: 'READY',
        scopePatterns: <String>['lib/**'],
        dependsOn: <String>[],
        dependencyMode: 'INDEPENDENT',
        riskClass: 'MEDIUM',
        wipCheckpointStatus: 'NOT_CHECKPOINTED',
        integrationStatus: 'NOT_READY',
      ),
    ];
  }

  @override
  Future<List<ExtensionRecord>> extensions() async => const <ExtensionRecord>[];
}

const phase5Authorization = OperationalAuthorizationContext(
  clientId: 'phase5-test',
  scopes: <String>['tasks:read'],
  readOnly: true,
  canDispatch: false,
  canContinue: false,
  canCancel: false,
  canVerify: false,
  canProbeTools: false,
);

GoRouter buildPhase5Router() {
  return GoRouter(
    initialLocation: '/tasks',
    routes: <RouteBase>[
      ShellRoute(
        builder: (context, state, child) => WorkspaceApplicationShell(
          location: state.uri.path,
          child: child,
        ),
        routes: <RouteBase>[
          GoRoute(
            path: '/tasks',
            builder: (context, state) => const EngineeringTaskBoardPage(),
          ),
          GoRoute(
            path: '/operations',
            builder: (context, state) => const Center(
              child: Text('PHASE5_OPERATIONS_DESTINATION'),
            ),
          ),
        ],
      ),
    ],
  );
}

void main() {
  testWidgets(
    'CPM-18 engineering task reaches existing operations center additively',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final router = buildPhase5Router();
      addTearDown(router.dispose);

      await tester.pumpWidget(
        ProviderScope(
          overrides: <Override>[
            engineeringOsApiProvider.overrideWithValue(
              FakePhase5EngineeringOsApi(),
            ),
            operationalAuthorizationProvider.overrideWith(
              (ref) async => phase5Authorization,
            ),
          ],
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        tester.takeException(),
        isNull,
        reason:
            'The production-shell-equivalent /tasks surface must render cleanly.',
      );
      expect(find.byType(WorkspaceApplicationShell), findsOneWidget);
      expect(find.byType(Scaffold), findsOneWidget);
      expect(find.text('لوحة المهام الهندسية'), findsOneWidget);
      expect(find.text('حفظ الوصول إلى مركز التشغيل'), findsOneWidget);

      final bridge = find.byKey(
        const ValueKey<String>(
          'engineering-task-operations-WM-PHASE5-UI-REACHABILITY',
        ),
      );
      expect(bridge, findsOneWidget);
      expect(find.text('مركز التشغيل'), findsOneWidget);

      await tester.ensureVisible(bridge);
      await tester.tap(bridge);
      await tester.pumpAndSettle();

      expect(
        tester.takeException(),
        isNull,
        reason:
            'Task-to-operations navigation must not introduce Flutter errors.',
      );
      expect(find.text('PHASE5_OPERATIONS_DESTINATION'), findsOneWidget);
    },
  );

  testWidgets(
    'CPM-18 task board horizontal scrollbar owns an attached controller',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final router = buildPhase5Router();
      addTearDown(router.dispose);

      await tester.pumpWidget(
        ProviderScope(
          overrides: <Override>[
            engineeringOsApiProvider.overrideWithValue(
              FakePhase5EngineeringOsApi(),
            ),
            operationalAuthorizationProvider.overrideWith(
              (ref) async => phase5Authorization,
            ),
          ],
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      final scrollbar = tester.widget<Scrollbar>(find.byType(Scrollbar));
      expect(scrollbar.controller, isNotNull);
      expect(scrollbar.thumbVisibility, isTrue);

      final horizontalScrollView = tester
          .widgetList<SingleChildScrollView>(find.byType(SingleChildScrollView))
          .firstWhere((view) => view.scrollDirection == Axis.horizontal);
      expect(horizontalScrollView.controller, same(scrollbar.controller));
    },
  );

  test('CPM-18 shell keeps tasks and operations destinations', () {
    final routes = WorkspaceApplicationShell.destinations
        .map((destination) => destination.route)
        .toSet();

    expect(routes, contains('/tasks'));
    expect(routes, contains('/operations'));
  });

  test('CPM-18 router keeps both legacy UI routes', () {
    final source = File(
      'lib/src/app/workspace_manager_app.dart',
    ).readAsStringSync();

    expect(source, contains("path: '/tasks'"));
    expect(source, contains("path: '/operations'"));
    expect(source, contains('EngineeringTaskBoardPage'));
    expect(source, contains('OrchestratorWorkspacePage'));
  });

  test('CPM-18 advanced operator capability surface remains reachable', () {
    final source = File(
      'lib/src/features/orchestrator/presentation/'
      'orchestrator_workspace_page.dart',
    ).readAsStringSync();

    for (final label in <String>[
      'صف المهام',
      'خطة الأدوات',
      'الترحيل',
      'الأحداث',
      'إرسال',
      'تفويض التنفيذ',
      'متابعة',
      'إلغاء',
      'تحقق مستقل',
      'إنشاء خطة الأدوات',
      'إنشاء الحزمة',
      'تم الترحيل',
      'تسجيل إقرار التنفيذ الخارجي',
      'استيراد النتيجة',
    ]) {
      expect(source, contains(label),
          reason: 'Missing capability label: $label');
    }
  });
}
