import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/config/orchestrator_runtime_config.dart';
import '../domain/portfolio_intelligence_models.dart';

abstract interface class PortfolioIntelligenceApi {
  Future<PortfolioCommandCenterSnapshot> overview();
}

class PortfolioIntelligenceApiException implements Exception {
  const PortfolioIntelligenceApiException(this.code, this.message);

  final String code;
  final String message;
}

class HttpPortfolioIntelligenceApi implements PortfolioIntelligenceApi {
  HttpPortfolioIntelligenceApi({
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
  Future<PortfolioCommandCenterSnapshot> overview() async {
    try {
      final baseUrl = OrchestratorRuntimeConfig.resolveBaseUrl(
        explicitBaseUrl: _baseUrlOverride,
      );
      final request = http.Request(
        'GET',
        Uri.parse('$baseUrl/v1/portfolio/overview'),
      )..headers['Accept'] = 'application/json';
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
          // Keep bounded fallback.
        }
        throw PortfolioIntelligenceApiException(
          'HTTP_${response.statusCode}',
          detail,
        );
      }
      return PortfolioCommandCenterSnapshot.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    } on OrchestratorRuntimeConfigurationException catch (error) {
      throw PortfolioIntelligenceApiException(error.code, error.message);
    } on TimeoutException {
      throw const PortfolioIntelligenceApiException(
        'TIMEOUT',
        'انتهت مهلة قراءة مركز قيادة المحفظة.',
      );
    } on http.ClientException {
      throw const PortfolioIntelligenceApiException(
        'CONNECTION_FAILED',
        'تعذر الوصول إلى Workspace Orchestrator.',
      );
    }
  }
}
