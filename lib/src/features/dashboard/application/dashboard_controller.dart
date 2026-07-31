import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../orchestrator/application/orchestrator_controller.dart';
import '../data/dashboard_api_client.dart';
import '../domain/dashboard_models.dart';

final dashboardApiProvider = Provider<DashboardApi>((ref) {
  return HttpDashboardApi(
    bearerToken: ref.watch(orchestratorTokenProvider),
  );
});

final dashboardControllerProvider =
    StateNotifierProvider<DashboardController, DashboardState>((ref) {
  return DashboardController(ref.watch(dashboardApiProvider));
});

class DashboardState {
  const DashboardState({
    this.summary,
    this.activity = const <RecentActivity>[],
    this.alerts = const <OperationalAlert>[],
    this.evidence = const <EvidenceIndexItem>[],
    this.loading = false,
    this.error,
  });

  final DashboardSummary? summary;
  final List<RecentActivity> activity;
  final List<OperationalAlert> alerts;
  final List<EvidenceIndexItem> evidence;
  final bool loading;
  final String? error;

  DashboardState copyWith({
    DashboardSummary? summary,
    List<RecentActivity>? activity,
    List<OperationalAlert>? alerts,
    List<EvidenceIndexItem>? evidence,
    bool? loading,
    String? error,
    bool clearError = false,
  }) {
    return DashboardState(
      summary: summary ?? this.summary,
      activity: activity ?? this.activity,
      alerts: alerts ?? this.alerts,
      evidence: evidence ?? this.evidence,
      loading: loading ?? this.loading,
      error: clearError ? null : error ?? this.error,
    );
  }
}

class DashboardController extends StateNotifier<DashboardState> {
  DashboardController(this._api) : super(const DashboardState());

  final DashboardApi _api;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final values = await Future.wait<dynamic>(<Future<dynamic>>[
        _api.summary(),
        _api.activity(),
        _api.alerts(),
        _api.evidence(),
      ]);
      state = state.copyWith(
        summary: values[0] as DashboardSummary,
        activity: values[1] as List<RecentActivity>,
        alerts: values[2] as List<OperationalAlert>,
        evidence: values[3] as List<EvidenceIndexItem>,
        loading: false,
      );
    } on DashboardApiException catch (error) {
      state = state.copyWith(loading: false, error: error.message);
    } on FormatException {
      state = state.copyWith(
        loading: false,
        error: 'استجابت الخدمة ببيانات لا تطابق عقد لوحة العمليات.',
      );
    }
  }
}
