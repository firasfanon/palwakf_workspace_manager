import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/app/workspace_application_shell.dart';
import 'package:palwakf_workspace_manager/src/features/daily_workspace/application/daily_workspace_controller.dart';
import 'package:palwakf_workspace_manager/src/features/daily_workspace/domain/user_workspace_insights.dart';
import 'package:palwakf_workspace_manager/src/features/daily_workspace/presentation/advanced_operations_hub_page.dart';
import 'package:palwakf_workspace_manager/src/features/daily_workspace/presentation/daily_workspace_home_page.dart';
import 'package:palwakf_workspace_manager/src/features/daily_workspace/presentation/user_dashboard_page.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/application/engineering_os_controller.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/data/engineering_os_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/domain/engineering_os_models.dart';

void main() {
  test('daily navigation includes user dashboard and keeps advanced secondary',
      () {
    final dailyRoutes = WorkspaceApplicationShell.dailyDestinations
        .map((item) => item.route)
        .toList(growable: false);
    final dailyLabels = WorkspaceApplicationShell.dailyDestinations
        .map((item) => item.label)
        .toList(growable: false);
    final advancedRoutes = WorkspaceApplicationShell.destinations
        .map((item) => item.route)
        .toSet();

    expect(
      dailyRoutes,
      <String>['/home', '/overview', '/projects', '/work'],
    );
    expect(
      dailyLabels,
      <String>['الرئيسية', 'لوحة التحكم', 'مشاريعي', 'أعمالي'],
    );
    expect(dailyRoutes, isNot(contains('/advanced')));
    expect(dailyRoutes, isNot(contains('/operations')));
    expect(dailyRoutes, isNot(contains('/tools')));
    expect(advancedRoutes, contains('/tasks'));
    expect(advancedRoutes, contains('/operations'));
    expect(advancedRoutes, contains('/tools'));
  });

  test('router starts on home and includes user dashboard plus advanced routes',
      () {
    final source =
        File('lib/src/app/workspace_manager_app.dart').readAsStringSync();

    expect(source, contains("initialLocation: '/home'"));
    expect(source, contains("redirect: (_, __) => '/home'"));
    expect(source, contains("path: '/overview'"));
    expect(source, contains('UserWorkspaceDashboardPage'));
    for (final route in <String>[
      '/advanced',
      '/dashboard',
      '/tasks',
      '/operations',
      '/tools',
      '/alerts',
      '/evidence',
      '/settings/connections',
    ]) {
      expect(source, contains("path: '$route'"), reason: 'Missing $route');
    }
  });

  test('user dashboard insights derive only from registered engineering tasks',
      () {
    final insights = UserWorkspaceInsights.fromTasks(<EngineeringTask>[
      _task(
        taskId: 'ACTIVE',
        title: 'Active work',
        projectId: 'PALWAKF_WORKSPACE_MANAGER',
        status: 'WIP_REMOTE_CHECKPOINTED',
      ),
      _task(
        taskId: 'ATTENTION',
        title: 'Needs review',
        projectId: 'PALWAKF_WORKSPACE_MANAGER',
        status: 'IN_REVIEW',
      ),
      _task(
        taskId: 'DONE',
        title: 'Done',
        projectId: 'MANASIKUNA_APP',
        status: 'INTEGRATED',
        integrationStatus: 'INTEGRATED',
      ),
    ]);

    expect(insights.projectCount, 2);
    expect(insights.activeWorkCount, 2);
    expect(insights.attentionCount, 1);
    expect(insights.completedCount, 1);
    expect(insights.primarySuggestion, isNotNull);
    expect(insights.primarySuggestion!.task.taskId, 'ATTENTION');
  });

  test('home productization exposes command center and quick actions', () {
    final source = File(
      'lib/src/features/daily_workspace/presentation/'
      'daily_workspace_home_page.dart',
    ).readAsStringSync();

    expect(source, contains('workspace-command-center'));
    expect(source, contains('ماذا تريد أن تنجز اليوم؟'));
    expect(source, contains('اقتراحات سريعة'));
    expect(source, contains('استكمل من حيث توقفت'));
    expect(source, contains('workspace-smart-suggestion'));
    expect(source, contains('BoxConstraints(maxWidth: 1380)'));
  });

  test('dashboard is user-facing and does not import governance runtime', () {
    final source = File(
      'lib/src/features/daily_workspace/presentation/'
      'user_dashboard_page.dart',
    ).readAsStringSync();

    expect(source, contains('لوحة التحكم'));
    expect(source, contains('نشاط المشاريع'));
    expect(source, contains('تحتاج انتباهك'));
    expect(source, contains('أعمال قيد المتابعة'));
    expect(source, contains('يقترح عليك Workspace'));
    expect(source, isNot(contains('orchestrator_api_client')));
    expect(source, isNot(contains('ToolPlan')));
    expect(source, isNot(contains('provider=')));
    expect(source, isNot(contains('Provider:')));
    expect(source, isNot(contains('Codex')));
    expect(source, isNot(contains('Tool Plan')));
  });

  testWidgets('productized home and dashboard render cleanly at desktop width',
      (tester) async {
    tester.view.physicalSize = const Size(1440, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          engineeringOsApiProvider.overrideWithValue(_FakeProductizationApi()),
        ],
        child: const MaterialApp(
          home: Scaffold(
            body: Directionality(
              textDirection: TextDirection.rtl,
              child: DailyWorkspaceHomePage(),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey<String>('workspace-command-center')),
        findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          engineeringOsApiProvider.overrideWithValue(_FakeProductizationApi()),
        ],
        child: const MaterialApp(
          home: Scaffold(
            body: Directionality(
              textDirection: TextDirection.rtl,
              child: UserWorkspaceDashboardPage(),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey<String>('user-workspace-dashboard')),
        findsOneWidget);
    expect(find.text('نشاط المشاريع'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  test('natural-language intent infers common daily work kinds', () {
    expect(
      DailyWorkspaceController.inferKind(
        'أصلح مشكلة شاشة المشاريع وشغل الاختبارات',
      ),
      DailyWorkKind.fix,
    );
    expect(
      DailyWorkspaceController.inferKind('راجع الكود الحالي فقط'),
      DailyWorkKind.review,
    );
    expect(
      DailyWorkspaceController.inferKind('حلل سبب الخلل ولا تعدل شيئا'),
      DailyWorkKind.analysis,
    );
    expect(
      DailyWorkspaceController.inferKind('طور الصفحة واضف التحسين الجديد'),
      DailyWorkKind.development,
    );
    expect(
      DailyWorkspaceController.inferKind(
        'راجع الخطأ الحالي دون تعديل أي ملف',
      ),
      DailyWorkKind.review,
    );
    expect(
      DailyWorkspaceController.inferKind(
        'افحص المشكلة فقط ولا تغير شيئا',
      ),
      DailyWorkKind.analysis,
    );
  });

  test('technical task identity is hidden behind a friendly work title', () {
    final task = _task(
      taskId: 'WM_PROVIDER_BOUNDED_WRITE_PROOF_V1',
      title: 'Governed Provider Bounded Write Proof',
      projectId: 'PALWAKF_WORKSPACE_MANAGER',
      status: 'WIP_REMOTE_CHECKPOINTED',
    );

    expect(
      DailyWorkspaceController.friendlyTaskTitle(task),
      'التحقق من التنفيذ الآمن داخل المشروع',
    );
    expect(
      DailyWorkspaceController.friendlyTaskTitle(task),
      isNot(contains('Provider')),
    );
    expect(
      DailyWorkspaceController.friendlyProjectLabel(task.projectId),
      'مساحة عمل PalWakf',
    );
  });

  test('confirmation explains user effect without exposing governance terms',
      () {
    final preview = DailyIntentPreview(
      task: _task(
        taskId: 'WM_PROVIDER_BOUNDED_WRITE_PROOF_V1',
        title: 'Governed Provider Bounded Write Proof',
        projectId: 'PALWAKF_WORKSPACE_MANAGER',
        status: 'WIP_REMOTE_CHECKPOINTED',
      ),
      kind: DailyWorkKind.fix,
    );

    expect(preview.confirmationText, contains('مساحة عمل PalWakf'));
    expect(preview.confirmationText, contains('لن يتم نشر أو دمج'));
    expect(preview.confirmationText, isNot(contains('Provider')));
    expect(preview.confirmationText, isNot(contains('SHA')));
    expect(preview.confirmationText, isNot(contains('branch')));
  });

  test('friendly failures abstract governance exception codes', () {
    final message = DailyWorkspaceController.userMessageForFailure(
      'AUTHORIZED_WORKSPACE_WRITE_PRODUCED_NO_SOURCE_CHANGE',
    );

    expect(message, contains('لم ينتج عن المحاولة أي تعديل فعلي'));
    expect(message, isNot(contains('AUTHORIZED_WORKSPACE_WRITE')));
  });

  test('daily prompt preserves bounded authority in the hidden layer', () {
    final prompt = DailyWorkspaceController.buildGovernedPrompt(
      'أصلح الخلل الحالي',
      DailyWorkKind.fix,
    );

    expect(prompt, contains('أصلح الخلل الحالي'));
    expect(prompt, contains('داخل صلاحية ونطاق المهمة الأب'));
    expect(prompt, contains('لا توسّع النطاق'));
  });

  testWidgets('advanced hub keeps technical surfaces reachable',
      (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: AdvancedOperationsHubPage()),
    );

    expect(find.text('الإدارة المتقدمة'), findsOneWidget);
    expect(find.text('لوحة العمليات'), findsOneWidget);
    expect(find.text('المهام الهندسية'), findsOneWidget);
    expect(find.text('مركز التشغيل'), findsOneWidget);
    expect(find.text('الأدوات'), findsOneWidget);
    expect(find.text('الأدلة'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

EngineeringTask _task({
  required String taskId,
  required String title,
  required String projectId,
  required String status,
  String integrationStatus = 'NOT_INTEGRATED',
}) {
  return EngineeringTask(
    taskId: taskId,
    title: title,
    description: 'technical description',
    projectId: projectId,
    repository: 'firasfanon/palwakf_workspace_manager',
    baseSha: 'base',
    taskBranch: 'task/example',
    ownerId: 'owner',
    actorId: 'actor',
    actorType: 'HUMAN',
    status: status,
    scopePatterns: const <String>['lib/**'],
    dependsOn: const <String>[],
    dependencyMode: 'INDEPENDENT',
    riskClass: 'MEDIUM',
    mutationClass: 'source-write',
    requiredCapabilities: const <String>[],
    requiredTests: const <String>[],
    wipCheckpointStatus: 'REMOTE_CHECKPOINTED',
    integrationStatus: integrationStatus,
    latestRemoteTaskSha: 'head',
  );
}

class _FakeProductizationApi extends EngineeringOsApiClient {
  _FakeProductizationApi() : super(baseUrl: 'http://127.0.0.1:1');

  @override
  Future<List<EngineeringTask>> tasks() async => <EngineeringTask>[
        _task(
          taskId: 'WM_PRODUCT_HOME_ACTIVE',
          title: 'تحسين مساحة العمل اليومية',
          projectId: 'PALWAKF_WORKSPACE_MANAGER',
          status: 'WIP_REMOTE_CHECKPOINTED',
        ),
        _task(
          taskId: 'WM_PRODUCT_HOME_REVIEW',
          title: 'مراجعة واجهة المستخدم',
          projectId: 'PALWAKF_WORKSPACE_MANAGER',
          status: 'IN_REVIEW',
        ),
      ];
}
