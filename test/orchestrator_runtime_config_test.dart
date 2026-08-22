import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/core/config/orchestrator_runtime_config.dart';

void main() {
  group('OrchestratorRuntimeConfig', () {
    test('local mode defaults to loopback runtime', () {
      expect(
        OrchestratorRuntimeConfig.resolveBaseUrl(
          runtimeModeOverride: 'local',
          configuredBaseUrlOverride: '',
        ),
        'http://127.0.0.1:8421',
      );
    });

    test('preview mode fails closed when endpoint is absent', () {
      expect(
        () => OrchestratorRuntimeConfig.resolveBaseUrl(
          runtimeModeOverride: 'preview',
          configuredBaseUrlOverride: '',
        ),
        throwsA(
          isA<OrchestratorRuntimeConfigurationException>().having(
            (error) => error.code,
            'code',
            'REMOTE_ENDPOINT_NOT_CONFIGURED',
          ),
        ),
      );
    });

    test('preview mode rejects loopback and insecure endpoints', () {
      for (final endpoint in <String>[
        'http://127.0.0.1:8421',
        'http://orchestrator.example',
        'https://localhost:8421',
      ]) {
        expect(
          () => OrchestratorRuntimeConfig.resolveBaseUrl(
            runtimeModeOverride: 'preview',
            configuredBaseUrlOverride: endpoint,
          ),
          throwsA(isA<OrchestratorRuntimeConfigurationException>()),
        );
      }
    });

    test('preview mode accepts HTTPS remote endpoint and trims slash', () {
      expect(
        OrchestratorRuntimeConfig.resolveBaseUrl(
          runtimeModeOverride: 'preview',
          configuredBaseUrlOverride: 'https://orchestrator.example/',
        ),
        'https://orchestrator.example',
      );
    });

    test('local mode rejects insecure nonlocal endpoint', () {
      expect(
        () => OrchestratorRuntimeConfig.resolveBaseUrl(
          runtimeModeOverride: 'local',
          explicitBaseUrl: 'http://orchestrator.example',
        ),
        throwsA(isA<OrchestratorRuntimeConfigurationException>()),
      );
    });
  });
}
