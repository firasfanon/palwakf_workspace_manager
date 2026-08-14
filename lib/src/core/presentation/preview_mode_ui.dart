import 'package:flutter/material.dart';

import '../config/orchestrator_runtime_config.dart';
import '../theme/palwakf_theme.dart';

abstract final class PreviewModeUi {
  static bool get isVisualPreview =>
      OrchestratorRuntimeConfig.runtimeMode.trim().toLowerCase() == 'preview';

  static String metricValue(int value, {required bool dataAvailable}) =>
      dataAvailable ? '$value' : '—';

  static String capabilityLabel(bool? value) {
    if (value == null) return 'غير متاح';
    return value ? 'متاح' : 'محجوب';
  }
}

class PreviewModeBanner extends StatelessWidget {
  const PreviewModeBanner({
    this.message =
        'البيانات التشغيلية غير متصلة في هذه البيئة؛ المعاينة مخصصة للتحقق البصري.',
    super.key,
  });

  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      decoration: BoxDecoration(
        color: scheme.secondaryContainer.withValues(alpha: 0.42),
        border: Border(
          bottom: BorderSide(
            color: PalWakfTheme.waqfGold.withValues(alpha: 0.34),
          ),
        ),
      ),
      child: Row(
        children: <Widget>[
          const Icon(Icons.visibility_outlined, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'وضع المعاينة البصرية',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                        color: PalWakfTheme.waqfGold,
                      ),
                ),
                const SizedBox(height: 2),
                Text(message),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class PreviewUnavailablePanel extends StatelessWidget {
  const PreviewUnavailablePanel({
    required this.title,
    required this.description,
    this.icon = Icons.visibility_outlined,
    super.key,
  });

  final String title;
  final String description;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(28),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 820),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Container(
                    width: 64,
                    height: 64,
                    decoration: BoxDecoration(
                      color: PalWakfTheme.waqfGold.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: Icon(icon, size: 32, color: PalWakfTheme.waqfGold),
                  ),
                  const SizedBox(height: 18),
                  Text(
                    title,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    description,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                  ),
                  const SizedBox(height: 22),
                  Wrap(
                    alignment: WrapAlignment.center,
                    spacing: 10,
                    runSpacing: 10,
                    children: const <Widget>[
                      _PreviewFact(
                        icon: Icons.check_circle_outline,
                        label: 'الواجهة متاحة',
                      ),
                      _PreviewFact(
                        icon: Icons.cloud_off_outlined,
                        label: 'البيانات التشغيلية غير متصلة',
                      ),
                      _PreviewFact(
                        icon: Icons.lock_outline,
                        label: 'لا عمليات كتابة في المعاينة',
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _PreviewFact extends StatelessWidget {
  const _PreviewFact({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Chip(
      avatar: Icon(icon, size: 17),
      label: Text(label),
      side: BorderSide(color: PalWakfTheme.waqfGold.withValues(alpha: 0.26)),
    );
  }
}
