import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../orchestrator/application/orchestrator_controller.dart';
import '../data/engineering_os_api_client.dart';
import '../domain/engineering_os_models.dart';

final engineeringOsApiProvider = Provider<EngineeringOsApiClient>((ref) {
  return EngineeringOsApiClient(
    bearerToken: ref.watch(orchestratorTokenProvider),
  );
});

final engineeringOsControllerProvider =
    StateNotifierProvider<EngineeringOsController, EngineeringOsState>((ref) {
  return EngineeringOsController(ref.watch(engineeringOsApiProvider));
});

class EngineeringOsState {
  const EngineeringOsState({
    this.summary,
    this.tasks = const <EngineeringTask>[],
    this.extensions = const <ExtensionRecord>[],
    this.loading = false,
    this.error,
  });

  final EngineeringOsSummary? summary;
  final List<EngineeringTask> tasks;
  final List<ExtensionRecord> extensions;
  final bool loading;
  final String? error;

  EngineeringOsState copyWith({
    EngineeringOsSummary? summary,
    List<EngineeringTask>? tasks,
    List<ExtensionRecord>? extensions,
    bool? loading,
    String? error,
    bool clearError = false,
  }) {
    return EngineeringOsState(
      summary: summary ?? this.summary,
      tasks: tasks ?? this.tasks,
      extensions: extensions ?? this.extensions,
      loading: loading ?? this.loading,
      error: clearError ? null : error ?? this.error,
    );
  }
}

class EngineeringOsController extends StateNotifier<EngineeringOsState> {
  EngineeringOsController(this._api) : super(const EngineeringOsState());

  final EngineeringOsApiClient _api;

  Future<void> load() async {
    state = state.copyWith(loading: true, clearError: true);
    try {
      final results = await Future.wait<dynamic>(<Future<dynamic>>[
        _api.summary(),
        _api.tasks(),
        _api.extensions(),
      ]);
      state = state.copyWith(
        summary: results[0] as EngineeringOsSummary,
        tasks: results[1] as List<EngineeringTask>,
        extensions: results[2] as List<ExtensionRecord>,
        loading: false,
      );
    } catch (error) {
      state = state.copyWith(loading: false, error: error.toString());
    }
  }

  Future<void> createTask(NewEngineeringTaskDraft draft) async {
    final created = await _api.createTask(draft);
    state = state.copyWith(
      tasks: <EngineeringTask>[
        created,
        ...state.tasks.where((task) => task.taskId != created.taskId),
      ],
    );
    await load();
  }

  Future<void> registerExtension(NewExtensionDraft draft) async {
    final created = await _api.registerExtension(draft);
    state = state.copyWith(
      extensions: <ExtensionRecord>[
        created,
        ...state.extensions.where(
          (extension) => extension.extensionId != created.extensionId,
        ),
      ],
    );
    await load();
  }
}
