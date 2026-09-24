import 'dart:async';

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

  Timer? _refreshTimer;
  bool _requestInFlight = false;
  int _refreshLeaseCount = 0;

  void startAutoRefresh({
    Duration interval = const Duration(seconds: 30),
  }) {
    _refreshLeaseCount += 1;

    _refreshTimer ??= Timer.periodic(
      interval,
      (_) => unawaited(load(silent: true)),
    );
  }

  void stopAutoRefresh() {
    if (_refreshLeaseCount > 0) {
      _refreshLeaseCount -= 1;
    }

    if (_refreshLeaseCount > 0) {
      return;
    }

    _refreshTimer?.cancel();
    _refreshTimer = null;
  }

  Future<void> load({bool silent = false}) async {
    if (_requestInFlight) return;

    _requestInFlight = true;

    if (!silent) {
      state = state.copyWith(
        loading: true,
        clearError: true,
      );
    }

    try {
      final snapshot = await _api.overview();

      state = state.copyWith(
        snapshot: snapshot,
        loading: false,
        clearError: true,
      );
    } on PortfolioIntelligenceApiException catch (error) {
      // Preserve the previous verified snapshot on transient failure.
      state = state.copyWith(
        loading: false,
        error: error.message,
      );
    } on FormatException {
      state = state.copyWith(
        loading: false,
        error: 'بيانات Portfolio Intelligence لا تطابق العقد المتوقع.',
      );
    } finally {
      _requestInFlight = false;
    }
  }

  @override
  void dispose() {
    _refreshLeaseCount = 0;
    _refreshTimer?.cancel();
    _refreshTimer = null;
    super.dispose();
  }
}
