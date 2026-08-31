import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/application/engineering_os_controller.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/data/engineering_os_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/domain/engineering_os_models.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/presentation/task_board_page.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/application/operational_authorization.dart';

const integratedHead = 'c801289e0d1084d06e4df1e8a9426ed604f4e861';
const remoteHead = '11c0d9dd3b7a7b2b76cb5ac10e5a929aa322a373';

EngineeringTask task(String id, String title, {String? latestRemoteTaskSha}) {
  return EngineeringTask(
    taskId: id,
    title: title,
    projectId: 'PALWAKF_WORKSPACE_MANAGER',
    repository: 'firasfanon/palwakf_workspace_manager',
    baseSha: integratedHead,
    taskBranch: 'task/WM-CONTROL-PLANE-MEGA-BATCH-V1',
    ownerId: 'firas',
    actorId: 'firas',
    actorType: 'HUMAN',
    status: latestRemoteTaskSha == null ? 'READY' : 'WIP_REMOTE_CHECKPOINTED',
    scopePatterns: const <String>[
      'orchestrator/src/palwakf_orchestrator/gateways.py',
    ],
    dependsOn: const <String>[],
    dependencyMode: 'INDEPENDENT',
    riskClass: 'MEDIUM',
    wipCheckpointStatus: latestRemoteTaskSha == null
        ? 'NOT_CHECKPOINTED'
        : 'REMOTE_CHECKPOINTED',
    integrationStatus: 'NOT_READY',
    latestRemoteTaskSha: latestRemoteTaskSha,
  );
}

class FakeRemoteWipApi extends EngineeringOsApiClient {
  FakeRemoteWipApi() : super(baseUrl: 'http://127.0.0.1:1');

  final List<String> syncCalls = <String>[];
  late List<EngineeringTask> records = <EngineeringTask>[
    task('WM-READY-ONE', 'Ready task one'),
    task('WM-READY-TWO', 'Ready task two'),
    task('WM_PROVIDER_BOUNDED_WRITE_PROOF_V1',
        'Governed provider bounded write proof'),
  ];

  @override
  Future<EngineeringOsSummary> summary() async {
    final checkpointed = records
        .where((item) => item.wipCheckpointStatus == 'REMOTE_CHECKPOINTED')
        .length;
    return EngineeringOsSummary(
      parallelTracks: const <String>[],
      tasksByStatus: <String, int>{'READY': records.length - checkpointed},
      extensionsByKind: const <String, int>{},
      quarantinedExtensions: 0,
      remoteCheckpointedTasks: checkpointed,
    );
  }

  @override
  Future<List<EngineeringTask>> tasks() async =>
      List<EngineeringTask>.from(records);

  @override
  Future<List<ExtensionRecord>> extensions() async => const <ExtensionRecord>[];

  @override
  Future<EngineeringTask> syncRemoteCheckpoint(String engineeringTaskId) async {
    syncCalls.add(engineeringTaskId);
    final current =
        records.firstWhere((item) => item.taskId == engineeringTaskId);
    final updated = task(
      current.taskId,
      current.title,
      latestRemoteTaskSha: remoteHead,
    );
    records = <EngineeringTask>[
      for (final item in records)
        if (item.taskId == engineeringTaskId) updated else item,
    ];
    return updated;
  }
}

const authorization = OperationalAuthorizationContext(
  clientId: 'task-board-fix-test',
  scopes: <String>['tasks:read', 'tasks:dispatch'],
  readOnly: false,
  canDispatch: true,
  canContinue: false,
  canCancel: false,
  canVerify: false,
  canProbeTools: false,
);

void main() {
  testWidgets(
    'task board vertically reaches lower cards and syncs verified remote WIP',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final api = FakeRemoteWipApi();
      await tester.pumpWidget(
        ProviderScope(
          overrides: <Override>[
            engineeringOsApiProvider.overrideWithValue(api),
            operationalAuthorizationProvider.overrideWith(
              (ref) async => authorization,
            ),
          ],
          child: const MaterialApp(
            home: Scaffold(body: EngineeringTaskBoardPage()),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      final vertical = find.byKey(
        const ValueKey<String>('engineering-task-board-vertical-scroll'),
      );
      expect(vertical, findsOneWidget);
      final verticalView = tester.widget<SingleChildScrollView>(vertical);
      expect(verticalView.scrollDirection, Axis.vertical);
      expect(verticalView.controller, isNotNull);
      expect(verticalView.controller!.position.maxScrollExtent, greaterThan(0));

      final target = find.byKey(
        const ValueKey<String>(
          'engineering-task-sync-wip-WM_PROVIDER_BOUNDED_WRITE_PROOF_V1',
        ),
      );
      expect(target, findsOneWidget);

      await tester.ensureVisible(target);
      await tester.pumpAndSettle();
      expect(verticalView.controller!.offset, greaterThan(0));

      await tester.tap(target);
      await tester.pumpAndSettle();

      expect(api.syncCalls, <String>['WM_PROVIDER_BOUNDED_WRITE_PROOF_V1']);
      expect(find.textContaining('تم التحقق من WIP البعيد ومزامنته'),
          findsOneWidget);
      expect(find.text('REMOTE_CHECKPOINTED'), findsWidgets);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('human parent task form rejects provider binding',
      (tester) async {
    tester.view.physicalSize = const Size(1280, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final api = FakeRemoteWipApi();
    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          engineeringOsApiProvider.overrideWithValue(api),
          operationalAuthorizationProvider.overrideWith(
            (ref) async => authorization,
          ),
        ],
        child: const MaterialApp(
          home: Scaffold(body: EngineeringTaskBoardPage()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('مهمة جديدة'));
    await tester.pumpAndSettle();

    final providerField =
        find.widgetWithText(TextFormField, 'Provider ID (اختياري)');
    expect(providerField, findsOneWidget);
    await tester.enterText(providerField, 'codex');
    await tester.tap(find.text('إنشاء'));
    await tester.pump();

    expect(
      find.text('المهمة البشرية لا ترتبط بمزود؛ اترك الحقل فارغًا.'),
      findsOneWidget,
    );
  });
}
