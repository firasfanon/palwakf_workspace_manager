import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/config/orchestrator_runtime_config.dart';
import '../../engineering_os/domain/engineering_os_models.dart';
import '../domain/external_project_models.dart';

class ProjectTaskBridgeApiException implements Exception {
  const ProjectTaskBridgeApiException(this.message);
  final String message;

  @override
  String toString() => message;
}

abstract interface class ProjectTaskBridgeApi {
  Future<EngineeringTask> createEngineeringTask(
    String projectId,
    String candidateId,
    ProjectCandidateEngineeringTaskDraft draft,
  );
}

class HttpProjectTaskBridgeApi implements ProjectTaskBridgeApi {
  HttpProjectTaskBridgeApi({
    http.Client? client,
    String? baseUrl,
    this.bearerToken,
    this.timeout = const Duration(seconds: 20),
  })  : _client = client ?? http.Client(),
        _baseUrlOverride = baseUrl;

  final http.Client _client;
  final String? _baseUrlOverride;
  final String? bearerToken;
  final Duration timeout;

  @override
  Future<EngineeringTask> createEngineeringTask(
    String projectId,
    String candidateId,
    ProjectCandidateEngineeringTaskDraft draft,
  ) async {
    final encodedProject = Uri.encodeComponent(projectId);
    final encodedCandidate = Uri.encodeComponent(candidateId);
    final path =
        '/v1/projects/$encodedProject/candidate-work-items/$encodedCandidate/engineering-task';
    try {
      final baseUrl = OrchestratorRuntimeConfig.resolveBaseUrl(
        explicitBaseUrl: _baseUrlOverride,
      );
      final request = http.Request('POST', Uri.parse('$baseUrl$path'))
        ..headers['Accept'] = 'application/json'
        ..headers['Content-Type'] = 'application/json'
        ..body = jsonEncode(draft.toJson());
      final token = bearerToken?.trim();
      if (token != null && token.isNotEmpty) {
        request.headers['Authorization'] = 'Bearer $token';
      }
      final response = await http.Response.fromStream(
        await _client.send(request).timeout(timeout),
      );
      if (response.statusCode < 200 || response.statusCode >= 300) {
        var detail = 'HTTP ${response.statusCode}';
        try {
          final decoded = jsonDecode(response.body);
          if (decoded is Map<String, dynamic> && decoded['detail'] != null) {
            detail = decoded['detail'].toString();
          }
        } catch (_) {
          // Preserve bounded HTTP fallback.
        }
        throw ProjectTaskBridgeApiException(detail);
      }
      return EngineeringTask.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    } on OrchestratorRuntimeConfigurationException catch (error) {
      throw ProjectTaskBridgeApiException(error.message);
    } on TimeoutException {
      throw const ProjectTaskBridgeApiException(
        'انتهت مهلة إنشاء المهمة التشغيلية.',
      );
    } on http.ClientException {
      throw const ProjectTaskBridgeApiException(
        'تعذر الوصول إلى خدمة Orchestrator المهيأة.',
      );
    }
  }
}
