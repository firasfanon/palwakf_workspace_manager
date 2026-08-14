import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/core/presentation/preview_mode_ui.dart';
import 'package:palwakf_workspace_manager/src/core/theme/palwakf_theme.dart';

void main() {
  test('canonical workspace theme is dark and sovereign', () {
    final theme = PalWakfTheme.dark();

    expect(theme.brightness, Brightness.dark);
    expect(theme.scaffoldBackgroundColor, PalWakfTheme.darkCanvas);
    expect(theme.colorScheme.primary, PalWakfTheme.waqfGold);
  });

  test('unavailable operational data is not represented as zero or blocked',
      () {
    expect(
      PreviewModeUi.metricValue(0, dataAvailable: false),
      '—',
    );
    expect(PreviewModeUi.capabilityLabel(null), 'غير متاح');
    expect(PreviewModeUi.capabilityLabel(false), 'محجوب');
    expect(PreviewModeUi.capabilityLabel(true), 'متاح');
  });

  testWidgets('preview unavailable panel is Arabic-first and informational', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: PalWakfTheme.dark(),
        home: const Scaffold(
          body: PreviewUnavailablePanel(
            title: 'بيانات المهام غير متاحة',
            description: 'هذه معاينة بصرية ولا تمثل سجلًا تشغيليًا فارغًا.',
          ),
        ),
      ),
    );

    expect(find.text('بيانات المهام غير متاحة'), findsOneWidget);
    expect(find.text('البيانات التشغيلية غير متصلة'), findsOneWidget);
    expect(find.text('لا عمليات كتابة في المعاينة'), findsOneWidget);
  });
}
