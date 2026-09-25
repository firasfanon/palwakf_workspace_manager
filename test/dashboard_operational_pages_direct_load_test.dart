import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/dashboard/application/dashboard_controller.dart';
import 'package:palwakf_workspace_manager/src/features/dashboard/data/dashboard_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/dashboard/domain/dashboard_models.dart';
import 'package:palwakf_workspace_manager/src/features/dashboard/presentation/operational_list_pages.dart';

class _FailingDashboardApi implements DashboardApi {
  int calls = 0;

  Future<T> _fail<T>() async {
    calls += 1;
    throw const DashboardApiException(
      'TEST_CONNECTION_FAILURE',
      'TEST_CONNECTION_FAILURE',
    );
  }

  @override
  Future<DashboardSummary> summary() => _fail<DashboardSummary>();

  @override
  Future<List<RecentActivity>> activity({int limit = 30}) =>
      _fail<List<RecentActivity>>();

  @override
  Future<List<OperationalAlert>> alerts() => _fail<List<OperationalAlert>>();

  @override
  Future<List<EvidenceIndexItem>> evidence({int limit = 50}) =>
      _fail<List<EvidenceIndexItem>>();
}

void main() {
  for (final entry in <(String, Widget Function())>[
    ('alerts', () => const OperationalAlertsPage()),
    ('evidence', () => const EvidenceIndexPage()),
    ('connections', () => const ConnectionsPage()),
  ]) {
    testWidgets('${entry.$1} page starts dashboard loading on direct entry',
        (tester) async {
      final api = _FailingDashboardApi();

      await tester.pumpWidget(
        ProviderScope(
          overrides: <Override>[
            dashboardApiProvider.overrideWithValue(api),
          ],
          child: MaterialApp(home: entry.$2()),
        ),
      );

      await tester.pumpAndSettle();

      expect(api.calls, 4);
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(find.text('TEST_CONNECTION_FAILURE'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
}
