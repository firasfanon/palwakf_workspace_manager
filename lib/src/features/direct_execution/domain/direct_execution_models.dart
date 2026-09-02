enum DirectWorkspaceItemClass {
  research,
  privateProject;

  String get wireValue => switch (this) {
        research => 'RESEARCH',
        privateProject => 'PRIVATE_PROJECT',
      };

  String get arabicLabel => switch (this) {
        research => 'بحث',
        privateProject => 'مشروع خاص',
      };
}

enum DirectExecutionStatus {
  completed,
  failed;

  static DirectExecutionStatus fromWire(String value) => switch (value) {
        'COMPLETED' => DirectExecutionStatus.completed,
        _ => DirectExecutionStatus.failed,
      };
}

class DirectExecutionDraft {
  const DirectExecutionDraft({
    required this.itemId,
    required this.itemClass,
    required this.title,
    required this.prompt,
    this.projectUid,
    this.technicalId,
    this.contextSummary = '',
  });

  final String itemId;
  final DirectWorkspaceItemClass itemClass;
  final String title;
  final String prompt;
  final String? projectUid;
  final String? technicalId;
  final String contextSummary;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'item_id': itemId,
        'item_class': itemClass.wireValue,
        'title': title,
        'prompt': prompt,
        'project_uid': projectUid,
        'technical_id': technicalId,
        'context_summary': contextSummary,
      };
}

class DirectExecutionReceipt {
  const DirectExecutionReceipt({
    required this.sessionId,
    required this.itemId,
    required this.itemClass,
    required this.title,
    required this.status,
    required this.model,
    required this.promptSha256,
    required this.route,
    required this.palwakfGovernanceUsed,
    required this.engineeringTaskUsed,
    required this.operatorAuthorizationUsed,
    required this.toolPlanUsed,
    this.projectUid,
    this.technicalId,
    this.providerId,
    this.output = '',
    this.errorCode,
  });

  final String sessionId;
  final String itemId;
  final String itemClass;
  final String? projectUid;
  final String? technicalId;
  final String title;
  final String route;
  final DirectExecutionStatus status;
  final String? providerId;
  final String model;
  final String promptSha256;
  final String output;
  final String? errorCode;
  final bool palwakfGovernanceUsed;
  final bool engineeringTaskUsed;
  final bool operatorAuthorizationUsed;
  final bool toolPlanUsed;

  factory DirectExecutionReceipt.fromJson(Map<String, dynamic> json) {
    return DirectExecutionReceipt(
      sessionId: json['session_id']?.toString() ?? '',
      itemId: json['item_id']?.toString() ?? '',
      itemClass: json['item_class']?.toString() ?? '',
      projectUid: json['project_uid']?.toString(),
      technicalId: json['technical_id']?.toString(),
      title: json['title']?.toString() ?? '',
      route: json['route']?.toString() ?? '',
      status: DirectExecutionStatus.fromWire(json['status']?.toString() ?? ''),
      providerId: json['provider_id']?.toString(),
      model: json['model']?.toString() ?? '',
      promptSha256: json['prompt_sha256']?.toString() ?? '',
      output: json['output']?.toString() ?? '',
      errorCode: json['error_code']?.toString(),
      palwakfGovernanceUsed: json['palwakf_governance_used'] as bool? ?? false,
      engineeringTaskUsed: json['engineering_task_used'] as bool? ?? false,
      operatorAuthorizationUsed:
          json['operator_authorization_used'] as bool? ?? false,
      toolPlanUsed: json['tool_plan_used'] as bool? ?? false,
    );
  }
}
