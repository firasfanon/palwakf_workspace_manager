import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/orchestrator_models.dart';

class OrchestratorApiException implements Exception {
  const OrchestratorApiException({
    required this.code,
    required this.message,
    required this.recoverable,
  });

  final String code;
  final String message;
  final bool recoverable;

  @override
  String toString() => '$code: $message';
}

abstract interface class OrchestratorApi {
  Future<RuntimeCapabilities> capabilities();

  Future<List<OperatorTask>> listTasks();

  Future<List<ToolOperationalHealth>> toolsHealth();

  Future<ToolOperationalHealth> toolHealth(String adapterId);

  Future<List<ToolHealthAlert>> toolAlerts();

  Future<ToolOperationalHealth> probeTool(String adapterId);

  Future<OperatorTask> createTask(TaskDraft draft);

  Future<OperatorTask> createProofTask();

  Future<OperatorTask> authorize(OperatorTask task);

  Future<OperatorTask> taskStatus(String taskId);

  Future<ToolPlan> planTools(String taskId);

  Future<ToolPlan> toolDecisions(String taskId);

  Future<List<ToolInvocation>> toolInvocations(String taskId);

  Future<ToolReconciliation> toolReconciliation(String taskId);

  Future<OperatorTask> dispatch(String taskId);

  Future<OperatorTask> continueTask(String taskId);

  Future<OperatorTask> cancel(String taskId);

  Future<OperatorTask> verify({
    required String taskId,
    required String receipt,
    required String head,
  });

  Future<ManualDispatchPackage> generateManualPackage(String taskId);

  Future<OperatorTask> markManualDispatched({
    required String taskId,
    required String packageReceipt,
  });

  Future<OperatorTask> recordManualAcknowledgement({
    required String taskId,
    required String packageReceipt,
    required String threadReference,
  });

  Future<OperatorTask> importManualResult({
    required String taskId,
    required Map<String, dynamic> result,
  });
}

class HttpOrchestratorApiClient implements OrchestratorApi {
  HttpOrchestratorApiClient({
    http.Client? client,
    String? baseUrl,
    this.bearerToken,
    this.timeout = const Duration(seconds: 15),
  })  : _client = client ?? http.Client(),
        baseUrl = (baseUrl ??
                const String.fromEnvironment(
                  'ORCHESTRATOR_API_BASE_URL',
                  defaultValue: 'http://127.0.0.1:8421',
                ))
            .replaceFirst(RegExp(r'/$'), '');

  final http.Client _client;
  final String baseUrl;
  final String? bearerToken;
  final Duration timeout;

  @override
  Future<RuntimeCapabilities> capabilities() async {
    return RuntimeCapabilities.fromJson(
      await _getObject('/v1/capabilities'),
    );
  }

  @override
  Future<List<OperatorTask>> listTasks() async {
    final response = await _request('GET', '/v1/tasks');
    final values = jsonDecode(response.body) as List<dynamic>;
    return values
        .map((value) => OperatorTask.fromJson(value as Map<String, dynamic>))
        .toList(growable: false);
  }

  @override
  Future<List<ToolOperationalHealth>> toolsHealth() async {
    final response = await _request('GET', '/v1/tools/health');
    return (jsonDecode(response.body) as List<dynamic>)
        .map(
          (value) =>
              ToolOperationalHealth.fromJson(value as Map<String, dynamic>),
        )
        .toList(growable: false);
  }

  @override
  Future<ToolOperationalHealth> toolHealth(String adapterId) async {
    return ToolOperationalHealth.fromJson(
      await _getObject('/v1/tools/$adapterId/health'),
    );
  }

  @override
  Future<List<ToolHealthAlert>> toolAlerts() async {
    final response = await _request('GET', '/v1/tools/alerts');
    return (jsonDecode(response.body) as List<dynamic>)
        .map(
          (value) => ToolHealthAlert.fromJson(value as Map<String, dynamic>),
        )
        .toList(growable: false);
  }

  @override
  Future<ToolOperationalHealth> probeTool(String adapterId) async {
    return ToolOperationalHealth.fromJson(
      await _postObject(
        '/v1/tools/$adapterId/probe',
        const <String, dynamic>{'requested_evidence': <String>[]},
      ),
    );
  }

  @override
  Future<OperatorTask> createTask(TaskDraft draft) async {
    return OperatorTask.fromJson(
      await _postObject('/v1/tasks', draft.toJson()),
    );
  }

  @override
  Future<OperatorTask> createProofTask() async {
    return OperatorTask.fromJson(
      await _postObject('/v1/local-product/proof-task', null),
    );
  }

  @override
  Future<OperatorTask> authorize(OperatorTask task) async {
    return OperatorTask.fromJson(
      await _postObject(
        '/v1/tasks/${task.taskId}/authorize',
        <String, dynamic>{
          'expected_head': task.expectedHead,
          'authority_reference': task.authorityReference,
          'acknowledgement': 'AUTHORIZE_GOVERNED_EXECUTION',
        },
      ),
    );
  }

  @override
  Future<OperatorTask> taskStatus(String taskId) async {
    return OperatorTask.fromJson(await _getObject('/v1/tasks/$taskId'));
  }

