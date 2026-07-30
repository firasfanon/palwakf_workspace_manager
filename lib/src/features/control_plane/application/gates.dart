import '../domain/control_plane_models.dart';

class RealityGate {
  const RealityGate();

  List<String> evaluate(ResumeRequest request) {
    final blockers = <String>[];

    if (!request.repository.isReachable) {
      blockers.add('REPOSITORY_NOT_REACHABLE');
    }
    if (request.repository.actualHead == null) {
      blockers.add('REMOTE_HEAD_NOT_VERIFIED');
    }
    if (request.repository.hasHeadDrift) {
      blockers.add('REMOTE_HEAD_DRIFT_DETECTED');
    }
    if (request.project.baselineStatus != VerificationStatus.verified) {
      blockers.add('BASELINE_NOT_VERIFIED');
    }

    return blockers;
  }
}

class DriftGate {
  const DriftGate();

  List<String> evaluate(ResumeRequest request) {
    return request.drifts
        .where(
          (drift) =>
              !drift.resolved &&
              (drift.severity == DriftSeverity.critical ||
                  drift.severity == DriftSeverity.high),
        )
        .map((drift) => 'UNRESOLVED_DRIFT:${drift.id}')
        .toList(growable: false);
  }
}

class AuthorizationGate {
  const AuthorizationGate();

  List<String> evaluate(ResumeRequest request) {
    if (!request.requestsMutation) {
      return const <String>[];
    }

    if (request.authorizationMode != AuthorizationMode.mutationAuthorized) {
      return const <String>['EXPLICIT_MUTATION_AUTHORIZATION_REQUIRED'];
    }

    return const <String>[];
  }
}
