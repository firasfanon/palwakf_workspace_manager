enum OrchestratorTaskStatus {
  pending,
  running,
  awaitingApproval,
  failed,
  pendingVerification,
  verified,
  drifted,
  timedOut,
  cancelled;

  static OrchestratorTaskStatus fromWire(String value) {
    return switch (value) {
      'pending' => pending,
      'running' => running,
      'awaiting_approval' => awaitingApproval,
      'failed' => failed,
      'pending_verification' => pendingVerification,
      'verified' => verified,
      'drifted' => drifted,
      'timed_out' => timedOut,
      'cancelled' => cancelled,
      _ => throw FormatException('Unknown orchestrator task status: $value'),
    };
  }

  String get wireValue => switch (this) {
        pending => 'pending',
        running => 'running',
        awaitingApproval => 'awaiting_approval',
        failed => 'failed',
        pendingVerification => 'pending_verification',
        verified => 'verified',
        drifted => 'drifted',
        timedOut => 'timed_out',
        cancelled => 'cancelled',
      };

  String get arabicLabel => switch (this) {
        pending => 'بانتظار الإرسال',
        running => 'قيد التنفيذ',
        awaitingApproval => 'بانتظار الموافقة',
        failed => 'فشل',
        pendingVerification => 'بانتظار التحقق',
        verified => 'متحقق',
        drifted => 'انحراف في HEAD',
        timedOut => 'انتهت المهلة',
        cancelled => 'ملغاة',
      };
}

class RuntimeCapabilities {
  const RuntimeCapabilities({
    required this.version,
    required this.taskLifecycle,
    required this.manualRelayFallback,
    required this.capabilityRouting,
    required this.toolDecisionTrace,
    required this.reconciliation,
    required this.automaticAgentsAvailable,
    required this.databaseConnected,
    required this.productionMutation,
  });

  factory RuntimeCapabilities.fromJson(Map<String, dynamic> json) {
    return RuntimeCapabilities(
      version: json['version'] as String,
      taskLifecycle: json['task_lifecycle'] as bool,
      manualRelayFallback: json['manual_relay_fallback'] as bool,
      capabilityRouting: json['capability_routing'] as bool,
      toolDecisionTrace: json['tool_decision_trace'] as bool,
      reconciliation: json['planned_actual_reconciliation'] as bool,
      automaticAgentsAvailable: json['automatic_agents_available'] as bool,
      databaseConnected: json['database_connected'] as bool,
      productionMutation: json['production_mutation'] as bool,
    );
  }

  final String version;
  final bool taskLifecycle;
  final bool manualRelayFallback;
  final bool capabilityRouting;
  final bool toolDecisionTrace;
  final bool reconciliation;
  final bool automaticAgentsAvailable;
  final bool databaseConnected;
  final bool productionMutation;
}

class TaskEvent {
  const TaskEvent({
    required this.type,
    required this.status,
    required this.message,
    required this.occurredAt,
  });

  factory TaskEvent.fromJson(Map<String, dynamic> json) {
    return TaskEvent(
      type: json['event_type'] as String,
      status: OrchestratorTaskStatus.fromWire(json['status'] as String),
      message: json['message'] as String,
      occurredAt: DateTime.parse(json['occurred_at'] as String),
    );
  }

  final String type;
  final OrchestratorTaskStatus status;
  final String message;
  final DateTime occurredAt;
}

class OperatorTask {
  const OperatorTask({
    required this.taskId,
    required this.projectId,
    required this.repository,
    required this.branch,
    required this.expectedHead,
    required this.authorityReference,
    required this.prompt,
    required this.constraints,
    required this.sandbox,
    required this.maxTurns,
    required this.timeoutSeconds,
    required this.idempotencyKey,
    required this.dispatchMode,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
    required this.lastEvent,
    required this.events,
    required this.changedFiles,
    required this.tests,
    required this.evidence,
    this.automaticFailureCode,
    this.blocker,
    this.threadId,
    this.executionReceipt,
    this.beforeHead,
    this.afterHead,
    this.verificationReceipt,
  });

