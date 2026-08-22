import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/core/domain/operational_data_state.dart';

void main() {
  group('OperationalDataContract', () {
    test('preview connection failure resolves to unavailable, not empty', () {
      expect(
        OperationalDataContract.resolve(
          loading: false,
          sourceConfirmed: false,
          hasData: false,
          preview: true,
          error: 'not configured',
        ),
        OperationalDataAvailability.unavailable,
      );
    });

    test('confirmed empty source resolves to empty', () {
      expect(
        OperationalDataContract.resolve(
          loading: false,
          sourceConfirmed: true,
          hasData: false,
          preview: true,
        ),
        OperationalDataAvailability.empty,
      );
    });

    test('confirmed data resolves to available', () {
      expect(
        OperationalDataContract.resolve(
          loading: false,
          sourceConfirmed: true,
          hasData: true,
          preview: true,
        ),
        OperationalDataAvailability.available,
      );
    });

    test('policy block is distinct from unavailable', () {
      expect(
        OperationalDataContract.resolve(
          loading: false,
          sourceConfirmed: false,
          hasData: false,
          preview: true,
          policyBlocked: true,
        ),
        OperationalDataAvailability.blocked,
      );
    });

    test('non-preview connection error remains error', () {
      expect(
        OperationalDataContract.resolve(
          loading: false,
          sourceConfirmed: false,
          hasData: false,
          preview: false,
          error: 'connection failed',
        ),
        OperationalDataAvailability.error,
      );
    });

    test('preview never permits mutation', () {
      expect(
        OperationalDataContract.canMutate(
          availability: OperationalDataAvailability.available,
          preview: true,
        ),
        isFalse,
      );
      expect(
        OperationalDataContract.canMutate(
          availability: OperationalDataAvailability.empty,
          preview: false,
        ),
        isTrue,
      );
      expect(
        OperationalDataContract.canMutate(
          availability: OperationalDataAvailability.unavailable,
          preview: false,
        ),
        isFalse,
      );
    });
  });
}
