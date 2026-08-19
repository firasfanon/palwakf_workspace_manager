import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../orchestrator/application/orchestrator_controller.dart';
import '../data/external_project_api_client.dart';
import '../data/project_task_bridge_api_client.dart';
import '../domain/external_project_models.dart';

final externalProjectApiProvider = Provider<ExternalProjectApi>((ref) {
  return HttpExternalProjectApi(
    bearerToken: ref.watch(orchestratorTokenProvider),
  );
});

final projectTaskBridgeApiProvider = Provider<ProjectTaskBridgeApi>((ref) {
  return HttpProjectTaskBridgeApi(
    bearerToken: ref.watch(orchestratorTokenProvider),
  );
});

final externalProjectsControllerProvider =
    StateNotifierProvider<ExternalProjectsController, ExternalProjectsState>(
        (ref) {
  return ExternalProjectsController(ref.watch(externalProjectApiProvider));
});

class ExternalProjectsState {
  const ExternalProjectsState({
    this.projects = const <ExternalProject>[],
    this.realityByProject = const <String, ProjectReality>{},
    this.loading = false,
    this.loaded = false,
    this.error,
  });

  final List<ExternalProject> projects;
  final Map<String, ProjectReality> realityByProject;
  final bool loading;
  final bool loaded;
  final String? error;

  ExternalProjectsState copyWith({
    List<ExternalProject>? projects,
    Map<String, ProjectReality>? realityByProject,
    bool? loading,
    bool? loaded,
    String? error,
    bool clearError = false,
  }) {
    return ExternalProjectsState(
      projects: projects ?? this.projects,
      realityByProject: realityByProject ?? this.realityByProject,
      loading: loading ?? this.loading,
      loaded: loaded ?? this.loaded,
      error: clearError ? null : error ?? this.error,
    );
  }
}

class ExternalProjectsController extends StateNotifier<ExternalProjectsState> {
  ExternalProjectsController(this._api) : super(const ExternalProjectsState());

  final ExternalProjectApi _api;

  Future<void> load() async {
    await _guard(() async {
      state = state.copyWith(
        projects: await _api.listProjects(),
        loaded: true,
      );
    });
  }

  Future<ExternalProject?> intake(ProjectIntakeDraft draft) async {
    ExternalProject? created;
    await _guard(() async {
      created = await _api.intake(draft);
      state = state.copyWith(
        projects: await _api.listProjects(),
        loaded: true,
      );
    });
    return created;
  }

  Future<void> loadReality(String projectId) async {
    await _guard(() async {
      _storeReality(await _api.reality(projectId));
    });
  }

  Future<void> probe(String projectId) async {
    await _guard(() async {
      _storeReality(await _api.probe(projectId));
      state = state.copyWith(
        projects: await _api.listProjects(),
        loaded: true,
      );
    });
  }

  Future<bool> prepareTask(String projectId, String candidateId) async {
    var prepared = false;
    await _guard(() async {
      await _api.prepareTask(projectId, candidateId);
      prepared = true;
    });
    return prepared;
  }

  void _storeReality(ProjectReality reality) {
    state = state.copyWith(
      realityByProject: <String, ProjectReality>{
        ...state.realityByProject,
        reality.projectId: reality,
      },
    );
  }

  Future<void> _guard(Future<void> Function() action) async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      await action();
      state = state.copyWith(loading: false, clearError: true);
    } on ExternalProjectApiException catch (error) {
      state = state.copyWith(loading: false, error: error.message);
    } catch (error) {
      state = state.copyWith(loading: false, error: error.toString());
    }
  }
}
