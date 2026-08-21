import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/data/engineering_os_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/domain/execution_run_models.dart';

Map<String, dynamic> workspacePayload({
  String lifecycle = 'READY',
  bool prepared = true,
  bool authorized = true,
  bool validationPassed = false,
}) {
  return <String, dynamic>{
    'execution_run_id': 'WM_EXTERNAL_RUN_001',
    'parent_engineering_task_id': 'WM-EXTERNAL-TASK-001',
    'project_id': 'PAL_EYES',
    'repository': 'firasfanon/palwakf_Eyes',
    'task_branch': 'task/PAL-EYES-EXTERNAL-RUNTIME-UAT',
    'expected_head': 'a' * 40,
    'workspace_path': r'C:\temp\external-runtime',
    'lifecycle': lifecycle,
    'prepared': prepared,
    'authorized': authorized,
    'current_head': 'a' * 40,
    'remote_head': null,
    'changed_files': <String>['lib/runtime_probe.dart'],
    'validation': validationPassed
        ? <String, dynamic>{
            'checks': <Map<String, dynamic>>[
              <String, dynamic>{
                'check': 'GIT_DIFF_CHECK',
                'command_summary': 'git diff --check',
                'status': 'PASS',
                'exit_code': 0,
                'duration_ms': 12,
                'output_excerpt': '',
              },
            ],
            'all_passed': true,
            'validated_paths': <String>['lib/runtime_probe.dart'],
            'started_at': '2026-08-20T10:00:00Z',
            'completed_at': '2026-08-20T10:00:01Z',
          }
        : null,
    'checkpoint_sha': lifecycle == 'CHECKPOINTED' ? 'b' * 40 : null,
    'last_error': null,
    'updated_at': '2026-08-20T10:00:01Z',
  };
}

void main() {
  test('external execution workspace model preserves governed runtime state',
      () {
    final workspace = ExternalExecutionWorkspaceStatus.fromJson(
      workspacePayload(validationPassed: true),
    );

    expect(workspace.repository, 'firasfanon/palwakf_Eyes');
    expect(workspace.prepared, isTrue);
    expect(workspace.authorized, isTrue);
    expect(workspace.changedFiles, <String>['lib/runtime_probe.dart']);
    expect(workspace.validationPassed, isTrue);
    expect(workspace.validation!.checks.single.check, 'GIT_DIFF_CHECK');
  });

  test('engineering OS client exposes external runtime API vertical slice',
      () async {
    final seen = <String>[];
    final bodies = <String, Map<String, dynamic>>{};
    final client = EngineeringOsApiClient(
      baseUrl: 'http://127.0.0.1:8421',
      bearerToken: 'test-token',
      client: MockClient((request) async {
        seen.add('${request.method} ${request.url.path}');
        if (request.body.isNotEmpty) {
          bodies[request.url.path] =
              jsonDecode(request.body) as Map<String, dynamic>;
        }
        return http.Response(
          jsonEncode(
            workspacePayload(
              lifecycle: request.url.path.endsWith('/checkpoint')
                  ? 'CHECKPOINTED'
                  : 'READY',
              validationPassed: request.url.path.endsWith('/validate') ||
                  request.url.path.endsWith('/checkpoint'),
            ),
          ),
          200,
          headers: <String, String>{'content-type': 'application/json'},
        );
      }),
    );

    const runId = 'WM_EXTERNAL_RUN_001';
    await client.externalWorkspaceStatus(runId);
    await client.prepareExternalWorkspace(runId);
    await client.applyExternalWorkspace(
      runId,
      <Map<String, dynamic>>[
        <String, dynamic>{
          'path': 'lib/runtime_probe.dart',
          'preimage_mode': 'ABSENT',
          'postimage_text': 'void main() {}\n',
        },
      ],
    );
    await client.validateExternalWorkspace(
      runId,
      checks: const <String>['GIT_DIFF_CHECK'],
    );
    final checkpoint = await client.checkpointExternalWorkspace(
      runId,
      commitMessage: 'test: governed external checkpoint',
    );

    expect(
      seen,
      <String>[
        'GET /v1/execution-runs/$runId/workspace',
        'POST /v1/execution-runs/$runId/workspace/prepare',
        'POST /v1/execution-runs/$runId/workspace/apply',
        'POST /v1/execution-runs/$runId/workspace/validate',
        'POST /v1/execution-runs/$runId/workspace/checkpoint',
      ],
    );
    expect(
      bodies['/v1/execution-runs/$runId/workspace/validate']!['checks'],
      <String>['GIT_DIFF_CHECK'],
    );
    expect(
      bodies['/v1/execution-runs/$runId/workspace/checkpoint']![
          'commit_message'],
      'test: governed external checkpoint',
    );
    expect(checkpoint.checkpointed, isTrue);
  });

  test('operations UI exposes coherent external execution runtime controls',
      () {
    final source = File(
      'lib/src/features/orchestrator/presentation/orchestrator_workspace_page.dart',
    ).readAsStringSync();

    expect(source, contains('مساحة التنفيذ الخارجية'));
    expect(source, contains('external-runtime-prepare'));
    expect(source, contains('external-runtime-apply'));
    expect(source, contains('external-runtime-validate'));
    expect(source, contains('external-runtime-checkpoint'));
    expect(source, contains('Remote WIP Checkpoint'));
    expect(source, contains('Integration'));
    expect(source, contains('Production'));
  });
}
