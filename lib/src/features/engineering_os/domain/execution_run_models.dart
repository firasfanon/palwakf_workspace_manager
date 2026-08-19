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
        'requires_explicit_authorization': requiresExplicitAuthorization,
      };
}
