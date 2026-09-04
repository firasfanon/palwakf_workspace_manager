import '../../orchestrator/domain/orchestrator_models.dart';
import 'engineering_os_models.dart';

class ExecutionRunRollup {
  const ExecutionRunRollup({
    required this.parentTaskId,
    required this.operatorTaskId,
    required this.parentStatus,
    required this.runStatus,
    required this.signal,
    required this.automaticParentTransition,
    required this.allowedExplicitParentTargets,
    required this.reservedRunState,
    required this.reason,
  });

  final String parentTaskId;
  final String operatorTaskId;
  final String parentStatus;
  final String runStatus;
  final String signal;
  final bool automaticParentTransition;
  final List<String> allowedExplicitParentTargets;
  final bool reservedRunState;
  final String reason;

  factory ExecutionRunRollup.fromJson(Map<String, dynamic> json) {
    return ExecutionRunRollup(
      parentTaskId: json['parent_task_id'] as String,
      operatorTaskId: json['operator_task_id'] as String,
      parentStatus: json['parent_status'] as String,
      runStatus: json['run_status'] as String,
      signal: json['signal'] as String,
      automaticParentTransition:
          json['automatic_parent_transition'] as bool? ?? false,
      allowedExplicitParentTargets:
          (json['allowed_explicit_parent_targets'] as List<dynamic>? ??
                  const <dynamic>[])
              .map((value) => value.toString())
              .toList(growable: false),
      reservedRunState: json['reserved_run_state'] as bool? ?? false,
      reason: json['reason'] as String? ?? '',
    );
  }

  String get arabicSignal => switch (signal) {
        'PENDING' => 'بانتظار التنفيذ',
        'ACTIVE_EXECUTION' => 'تشغيل فعلي جارٍ',
        'VERIFICATION_REQUIRED' => 'بانتظار التحقق المستقل',
        'VERIFIED_RUN_AVAILABLE' => 'تشغيل متحقق متاح للمراجعة',
        'EXECUTION_FAILURE' => 'فشل التشغيل',
        'CANCELLED_RUN' => 'تشغيل ملغى',
        _ => 'حالة توافق محفوظة',
      };
}

class EngineeringExecutionRunView {
  const EngineeringExecutionRunView({
    required this.executionRunId,
    required this.legacyOperatorTaskId,
    required this.parentEngineeringTaskId,
    required this.parentTask,
    required this.operatorTask,
    required this.rollup,
  });

  final String executionRunId;
  final String legacyOperatorTaskId;
  final String parentEngineeringTaskId;
  final EngineeringTask parentTask;
  final OperatorTask operatorTask;
  final ExecutionRunRollup rollup;

  factory EngineeringExecutionRunView.fromJson(Map<String, dynamic> json) {
    return EngineeringExecutionRunView(
      executionRunId: json['execution_run_id'] as String,
      legacyOperatorTaskId: json['legacy_operator_task_id'] as String,
      parentEngineeringTaskId: json['parent_engineering_task_id'] as String,
      parentTask:
          EngineeringTask.fromJson(json['parent_task'] as Map<String, dynamic>),
      operatorTask:
          OperatorTask.fromJson(json['operator_task'] as Map<String, dynamic>),
      rollup:
          ExecutionRunRollup.fromJson(json['rollup'] as Map<String, dynamic>),
    );
  }
}

class EngineeringTaskExecutionContext {
  const EngineeringTaskExecutionContext({
    required this.parentTask,
    required this.runs,
  });

  final EngineeringTask parentTask;
  final List<EngineeringExecutionRunView> runs;

  factory EngineeringTaskExecutionContext.fromJson(Map<String, dynamic> json) {
    return EngineeringTaskExecutionContext(
      parentTask:
          EngineeringTask.fromJson(json['parent_task'] as Map<String, dynamic>),
      runs: (json['runs'] as List<dynamic>? ?? const <dynamic>[])
          .map(
            (value) => EngineeringExecutionRunView.fromJson(
              value as Map<String, dynamic>,
            ),
          )
          .toList(growable: false),
    );
  }
}

class NewExecutionRunDraft {
  const NewExecutionRunDraft({
    required this.executionRunId,
    required this.authorityReference,
    required this.prompt,
    required this.constraints,
    required this.sandbox,
    required this.maxTurns,
    required this.timeoutSeconds,
    required this.idempotencyKey,
    required this.relayProviderId,
    this.providerMode = 'execution_relay',
    this.requiresExplicitAuthorization = true,
  });

