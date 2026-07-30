import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/projects/application/external_projects_controller.dart';
import 'package:palwakf_workspace_manager/src/features/projects/data/external_project_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/projects/domain/external_project_models.dart';
import 'package:palwakf_workspace_manager/src/features/projects/presentation/external_projects_page.dart';
import 'package:palwakf_workspace_manager/src/features/projects/presentation/project_reality_page.dart';

const project = ExternalProject(
  projectId: 'FIRASFANON_PAL_EYES',
  displayName: 'بعيون فلسطينية',
  repositoryFullName: 'firasfanon/Pal_Eyes',
  adapter: 'github_repository',
  status: 'probed',
  stack: <String>['Dart', 'Flutter'],
  blockers: <String>[],
  observedHead: 'c67ff5e28205aac57ff28e8b8120c3bac5de4488',
  defaultBranch: 'main',
  baselineFingerprint:
      'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
);

const sampleReality = ProjectReality(
  projectId: 'FIRASFANON_PAL_EYES',
  repositoryFullName: 'firasfanon/Pal_Eyes',
  defaultBranch: 'main',
  observedBranch: 'main',
  observedHead: 'c67ff5e28205aac57ff28e8b8120c3bac5de4488',
  driftStatus: 'BASELINE_CREATED',
  visibility: 'public',
  stack: <String>['Dart', 'Flutter'],
  packageManagers: <String>['pub'],
  toolchainVersions: <String, String>{'flutter': '>=3.38.0'},
  commands: <ProjectCommand>[
    ProjectCommand(
      command: 'flutter test',
      purpose: 'test',
      evidence: 'docs/11_LOCAL_RUN_AND_VALIDATION.md',
    ),
  ],
  ci: <ProjectCiReality>[],
  ciStatus: 'NOT_CONFIGURED',
  deployments: <ProjectDeploymentReality>[
    ProjectDeploymentReality(
      provider: 'vercel',
      status: 'NOT_DISCOVERED',
      evidence: 'read-only Vercel inventory',
    ),
  ],
  deploymentStatus: 'NOT_DISCOVERED',
  indicators: <String, bool>{'flutter': true, 'supabase': true},
  capabilityProfile: ProjectCapabilityProfile(
    version: 'PROJECT_CAPABILITY_PROFILE_V1',
    selected: <ProjectToolDecision>[
      ProjectToolDecision(
        adapterId: 'github_repository',
        disposition: 'selected',
        reason: 'Repository and CI reads are required.',
        evidence: <String>['github_api:read_only'],
      ),
    ],
    conditional: <ProjectToolDecision>[],
    excluded: <ProjectToolDecision>[],
    blocked: <ProjectToolDecision>[
      ProjectToolDecision(
        adapterId: 'supabase',
        disposition: 'blocked',
        reason: 'Task authority excludes all Supabase access.',
        evidence: <String>['task:SUPABASE_EXCLUDED'],
      ),
    ],
  ),
  candidates: <CandidateWorkItem>[
    CandidateWorkItem(
      rank: 1,
      candidateId: 'PAL_EYES_GIS_CANDIDATE_VALIDATION',
      title: 'التحقق من مدخلات مرشح GIS',
      rationale: 'الإجراء الحالي ينشئ إحداثيات مؤقتة.',
      acceptanceTest: 'ترفض الاختبارات الإحداثيات المؤقتة.',
      evidence: <String>['gis_review_screen.dart'],
      blocked: false,
    ),
  ],
  blockers: <String>[],
  baselineFingerprint:
      'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
  totalFiles: 291,
  scannedFiles: 291,
  secretRiskFileNames: <String>['.env.example'],
  ignoredSecretPolicyPresent: true,
);

class FakeExternalProjectApi implements ExternalProjectApi {
  FakeExternalProjectApi({this.failReality = false});

  final bool failReality;
  var prepareCalls = 0;

  @override
  Future<ExternalProject> intake(ProjectIntakeDraft draft) async => project;

  @override
  Future<List<ExternalProject>> listProjects() async =>
      const <ExternalProject>[project];

  @override
  Future<void> prepareTask(String projectId, String candidateId) async {
    prepareCalls += 1;
  }

  @override
  Future<ProjectReality> probe(String projectId) async => sampleReality;

  @override
  Future<ProjectReality> reality(String projectId) async {
    if (failReality) {
      throw const ExternalProjectApiException(
        'HTTP_404',
        'PROJECT_REALITY_NOT_PROBED',
      );
    }
    return sampleReality;
  }
}

Widget app(Widget child, FakeExternalProjectApi api) {
  return ProviderScope(
    overrides: <Override>[
      externalProjectApiProvider.overrideWithValue(api),
    ],
    child: MaterialApp(
      locale: const Locale('ar'),
      home: Directionality(textDirection: TextDirection.rtl, child: child),
    ),
  );
}

void main() {
  testWidgets('project intake and external registry render', (tester) async {
    final api = FakeExternalProjectApi();
    await tester.pumpWidget(app(const ExternalProjectsPage(), api));
    await tester.pumpAndSettle();

    expect(find.text('إدخال مشروع'), findsOneWidget);
    expect(find.text('بعيون فلسطينية'), findsWidgets);
    expect(find.text('firasfanon/Pal_Eyes'), findsWidgets);
    expect(find.text('READ_ONLY_ZERO_MUTATION'), findsOneWidget);
    expect(find.text('Supabase محظور'), findsOneWidget);
  });

  testWidgets('project reality renders drift, tools, and ranked candidate', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1000, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = FakeExternalProjectApi();
    await tester.pumpWidget(
      app(
        const ProjectRealityPage(projectId: 'FIRASFANON_PAL_EYES'),
        api,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('BASELINE_CREATED'), findsOneWidget);
    expect(find.text('flutter test'), findsOneWidget);
    expect(find.text('NOT_DISCOVERED'), findsWidgets);
    final scrollable = find.byType(Scrollable).last;
    await tester.scrollUntilVisible(
      find.text('supabase'),
      500,
      scrollable: scrollable,
    );
    expect(find.text('supabase'), findsOneWidget);
    expect(find.text('blocked'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('التحقق من مدخلات مرشح GIS'),
      500,
      scrollable: scrollable,
    );
    expect(find.text('التحقق من مدخلات مرشح GIS'), findsOneWidget);

    await tester.scrollUntilVisible(
      find.text('تجهيز غلاف مهمة'),
      300,
      scrollable: scrollable,
    );
    await tester.tap(find.text('تجهيز غلاف مهمة'));
    await tester.pumpAndSettle();
    expect(api.prepareCalls, 1);
    expect(find.text('تم تجهيز الغلاف فقط. لم يتم إرسال أي مهمة.'),
        findsOneWidget);
  });

  testWidgets('unprobed and blocked state offers a read-only probe', (
    tester,
  ) async {
    final api = FakeExternalProjectApi(failReality: true);
    await tester.pumpWidget(
      app(
        const ProjectRealityPage(projectId: 'FIRASFANON_PAL_EYES'),
        api,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('PROJECT_REALITY_NOT_PROBED'), findsOneWidget);
    expect(find.text('لم يُنشأ خط أساس للواقع بعد'), findsOneWidget);
    expect(find.text('ابدأ فحص القراءة'), findsOneWidget);
  });
}
