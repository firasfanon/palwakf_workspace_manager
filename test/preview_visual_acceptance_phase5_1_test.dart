import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:palwakf_workspace_manager/src/app/workspace_application_shell.dart';
import 'package:palwakf_workspace_manager/src/core/presentation/preview_mode_ui.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/application/engineering_os_controller.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/data/engineering_os_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/domain/engineering_os_models.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/presentation/task_board_page.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/application/operational_authorization.dart';

class FailingPreviewEngineeringOsApi extends EngineeringOsApiClient {
  FailingPreviewEngineeringOsApi() : super(baseUrl: 'http://127.0.0.1:1');

  StateError _unavailable() =>
      StateError('PHASE5_1_PREVIEW_OPERATIONAL_ENDPOINT_UNAVAILABLE');

  @override
  Future<EngineeringOsSummary> summary() async => throw _unavailable();

  @override
  Future<List<EngineeringTask>> tasks() async => throw _unavailable();

  @override
  Future<List<ExtensionRecord>> extensions() async => throw _unavailable();
}

const previewAuthorization = OperationalAuthorizationContext(
  clientId: 'phase5-1-preview-test',
  scopes: <String>['tasks:read'],
  readOnly: true,
  canDispatch: false,
  canContinue: false,
  canCancel: false,
  canVerify: false,
  canProbeTools: false,
);

GoRouter buildRouter() {
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
              child: Text('PHASE5_1_PREVIEW_OPERATIONS_DESTINATION'),
            ),
          ),
        ],
      ),
    ],
  );
}

void main() {
  testWidgets(
    'preview unavailable renders a labelled non-operational capability sample',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final router = buildRouter();
      addTearDown(router.dispose);

      final container = ProviderContainer(
        overrides: <Override>[
          engineeringOsApiProvider.overrideWithValue(
            FailingPreviewEngineeringOsApi(),
          ),
          operationalAuthorizationProvider.overrideWith(
            (ref) async => previewAuthorization,
          ),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();

      expect(PreviewModeUi.isVisualPreview, isTrue);
      expect(tester.takeException(), isNull);

      expect(find.text('بيانات المهام غير متاحة'), findsOneWidget);
      expect(find.text('نموذج معاينة غير تشغيلي'), findsOneWidget);
      expect(
        find.text(
          'هذا المثال يعرض موضع وسلوك عناصر الواجهة فقط؛ لا يمثل مهمة أو حالة أو قيمة تشغيلية حقيقية.',
        ),
        findsOneWidget,
      );

      final state = container.read(engineeringOsControllerProvider);
      expect(state.summary, isNull);
      expect(state.tasks, isEmpty);
      expect(state.extensions, isEmpty);
      expect(state.error, isNotNull);

      final sample = find.byKey(
        const ValueKey<String>('engineering-task-preview-capability-sample'),
      );
      final bridge = find.byKey(
        const ValueKey<String>('preview-task-operations-capability-sample'),
      );
      expect(sample, findsOneWidget);
      expect(bridge, findsOneWidget);
      expect(find.text('مركز التشغيل'), findsOneWidget);

      await tester.tap(bridge);
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(
        find.text('PHASE5_1_PREVIEW_OPERATIONS_DESTINATION'),
        findsOneWidget,
      );
    },
    skip: !PreviewModeUi.isVisualPreview,
  );

  test('preview sample source cannot synthesize operational truth', () {
    final source = File(
      'lib/src/features/engineering_os/presentation/task_board_page.dart',
    ).readAsStringSync();

    final start =
        source.indexOf('class EngineeringTaskPreviewCapabilitySample');
    final end = source.indexOf('class _Header extends StatelessWidget', start);
    expect(start, greaterThanOrEqualTo(0));
    expect(end, greaterThan(start));

    final sample = source.substring(start, end);
    expect(sample, contains('نموذج معاينة غير تشغيلي'));
    expect(sample, contains("context.go('/operations')"));

    for (final forbidden in <String>[
      'EngineeringTask(',
      '.taskId',
      '.baseSha',
      '.status',
      'createTask(',
      'latestRemoteTaskSha',
      'remoteCheckpointedTasks',
    ]) {
      expect(sample, isNot(contains(forbidden)), reason: forbidden);
    }
  });
}