  final String executionRunId;
  final String authorityReference;
  final String prompt;
  final List<String> constraints;
  final String sandbox;
  final int maxTurns;
  final int timeoutSeconds;
  final String idempotencyKey;
  final String relayProviderId;
  final String providerMode;
  final bool requiresExplicitAuthorization;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'execution_run_id': executionRunId,
        'authority_reference': authorityReference,
        'prompt': prompt,
        'constraints': constraints,
        'sandbox': sandbox,
        'max_turns': maxTurns,
        'timeout_seconds': timeoutSeconds,
        'idempotency_key': idempotencyKey,
        'relay_provider_id': relayProviderId,
        'provider_mode': providerMode,
        'requires_explicit_authorization': requiresExplicitAuthorization,
      };
}

class ExternalValidationCommandResult {
  const ExternalValidationCommandResult({
    required this.check,
    required this.commandSummary,
    required this.status,
    required this.durationMs,
    required this.outputExcerpt,
    this.exitCode,
  });

  final String check;
  final String commandSummary;
  final String status;
  final int? exitCode;
  final int durationMs;
  final String outputExcerpt;

  factory ExternalValidationCommandResult.fromJson(Map<String, dynamic> json) {
    return ExternalValidationCommandResult(
      check: json['check'] as String? ?? '',
      commandSummary: json['command_summary'] as String? ?? '',
      status: json['status'] as String? ?? 'FAIL',
      exitCode: json['exit_code'] as int?,
      durationMs: json['duration_ms'] as int? ?? 0,
      outputExcerpt: json['output_excerpt'] as String? ?? '',
    );
  }
}

class ExternalValidationResult {
  const ExternalValidationResult({
    required this.checks,
    required this.allPassed,
    required this.validatedPaths,
  });

  final List<ExternalValidationCommandResult> checks;
  final bool allPassed;
  final List<String> validatedPaths;

  factory ExternalValidationResult.fromJson(Map<String, dynamic> json) {
    return ExternalValidationResult(
      checks: (json['checks'] as List<dynamic>? ?? const <dynamic>[])
          .map(
            (value) => ExternalValidationCommandResult.fromJson(
              value as Map<String, dynamic>,
            ),
          )
          .toList(growable: false),
      allPassed: json['all_passed'] as bool? ?? false,
      validatedPaths:
          (json['validated_paths'] as List<dynamic>? ?? const <dynamic>[])
              .map((value) => value.toString())
              .toList(growable: false),
    );
  }
}

class ExternalExecutionWorkspaceStatus {
  const ExternalExecutionWorkspaceStatus({
    required this.executionRunId,
    required this.parentEngineeringTaskId,
    required this.projectId,
    required this.repository,
    required this.taskBranch,
    required this.expectedHead,
    required this.lifecycle,
    required this.prepared,
    required this.authorized,
    required this.changedFiles,
    this.workspacePath,
    this.currentHead,
    this.remoteHead,
    this.validation,
    this.checkpointSha,
    this.lastError,
  });

  final String executionRunId;
  final String parentEngineeringTaskId;
  final String projectId;
  final String repository;
  final String taskBranch;
  final String expectedHead;
  final String? workspacePath;
  final String lifecycle;
  final bool prepared;
  final bool authorized;
  final String? currentHead;
  final String? remoteHead;
  final List<String> changedFiles;
  final ExternalValidationResult? validation;
  final String? checkpointSha;
  final String? lastError;

  bool get validationPassed => validation?.allPassed ?? false;
  bool get checkpointed => lifecycle == 'CHECKPOINTED';

  factory ExternalExecutionWorkspaceStatus.fromJson(
    Map<String, dynamic> json,
  ) {
    final validationJson = json['validation'];
    return ExternalExecutionWorkspaceStatus(
      executionRunId: json['execution_run_id'] as String,
      parentEngineeringTaskId:
          json['parent_engineering_task_id'] as String? ?? '',
      projectId: json['project_id'] as String? ?? '',
      repository: json['repository'] as String,
      taskBranch: json['task_branch'] as String,
      expectedHead: json['expected_head'] as String,
      workspacePath: json['workspace_path'] as String?,
      lifecycle: json['lifecycle'] as String? ?? 'UNPREPARED',
      prepared: json['prepared'] as bool? ?? false,
      authorized: json['authorized'] as bool? ?? false,
      currentHead: json['current_head'] as String?,
      remoteHead: json['remote_head'] as String?,
      changedFiles:
          (json['changed_files'] as List<dynamic>? ?? const <dynamic>[])
              .map((value) => value.toString())
              .toList(growable: false),
      validation: validationJson is Map<String, dynamic>
          ? ExternalValidationResult.fromJson(validationJson)
          : null,
      checkpointSha: json['checkpoint_sha'] as String?,
      lastError: json['last_error'] as String?,
    );
  }
}
