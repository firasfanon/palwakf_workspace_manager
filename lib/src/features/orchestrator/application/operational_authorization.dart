import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../../core/config/orchestrator_runtime_config.dart';
import 'orchestrator_controller.dart';

class OperationalAuthorizationContext {
  const OperationalAuthorizationContext({
    required this.clientId,
    required this.scopes,
    required this.readOnly,
    required this.canDispatch,
    required this.canContinue,
    required this.canCancel,
    required this.canVerify,
    required this.canProbeTools,
  });

  factory OperationalAuthorizationContext.fromJson(
    Map<String, dynamic> json,
  ) {
    return OperationalAuthorizationContext(
      clientId: json['client_id'] as String,
      scopes: List<String>.from(json['scopes'] as List<dynamic>),
      readOnly: json['read_only'] as bool,
      canDispatch: json['can_dispatch'] as bool,
      canContinue: json['can_continue'] as bool,
      canCancel: json['can_cancel'] as bool,
      canVerify: json['can_verify'] as bool,
      canProbeTools: json['can_probe_tools'] as bool,
    );
  }

  final String clientId;
  final List<String> scopes;
  final bool readOnly;
  final bool canDispatch;
  final bool canContinue;
  final bool canCancel;
  final bool canVerify;
  final bool canProbeTools;
}

class OperationalAuthorizationException implements Exception {
  const OperationalAuthorizationException(this.message);

  final String message;

  @override
  String toString() => message;
}

class OperationalAuthorizationApiClient {
  OperationalAuthorizationApiClient({
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

  Future<OperationalAuthorizationContext> load() async {
    try {
      final baseUrl = OrchestratorRuntimeConfig.resolveBaseUrl(
        explicitBaseUrl: _baseUrlOverride,
      );
      final request = http.Request(
        'GET',
        Uri.parse('$baseUrl/v1/auth/context'),
      )..headers['Accept'] = 'application/json';
      final token = bearerToken?.trim();
      if (token != null && token.isNotEmpty) {
        request.headers['Authorization'] = 'Bearer $token';
      }
      final streamed = await _client.send(request).timeout(timeout);
      final response = await http.Response.fromStream(streamed);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw const OperationalAuthorizationException(
          'تعذر التحقق من صلاحيات الجلسة الحالية.',
        );
      }
      return OperationalAuthorizationContext.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    } on OrchestratorRuntimeConfigurationException {
      throw const OperationalAuthorizationException(
        'سياق الصلاحيات غير متاح في هذه البيئة.',
      );
    } on TimeoutException {
      throw const OperationalAuthorizationException(
        'انتهت مهلة التحقق من صلاحيات الجلسة.',
      );
    } on http.ClientException {
      throw const OperationalAuthorizationException(
        'تعذر الوصول إلى سياق صلاحيات Orchestrator.',
      );
    }
  }
}

final operationalAuthorizationProvider =
    FutureProvider<OperationalAuthorizationContext>((ref) async {
  return OperationalAuthorizationApiClient(
    bearerToken: ref.watch(orchestratorTokenProvider),
  ).load();
});
