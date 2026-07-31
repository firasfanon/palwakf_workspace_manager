class DashboardSummary {
  const DashboardSummary({
    required this.generatedAt,
    required this.portfolioTotal,
    required this.portfolioReady,
    required this.portfolioAttentionRequired,
    required this.activeRepositoryWriters,
    required this.humanActionRequired,
    required this.tasks,
    required this.tools,
    required this.alertCount,
    required this.criticalAlertCount,
    required this.projects,
    required this.connection,
    required this.checkpoints,
    required this.actions,
    this.managedWorkspace,
  });

  factory DashboardSummary.fromJson(Map<String, dynamic> json) {
    return DashboardSummary(
      generatedAt: DateTime.parse(json['generated_at'] as String),
      portfolioTotal: json['portfolio_total'] as int,
      portfolioReady: json['portfolio_ready'] as int,
      portfolioAttentionRequired: json['portfolio_attention_required'] as int,
      activeRepositoryWriters: json['active_repository_writers'] as int,
      humanActionRequired: json['human_action_required'] as int,
      tasks: TaskStatusSummary.fromJson(json['tasks'] as Map<String, dynamic>),
      tools: ToolHealthSummary.fromJson(json['tools'] as Map<String, dynamic>),
      alertCount: json['alert_count'] as int,
      criticalAlertCount: json['critical_alert_count'] as int,
      projects: (json['projects'] as List<dynamic>)
          .map((value) =>
              PortfolioProjectSummary.fromJson(value as Map<String, dynamic>))
          .toList(growable: false),
      connection: ConnectionReadinessSummary.fromJson(
        json['connection'] as Map<String, dynamic>,
      ),
      checkpoints: (json['checkpoints'] as List<dynamic>)
          .map((value) =>
              ResumeCheckpointSummary.fromJson(value as Map<String, dynamic>))
          .toList(growable: false),
      actions: (json['actions'] as List<dynamic>)
          .map((value) =>
              DashboardAction.fromJson(value as Map<String, dynamic>))
          .toList(growable: false),
      managedWorkspace: json['managed_workspace'] == null
          ? null
          : ManagedWorkspaceStatus.fromJson(
              json['managed_workspace'] as Map<String, dynamic>,
            ),
    );
  }

  final DateTime generatedAt;
  final int portfolioTotal;
  final int portfolioReady;
  final int portfolioAttentionRequired;
  final int activeRepositoryWriters;
  final int humanActionRequired;
  final TaskStatusSummary tasks;
  final ToolHealthSummary tools;
  final int alertCount;
  final int criticalAlertCount;
  final List<PortfolioProjectSummary> projects;
  final ConnectionReadinessSummary connection;
  final List<ResumeCheckpointSummary> checkpoints;
  final List<DashboardAction> actions;
  final ManagedWorkspaceStatus? managedWorkspace;
}

class CapabilityState {
  const CapabilityState({required this.status, this.blocker});

  factory CapabilityState.fromJson(Map<String, dynamic> json) {
    return CapabilityState(
      status: json['status'] as String,
      blocker: json['blocker'] as String?,
    );
  }

  final String status;
  final String? blocker;
}

class ManagedWorkspaceStatus {
  const ManagedWorkspaceStatus({
    required this.registered,
    required this.repository,
    required this.branch,
    required this.pullRequestNumber,
    required this.pullRequestState,
    required this.ciStatus,
    required this.previewStatus,
    required this.github,
    required this.agentsSdk,
    required this.codex,
    required this.authentication,
    required this.orchestrator,
    required this.refreshedAt,
    this.localHead,
    this.remoteHead,
    this.pullRequestHead,
    this.worktreeClean,
    this.activeWriterTaskId,
    this.currentTaskId,
    this.latestVerifiedTaskId,
  });

