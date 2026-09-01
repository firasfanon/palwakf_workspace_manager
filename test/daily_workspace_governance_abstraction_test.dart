import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/app/workspace_application_shell.dart';
import 'package:palwakf_workspace_manager/src/features/daily_workspace/application/daily_workspace_controller.dart';
import 'package:palwakf_workspace_manager/src/features/daily_workspace/presentation/advanced_operations_hub_page.dart';

void main() {
  test('daily navigation hides control-plane routes while preserving registry',
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

    expect(dailyRoutes, <String>['/home', '/projects', '/work', '/advanced']);
    expect(
      dailyLabels,
      <String>['الرئيسية', 'مشاريعي', 'أعمالي', 'الإدارة المتقدمة'],
    );
    expect(dailyRoutes, isNot(contains('/operations')));
    expect(dailyRoutes, isNot(contains('/tools')));
    expect(dailyRoutes, isNot(contains('/evidence')));
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

  test('friendly failures abstract governance exception codes', () {
    final message = DailyWorkspaceController.userMessageForFailure(
      'AUTHORIZED_WORKSPACE_WRITE_PRODUCED_NO_SOURCE_CHANGE',
    );

    expect(message, contains('لم ينتج عن المحاولة أي تعديل فعلي'));
    expect(message, isNot(contains('AUTHORIZED_WORKSPACE_WRITE')));
  });

  test('daily prompt preserves bounded authority language', () {
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
