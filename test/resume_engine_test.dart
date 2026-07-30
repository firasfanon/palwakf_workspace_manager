import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/control_plane/application/resume_engine.dart';
import 'package:palwakf_workspace_manager/src/features/control_plane/domain/control_plane_models.dart';

void main() {
  const engine = ResumeEngine();

  ProjectState verifiedProject() {
    return ProjectState(
      projectKey: 'PAL_EYES',
      projectName: 'بعيون فلسطينية',
      repositoryFullName: 'firasfanon/Pal_Eyes',
      currentBaselineId: 'PAL_EYES_R8',
      baselineStatus: VerificationStatus.verified,
      currentTaskId: 'TASK-1',
      taskStatus: TaskStatus.authorized,
      nextAction: 'VERIFY',
      updatedAt: DateTime.utc(2026, 7, 29),
    );
  }

  test('allows a read-only resume when reality is verified', () {
    final plan = engine.buildPlan(
      ResumeRequest(
        project: verifiedProject(),
        repository: const RepositoryReality(
          repositoryFullName: 'firasfanon/Pal_Eyes',
          expectedHead: 'abc',
          actualHead: 'abc',
          isReachable: true,
        ),
        drifts: const <DriftRecord>[],
        authorizationMode: AuthorizationMode.readOnly,
        requestsMutation: false,
      ),
    );

    expect(plan.allowed, isTrue);
    expect(plan.readOnly, isTrue);
    expect(plan.blockers, isEmpty);
  });

  test('fails closed when remote HEAD drifts', () {
    final plan = engine.buildPlan(
      ResumeRequest(
        project: verifiedProject(),
        repository: const RepositoryReality(
          repositoryFullName: 'firasfanon/Pal_Eyes',
          expectedHead: 'abc',
          actualHead: 'def',
          isReachable: true,
        ),
        drifts: const <DriftRecord>[],
        authorizationMode: AuthorizationMode.readOnly,
        requestsMutation: false,
      ),
    );

    expect(plan.allowed, isFalse);
    expect(plan.blockers, contains('REMOTE_HEAD_DRIFT_DETECTED'));
  });

  test('blocks mutation without explicit authorization', () {
    final plan = engine.buildPlan(
      ResumeRequest(
        project: verifiedProject(),
        repository: const RepositoryReality(
          repositoryFullName: 'firasfanon/Pal_Eyes',
          expectedHead: 'abc',
          actualHead: 'abc',
          isReachable: true,
        ),
        drifts: const <DriftRecord>[],
        authorizationMode: AuthorizationMode.explicitMutationRequired,
        requestsMutation: true,
      ),
    );

    expect(plan.allowed, isFalse);
    expect(
      plan.blockers,
      contains('EXPLICIT_MUTATION_AUTHORIZATION_REQUIRED'),
    );
  });

  test('blocks unresolved high or critical drift', () {
    final plan = engine.buildPlan(
      ResumeRequest(
        project: verifiedProject(),
        repository: const RepositoryReality(
          repositoryFullName: 'firasfanon/Pal_Eyes',
          expectedHead: 'abc',
          actualHead: 'abc',
          isReachable: true,
        ),
        drifts: const <DriftRecord>[
          DriftRecord(
            id: 'DRIFT-1',
            severity: DriftSeverity.high,
            resolved: false,
            expectedState: 'abc',
            actualState: 'def',
          ),
        ],
        authorizationMode: AuthorizationMode.readOnly,
        requestsMutation: false,
      ),
    );

    expect(plan.allowed, isFalse);
    expect(plan.blockers, contains('UNRESOLVED_DRIFT:DRIFT-1'));
  });
}