  factory ManagedWorkspaceStatus.fromJson(Map<String, dynamic> json) {
    CapabilityState capability(String key) =>
        CapabilityState.fromJson(json[key] as Map<String, dynamic>);
    return ManagedWorkspaceStatus(
      registered: json['registered'] as bool,
      repository: json['repository'] as String,
      branch: json['branch'] as String,
      pullRequestNumber: json['pull_request_number'] as int,
      localHead: json['local_head'] as String?,
      remoteHead: json['remote_head'] as String?,
      pullRequestHead: json['pull_request_head'] as String?,
      worktreeClean: json['worktree_clean'] as bool?,
      pullRequestState: json['pull_request_state'] as String,
      ciStatus: json['ci_status'] as String,
      previewStatus: json['preview_status'] as String,
      activeWriterTaskId: json['active_writer_task_id'] as String?,
      currentTaskId: json['current_task_id'] as String?,
      latestVerifiedTaskId: json['latest_verified_task_id'] as String?,
      github: capability('github'),
      agentsSdk: capability('agents_sdk'),
      codex: capability('codex'),
      authentication: capability('authentication'),
      orchestrator: capability('orchestrator'),
      refreshedAt: DateTime.parse(json['refreshed_at'] as String),
    );
  }

  final bool registered;
  final String repository;
  final String branch;
  final int pullRequestNumber;
  final String? localHead;
  final String? remoteHead;
  final String? pullRequestHead;
  final bool? worktreeClean;
  final String pullRequestState;
  final String ciStatus;
  final String previewStatus;
  final String? activeWriterTaskId;
  final String? currentTaskId;
  final String? latestVerifiedTaskId;
  final CapabilityState github;
  final CapabilityState agentsSdk;
  final CapabilityState codex;
  final CapabilityState authentication;
  final CapabilityState orchestrator;
  final DateTime refreshedAt;
}

class TaskStatusSummary {
  const TaskStatusSummary({
    required this.total,
    required this.queued,
    required this.running,
    required this.pendingVerification,
    required this.verified,
    required this.failed,
    required this.stale,
    required this.activeTaskIds,
    this.latestVerifiedTaskId,
    this.latestVerifiedAt,
  });

  factory TaskStatusSummary.fromJson(Map<String, dynamic> json) {
    return TaskStatusSummary(
      total: json['total'] as int,
      queued: json['queued'] as int,
      running: json['running'] as int,
      pendingVerification: json['pending_verification'] as int,
      verified: json['verified'] as int,
      failed: json['failed'] as int,
      stale: json['stale'] as int,
      activeTaskIds:
          List<String>.from(json['active_task_ids'] as List<dynamic>),
      latestVerifiedTaskId: json['latest_verified_task_id'] as String?,
      latestVerifiedAt: _date(json['latest_verified_at']),
    );
  }

  final int total;
  final int queued;
  final int running;
  final int pendingVerification;
  final int verified;
  final int failed;
  final int stale;
  final List<String> activeTaskIds;
  final String? latestVerifiedTaskId;
  final DateTime? latestVerifiedAt;
}

class ToolHealthSummary {
  const ToolHealthSummary({
    required this.total,
    required this.healthy,
    required this.degraded,
    required this.blocked,
    required this.stale,
    required this.unknown,
    required this.requiredAttention,
  });

  factory ToolHealthSummary.fromJson(Map<String, dynamic> json) {
    return ToolHealthSummary(
      total: json['total'] as int,
      healthy: json['healthy'] as int,
      degraded: json['degraded'] as int,
      blocked: json['blocked'] as int,
      stale: json['stale'] as int,
      unknown: json['unknown'] as int,
      requiredAttention: json['required_attention'] as int,
    );
  }

  final int total;
  final int healthy;
  final int degraded;
  final int blocked;
  final int stale;
  final int unknown;
  final int requiredAttention;
}

class PortfolioProjectSummary {
  const PortfolioProjectSummary({
    required this.projectId,
    required this.displayName,
    required this.repositoryFullName,
    required this.status,
    required this.readiness,
    required this.attentionRequired,
    required this.freshness,
    required this.stack,
    required this.ciStatus,
    required this.deploymentStatus,
    required this.driftStatus,
    required this.blockers,
    required this.toolGapCount,
    required this.taskCount,
    required this.activeWriter,
    required this.evidenceCount,
    this.observedBranch,
    this.observedHead,
    this.lastProbeAt,
    this.topCandidateId,
    this.topCandidateTitle,
  });

