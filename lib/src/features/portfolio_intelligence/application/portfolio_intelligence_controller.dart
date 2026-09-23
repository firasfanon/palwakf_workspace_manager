import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../orchestrator/application/orchestrator_controller.dart';
import '../data/portfolio_intelligence_api_client.dart';
import '../domain/portfolio_intelligence_models.dart';

final portfolioIntelligenceApiProvider =
    Provider<PortfolioIntelligenceApi>((ref) {
  return HttpPortfolioIntelligenceApi(
    bearerToken: ref.watch(orchestratorTokenProvider),
  );
});

final portfolioIntelligenceControllerProvider = StateNotifierProvider<
    PortfolioIntelligenceController, PortfolioIntelligenceState>((ref) {
  return PortfolioIntelligenceController(
    ref.watch(portfolioIntelligenceApiProvider),
  );
});

class PortfolioIntelligenceState {
  const PortfolioIntelligenceState({
    this.snapshot,
    this.loading = false,
    this.error,
  });

  final PortfolioCommandCenterSnapshot? snapshot;
  final bool loading;
  final String? error;

  PortfolioIntelligenceState copyWith({
    PortfolioCommandCenterSnapshot? snapshot,
    bool? loading,
    String? error,
    bool clearError = false,
  }) {
    return PortfolioIntelligenceState(
      snapshot: snapshot ?? this.snapshot,
      loading: loading ?? this.loading,
      error: clearError ? null : error ?? this.error,
    );
  }
}

class PortfolioIntelligenceController
    extends StateNotifier<PortfolioIntelligenceState> {
  PortfolioIntelligenceController(this._api)
      : super(const PortfolioIntelligenceState());

  final PortfolioIntelligenceApi _api;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final snapshot = await _api.overview();
      state = state.copyWith(snapshot: snapshot, loading: false);
    } on PortfolioIntelligenceApiException catch (error) {
      state = state.copyWith(loading: false, error: error.message);
    } on FormatException {
      state = state.copyWith(
        loading: false,
        error: 'بيانات Portfolio Intelligence لا تطابق العقد المتوقع.',
      );
    }
  }
}
