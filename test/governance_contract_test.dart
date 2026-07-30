import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('foundation repository excludes operational secret files', () {
    expect(File('.env').existsSync(), isFalse);
    expect(File('.env.production').existsSync(), isFalse);
    expect(File('.env.staging').existsSync(), isFalse);
  });

  test('required governance artifacts are present', () {
    const required = <String>[
      'CHANGELOG.md',
      'CURRENT_TASK.md',
      'STATE.md',
      'ERROR_RECORD.md',
      'docs/governance/PLATFORM_GUIDE_PIN.md',
      'docs/contracts/RESUME_PROTOCOL_V1.md',
      'schemas/control_plane_foundation.schema.json',
    ];

    for (final path in required) {
      expect(File(path).existsSync(), isTrue, reason: 'Missing $path');
    }
  });
}
