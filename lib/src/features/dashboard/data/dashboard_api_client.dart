import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/config/orchestrator_runtime_config.dart';
import '../domain/dashboard_models.dart';

abstract interface class DashboardApi {
  Future<DashboardSummary> summary();
  Future<List<RecentActivity>> activity({int limit = 30});
  Future<List<OperationalAlert>> alerts();
  Future<List<EvidenceIndexItem>> evidence({int limit = 50});
}

class DashboardApiException implements Exception {
  const DashboardApiException(this.code, this.message);

  final String code;
  final String message;
}

class HttpDashboardApi implements DashboardApi {
  HttpDashboardApi({
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

  @override
  Future<DashboardSummary> summary() async =>
      DashboardSummary.fromJson(await _object('/v1/dashboard/summary'));

  @override
  Future<List<RecentActivity>> activity({int limit = 30}) async =>
      (await _list('/v1/dashboard/activity?limit=$limit'))
          .map(RecentActivity.fromJson)
          .toList(growable: false);

  @override
  Future<List<OperationalAlert>> alerts() async => (await _list('/v1/alerts'))
      .map(OperationalAlert.fromJson)
      .toList(growable: false);

  @override
  Future<List<EvidenceIndexItem>> evidence({int limit = 50}) async =>
      (await _list('/v1/evidence?limit=$limit'))
          .map(EvidenceIndexItem.fromJson)
          .toList(growable: false);

  Future<Map<String, dynamic>> _object(String path) async =>
      jsonDecode((await _request(path)).body) as Map<String, dynamic>;

  Future<List<Map<String, dynamic>>> _list(String path) async =>
      (jsonDecode((await _request(path)).body) as List<dynamic>)
          .cast<Map<String, dynamic>>();

  Future<http.Response> _request(String path) async {
    try {
      final baseUrl = OrchestratorRuntimeConfig.resolveBaseUrl(
        explicitBaseUrl: _baseUrlOverride,
      );
      final request = http.Request('GET', Uri.parse('$baseUrl$path'))
        ..headers['Accept'] = 'application/json';
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
          detail = (jsonDecode(response.body) as Map<String, dynamic>)['detail']
              .toString();
        } on FormatException {
          // Keep the bounded HTTP fallback.
        }
        throw DashboardApiException('HTTP_${response.statusCode}', detail);
      }
      return response;
    } on OrchestratorRuntimeConfigurationException catch (error) {
      throw DashboardApiException(error.code, error.message);
    } on TimeoutException {
      throw const DashboardApiException(
        'TIMEOUT',
        'انتهت مهلة الاتصال بخدمة مساحة العمل.',
      );
    } on http.ClientException {
      throw const DashboardApiException(
        'CONNECTION_FAILED',
        'تعذر الوصول إلى خدمة Orchestrator الموثقة.',
      );
    }
  }
}
