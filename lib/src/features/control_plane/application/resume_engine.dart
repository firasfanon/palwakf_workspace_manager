import '../domain/control_plane_models.dart';
import 'gates.dart';

class ResumeEngine {
  const ResumeEngine({
    this.realityGate = const RealityGate(),
    this.driftGate = const DriftGate(),
    this.authorizationGate = const AuthorizationGate(),
  });

  final RealityGate realityGate;
  final DriftGate driftGate;
  final AuthorizationGate authorizationGate;

  ResumePlan buildPlan(ResumeRequest request) {
    final blockers = <String>[
      ...realityGate.evaluate(request),
      ...driftGate.evaluate(request),
      ...authorizationGate.evaluate(request),
    ];

    if (blockers.isNotEmpty) {
      return ResumePlan(
        allowed: false,
        readOnly: true,
        steps: const <String>[
          'READ_CURRENT_CHECKPOINT',
          'VERIFY_REPOSITORY_REALITY',
          'REPORT_BLOCKERS_WITHOUT_MUTATION',
        ],
        blockers: List<String>.unmodifiable(blockers),
      );
    }

    final steps = <String>[
      'READ_CURRENT_CHECKPOINT',
      'VERIFY_REPOSITORY_REALITY',
      'VERIFY_BASELINE',
      'VERIFY_OPEN_TASK',
      if (request.requestsMutation) 'APPLY_AUTHORIZED_SCOPED_MUTATION',
      'CAPTURE_EVIDENCE',
      'WRITE_SESSION_CHECKPOINT',
    ];

    return ResumePlan(
      allowed: true,
      readOnly: !request.requestsMutation,
      steps: List<String>.unmodifiable(steps),
      blockers: const <String>[],
    );
  }
}
