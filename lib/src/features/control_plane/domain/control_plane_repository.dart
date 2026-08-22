import 'control_plane_models.dart';

abstract interface class ControlPlaneReadRepository {
  Future<ProjectState?> readProject(String projectKey);

  Future<RepositoryReality?> readRepositoryReality(String projectKey);

  Future<List<DriftRecord>> readOpenDrifts(String projectKey);
}

abstract interface class SessionCheckpointWriter {
  Future<void> writeCheckpoint({
    required String projectKey,
    required ResumePlan plan,
    required DateTime recordedAt,
  });
}
