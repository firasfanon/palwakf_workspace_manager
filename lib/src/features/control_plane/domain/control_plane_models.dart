enum VerificationStatus {
  verified,
  documentedNotVerified,
  drifted,
  unknown,
}

enum TaskStatus {
  planned,
  authorized,
  inProgress,
  blocked,
  verified,
  completed,
  superseded,
}

enum AuthorizationMode {
  readOnly,
  explicitMutationRequired,
  mutationAuthorized,
}

enum DriftSeverity {
  low,
  medium,
  high,
  critical,
}

class ProjectState {
  const ProjectState({
    required this.projectKey,
    required this.projectName,
    required this.repositoryFullName,
    required this.currentBaselineId,
    required this.baselineStatus,
    required this.currentTaskId,
    required this.taskStatus,
    required this.nextAction,
    required this.updatedAt,
  });

  final String projectKey;
  final String projectName;
  final String? repositoryFullName;
  final String? currentBaselineId;
  final VerificationStatus baselineStatus;
  final String? currentTaskId;
  final TaskStatus taskStatus;
  final String nextAction;
  final DateTime updatedAt;
}

class RepositoryReality {
  const RepositoryReality({
    required this.repositoryFullName,
    required this.expectedHead,
    required this.actualHead,
    required this.isReachable,
  });

  final String repositoryFullName;
  final String? expectedHead;
  final String? actualHead;
  final bool isReachable;

  bool get hasHeadDrift =>
      expectedHead != null && actualHead != null && expectedHead != actualHead;
}

class DriftRecord {
  const DriftRecord({
    required this.id,
    required this.severity,
    required this.resolved,
    required this.expectedState,
    required this.actualState,
  });

  final String id;
  final DriftSeverity severity;
  final bool resolved;
  final String expectedState;
  final String actualState;
}

class ResumeRequest {
  const ResumeRequest({
    required this.project,
    required this.repository,
    required this.drifts,
    required this.authorizationMode,
    required this.requestsMutation,
  });

  final ProjectState project;
  final RepositoryReality repository;
  final List<DriftRecord> drifts;
  final AuthorizationMode authorizationMode;
  final bool requestsMutation;
}

class ResumePlan {
  const ResumePlan({
    required this.allowed,
    required this.readOnly,
    required this.steps,
    required this.blockers,
  });

  final bool allowed;
  final bool readOnly;
  final List<String> steps;
  final List<String> blockers;
}
