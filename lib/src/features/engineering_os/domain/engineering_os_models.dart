class EngineeringOsSummary {
  const EngineeringOsSummary({
    required this.parallelTracks,
    required this.tasksByStatus,
    required this.extensionsByKind,
    required this.quarantinedExtensions,
    required this.remoteCheckpointedTasks,
  });

  final List<String> parallelTracks;
  final Map<String, int> tasksByStatus;
  final Map<String, int> extensionsByKind;
  final int quarantinedExtensions;
  final int remoteCheckpointedTasks;

  factory EngineeringOsSummary.fromJson(Map<String, dynamic> json) {
    return EngineeringOsSummary(
      parallelTracks:
          (json['parallel_tracks'] as List<dynamic>? ?? const <dynamic>[])
              .map((value) => value.toString())
              .toList(growable: false),
      tasksByStatus: (json['tasks_by_status'] as Map<String, dynamic>? ??
              const <String, dynamic>{})
          .map((key, value) => MapEntry(key, (value as num).toInt())),
      extensionsByKind: (json['extensions_by_kind'] as Map<String, dynamic>? ??
              const <String, dynamic>{})
          .map((key, value) => MapEntry(key, (value as num).toInt())),
      quarantinedExtensions:
          (json['quarantined_extensions'] as num? ?? 0).toInt(),
      remoteCheckpointedTasks:
          (json['remote_checkpointed_tasks'] as num? ?? 0).toInt(),
    );
  }
}

class EngineeringTask {
  const EngineeringTask({
    required this.taskId,
    required this.title,
    required this.projectId,
    required this.repository,
    required this.baseSha,
    required this.taskBranch,
    required this.ownerId,
    required this.actorId,
    required this.actorType,
    required this.status,
    required this.scopePatterns,
    required this.dependsOn,
    required this.dependencyMode,
    required this.riskClass,
    required this.wipCheckpointStatus,
    required this.integrationStatus,
    this.providerId,
    this.latestRemoteTaskSha,
  });

  final String taskId;
  final String title;
  final String projectId;
  final String repository;
  final String baseSha;
  final String taskBranch;
  final String ownerId;
  final String actorId;
  final String actorType;
  final String? providerId;
  final String status;
  final List<String> scopePatterns;
  final List<String> dependsOn;
  final String dependencyMode;
  final String riskClass;
  final String wipCheckpointStatus;
  final String integrationStatus;
  final String? latestRemoteTaskSha;

  factory EngineeringTask.fromJson(Map<String, dynamic> json) {
    List<String> strings(String key) =>
        (json[key] as List<dynamic>? ?? const <dynamic>[])
            .map((value) => value.toString())
            .toList(growable: false);

    return EngineeringTask(
      taskId: json['task_id'] as String,
      title: json['title'] as String,
      projectId: json['project_id'] as String,
      repository: json['repository'] as String,
      baseSha: json['base_sha'] as String,
      taskBranch: json['task_branch'] as String,
      ownerId: json['owner_id'] as String,
      actorId: json['actor_id'] as String,
      actorType: json['actor_type'] as String,
      providerId: json['provider_id'] as String?,
      status: json['status'] as String,
      scopePatterns: strings('scope_patterns'),
      dependsOn: strings('depends_on'),
      dependencyMode: json['dependency_mode'] as String,
      riskClass: json['risk_class'] as String,
      wipCheckpointStatus: json['wip_checkpoint_status'] as String,
      integrationStatus: json['integration_status'] as String,
      latestRemoteTaskSha: json['latest_remote_task_sha'] as String?,
    );
  }
}

class ExtensionRecord {
  const ExtensionRecord({
    required this.extensionId,
    required this.kind,
    required this.name,
    required this.version,
    required this.sourceKind,
    required this.sourceReference,
    required this.openSource,
    required this.capabilities,
    required this.requiredPermissions,
    required this.riskClass,
    required this.lifecycle,
    required this.healthStatus,
    this.license,
  });

  final String extensionId;
  final String kind;
  final String name;
  final String version;
  final String sourceKind;
  final String sourceReference;
  final bool openSource;
  final String? license;
  final List<String> capabilities;
  final List<String> requiredPermissions;
  final String riskClass;
  final String lifecycle;
  final String healthStatus;

  factory ExtensionRecord.fromJson(Map<String, dynamic> json) {
    List<String> strings(String key) =>
        (json[key] as List<dynamic>? ?? const <dynamic>[])
            .map((value) => value.toString())
            .toList(growable: false);

    return ExtensionRecord(
      extensionId: json['extension_id'] as String,
      kind: json['kind'] as String,
      name: json['name'] as String,
      version: json['version'] as String,
      sourceKind: json['source_kind'] as String,
      sourceReference: json['source_reference'] as String,
      openSource: json['open_source'] as bool,
      license: json['license'] as String?,
      capabilities: strings('capabilities'),
      requiredPermissions: strings('required_permissions'),
      riskClass: json['risk_class'] as String,
      lifecycle: json['lifecycle'] as String,
      healthStatus: json['health_status'] as String,
    );
  }
}

class NewEngineeringTaskDraft {
  const NewEngineeringTaskDraft({
    required this.taskId,
    required this.title,
    required this.description,
    required this.baseSha,
    required this.taskBranch,
    required this.ownerId,
    required this.actorId,
    required this.actorType,
    required this.scopePatterns,
    this.providerId,
  });

  final String taskId;
  final String title;
  final String description;
  final String baseSha;
  final String taskBranch;
  final String ownerId;
  final String actorId;
  final String actorType;
  final String? providerId;
  final List<String> scopePatterns;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'task_id': taskId,
        'project_id': 'PALWAKF_WORKSPACE_MANAGER',
        'title': title,
        'description': description,
        'repository': 'firasfanon/palwakf_workspace_manager',
        'base_sha': baseSha,
        'task_branch': taskBranch,
        'owner_id': ownerId,
        'actor_id': actorId,
        'actor_type': actorType,
        'provider_id': providerId,
        'scope_patterns': scopePatterns,
        'depends_on': const <String>[],
        'dependency_mode': 'INDEPENDENT',
        'risk_class': 'MEDIUM',
        'mutation_class': 'source-write',
        'required_capabilities': const <String>[
          'source.control',
          'runtime.verification',
          'evidence.capture',
        ],
        'required_tests': const <String>['targeted', 'regression'],
      };
}

class NewExtensionDraft {
  const NewExtensionDraft({
    required this.extensionId,
    required this.kind,
    required this.name,
    required this.version,
    required this.sourceKind,
    required this.sourceReference,
    required this.openSource,
    required this.capabilities,
    this.license,
  });

  final String extensionId;
  final String kind;
  final String name;
  final String version;
  final String sourceKind;
  final String sourceReference;
  final bool openSource;
  final String? license;
  final List<String> capabilities;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'extension_id': extensionId,
        'kind': kind,
        'name': name,
        'version': version,
        'source_kind': sourceKind,
        'source_reference': sourceReference,
        'open_source': openSource,
        'license': license,
        'capabilities': capabilities,
        'required_permissions': const <String>[],
        'allowed_projects': const <String>['PALWAKF_WORKSPACE_MANAGER'],
        'risk_class': 'MEDIUM',
        'fork_strategy': 'PREFER_FORK',
      };
}