  factory PortfolioProjectSummary.fromJson(Map<String, dynamic> json) {
    return PortfolioProjectSummary(
      projectId: json['project_id'] as String,
      displayName: json['display_name'] as String,
      repositoryFullName: json['repository_full_name'] as String,
      status: json['status'] as String,
      readiness: json['readiness'] as String,
      attentionRequired: json['attention_required'] as bool,
      freshness: json['freshness'] as String,
      stack: List<String>.from(json['stack'] as List<dynamic>),
      ciStatus: json['ci_status'] as String,
      deploymentStatus: json['deployment_status'] as String,
      driftStatus: json['drift_status'] as String,
      blockers: List<String>.from(json['blockers'] as List<dynamic>),
      toolGapCount: json['tool_gap_count'] as int,
      taskCount: json['task_count'] as int,
      activeWriter: json['active_writer'] as bool,
      evidenceCount: json['evidence_count'] as int,
      observedBranch: json['observed_branch'] as String?,
      observedHead: json['observed_head'] as String?,
      lastProbeAt: _date(json['last_probe_at']),
      topCandidateId: json['top_candidate_id'] as String?,
      topCandidateTitle: json['top_candidate_title'] as String?,
    );
  }

  final String projectId;
  final String displayName;
  final String repositoryFullName;
  final String status;
  final String readiness;
  final bool attentionRequired;
  final String freshness;
  final List<String> stack;
  final String ciStatus;
  final String deploymentStatus;
  final String driftStatus;
  final List<String> blockers;
  final int toolGapCount;
  final int taskCount;
  final bool activeWriter;
  final int evidenceCount;
  final String? observedBranch;
  final String? observedHead;
  final DateTime? lastProbeAt;
  final String? topCandidateId;
  final String? topCandidateTitle;
}

class ConnectionReadinessSummary {
  const ConnectionReadinessSummary({
    required this.mode,
    required this.ready,
    required this.authenticationConfigured,
    required this.storeHealthy,
    required this.workersStarted,
    required this.localSecure,
    required this.chatgptLiveState,
    required this.executionHostCompatibility,
    required this.toolExecutorCompatibility,
    this.lastSuccessfulCodexExecutionAt,
  });

  factory ConnectionReadinessSummary.fromJson(Map<String, dynamic> json) {
    return ConnectionReadinessSummary(
      mode: json['mode'] as String,
      ready: json['ready'] as bool,
      authenticationConfigured: json['authentication_configured'] as bool,
      storeHealthy: json['store_healthy'] as bool,
      workersStarted: json['workers_started'] as bool,
      localSecure: json['local_secure'] as bool,
      chatgptLiveState: json['chatgpt_live_state'] as String,
      executionHostCompatibility:
          json['execution_host_compatibility'] as String,
      toolExecutorCompatibility: json['tool_executor_compatibility'] as String,
      lastSuccessfulCodexExecutionAt:
          _date(json['last_successful_codex_execution_at']),
    );
  }

  final String mode;
  final bool ready;
  final bool authenticationConfigured;
  final bool storeHealthy;
  final bool workersStarted;
  final bool localSecure;
  final String chatgptLiveState;
  final String executionHostCompatibility;
  final String toolExecutorCompatibility;
  final DateTime? lastSuccessfulCodexExecutionAt;
}

class OperationalAlert {
  const OperationalAlert({
    required this.alertId,
    required this.severity,
    required this.sourceKind,
    required this.sourceId,
    required this.code,
    required this.message,
    required this.requiredAction,
    required this.observedAt,
    required this.freshness,
    this.evidenceReference,
  });

