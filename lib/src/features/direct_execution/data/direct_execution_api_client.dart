import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../../core/config/orchestrator_runtime_config.dart';
import '../domain/direct_execution_models.dart';

final directExecutionApiProvider = Provider<DirectExecutionApi>(
  (ref) => HttpDirectExecutionApiClient(),
);

abstract interface class DirectExecutionApi {
  Future<DirectExecutionReceipt> execute(DirectExecutionDraft draft);

  Future<DirectExecutionReceipt> status(String sessionId);
}

class DirectExecutionApiException implements Exception {
  const DirectExecutionApiException(this.code, this.message);

  final String code;
  final String message;

  @override
  String toString() => '$code: $message';
}

class HttpDirectExecutionApiClient implements DirectExecutionApi {
  HttpDirectExecutionApiClient({
    http.Client? client,
    String? baseUrl,
    this.timeout = const Duration(seconds: 120),
  })  : _client = client ?? http.Client(),
        _baseUrlOverride = baseUrl;

  final http.Client _client;
  final String? _baseUrlOverride;
  final Duration timeout;

  @override
  Future<DirectExecutionReceipt> execute(DirectExecutionDraft draft) async {
    return DirectExecutionReceipt.fromJson(
      await _objectRequest(
        'POST',
        '/v1/direct-execution/sessions',
        body: draft.toJson(),
      ),
    );
  }

  @override
  Future<DirectExecutionReceipt> status(String sessionId) async {
    return DirectExecutionReceipt.fromJson(
      await _objectRequest(
        'GET',
        '/v1/direct-execution/sessions/$sessionId',
      ),
    );
  }

  Future<Map<String, dynamic>> _objectRequest(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    try {
      final baseUrl = OrchestratorRuntimeConfig.resolveBaseUrl(
        explicitBaseUrl: _baseUrlOverride,
      );
      final request = http.Request(method, Uri.parse('$baseUrl$path'))
        ..headers['Accept'] = 'application/json';
      if (body != null) {
        request.headers['Content-Type'] = 'application/json';
        request.body = jsonEncode(body);
      }
      final streamed = await _client.send(request).timeout(timeout);
      final response = await http.Response.fromStream(streamed);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        var detail = 'HTTP ${response.statusCode}';
        try {
          final payload = jsonDecode(response.body) as Map<String, dynamic>;
          detail = payload['detail']?.toString() ?? detail;
        } on FormatException {
          // Preserve bounded status fallback.
        }
        throw DirectExecutionApiException(
          'HTTP_${response.statusCode}',
          detail,
        );
      }
      return jsonDecode(response.body) as Map<String, dynamic>;
    } on OrchestratorRuntimeConfigurationException catch (error) {
      throw DirectExecutionApiException(error.code, error.message);
    } on TimeoutException {
      throw const DirectExecutionApiException(
        'TIMEOUT',
        'انتهت مهلة التنفيذ المباشر.',
      );
    } on http.ClientException {
      throw const DirectExecutionApiException(
        'CONNECTION_FAILED',
        'تعذر الوصول إلى خدمة التنفيذ المباشر.',
      );
    }
  }
}
