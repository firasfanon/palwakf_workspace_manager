class OrchestratorRuntimeConfigurationException implements Exception {
  const OrchestratorRuntimeConfigurationException(this.code, this.message);

  final String code;
  final String message;

  @override
  String toString() => message;
}

abstract final class OrchestratorRuntimeConfig {
  static const String runtimeMode = String.fromEnvironment(
    'PALWAKF_RUNTIME_MODE',
    defaultValue: 'local',
  );

  static const String configuredBaseUrl = String.fromEnvironment(
    'ORCHESTRATOR_API_BASE_URL',
    defaultValue: '',
  );

  static String resolveBaseUrl({
    String? explicitBaseUrl,
    String? runtimeModeOverride,
    String? configuredBaseUrlOverride,
  }) {
    final mode = (runtimeModeOverride ?? runtimeMode).trim().toLowerCase();
    if (!const <String>{'local', 'preview', 'remote'}.contains(mode)) {
      throw const OrchestratorRuntimeConfigurationException(
        'INVALID_RUNTIME_MODE',
        'وضع الاتصال التشغيلي غير صالح.',
      );
    }

    final configured =
        (explicitBaseUrl ?? configuredBaseUrlOverride ?? configuredBaseUrl)
            .trim();

    if (configured.isEmpty) {
      if (mode == 'local') {
        return 'http://127.0.0.1:8421';
      }
      throw const OrchestratorRuntimeConfigurationException(
        'REMOTE_ENDPOINT_NOT_CONFIGURED',
        'الاتصال التشغيلي غير مهيأ لهذه المعاينة.',
      );
    }

    final uri = Uri.tryParse(configured);
    if (uri == null ||
        !uri.hasScheme ||
        uri.host.isEmpty ||
        (uri.scheme != 'http' && uri.scheme != 'https')) {
      throw const OrchestratorRuntimeConfigurationException(
        'INVALID_ORCHESTRATOR_ENDPOINT',
        'عنوان خدمة Orchestrator غير صالح.',
      );
    }

    final loopback = <String>{
      '127.0.0.1',
      'localhost',
      '::1',
    }.contains(uri.host.toLowerCase());

    if (mode != 'local' && (uri.scheme != 'https' || loopback)) {
      throw const OrchestratorRuntimeConfigurationException(
        'INSECURE_REMOTE_ORCHESTRATOR_ENDPOINT',
        'المعاينة البعيدة تتطلب عنوان Orchestrator آمنًا عبر HTTPS.',
      );
    }

    if (mode == 'local' && !loopback && uri.scheme != 'https') {
      throw const OrchestratorRuntimeConfigurationException(
        'INSECURE_NONLOCAL_ORCHESTRATOR_ENDPOINT',
        'أي Orchestrator غير محلي يجب أن يستخدم HTTPS.',
      );
    }

    return configured.replaceFirst(RegExp(r'/$'), '');
  }
}
