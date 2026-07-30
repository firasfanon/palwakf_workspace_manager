class ExternalProject {
  const ExternalProject({
    required this.projectId,
    required this.displayName,
    required this.repositoryFullName,
    required this.adapter,
    required this.status,
    required this.stack,
    required this.blockers,
    this.observedHead,
    this.defaultBranch,
    this.baselineFingerprint,
  });

  factory ExternalProject.fromJson(Map<String, dynamic> json) {
    return ExternalProject(
      projectId: json['project_id'] as String,
      displayName: json['display_name'] as String,
      repositoryFullName: json['repository_full_name'] as String,
      adapter: json['adapter'] as String,
      status: json['status'] as String,
      observedHead: json['observed_head'] as String?,
      defaultBranch: json['default_branch'] as String?,
      baselineFingerprint: json['baseline_fingerprint'] as String?,
      stack: _strings(json['stack']),
      blockers: _strings(json['blockers']),
    );
  }

  final String projectId;
  final String displayName;
  final String repositoryFullName;
  final String adapter;
  final String status;
  final String? observedHead;
  final String? defaultBranch;
  final String? baselineFingerprint;
  final List<String> stack;
  final List<String> blockers;
}

class ProjectIntakeDraft {
  const ProjectIntakeDraft({
    required this.repositoryFullName,
    required this.displayName,
    required this.adapter,
    this.localRepositoryPath,
  });

  final String repositoryFullName;
  final String displayName;
  final String adapter;
  final String? localRepositoryPath;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'repository_full_name': repositoryFullName,
      'display_name': displayName,
      'adapter': adapter,
      if (localRepositoryPath != null)
        'local_repository_path': localRepositoryPath,
      'authority_mode': 'READ_ONLY_ZERO_MUTATION',
    };
  }
}

class ProjectCommand {
  const ProjectCommand({
    required this.command,
    required this.purpose,
    required this.evidence,
  });

  factory ProjectCommand.fromJson(Map<String, dynamic> json) {
    return ProjectCommand(
      command: json['command'] as String,
      purpose: json['purpose'] as String,
      evidence: json['evidence'] as String,
    );
  }

  final String command;
  final String purpose;
  final String evidence;
}

class ProjectCiReality {
  const ProjectCiReality({
    required this.provider,
    required this.name,
    required this.status,
    this.conclusion,
    this.url,
  });

  factory ProjectCiReality.fromJson(Map<String, dynamic> json) {
    return ProjectCiReality(
      provider: json['provider'] as String,
      name: json['name'] as String,
      status: json['status'] as String,
      conclusion: json['conclusion'] as String?,
      url: json['url'] as String?,
    );
  }

  final String provider;
  final String name;
  final String status;
  final String? conclusion;
  final String? url;
}

class ProjectDeploymentReality {
  const ProjectDeploymentReality({
    required this.provider,
    required this.status,
    required this.evidence,
    this.url,
  });

  factory ProjectDeploymentReality.fromJson(Map<String, dynamic> json) {
    return ProjectDeploymentReality(
      provider: json['provider'] as String,
      status: json['status'] as String,
      evidence: json['evidence'] as String,
      url: json['url'] as String?,
    );
  }

  final String provider;
  final String status;
  final String evidence;
  final String? url;
}

class ProjectToolDecision {
  const ProjectToolDecision({
    required this.adapterId,
    required this.disposition,
    required this.reason,
    required this.evidence,
  });

  factory ProjectToolDecision.fromJson(Map<String, dynamic> json) {
    return ProjectToolDecision(
      adapterId: json['adapter_id'] as String,
      disposition: json['disposition'] as String,
      reason: json['reason'] as String,
      evidence: _strings(json['evidence']),
    );
  }

  final String adapterId;
  final String disposition;
  final String reason;
  final List<String> evidence;
}

class ProjectCapabilityProfile {
  const ProjectCapabilityProfile({
    required this.version,
    required this.selected,
    required this.conditional,
    required this.excluded,
    required this.blocked,
  });

  factory ProjectCapabilityProfile.fromJson(Map<String, dynamic> json) {
    List<ProjectToolDecision> decisions(String key) {
      return (json[key] as List<dynamic>? ?? const <dynamic>[])
          .map(
            (value) => ProjectToolDecision.fromJson(
              value as Map<String, dynamic>,
            ),
          )
          .toList(growable: false);
    }

    return ProjectCapabilityProfile(
      version: json['profile_version'] as String,
      selected: decisions('selected_tools'),
      conditional: decisions('conditional_tools'),
      excluded: decisions('excluded_tools'),
      blocked: decisions('blocked_tools'),
    );
  }

  final String version;
  final List<ProjectToolDecision> selected;
  final List<ProjectToolDecision> conditional;
  final List<ProjectToolDecision> excluded;
  final List<ProjectToolDecision> blocked;

