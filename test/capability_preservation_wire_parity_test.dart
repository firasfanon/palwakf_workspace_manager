import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/domain/engineering_os_models.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/domain/orchestrator_models.dart';

void main() {
  const engineeringStatuses = <String>[
    'PLANNED',
    'READY',
    'IN_PROGRESS',
    'WIP_REMOTE_CHECKPOINTED',
    'BLOCKED_DEPENDENCY',
    'READY_FOR_REVIEW',
    'READY_FOR_INTEGRATION',
    'IN_MERGE_QUEUE',
    'RECONCILIATION_REQUIRED',
    'INTEGRATED',
    'FAILED',
    'CANCELLED',
    'SUPERSEDED',
  ];

  Map<String, dynamic> engineeringJson(String status) => <String, dynamic>{
        'task_id': 'WM-PARITY-DART',
        'title': 'Parity task',
        'project_id': 'PALWAKF_WORKSPACE_MANAGER',
        'repository': 'firasfanon/palwakf_workspace_manager',
        'base_sha': 'a' * 40,
        'task_branch': 'task/WM-PARITY-DART',
        'owner_id': 'firas',
        'actor_id': 'agent-a',
        'actor_type': 'AGENT',
        'provider_id': 'provider-a',
        'status': status,
        'scope_patterns': <String>['lib/**'],
        'depends_on': <String>['WM-UPSTREAM'],
        'dependency_mode': 'STACKED',
        'risk_class': 'HIGH',
        'wip_checkpoint_status': 'REMOTE_CHECKPOINTED',
        'integration_status': 'RECONCILIATION_REQUIRED',
        'latest_remote_task_sha': 'b' * 40,
      };

  Map<String, dynamic> operatorJson(String status) => <String, dynamic>{
        'task_id': 'WM_PARITY_DART_OP',
        'project_id': 'PALWAKF_WORKSPACE_MANAGER',
        'repository': 'firasfanon/palwakf_workspace_manager',
        'branch': 'agent/workspace-manager-foundation-v1',
        'expected_head': 'b' * 40,
        'authority_reference': 'AUTHORITY://CAPABILITY_PRESERVATION_V1',
        'prompt': 'Preserve operator task wire semantics during consolidation.',
        'constraints': <String>['NO_PRODUCTION'],
        'sandbox': 'read-only',
        'max_turns': 3,
        'timeout_seconds': 120,
        'idempotency_key': 'capability-preservation-dart-op',
        'automatic_failure_code': null,
        'dispatch_mode': 'automatic',
        'status': status,
        'created_at': '2026-08-16T00:00:00Z',
        'updated_at': '2026-08-16T00:00:00Z',
        'last_event': 'PARITY_FIXTURE',
        'blocker': null,
        'thread_id': null,
        'execution_receipt': null,
        'before_head': null,
        'after_head': null,
        'changed_files': <String>[],
        'tests': <String>[],
        'evidence': <String>[],
        'verification_receipt': null,
        'requires_explicit_authorization': false,
        'authorized_at': null,
        'authorized_by': null,
        'events': <Map<String, dynamic>>[],
      };

  test('PT-STATE-001 preserves every EngineeringTask status on the wire', () {
    for (final status in engineeringStatuses) {
      final task = EngineeringTask.fromJson(engineeringJson(status));
      expect(task.status, status);
    }
  });

  test('PT-STATE-002 preserves every OperatorTask status on the wire', () {
    for (final status in OrchestratorTaskStatus.values) {
      final task = OperatorTask.fromJson(operatorJson(status.wireValue));
      expect(task.status, status);
      expect(task.status.wireValue, status.wireValue);
    }
  });

  test('PT-SEM-001 keeps task base SHA separate from run expected HEAD', () {
    final task = EngineeringTask.fromJson(
      engineeringJson('WIP_REMOTE_CHECKPOINTED'),
    );
    final run = OperatorTask.fromJson(operatorJson('pending'));

    expect(task.baseSha, 'a' * 40);
    expect(task.latestRemoteTaskSha, 'b' * 40);
    expect(run.expectedHead, 'b' * 40);
    expect(task.baseSha, isNot(run.expectedHead));
  });

  test('PT-ENG-004 keeps declared Engineering lifecycle values distinct', () {
    final observed = engineeringStatuses
        .map((status) =>
            EngineeringTask.fromJson(engineeringJson(status)).status)
        .toSet();

    expect(observed.length, engineeringStatuses.length);
    expect(observed, contains('RECONCILIATION_REQUIRED'));
    expect(observed, contains('SUPERSEDED'));
    expect(observed, contains('BLOCKED_DEPENDENCY'));
  });
}
