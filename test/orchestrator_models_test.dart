import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/domain/orchestrator_models.dart';

void main() {
  test('parses every orchestrator task state', () {
    const values = <String>[
      'pending',
      'queued',
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

  test('health facts preserve unknown provider values and provenance', () {
    final fact = HealthFact.fromJson(
      <String, dynamic>{
        'value': null,
        'provenance': 'NOT_EXPOSED_BY_PROVIDER',
        'observed_at': null,
        'unit': null,
        'note': 'Provider does not expose a verified value',
      },
    );

    expect(fact.value, isNull);
    expect(fact.displayValue, 'غير متاح من المزود');
    expect(fact.provenance, 'NOT_EXPOSED_BY_PROVIDER');
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

  test('tool health preserves role-specific authority', () {
    final tool = ToolOperationalHealth.fromJson(<String, dynamic>{
      'adapter_id': 'codex',
      'display_name': 'Codex',
      'required': true,
      'connection': <String, dynamic>{
        'value': 'available',
        'provenance': 'VERIFIED_PLATFORM_UI'
      },
      'authentication': <String, dynamic>{
        'value': 'SET',
        'provenance': 'VERIFIED_RUNTIME_PROBE'
      },
      'permission': <String, dynamic>{
        'value': 'authorized',
        'provenance': 'VERIFIED_PLATFORM_UI'
      },
      'entitlement': <String, dynamic>{
        'value': null,
        'provenance': 'NOT_EXPOSED_BY_PROVIDER'
      },
      'quota': <String, dynamic>{
        'value': 'AVAILABLE',
        'provenance': 'VERIFIED_RUNTIME_PROBE'
      },
      'usage': <String, dynamic>{
        'value': null,
        'provenance': 'NOT_EXPOSED_BY_PROVIDER'
      },
      'cost': <String, dynamic>{
        'value': null,
        'provenance': 'NOT_EXPOSED_BY_PROVIDER'
      },
      'balance': <String, dynamic>{
        'value': null,
        'provenance': 'NOT_EXPOSED_BY_PROVIDER'
      },
      'credit_expiry': <String, dynamic>{
        'value': null,
        'provenance': 'NOT_EXPOSED_BY_PROVIDER'
      },
      'renewal': <String, dynamic>{
        'value': null,
        'provenance': 'NOT_EXPOSED_BY_PROVIDER'
      },
      'rate_limit': <String, dynamic>{
        'value': null,
        'provenance': 'NOT_EXPOSED_BY_PROVIDER'
      },
      'freshness': <String, dynamic>{
        'value': 'fresh',
        'provenance': 'VERIFIED_PLATFORM_UI'
      },
      'operator_actions': <String>[],
      'evidence': <String>[],
      'role_authorities': <String, dynamic>{
        'autonomous_development': 'SUSPENDED',
        'governed_patch_relay': 'AUTHORIZED_GOVERNED_SCOPE',
        'git_transport': 'AUTHORIZED_GOVERNED_SCOPE',
      },
    });

    expect(tool.quota.displayValue, 'AVAILABLE');
    expect(tool.roleAuthorities['autonomous_development'], 'SUSPENDED');
    expect(tool.roleAuthorities['governed_patch_relay'],
        'AUTHORIZED_GOVERNED_SCOPE');
  });
}
