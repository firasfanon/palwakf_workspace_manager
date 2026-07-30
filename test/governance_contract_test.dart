import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('foundation repository excludes operational secret files', () {
    expect(File('.env').existsSync(), isFalse);
    expect(File('.env.production').existsSync(), isFalse);
    expect(File('.env.staging').existsSync(), isFalse);
    final flutterSource = Directory('lib')
        .listSync(recursive: true)
        .whereType<File>()
        .where((file) => file.path.endsWith('.dart'))
        .map((file) => file.readAsStringSync())
        .join();
    expect(flutterSource.contains('OPENAI_API_KEY'), isFalse);
  });

  test('required governance artifacts are present', () {
    const required = <String>[
      'CHANGELOG.md',
      'CURRENT_TASK.md',
      'STATE.md',
      'ERROR_RECORD.md',
      'docs/governance/PLATFORM_GUIDE_PIN.md',
      'docs/contracts/RESUME_PROTOCOL_V1.md',
      'docs/contracts/SELF_HOSTING_OPERATIONAL_LOOP_V1.md',
      'schemas/control_plane_foundation.schema.json',
      'schemas/self_hosting_checkpoint_v1.schema.json',
    ];

    for (final path in required) {
      expect(File(path).existsSync(), isTrue, reason: 'Missing $path');
    }
  });
}
