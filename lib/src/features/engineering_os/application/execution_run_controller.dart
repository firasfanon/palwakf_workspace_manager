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
    this.workspace,
    this.loading = false,
    this.workspaceLoading = false,
    this.error,
    this.workspaceError,
  });

  final EngineeringTaskExecutionContext? context;
  final ExternalExecutionWorkspaceStatus? workspace;
  final bool loading;
  final bool workspaceLoading;
  final String? error;
  final String? workspaceError;

  ExecutionRunContextState copyWith({
    EngineeringTaskExecutionContext? context,
    ExternalExecutionWorkspaceStatus? workspace,
    bool? loading,
    bool? workspaceLoading,
    String? error,
    String? workspaceError,
    bool clearError = false,
    bool clearWorkspaceError = false,
    bool clearWorkspace = false,
  }) {
    return ExecutionRunContextState(
      context: context ?? this.context,
      workspace: clearWorkspace ? null : workspace ?? this.workspace,
      loading: loading ?? this.loading,
      workspaceLoading: workspaceLoading ?? this.workspaceLoading,
      error: clearError ? null : error ?? this.error,
      workspaceError:
          clearWorkspaceError ? null : workspaceError ?? this.workspaceError,
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

  Future<void> loadWorkspace(String executionRunId) async {
    state = state.copyWith(
      workspaceLoading: true,
      clearWorkspaceError: true,
      clearWorkspace: state.workspace?.executionRunId != executionRunId,
    );
    try {
      final workspace = await _api.externalWorkspaceStatus(executionRunId);
      state = state.copyWith(
        workspace: workspace,
        workspaceLoading: false,
        clearWorkspaceError: true,
      );
    } catch (error) {
      state = state.copyWith(
        workspaceLoading: false,
        workspaceError: error.toString(),
      );
    }
  }

  Future<ExternalExecutionWorkspaceStatus> prepareWorkspace(
    String executionRunId, {
    bool recreate = false,
  }) async {
    return _workspaceMutation(
      executionRunId,
      () => _api.prepareExternalWorkspace(
        executionRunId,
        recreate: recreate,
      ),
    );
  }

  Future<ExternalExecutionWorkspaceStatus> applyWorkspace(
    String executionRunId,
    List<Map<String, dynamic>> files,
  ) async {
    return _workspaceMutation(
      executionRunId,
      () => _api.applyExternalWorkspace(executionRunId, files),
    );
  }

  Future<ExternalExecutionWorkspaceStatus> validateWorkspace(
    String executionRunId, {
    List<String> checks = const <String>[],
  }) async {
    return _workspaceMutation(
      executionRunId,
      () => _api.validateExternalWorkspace(executionRunId, checks: checks),
    );
  }

  Future<ExternalExecutionWorkspaceStatus> checkpointWorkspace(
    String executionRunId, {
    required String commitMessage,
    List<String> evidence = const <String>[],
  }) async {
    final workspace = await _workspaceMutation(
      executionRunId,
      () => _api.checkpointExternalWorkspace(
        executionRunId,
        commitMessage: commitMessage,
        evidence: evidence,
      ),
    );
    await load();
    return workspace;
  }

  Future<ExternalExecutionWorkspaceStatus> _workspaceMutation(
    String executionRunId,
    Future<ExternalExecutionWorkspaceStatus> Function() action,
  ) async {
    state = state.copyWith(
      workspaceLoading: true,
      clearWorkspaceError: true,
    );
    try {
      final workspace = await action();
      state = state.copyWith(
        workspace: workspace,
        workspaceLoading: false,
        clearWorkspaceError: true,
      );
      return workspace;
    } catch (error) {
      state = state.copyWith(
        workspaceLoading: false,
        workspaceError: error.toString(),
      );
      rethrow;
    }
  }
}
