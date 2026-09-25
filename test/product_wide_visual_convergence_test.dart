import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/app/workspace_application_shell.dart';
import 'package:palwakf_workspace_manager/src/core/theme/palwakf_theme.dart';

void main() {
  test('canonical command center palette is owned by shared workspace theme',
      () {
    final theme = PalWakfTheme.dark();

    expect(theme.scaffoldBackgroundColor, PalWakfTheme.workspaceBg);
    expect(theme.colorScheme.primary, PalWakfTheme.workspaceTeal);
    expect(theme.colorScheme.secondary, PalWakfTheme.workspaceCyan);
    expect(theme.colorScheme.error, PalWakfTheme.workspaceRed);
  });

  test('one product shell owns portfolio daily and advanced navigation', () {
    expect(
      WorkspaceApplicationShell.portfolioDestinations.map((item) => item.route),
      containsAll(<String>[
        '/dashboard',
        '/portfolio/projects',
        '/portfolio/dependencies',
        '/portfolio/recommendations',
        '/portfolio/decisions',
      ]),
    );
    expect(
      WorkspaceApplicationShell.dailyDestinations.map((item) => item.route),
      containsAll(<String>['/home', '/overview', '/projects', '/work']),
    );
    expect(
      WorkspaceApplicationShell.advancedDestinations.map((item) => item.route),
      containsAll(<String>[
        '/advanced',
        '/tasks',
        '/operations',
        '/tools',
        '/alerts',
        '/evidence',
        '/settings/connections',
      ]),
    );
  });

  test('command center is embedded into the shared shell in production router',
      () {
    final router =
        File('lib/src/app/workspace_manager_app.dart').readAsStringSync();
    final shell =
        File('lib/src/app/workspace_application_shell.dart').readAsStringSync();
    final commandCenter = File(
      'lib/src/features/portfolio_intelligence/presentation/'
      'portfolio_command_center_page.dart',
    ).readAsStringSync();

    expect(router, contains('PortfolioCommandCenterPage(embedded: true)'));
    expect(shell, contains("'palwakf-unified-rtl-sidebar'"));
    expect(shell, contains("'palwakf-unified-command-header'"));
    expect(
      shell,
      isNot(contains(
        "if (location == '/dashboard' || location.startsWith('/portfolio/'))",
      )),
    );
    expect(commandCenter, contains('PalWakfTheme.workspaceBg'));
    expect(commandCenter, contains('desktop && !widget.embedded'));
  });
}
