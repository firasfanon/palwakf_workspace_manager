import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/engineering_os_models.dart';

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
    } on TimeoutException {
      throw const EngineeringOsApiException('انتهت مهلة الاتصال بالمحرك.');
    }
  }
}
