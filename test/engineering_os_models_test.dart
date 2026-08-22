import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/engineering_os/domain/engineering_os_models.dart';

void main() {
  test('engineering os summary parses operator metrics', () {
    final summary = EngineeringOsSummary.fromJson(<String, dynamic>{
      'parallel_tracks': <String>[
        'PRODUCT_UI',
        'ENGINEERING_GOVERNANCE',
        'EXTENSIBILITY',
      ],
      'tasks_by_status': <String, dynamic>{'READY': 2},
      'extensions_by_kind': <String, dynamic>{'SKILL': 3},
      'quarantined_extensions': 1,
      'remote_checkpointed_tasks': 4,
    });

    expect(summary.parallelTracks, hasLength(3));
    expect(summary.tasksByStatus['READY'], 2);
    expect(summary.extensionsByKind['SKILL'], 3);
    expect(summary.quarantinedExtensions, 1);
    expect(summary.remoteCheckpointedTasks, 4);
  });

  test('task and extension models preserve remote authority fields', () {
    final task = EngineeringTask.fromJson(<String, dynamic>{
      'task_id': 'WM-101',
      'title': 'Remote task',
      'project_id': 'PALWAKF_WORKSPACE_MANAGER',
      'repository': 'firasfanon/palwakf_workspace_manager',
      'base_sha': 'a' * 40,
      'task_branch': 'task/WM-101',
      'owner_id': 'firas',
      'actor_id': 'firas',
      'actor_type': 'HUMAN',
      'provider_id': null,
      'status': 'WIP_REMOTE_CHECKPOINTED',
      'scope_patterns': <String>['lib/**'],
      'depends_on': <String>[],
      'dependency_mode': 'INDEPENDENT',
      'risk_class': 'MEDIUM',
      'wip_checkpoint_status': 'REMOTE_CHECKPOINTED',
      'integration_status': 'NOT_READY',
      'latest_remote_task_sha': 'b' * 40,
    });
    expect(task.taskBranch, 'task/WM-101');
    expect(task.latestRemoteTaskSha, 'b' * 40);

    final extension = ExtensionRecord.fromJson(<String, dynamic>{
      'extension_id': 'skill.example',
      'kind': 'SKILL',
      'name': 'Example',
      'version': '1.0.0',
      'source_kind': 'GITHUB',
      'source_reference': 'example/skill',
      'open_source': true,
      'license': 'MIT',
      'capabilities': <String>['source.analysis'],
      'declared_roles': <String>['knowledge.skill'],
      'role_authorities': <String, dynamic>{
        'knowledge.skill': 'NOT_AUTHORIZED',
      },
      'required_permissions': <String>['read'],
      'risk_class': 'LOW',
      'lifecycle': 'QUARANTINED',
      'health_status': 'UNKNOWN',
    });
    expect(extension.lifecycle, 'QUARANTINED');
    expect(extension.openSource, isTrue);
    expect(extension.declaredRoles, <String>['knowledge.skill']);
    expect(extension.roleAuthorities['knowledge.skill'], 'NOT_AUTHORIZED');
  });
}
