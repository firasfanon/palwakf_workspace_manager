import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/domain/engineering_os_models.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/application/operational_authorization.dart';
import 'package:palwakf_workspace_manager/src/features/projects/application/external_projects_controller.dart';
import 'package:palwakf_workspace_manager/src/features/projects/data/external_project_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/projects/data/project_task_bridge_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/projects/domain/external_project_models.dart';
import 'package:palwakf_workspace_manager/src/features/projects/presentation/project_reality_page.dart';

const authorization = OperationalAuthorizationContext(
  clientId: 'candidate-task-bridge-test',
  scopes: <String>[
    'tasks:read',
    'tasks:dispatch',
    'tools:probe',
  ],
  readOnly: false,
  canDispatch: true,
  canContinue: false,
  canCancel: false,
  canVerify: false,
  canProbeTools: true,
);

const projectReality = ProjectReality(
  projectId: 'FIRASFANON_PAL_EYES',
  repositoryFullName: 'firasfanon/Pal_Eyes',
  defaultBranch: 'main',
  observedBranch: 'main',
  observedHead: 'c67ff5e28205aac57ff28e8b8120c3bac5de4488',
  driftStatus: 'UNCHANGED',
  visibility: 'public',
  stack: <String>['Dart', 'Flutter'],
  packageManagers: <String>['pub'],
  toolchainVersions: <String, String>{},
  commands: <ProjectCommand>[],
  ci: <ProjectCiReality>[],
  ciStatus: 'NOT_CONFIGURED',
  deployments: <ProjectDeploymentReality>[],
  deploymentStatus: 'NOT_DISCOVERED',
  indicators: <String, bool>{},
  capabilityProfile: ProjectCapabilityProfile(
    version: 'PROJECT_CAPABILITY_PROFILE_V1',
    selected: <ProjectToolDecision>[],
    conditional: <ProjectToolDecision>[],
    excluded: <ProjectToolDecision>[],
    blocked: <ProjectToolDecision>[],
  ),
  candidates: <CandidateWorkItem>[
    CandidateWorkItem(
      rank: 1,
      candidateId: 'PAL_EYES_GIS_CANDIDATE_VALIDATION',
      title: 'التحقق من مدخلات مرشح GIS',
      rationale: 'الإجراء الحالي يحتاج مهمة تشغيلية حقيقية.',
      acceptanceTest: 'تظهر المهمة في Engineering OS وتفتح مركز التشغيل.',
      evidence: <String>['gis_review_screen.dart'],
      blocked: false,
    ),
  ],
  blockers: <String>[],
  baselineFingerprint:
      'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
  totalFiles: 100,
  scannedFiles: 100,
  secretRiskFileNames: <String>[],
  ignoredSecretPolicyPresent: true,
);

class FakeProjectApi implements ExternalProjectApi {
  @override
  Future<ExternalProject> intake(ProjectIntakeDraft draft) =>
      throw UnimplementedError();

  @override
  Future<List<ExternalProject>> listProjects() async =>
      const <ExternalProject>[];

  @override
  Future<void> prepareTask(String projectId, String candidateId) async {}

  @override
  Future<ProjectReality> probe(String projectId) async => projectReality;

  @override
  Future<ProjectReality> reality(String projectId) async => projectReality;
}

class FakeBridgeApi implements ProjectTaskBridgeApi {
  var calls = 0;
  ProjectCandidateEngineeringTaskDraft? lastDraft;

  @override
  Future<EngineeringTask> createEngineeringTask(
    String projectId,
    String candidateId,
    ProjectCandidateEngineeringTaskDraft draft,
  ) async {
    calls += 1;
    lastDraft = draft;
    return const EngineeringTask(
      taskId: 'PAL_EYES_GIS_CANDIDATE_VALIDATION',
      title: 'التحقق من مدخلات مرشح GIS',
      description: 'server-derived',
      projectId: 'FIRASFANON_PAL_EYES',
      repository: 'firasfanon/Pal_Eyes',
      baseSha: 'c67ff5e28205aac57ff28e8b8120c3bac5de4488',
      taskBranch: 'task/PAL_EYES_GIS_CANDIDATE_VALIDATION',
      ownerId: 'firas',
      actorId: 'firas',
      actorType: 'HUMAN',
      status: 'READY',
      scopePatterns: <String>['lib/**', 'test/**'],
      dependsOn: <String>[],
      dependencyMode: 'INDEPENDENT',
      riskClass: 'MEDIUM',
      wipCheckpointStatus: 'NOT_CHECKPOINTED',
      integrationStatus: 'NOT_READY',
    );
  }
}

void main() {
  testWidgets(
    'project candidate becomes a governed task and opens task-scoped operations',
    (tester) async {
      tester.view.physicalSize = const Size(1100, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final bridge = FakeBridgeApi();
      final router = GoRouter(
        initialLocation: '/project',
        routes: <RouteBase>[
          GoRoute(
            path: '/project',
            builder: (context, state) => const Scaffold(
              body: ProjectRealityPage(
                projectId: 'FIRASFANON_PAL_EYES',
              ),
            ),
          ),
          GoRoute(
            path: '/operations',
            builder: (context, state) => Scaffold(
              body: Text(
                'OPS:${state.uri.queryParameters['engineeringTaskId']}',
              ),
            ),
          ),
        ],
      );
      addTearDown(router.dispose);

      await tester.pumpWidget(
        ProviderScope(
          overrides: <Override>[
            externalProjectApiProvider.overrideWithValue(FakeProjectApi()),
            projectTaskBridgeApiProvider.overrideWithValue(bridge),
            operationalAuthorizationProvider.overrideWith(
              (ref) async => authorization,
            ),
          ],
          child: MaterialApp.router(
            locale: const Locale('ar'),
            routerConfig: router,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('العمل المرشح'));
      await tester.pumpAndSettle();

      final create = find.text('إنشاء مهمة تشغيلية');
      await tester.scrollUntilVisible(
        create,
        250,
        scrollable: find.byType(Scrollable).last,
      );
      await tester.tap(create);
      await tester.pumpAndSettle();

      expect(find.text('إنشاء مهمة تشغيلية من المرشح'), findsOneWidget);
      expect(find.text('firasfanon/Pal_Eyes'), findsWidgets);
      expect(
        find.text('c67ff5e28205aac57ff28e8b8120c3bac5de4488'),
        findsWidgets,
      );
      expect(
        find.text('task/PAL_EYES_GIS_CANDIDATE_VALIDATION'),
        findsOneWidget,
      );

      await tester.tap(find.text('إنشاء المهمة'));
      await tester.pumpAndSettle();

      expect(bridge.calls, 1);
      expect(
        bridge.lastDraft?.scopePatterns,
        <String>['lib/**', 'test/**'],
      );
      expect(
        find.text('OPS:PAL_EYES_GIS_CANDIDATE_VALIDATION'),
        findsOneWidget,
      );
    },
  );
}