  List<ProjectToolDecision> get all => <ProjectToolDecision>[
        ...selected,
        ...conditional,
        ...excluded,
        ...blocked,
      ];
}

class CandidateWorkItem {
  const CandidateWorkItem({
    required this.rank,
    required this.candidateId,
    required this.title,
    required this.rationale,
    required this.acceptanceTest,
    required this.evidence,
    required this.blocked,
    this.blocker,
  });

  factory CandidateWorkItem.fromJson(Map<String, dynamic> json) {
    return CandidateWorkItem(
      rank: json['rank'] as int,
      candidateId: json['candidate_id'] as String,
      title: json['title'] as String,
      rationale: json['rationale'] as String,
      acceptanceTest: json['acceptance_test'] as String,
      evidence: _strings(json['evidence']),
      blocked: json['blocked'] as bool? ?? false,
      blocker: json['blocker'] as String?,
    );
  }

  final int rank;
  final String candidateId;
  final String title;
  final String rationale;
  final String acceptanceTest;
  final List<String> evidence;
  final bool blocked;
  final String? blocker;
}

class ProjectReality {
  const ProjectReality({
    required this.projectId,
    required this.repositoryFullName,
    required this.defaultBranch,
    required this.observedBranch,
    required this.observedHead,
    required this.driftStatus,
    required this.visibility,
    required this.stack,
    required this.packageManagers,
    required this.toolchainVersions,
    required this.commands,
    required this.ci,
    required this.ciStatus,
    required this.deployments,
    required this.deploymentStatus,
    required this.indicators,
    required this.capabilityProfile,
    required this.candidates,
    required this.blockers,
    required this.baselineFingerprint,
    required this.totalFiles,
    required this.scannedFiles,
    required this.secretRiskFileNames,
    required this.ignoredSecretPolicyPresent,
  });

  factory ProjectReality.fromJson(Map<String, dynamic> json) {
    final tree = json['tree'] as Map<String, dynamic>;
    return ProjectReality(
      projectId: json['project_id'] as String,
      repositoryFullName: json['repository_full_name'] as String,
      defaultBranch: json['default_branch'] as String,
      observedBranch: json['observed_branch'] as String,
      observedHead: json['observed_head'] as String,
      driftStatus: json['drift_status'] as String,
      visibility: json['visibility'] as String,
      stack: _strings(json['stack']),
      packageManagers: _strings(json['package_managers']),
      toolchainVersions: (json['toolchain_versions'] as Map<String, dynamic>)
          .map((key, value) => MapEntry(key, value.toString())),
      commands: _objects(json['commands'])
          .map(ProjectCommand.fromJson)
          .toList(growable: false),
      ci: _objects(json['ci'])
          .map(ProjectCiReality.fromJson)
          .toList(growable: false),
      ciStatus: json['ci_status'] as String,
      deployments: _objects(json['deployments'])
          .map(ProjectDeploymentReality.fromJson)
          .toList(growable: false),
      deploymentStatus: json['deployment_status'] as String,
      indicators: (json['indicators'] as Map<String, dynamic>)
          .map((key, value) => MapEntry(key, value as bool)),
      capabilityProfile: ProjectCapabilityProfile.fromJson(
        json['capability_profile'] as Map<String, dynamic>,
      ),
      candidates: _objects(json['candidate_work_items'])
          .map(CandidateWorkItem.fromJson)
          .toList(growable: false),
      blockers: _strings(json['blockers']),
      baselineFingerprint: json['baseline_fingerprint'] as String,
      totalFiles: tree['total_files'] as int,
      scannedFiles: tree['scanned_files'] as int,
      secretRiskFileNames: _strings(tree['secret_risk_file_names']),
      ignoredSecretPolicyPresent:
          tree['ignored_secret_policy_present'] as bool? ?? false,
    );
  }

  final String projectId;
  final String repositoryFullName;
  final String defaultBranch;
  final String observedBranch;
  final String observedHead;
  final String driftStatus;
  final String visibility;
  final List<String> stack;
  final List<String> packageManagers;
  final Map<String, String> toolchainVersions;
  final List<ProjectCommand> commands;
  final List<ProjectCiReality> ci;
  final String ciStatus;
  final List<ProjectDeploymentReality> deployments;
  final String deploymentStatus;
  final Map<String, bool> indicators;
  final ProjectCapabilityProfile capabilityProfile;
  final List<CandidateWorkItem> candidates;
  final List<String> blockers;
  final String baselineFingerprint;
  final int totalFiles;
  final int scannedFiles;
  final List<String> secretRiskFileNames;
  final bool ignoredSecretPolicyPresent;
}

List<String> _strings(Object? value) {
  return (value as List<dynamic>? ?? const <dynamic>[])
      .map((item) => item.toString())
      .toList(growable: false);
}

List<Map<String, dynamic>> _objects(Object? value) {
  return (value as List<dynamic>? ?? const <dynamic>[])
      .map((item) => item as Map<String, dynamic>)
      .toList(growable: false);
}
