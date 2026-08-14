import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/application/operational_authorization.dart';

void main() {
  test('read-only authorization context disables mutation capabilities', () {
    final context = OperationalAuthorizationContext.fromJson(
      <String, dynamic>{
        'client_id': 'read-only-uat',
        'scopes': <String>['tasks:read'],
        'read_only': true,
        'can_dispatch': false,
        'can_continue': false,
        'can_cancel': false,
        'can_verify': false,
        'can_probe_tools': false,
      },
    );

    expect(context.readOnly, isTrue);
    expect(context.canDispatch, isFalse);
    expect(context.canProbeTools, isFalse);
    expect(context.scopes, <String>['tasks:read']);
  });

  test('full authorization context exposes explicit capabilities', () {
    final context = OperationalAuthorizationContext.fromJson(
      <String, dynamic>{
        'client_id': 'full-uat',
        'scopes': <String>[
          'tasks:read',
          'tasks:dispatch',
          'tasks:continue',
          'tasks:cancel',
          'tasks:verify',
          'tools:probe',
        ],
        'read_only': false,
        'can_dispatch': true,
        'can_continue': true,
        'can_cancel': true,
        'can_verify': true,
        'can_probe_tools': true,
      },
    );

    expect(context.readOnly, isFalse);
    expect(context.canDispatch, isTrue);
    expect(context.canContinue, isTrue);
    expect(context.canCancel, isTrue);
    expect(context.canVerify, isTrue);
    expect(context.canProbeTools, isTrue);
  });
}
