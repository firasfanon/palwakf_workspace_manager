import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('functional convergence routes and refresh contract are wired', () {
    final router = File(
      'lib/src/app/workspace_manager_app.dart',
    ).readAsStringSync();

    final page = File(
      'lib/src/features/portfolio_intelligence/'
      'presentation/portfolio_command_center_page.dart',
    ).readAsStringSync();

    final controller = File(
      'lib/src/features/portfolio_intelligence/'
      'application/portfolio_intelligence_controller.dart',
    ).readAsStringSync();

    const routes = <String>[
      '/portfolio/projects',
      '/portfolio/timeline',
      '/portfolio/programs',
      '/portfolio/dependencies',
      '/portfolio/capabilities',
      '/portfolio/agents',
      '/portfolio/intelligence',
      '/portfolio/waqf',
      '/portfolio/hajj-umrah',
      '/portfolio/gis',
      '/portfolio/reports',
      '/portfolio/recommendations',
      '/portfolio/decisions',
      '/portfolio/activity',
      '/portfolio/projects/:projectId',
    ];

    for (final route in routes) {
      expect(
        router,
        contains(route),
      );
    }

    expect(
      controller,
      contains('Timer.periodic'),
    );

    expect(
      controller,
      contains('startAutoRefresh'),
    );

    expect(
      page,
      contains(
        'FINAL_COMMAND_CENTER_FUNCTIONAL_CONVERGENCE_V1',
      ),
    );

    expect(
      page,
      contains(
        '/portfolio/projects/',
      ),
    );
  });
}
