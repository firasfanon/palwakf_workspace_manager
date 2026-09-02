import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/app/workspace_application_shell.dart';
import 'package:palwakf_workspace_manager/src/features/daily_workspace/application/daily_workspace_controller.dart';
import 'package:palwakf_workspace_manager/src/features/daily_workspace/presentation/advanced_operations_hub_page.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/domain/engineering_os_models.dart';

void main() {
  test('daily navigation is user-first and advanced remains secondary', () {
    final dailyRoutes = WorkspaceApplicationShell.dailyDestinations
        .map((item) => item.route)
        .toList(growable: false);
    final dailyLabels = WorkspaceApplicationShell.dailyDestinations
        .map((item) => item.label)
        .toList(growable: false);
    final advancedRoutes = WorkspaceApplicationShell.destinations
        .map((item) => item.route)
        .toSet();

    expect(dailyRoutes, <String>['/home', '/projects', '/work']);
    expect(dailyLabels, <String>['الرئيسية', 'مشاريعي', 'أعمالي']);
    expect(dailyRoutes, isNot(contains('/advanced')));
    expect(dailyRoutes, isNot(contains('/operations')));
    expect(dailyRoutes, isNot(contains('/tools')));
    expect(advancedRoutes, contains('/tasks'));
    expect(advancedRoutes, contains('/operations'));
    expect(advancedRoutes, contains('/tools'));
  });

  test('router starts on the daily home and preserves advanced routes', () {
    final source =
        File('lib/src/app/workspace_manager_app.dart').readAsStringSync();

    expect(source, contains("initialLocation: '/home'"));
    expect(source, contains("redirect: (_, __) => '/home'"));
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
}) {
  return EngineeringTask(
    taskId: taskId,
    title: title,
    description: 'technical description',
    projectId: 'PALWAKF_WORKSPACE_MANAGER',
    repository: 'firasfanon/palwakf_workspace_manager',
    baseSha: 'base',
    taskBranch: 'task/example',
    ownerId: 'owner',
    actorId: 'actor',
    actorType: 'HUMAN',
    status: 'WIP_REMOTE_CHECKPOINTED',
    scopePatterns: const <String>['lib/**'],
    dependsOn: const <String>[],
    dependencyMode: 'INDEPENDENT',
    riskClass: 'MEDIUM',
    mutationClass: 'source-write',
    requiredCapabilities: const <String>[],
    requiredTests: const <String>[],
    wipCheckpointStatus: 'REMOTE_CHECKPOINTED',
    integrationStatus: 'NOT_INTEGRATED',
    latestRemoteTaskSha: 'head',
  );
}
