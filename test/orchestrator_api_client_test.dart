import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:palwakf_workspace_manager/src/features/orchestrator/data/orchestrator_api_client.dart';

void main() {
  test('connection failure is structured and recoverable', () async {
    final client = MockClient((request) async {
      throw http.ClientException('offline', request.url);
    });
    final api = HttpOrchestratorApiClient(
      client: client,
      baseUrl: 'http://127.0.0.1:8421',
      timeout: const Duration(milliseconds: 100),
    );

    await expectLater(
      api.capabilities(),
      throwsA(
        isA<OrchestratorApiException>()
            .having((error) => error.code, 'code', 'CONNECTION_FAILED')
            .having((error) => error.recoverable, 'recoverable', isTrue),
      ),
    );
  });

  test('client sends no OpenAI credential header', () async {
    late http.Request captured;
    final client = MockClient((request) async {
      captured = request;
      return http.Response(
        '{"version":"SELF_HOSTING_OPERATIONAL_LOOP_V1",'
        '"task_lifecycle":true,"manual_relay_fallback":true,'
        '"capability_routing":true,"tool_decision_trace":true,'
        '"planned_actual_reconciliation":true,'
        '"automatic_agents_available":false,"database_connected":false,'
        '"production_mutation":false,"secret_values_exposed":false}',
        200,
      );
    });
    final api = HttpOrchestratorApiClient(
      client: client,
      baseUrl: 'http://127.0.0.1:8421',
    );

    await api.capabilities();

    expect(captured.headers.keys, isNot(contains('authorization')));
    expect(captured.headers.keys, isNot(contains('x-api-key')));
    expect(captured.body, isEmpty);
  });
}
