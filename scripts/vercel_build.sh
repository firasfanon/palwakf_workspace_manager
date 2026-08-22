#!/usr/bin/env bash
set -euo pipefail

readonly FLUTTER_VERSION="3.44.1"
readonly FLUTTER_REVISION="924134a44c189315be2148659913dda1671cbe99"
readonly FLUTTER_ROOT="${TMPDIR:-/tmp}/flutter-${FLUTTER_REVISION}"

if [[ ! -x "${FLUTTER_ROOT}/bin/flutter" ]]; then
  git clone \
    --quiet \
    --depth 1 \
    --branch "${FLUTTER_VERSION}" \
    https://github.com/flutter/flutter.git \
    "${FLUTTER_ROOT}"
fi

actual_revision="$(git -C "${FLUTTER_ROOT}" rev-parse HEAD)"
if [[ "${actual_revision}" != "${FLUTTER_REVISION}" ]]; then
  printf 'Flutter revision mismatch: expected %s, got %s\n' \
    "${FLUTTER_REVISION}" \
    "${actual_revision}" >&2
  exit 1
fi

export PATH="${FLUTTER_ROOT}/bin:${PATH}"

flutter config --no-analytics
flutter pub get --enforce-lockfile

runtime_mode="${PALWAKF_RUNTIME_MODE:-preview}"
if [[ "${runtime_mode}" != "preview" ]]; then
  printf 'Vercel build requires PALWAKF_RUNTIME_MODE=preview, got %s\n' \
    "${runtime_mode}" >&2
  exit 1
fi

dart_defines=(
  "--dart-define=PALWAKF_RUNTIME_MODE=preview"
)

if [[ -n "${ORCHESTRATOR_API_BASE_URL:-}" ]]; then
  case "${ORCHESTRATOR_API_BASE_URL}" in
    https://127.0.0.1*|https://localhost*|http://*)
      printf 'Preview ORCHESTRATOR_API_BASE_URL must be non-loopback HTTPS\n' >&2
      exit 1
      ;;
    https://*)
      dart_defines+=(
        "--dart-define=ORCHESTRATOR_API_BASE_URL=${ORCHESTRATOR_API_BASE_URL}"
      )
      ;;
    *)
      printf 'Invalid ORCHESTRATOR_API_BASE_URL for Preview\n' >&2
      exit 1
      ;;
  esac
  printf 'PREVIEW_ORCHESTRATOR_ENDPOINT=CONFIGURED_HTTPS\n'
else
  printf 'PREVIEW_ORCHESTRATOR_ENDPOINT=NOT_CONFIGURED_VISUAL_ONLY\n'
fi

flutter build web --release "${dart_defines[@]}"

test -f build/web/index.html
