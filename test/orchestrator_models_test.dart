import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/domain/orchestrator_models.dart';

void main() {
  test('parses every orchestrator task state', () {
    const values = <String>[
      'pending',
      'running',
      'awaiting_approval',
      'failed',
      'pending_verification',
      'verified',
      'drifted',
      'timed_out',
      'cancelled',
    ];

    for (final value in values) {
      final status = OrchestratorTaskStatus.fromWire(value);
      expect(status.wireValue, value);
      expect(status.arabicLabel, isNotEmpty);
    }
  });

  test('task draft rejects missing governed fields', () {
    const draft = TaskDraft(
      taskId: '',
      projectId: 'PALWAKF_WORKSPACE_MANAGER',
      repository: 'firasfanon/palwakf_workspace_manager',
      branch: 'agent/workspace-manager-foundation-v1',
      expectedHead: '',
      authorityReference: '',
      prompt: '',
      constraints: <String>[],
      sandbox: 'read-only',
      maxTurns: 0,
      timeoutSeconds: 0,
      idempotencyKey: '',
    );

    final errors = draft.validate();

    expect(errors, contains('authority_reference'));
    expect(errors, contains('expected_head'));
    expect(errors, contains('timeout_seconds'));
    expect(errors, contains('max_turns'));
    expect(errors, contains('idempotency_key'));
  });

  test('runtime capability response contains flags only', () {
    final capabilities = RuntimeCapabilities.fromJson(
      <String, dynamic>{
        'version': 'SELF_HOSTING_OPERATIONAL_LOOP_V1',
        'task_lifecycle': true,
        'manual_relay_fallback': true,
        'capability_routing': true,
        'tool_decision_trace': true,
        'planned_actual_reconciliation': true,
        'automatic_agents_available': false,
        'database_connected': false,
        'production_mutation': false,
      },
    );

    expect(capabilities.manualRelayFallback, isTrue);
    expect(capabilities.automaticAgentsAvailable, isFalse);
    expect(capabilities.databaseConnected, isFalse);
  });
}