  factory OperatorTask.fromJson(Map<String, dynamic> json) {
    List<String> strings(String key) =>
        (json[key] as List<dynamic>? ?? const <dynamic>[])
            .map((value) => value as String)
            .toList(growable: false);

    return OperatorTask(
      taskId: json['task_id'] as String,
      projectId: json['project_id'] as String,
      repository: json['repository'] as String,
      branch: json['branch'] as String,
      expectedHead: json['expected_head'] as String,
      authorityReference: json['authority_reference'] as String,
      prompt: json['prompt'] as String,
      constraints: strings('constraints'),
      sandbox: json['sandbox'] as String,
      maxTurns: json['max_turns'] as int,
      timeoutSeconds: json['timeout_seconds'] as int,
      idempotencyKey: json['idempotency_key'] as String,
      automaticFailureCode: json['automatic_failure_code'] as String?,
      dispatchMode: json['dispatch_mode'] as String,
      status: OrchestratorTaskStatus.fromWire(json['status'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
      lastEvent: json['last_event'] as String,
      blocker: json['blocker'] as String?,
      threadId: json['thread_id'] as String?,
      executionReceipt: json['execution_receipt'] as String?,
      beforeHead: json['before_head'] as String?,
      afterHead: json['after_head'] as String?,
      changedFiles: strings('changed_files'),
      tests: strings('tests'),
      evidence: strings('evidence'),
      verificationReceipt: json['verification_receipt'] as String?,
      events: (json['events'] as List<dynamic>? ?? const <dynamic>[])
          .map(
            (value) => TaskEvent.fromJson(value as Map<String, dynamic>),
          )
          .toList(growable: false),
    );
  }

  final String taskId;
  final String projectId;
  final String repository;
  final String branch;
  final String expectedHead;
  final String authorityReference;
  final String prompt;
  final List<String> constraints;
  final String sandbox;
  final int maxTurns;
  final int timeoutSeconds;
  final String idempotencyKey;
  final String? automaticFailureCode;
  final String dispatchMode;
  final OrchestratorTaskStatus status;
  final DateTime createdAt;
  final DateTime updatedAt;
  final String lastEvent;
  final String? blocker;
  final String? threadId;
  final String? executionReceipt;
  final String? beforeHead;
  final String? afterHead;
  final List<String> changedFiles;
  final List<String> tests;
  final List<String> evidence;
  final String? verificationReceipt;
  final List<TaskEvent> events;

  bool get manualFallbackAvailable =>
      automaticFailureCode != null || dispatchMode == 'user_relay_fallback';
}

class TaskDraft {
  const TaskDraft({
    required this.taskId,
    required this.projectId,
    required this.repository,
    required this.branch,
    required this.expectedHead,
    required this.authorityReference,
    required this.prompt,
    required this.constraints,
    required this.sandbox,
    required this.maxTurns,
    required this.timeoutSeconds,
    required this.idempotencyKey,
    this.automaticFailureCode,
  });

  final String taskId;
  final String projectId;
  final String repository;
  final String branch;
  final String expectedHead;
  final String authorityReference;
  final String prompt;
  final List<String> constraints;
  final String sandbox;
  final int maxTurns;
  final int timeoutSeconds;
  final String idempotencyKey;
  final String? automaticFailureCode;

  Map<String, String> validate() {
    final errors = <String, String>{};
    if (taskId.trim().isEmpty) errors['task_id'] = 'معرّف المهمة مطلوب';
    if (authorityReference.trim().isEmpty) {
      errors['authority_reference'] = 'مرجع التفويض مطلوب';
    }
    if (!RegExp(r'^[0-9a-fA-F]{40}$').hasMatch(expectedHead.trim())) {
      errors['expected_head'] = 'HEAD كامل من 40 محرفًا مطلوب';
    }
    if (prompt.trim().isEmpty) errors['prompt'] = 'وصف المهمة مطلوب';
    if (constraints.isEmpty) errors['constraints'] = 'قيد واحد مطلوب على الأقل';
    if (maxTurns < 1) errors['max_turns'] = 'عدد الجولات مطلوب';
    if (timeoutSeconds < 30) errors['timeout_seconds'] = 'المهلة مطلوبة';
    if (idempotencyKey.trim().length < 8) {
      errors['idempotency_key'] = 'مفتاح idempotency مطلوب';
    }
    return errors;
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'task_id': taskId.trim(),
      'project_id': projectId,
      'repository': repository,
      'branch': branch,
      'expected_head': expectedHead.trim(),
      'authority_reference': authorityReference.trim(),
      'prompt': prompt.trim(),
      'constraints': constraints,
      'approval_policy': 'never',
      'sandbox': sandbox,
      'max_turns': maxTurns,
      'timeout_seconds': timeoutSeconds,
      'idempotency_key': idempotencyKey.trim(),
      'automatic_failure_code': automaticFailureCode,
      'manual_fallback_selected': false,
    };
  }
}

class ManualDispatchPackage {
  const ManualDispatchPackage({
    required this.receipt,
    required this.taskId,
    required this.canonicalHash,
    required this.generatedAt,
    required this.envelope,
  });

