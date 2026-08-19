import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/engineering_os_api_client.dart';
import '../domain/execution_run_models.dart';
import 'engineering_os_controller.dart';

final executionRunContextControllerProvider = StateNotifierProvider.family<
    ExecutionRunContextController,
    ExecutionRunContextState,
    String>((ref, engineeringTaskId) {
  return ExecutionRunContextController(
    ref.watch(engineeringOsApiProvider),
    engineeringTaskId,
  );
});

class ExecutionRunContextState {
  const ExecutionRunContextState({
    this.context,
    this.loading = false,
    this.error,
  });

  final EngineeringTaskExecutionContext? context;
  final bool loading;
  final String? error;

  ExecutionRunContextState copyWith({
    EngineeringTaskExecutionContext? context,
    bool? loading,
    String? error,
    bool clearError = false,
  }) {
    return ExecutionRunContextState(
      context: context ?? this.context,
      loading: loading ?? this.loading,
      error: clearError ? null : error ?? this.error,
    );
  }
}

class ExecutionRunContextController
    extends StateNotifier<ExecutionRunContextState> {
  ExecutionRunContextController(this._api, this.engineeringTaskId)
      : super(const ExecutionRunContextState());

  final EngineeringOsApiClient _api;
  final String engineeringTaskId;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final context = await _api.executionContext(engineeringTaskId);
      state = state.copyWith(
        context: context,
        loading: false,
        clearError: true,
      );
    } catch (error) {
      state = state.copyWith(loading: false, error: error.toString());
    }
  }

  Future<EngineeringExecutionRunView> create(NewExecutionRunDraft draft) async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final run = await _api.createExecutionRun(engineeringTaskId, draft);
      final refreshed = await _api.executionContext(engineeringTaskId);
      state = state.copyWith(
        context: refreshed,
        loading: false,
        clearError: true,
      );
      return run;
    } catch (error) {
      state = state.copyWith(loading: false, error: error.toString());
      rethrow;
    }
  }
}
