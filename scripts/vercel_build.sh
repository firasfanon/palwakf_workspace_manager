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
flutter build web --release

test -f build/web/index.html