  factory ManualDispatchPackage.fromJson(Map<String, dynamic> json) {
    return ManualDispatchPackage(
      receipt: json['package_receipt'] as String,
      taskId: json['task_id'] as String,
      canonicalHash: json['canonical_envelope_sha256'] as String,
      generatedAt: DateTime.parse(json['generated_at'] as String),
      envelope: Map<String, dynamic>.unmodifiable(json),
    );
  }

  final String receipt;
  final String taskId;
  final String canonicalHash;
  final DateTime generatedAt;
  final Map<String, dynamic> envelope;
}

class AdapterExclusion {
  const AdapterExclusion({required this.adapterId, required this.reason});

  factory AdapterExclusion.fromJson(Map<String, dynamic> json) {
    return AdapterExclusion(
      adapterId: json['adapter_id'] as String,
      reason: json['reason'] as String,
    );
  }

  final String adapterId;
  final String reason;
}

class ToolDecision {
  const ToolDecision({
    required this.capabilityId,
    required this.selectedReason,
    required this.exclusions,
    required this.permissionStatus,
    required this.approvalRequired,
    required this.blocked,
    required this.substituted,
    this.selectedAdapterId,
  });

  factory ToolDecision.fromJson(Map<String, dynamic> json) {
    return ToolDecision(
      capabilityId: json['capability_id'] as String,
      selectedAdapterId: json['selected_adapter_id'] as String?,
      selectedReason: json['selected_reason'] as String,
      exclusions: (json['excluded_adapters_with_reason'] as List<dynamic>? ??
              const <dynamic>[])
          .map(
            (value) => AdapterExclusion.fromJson(value as Map<String, dynamic>),
          )
          .toList(growable: false),
      permissionStatus: json['permission_status'] as String,
      approvalRequired: json['approval_required'] as bool,
      blocked: json['blocked'] as bool,
      substituted: json['substituted'] as bool,
    );
  }

  final String capabilityId;
  final String? selectedAdapterId;
  final String selectedReason;
  final List<AdapterExclusion> exclusions;
  final String permissionStatus;
  final bool approvalRequired;
  final bool blocked;
  final bool substituted;
}

class ToolPlan {
  const ToolPlan({
    required this.decisions,
    required this.dispatchBlocked,
    required this.blockers,
  });

  factory ToolPlan.fromJson(Map<String, dynamic> json) {
    return ToolPlan(
      decisions: (json['decisions'] as List<dynamic>)
          .map(
            (value) => ToolDecision.fromJson(value as Map<String, dynamic>),
          )
          .toList(growable: false),
      dispatchBlocked: json['dispatch_blocked'] as bool,
      blockers: (json['blockers'] as List<dynamic>)
          .map((value) => value as String)
          .toList(growable: false),
    );
  }

  final List<ToolDecision> decisions;
  final bool dispatchBlocked;
  final List<String> blockers;
}

class ToolInvocation {
  const ToolInvocation({
    required this.capabilityId,
    required this.adapterId,
    required this.status,
    required this.occurredAt,
  });

  factory ToolInvocation.fromJson(Map<String, dynamic> json) {
    return ToolInvocation(
      capabilityId: json['capability_id'] as String,
      adapterId: json['adapter_id'] as String,
      status: json['status'] as String,
      occurredAt: DateTime.parse(json['occurred_at'] as String),
    );
  }

  final String capabilityId;
  final String adapterId;
  final String status;
  final DateTime occurredAt;
}

class ToolReconciliation {
  const ToolReconciliation({
    required this.planned,
    required this.actual,
    required this.missing,
    required this.unexpected,
    required this.reconciled,
  });

  factory ToolReconciliation.fromJson(Map<String, dynamic> json) {
    List<String> values(String key) => (json[key] as List<dynamic>)
        .map((value) => value as String)
        .toList(growable: false);

    return ToolReconciliation(
      planned: values('planned_adapter_ids'),
      actual: values('actual_adapter_ids'),
      missing: values('missing_adapter_ids'),
      unexpected: values('unexpected_adapter_ids'),
      reconciled: json['reconciled'] as bool,
    );
  }

  final List<String> planned;
  final List<String> actual;
  final List<String> missing;
  final List<String> unexpected;
  final bool reconciled;
}
