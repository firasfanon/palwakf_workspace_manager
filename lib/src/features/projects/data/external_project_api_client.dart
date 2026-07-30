import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/external_project_models.dart';

class ExternalProjectApiException implements Exception {
  const ExternalProjectApiException(this.code, this.message);

  final String code;
  final String message;
}

abstract interface class ExternalProjectApi {
  Future<List<ExternalProject>> listProjects();

  Future<ExternalProject> intake(ProjectIntakeDraft draft);

  Future<ProjectReality> reality(String projectId);

  Future<ProjectReality> probe(String projectId);

  Future<void> prepareTask(String projectId, String candidateId);
}

class HttpExternalProjectApi implements ExternalProjectApi {
  HttpExternalProjectApi({
    http.Client? client,
    String? baseUrl,
    this.bearerToken,
    this.timeout = const Duration(seconds: 20),
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
  Future<List<ExternalProject>> listProjects() async {
    final response = await _request('GET', '/v1/projects');
    return (jsonDecode(response.body) as List<dynamic>)
        .map(
          (value) => ExternalProject.fromJson(value as Map<String, dynamic>),
        )
        .toList(growable: false);
  }

  @override
  Future<ExternalProject> intake(ProjectIntakeDraft draft) async {
    return ExternalProject.fromJson(
      await _object('POST', '/v1/projects/intake', body: draft.toJson()),
    );
  }

  @override
  Future<ProjectReality> reality(String projectId) async {
    return ProjectReality.fromJson(
      await _object('GET', '/v1/projects/$projectId/reality'),
    );
  }

  @override
  Future<ProjectReality> probe(String projectId) async {
    return ProjectReality.fromJson(
      await _object('POST', '/v1/projects/$projectId/probe'),
    );
  }

  @override
  Future<void> prepareTask(String projectId, String candidateId) async {
    await _object(
      'POST',
      '/v1/projects/$projectId/prepare-task',
      body: <String, dynamic>{'candidate_id': candidateId},
    );
  }

  Future<Map<String, dynamic>> _object(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final response = await _request(method, path, body: body);
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
      final response = await http.Response.fromStream(
        await _client.send(request).timeout(timeout),
      );
      if (response.statusCode < 200 || response.statusCode >= 300) {
        var detail = 'HTTP ${response.statusCode}';
        try {
          detail = (jsonDecode(response.body) as Map<String, dynamic>)['detail']
              .toString();
        } on FormatException {
          // Keep the bounded HTTP fallback.
        }
        throw ExternalProjectApiException(
          'HTTP_${response.statusCode}',
          detail,
        );
      }
      return response;
    } on TimeoutException {
      throw const ExternalProjectApiException(
        'TIMEOUT',
        'انتهت مهلة الاتصال بخدمة المشاريع.',
      );
    } on http.ClientException {
      throw const ExternalProjectApiException(
        'CONNECTION_FAILED',
        'تعذر الوصول إلى Orchestrator المحلي.',
      );
    }
  }
}