  @override
  Future<ToolPlan> planTools(String taskId) async {
    return ToolPlan.fromJson(
      await _postObject(
        '/v1/tasks/$taskId/tool-plan',
        <String, dynamic>{
          'task_id': taskId,
          'project_id': 'PALWAKF_WORKSPACE_MANAGER',
          'required_capability_ids': <String>[],
          'optional_capability_ids': <String>[],
          'task_type': 'self-hosting-product',
          'mutation_class': 'source-write',
          'environment': 'local',
          'data_classification': 'internal',
          'acceptance_requirements': <String>[
            'tests',
            'ci',
            'evidence',
            'manifest',
          ],
        },
      ),
    );
  }

  @override
  Future<ToolPlan> toolDecisions(String taskId) async {
    return ToolPlan.fromJson(
      await _getObject('/v1/tasks/$taskId/tool-decisions'),
    );
  }

  @override
  Future<List<ToolInvocation>> toolInvocations(String taskId) async {
    final response = await _request(
      'GET',
      '/v1/tasks/$taskId/tool-invocations',
    );
    return (jsonDecode(response.body) as List<dynamic>)
        .map((value) => ToolInvocation.fromJson(value as Map<String, dynamic>))
        .toList(growable: false);
  }

  @override
  Future<ToolReconciliation> toolReconciliation(String taskId) async {
    return ToolReconciliation.fromJson(
      await _getObject('/v1/tasks/$taskId/tool-reconciliation'),
    );
  }

  @override
  Future<OperatorTask> dispatch(String taskId) async {
    return _taskCommand(taskId, 'dispatch');
  }

  @override
  Future<OperatorTask> continueTask(String taskId) async {
    return _taskCommand(taskId, 'continue');
  }

  @override
  Future<OperatorTask> cancel(String taskId) async {
    return _taskCommand(taskId, 'cancel');
  }

  @override
  Future<OperatorTask> verify({
    required String taskId,
    required String receipt,
    required String head,
  }) async {
    return OperatorTask.fromJson(
      await _postObject(
        '/v1/tasks/$taskId/verify',
        <String, dynamic>{
          'verification_receipt': receipt,
          'ci_status': 'success',
          'verified_head': head,
        },
      ),
    );
  }

  @override
  Future<ManualDispatchPackage> generateManualPackage(String taskId) async {
    return ManualDispatchPackage.fromJson(
      await _postObject('/v1/tasks/$taskId/manual-package', null),
    );
  }

  @override
  Future<OperatorTask> markManualDispatched({
    required String taskId,
    required String packageReceipt,
  }) async {
    return OperatorTask.fromJson(
      await _postObject(
        '/v1/tasks/$taskId/manual-dispatched',
        <String, dynamic>{'package_receipt': packageReceipt},
      ),
    );
  }

  @override
  Future<OperatorTask> recordManualAcknowledgement({
    required String taskId,
    required String packageReceipt,
    required String threadReference,
  }) async {
    return OperatorTask.fromJson(
      await _postObject(
        '/v1/tasks/$taskId/manual-ack',
        <String, dynamic>{
          'package_receipt': packageReceipt,
          'thread_reference': threadReference,
        },
      ),
    );
  }

  @override
  Future<OperatorTask> importManualResult({
    required String taskId,
    required Map<String, dynamic> result,
  }) async {
    return OperatorTask.fromJson(
      await _postObject('/v1/tasks/$taskId/manual-result', result),
    );
  }

  Future<OperatorTask> _taskCommand(String taskId, String command) async {
    return OperatorTask.fromJson(
      await _postObject('/v1/tasks/$taskId/$command', null),
    );
  }

  Future<Map<String, dynamic>> _getObject(String path) async {
    final response = await _request('GET', path);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> _postObject(
    String path,
    Map<String, dynamic>? body,
  ) async {
    final response = await _request('POST', path, body: body);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<http.Response> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    try {
      final request = http.Request(method, Uri.parse('$baseUrl$path'))
        ..headers['Accept'] = 'application/json';
      final token = bearerToken?.trim();
      if (token != null && token.isNotEmpty) {
        request.headers['Authorization'] = 'Bearer $token';
      }
      if (body != null) {
        request.headers['Content-Type'] = 'application/json';
        request.body = jsonEncode(body);
      }
      final streamed = await _client.send(request).timeout(timeout);
      final response = await http.Response.fromStream(streamed);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        String detail = 'HTTP ${response.statusCode}';
        try {
          final payload = jsonDecode(response.body) as Map<String, dynamic>;
          detail = payload['detail']?.toString() ?? detail;
        } on FormatException {
          // Preserve the bounded HTTP status fallback.
        }
        throw OrchestratorApiException(
          code: 'HTTP_${response.statusCode}',
          message: detail,
          recoverable: response.statusCode >= 500 ||
              response.statusCode == 408 ||
              response.statusCode == 409,
        );
      }
      return response;
    } on TimeoutException {
      throw const OrchestratorApiException(
        code: 'TIMEOUT',
        message: 'انتهت مهلة الاتصال بالخدمة.',
        recoverable: true,
      );
    } on http.ClientException {
      throw const OrchestratorApiException(
        code: 'CONNECTION_FAILED',
        message: 'تعذر الوصول إلى Orchestrator المحلي.',
        recoverable: true,
      );
    }
  }
}