  factory OperationalAlert.fromJson(Map<String, dynamic> json) {
    return OperationalAlert(
      alertId: json['alert_id'] as String,
      severity: json['severity'] as String,
      sourceKind: json['source_kind'] as String,
      sourceId: json['source_id'] as String,
      code: json['code'] as String,
      message: json['message'] as String,
      requiredAction: json['required_action'] as String,
      observedAt: DateTime.parse(json['observed_at'] as String),
      freshness: json['freshness'] as String,
      evidenceReference: json['evidence_reference'] as String?,
    );
  }

  final String alertId;
  final String severity;
  final String sourceKind;
  final String sourceId;
  final String code;
  final String message;
  final String requiredAction;
  final DateTime observedAt;
  final String freshness;
  final String? evidenceReference;
}

class RecentActivity {
  const RecentActivity({
    required this.activityId,
    required this.kind,
    required this.subjectId,
    required this.title,
    required this.detail,
    required this.occurredAt,
    required this.status,
    required this.provenance,
  });

  factory RecentActivity.fromJson(Map<String, dynamic> json) {
    return RecentActivity(
      activityId: json['activity_id'] as String,
      kind: json['kind'] as String,
      subjectId: json['subject_id'] as String,
      title: json['title'] as String,
      detail: json['detail'] as String,
      occurredAt: DateTime.parse(json['occurred_at'] as String),
      status: json['status'] as String,
      provenance: json['provenance'] as String,
    );
  }

  final String activityId;
  final String kind;
  final String subjectId;
  final String title;
  final String detail;
  final DateTime occurredAt;
  final String status;
  final String provenance;
}

class EvidenceIndexItem {
  const EvidenceIndexItem({
    required this.evidenceId,
    required this.associationKind,
    required this.evidenceType,
    required this.safeReference,
    required this.status,
    required this.provenance,
    this.associationId,
    this.observedAt,
    this.fingerprint,
  });

  factory EvidenceIndexItem.fromJson(Map<String, dynamic> json) {
    return EvidenceIndexItem(
      evidenceId: json['evidence_id'] as String,
      associationKind: json['association_kind'] as String,
      associationId: json['association_id'] as String?,
      evidenceType: json['evidence_type'] as String,
      observedAt: _date(json['observed_at']),
      fingerprint: json['fingerprint'] as String?,
      safeReference: json['safe_reference'] as String,
      status: json['status'] as String,
      provenance: json['provenance'] as String,
    );
  }

  final String evidenceId;
  final String associationKind;
  final String? associationId;
  final String evidenceType;
  final DateTime? observedAt;
  final String? fingerprint;
  final String safeReference;
  final String status;
  final String provenance;
}

class ResumeCheckpointSummary {
  const ResumeCheckpointSummary({
    required this.checkpointId,
    required this.taskId,
    required this.status,
    required this.updatedAt,
    required this.nextAction,
    this.evidenceReference,
  });

  factory ResumeCheckpointSummary.fromJson(Map<String, dynamic> json) {
    return ResumeCheckpointSummary(
      checkpointId: json['checkpoint_id'] as String,
      taskId: json['task_id'] as String,
      status: json['status'] as String,
      updatedAt: DateTime.parse(json['updated_at'] as String),
      nextAction: json['next_action'] as String,
      evidenceReference: json['evidence_reference'] as String?,
    );
  }

  final String checkpointId;
  final String taskId;
  final String status;
  final DateTime updatedAt;
  final String nextAction;
  final String? evidenceReference;
}

class DashboardAction {
  const DashboardAction({
    required this.actionId,
    required this.label,
    required this.route,
    required this.enabled,
    required this.authority,
    this.disabledReason,
  });

  factory DashboardAction.fromJson(Map<String, dynamic> json) {
    return DashboardAction(
      actionId: json['action_id'] as String,
      label: json['label'] as String,
      route: json['route'] as String,
      enabled: json['enabled'] as bool,
      disabledReason: json['disabled_reason'] as String?,
      authority: json['authority'] as String,
    );
  }

  final String actionId;
  final String label;
  final String route;
  final bool enabled;
  final String? disabledReason;
  final String authority;
}

DateTime? _date(dynamic value) =>
    value is String ? DateTime.parse(value) : null;
