enum OperationalDataAvailability {
  loading,
  available,
  empty,
  unavailable,
  blocked,
  error,
}

abstract final class OperationalDataContract {
  static OperationalDataAvailability resolve({
    required bool loading,
    required bool sourceConfirmed,
    required bool hasData,
    required bool preview,
    String? error,
    bool policyBlocked = false,
  }) {
    if (policyBlocked) return OperationalDataAvailability.blocked;

    if (sourceConfirmed) {
      return hasData
          ? OperationalDataAvailability.available
          : OperationalDataAvailability.empty;
    }

    if (loading) return OperationalDataAvailability.loading;

    final hasError = error?.trim().isNotEmpty ?? false;
    if (hasError) {
      return preview
          ? OperationalDataAvailability.unavailable
          : OperationalDataAvailability.error;
    }

    return preview
        ? OperationalDataAvailability.unavailable
        : OperationalDataAvailability.loading;
  }

  static bool canMutate({
    required OperationalDataAvailability availability,
    required bool preview,
  }) {
    if (preview) return false;
    return availability == OperationalDataAvailability.available ||
        availability == OperationalDataAvailability.empty;
  }
}
