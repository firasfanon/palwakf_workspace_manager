import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/config/orchestrator_runtime_config.dart';
import '../domain/engineering_os_models.dart';
import '../domain/execution_run_models.dart';

class EngineeringOsApiException implements Exception {
  const EngineeringOsApiException(this.message);
  final String message;

  @override
  String toString() => message;
}

class EngineeringOsApiClient {
  EngineeringOsApiClient({
    http.Client? client,
    String? baseUrl,
    this.bearerToken,
    this.timeout = const Duration(seconds: 15),
  })  : _client = client ?? http.Client(),
        _baseUrlOverride = baseUrl;

  final http.Client _client;
  final String? _baseUrlOverride;
  final String? bearerToken;
  final Duration timeout;

  Future<EngineeringOsSummary> summary() async {
    return EngineeringOsSummary.fromJson(
      await _getObject('/v1/engineering-os/summary'),
    );
  }

  Future<List<EngineeringTask>> tasks() async {
    final response = await _request('GET', '/v1/engineering-os/tasks');
    return (jsonDecode(response.body) as List<dynamic>)
        .map((value) => EngineeringTask.fromJson(value as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<EngineeringTask> createTask(NewEngineeringTaskDraft draft) async {
    return EngineeringTask.fromJson(
      await _postObject('/v1/engineering-os/tasks', draft.toJson()),
    );
  }

  Future<EngineeringTaskExecutionContext> executionContext(
    String engineeringTaskId,
  ) async {
    final encoded = Uri.encodeComponent(engineeringTaskId);
    return EngineeringTaskExecutionContext.fromJson(
      await _getObject(
        '/v1/engineering-os/tasks/$encoded/execution-context',
      ),
    );
  }

  Future<EngineeringExecutionRunView> createExecutionRun(
    String engineeringTaskId,
    NewExecutionRunDraft draft,
  ) async {
    final encoded = Uri.encodeComponent(engineeringTaskId);
    return EngineeringExecutionRunView.fromJson(
      await _postObject(
        '/v1/engineering-os/tasks/$encoded/runs',
        draft.toJson(),
      ),
    );
  }

  Future<ExternalExecutionWorkspaceStatus> externalWorkspaceStatus(
    String executionRunId,
  ) async {
    final encoded = Uri.encodeComponent(executionRunId);
    return ExternalExecutionWorkspaceStatus.fromJson(
      await _getObject('/v1/execution-runs/$encoded/workspace'),
    );
  }

  Future<ExternalExecutionWorkspaceStatus> prepareExternalWorkspace(
    String executionRunId, {
    bool recreate = false,
  }) async {
    final encoded = Uri.encodeComponent(executionRunId);
    return ExternalExecutionWorkspaceStatus.fromJson(
      await _postObject(
        '/v1/execution-runs/$encoded/workspace/prepare',
        <String, dynamic>{'recreate': recreate},
      ),
    );
  }

  Future<ExternalExecutionWorkspaceStatus> applyExternalWorkspace(
    String executionRunId,
    List<Map<String, dynamic>> files,
  ) async {
    final encoded = Uri.encodeComponent(executionRunId);
    return ExternalExecutionWorkspaceStatus.fromJson(
      await _postObject(
        '/v1/execution-runs/$encoded/workspace/apply',
        <String, dynamic>{'files': files},
      ),
    );
  }

  Future<ExternalExecutionWorkspaceStatus> validateExternalWorkspace(
    String executionRunId, {
    List<String> checks = const <String>[],
  }) async {
    final encoded = Uri.encodeComponent(executionRunId);
    return ExternalExecutionWorkspaceStatus.fromJson(
      await _postObject(
        '/v1/execution-runs/$encoded/workspace/validate',
        <String, dynamic>{'checks': checks},
      ),
    );
  }

  Future<ExternalExecutionWorkspaceStatus> checkpointExternalWorkspace(
    String executionRunId, {
    required String commitMessage,
    List<String> evidence = const <String>[],
  }) async {
    final encoded = Uri.encodeComponent(executionRunId);
    return ExternalExecutionWorkspaceStatus.fromJson(
      await _postObject(
        '/v1/execution-runs/$encoded/workspace/checkpoint',
        <String, dynamic>{
          'commit_message': commitMessage,
          'evidence': evidence,
        },
      ),
    );
  }

  Future<List<ExtensionRecord>> extensions() async {
    final response = await _request('GET', '/v1/extensions');
    return (jsonDecode(response.body) as List<dynamic>)
        .map((value) => ExtensionRecord.fromJson(value as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<ExtensionRecord> registerExtension(NewExtensionDraft draft) async {
    return ExtensionRecord.fromJson(
      await _postObject('/v1/extensions', draft.toJson()),
    );
  }

  Future<Map<String, dynamic>> _getObject(String path) async {
    final response = await _request('GET', path);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> _postObject(
    String path,
    Map<String, dynamic> body,
  ) async {
    final response = await _request('POST', path, body: body);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<http.Response> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final headers = <String, String>{
      'Accept': 'application/json',
      if (body != null) 'Content-Type': 'application/json',
      if ((bearerToken ?? '').trim().isNotEmpty)
        'Authorization': 'Bearer ${bearerToken!.trim()}',
    };
    try {
      final baseUrl = OrchestratorRuntimeConfig.resolveBaseUrl(
        explicitBaseUrl: _baseUrlOverride,
      );
      final request = http.Request(method, Uri.parse('$baseUrl$path'))
        ..headers.addAll(headers);
      if (body != null) {
        request.body = jsonEncode(body);
      }
      final streamed = await _client.send(request).timeout(timeout);
      final response = await http.Response.fromStream(streamed);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        String detail = 'HTTP ${response.statusCode}';
        try {
          final decoded = jsonDecode(response.body);
          if (decoded is Map<String, dynamic> && decoded['detail'] != null) {
            detail = decoded['detail'].toString();
          }
        } catch (_) {
          // Keep bounded HTTP detail.
        }
        throw EngineeringOsApiException(detail);
      }
      return response;
    } on OrchestratorRuntimeConfigurationException catch (error) {
      throw EngineeringOsApiException(error.message);
    } on TimeoutException {
      throw const EngineeringOsApiException('انتهت مهلة الاتصال بالمحرك.');
    } on http.ClientException {
      throw const EngineeringOsApiException(
        'تعذر الوصول إلى خدمة Orchestrator المهيأة.',
      );
    }
  }
}
