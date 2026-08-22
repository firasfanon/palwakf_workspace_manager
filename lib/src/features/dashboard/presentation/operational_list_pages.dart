import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' hide TextDirection;

import '../../../core/domain/operational_data_state.dart';
import '../../../core/presentation/preview_mode_ui.dart';
import '../../../core/theme/palwakf_theme.dart';
import '../application/dashboard_controller.dart';
import '../domain/dashboard_models.dart';

class OperationalAlertsPage extends ConsumerWidget {
  const OperationalAlertsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(dashboardControllerProvider);
    final alerts = state.alerts;
    final availability = PreviewModeUi.resolveAvailability(
      loading: state.loading,
      sourceConfirmed: state.summary != null,
      hasData: alerts.isNotEmpty,
      error: state.error,
    );
    if (availability == OperationalDataAvailability.loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (availability == OperationalDataAvailability.unavailable) {
      return const PreviewUnavailablePanel(
        icon: Icons.notifications_outlined,
        title: 'بيانات التنبيهات غير متاحة',
        description:
            'لا يمكن استنتاج وجود أو عدم وجود تنبيهات تشغيلية دون الاتصال بمصادر الحقيقة.',
      );
    }
    if (availability == OperationalDataAvailability.error) {
      return _OperationalError(message: state.error ?? 'تعذر تحميل التنبيهات.');
    }
    if (alerts.isEmpty) {
      return const _PageEmpty(
        icon: Icons.notifications_none,
        title: 'لا توجد تنبيهات تشغيلية',
        detail: 'لم تسجل المصادر الموثقة أي تنبيه حالي.',
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 40),
      itemCount: alerts.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, index) => _AlertTile(alert: alerts[index]),
    );
  }
}

class EvidenceIndexPage extends ConsumerWidget {
  const EvidenceIndexPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(dashboardControllerProvider);
    final evidence = state.evidence;
    final availability = PreviewModeUi.resolveAvailability(
      loading: state.loading,
      sourceConfirmed: state.summary != null,
      hasData: evidence.isNotEmpty,
      error: state.error,
    );
    if (availability == OperationalDataAvailability.loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (availability == OperationalDataAvailability.unavailable) {
      return const PreviewUnavailablePanel(
        icon: Icons.fact_check_outlined,
        title: 'بيانات الأدلة غير متاحة',
        description: 'غياب الاتصال في المعاينة لا يعني أن فهرس الأدلة فارغ.',
      );
    }
    if (availability == OperationalDataAvailability.error) {
      return _OperationalError(message: state.error ?? 'تعذر تحميل الأدلة.');
    }
    if (evidence.isEmpty) {
      return const _PageEmpty(
        icon: Icons.fact_check_outlined,
        title: 'لا توجد مراجع أدلة آمنة',
        detail: 'يعرض الفهرس مراجع نسبية محدودة فقط.',
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 40),
      itemCount: evidence.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final item = evidence[index];
        return ListTile(
          contentPadding: const EdgeInsets.symmetric(vertical: 8),
          leading: const Icon(Icons.description_outlined),
          title: Text(item.evidenceType),
          subtitle: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              const SizedBox(height: 4),
              SelectableText(
                item.safeReference,
                textDirection: TextDirection.ltr,
              ),
              Text(
                '${item.associationKind} · ${item.associationId ?? 'workspace'} · ${item.provenance}',
              ),
            ],
          ),
          trailing: Text(item.status),
        );
      },
    );
  }
}

class ConnectionsPage extends ConsumerWidget {
  const ConnectionsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(dashboardControllerProvider);
    final connection = state.summary?.connection;
    final availability = PreviewModeUi.resolveAvailability(
      loading: state.loading,
      sourceConfirmed: state.summary != null,
      hasData: connection != null,
      error: state.error,
    );
    if (availability == OperationalDataAvailability.loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (availability == OperationalDataAvailability.unavailable) {
      return const PreviewUnavailablePanel(
        icon: Icons.cable_outlined,
        title: 'بيانات الاتصالات غير متاحة',
        description:
            'لا يمكن استنتاج أن الاتصالات غير مهيأة من معاينة غير متصلة بمصدر الحقيقة.',
      );
    }
    if (availability == OperationalDataAvailability.error) {
      return _OperationalError(
        message: state.error ?? 'تعذر تحميل حالة الاتصالات.',
      );
    }
    if (connection == null) {
      return const _PageEmpty(
        icon: Icons.cable_outlined,
        title: 'لا توجد حالة اتصال موثقة',
        detail: 'الخدمة المتصلة لم تُرجع حالة اتصال موثقة.',
      );
    }
    final facts = <(String, String, bool)>[
      ('وضع الخدمة', connection.mode, connection.localSecure),
      (
        'مصادقة العملاء',
        connection.authenticationConfigured ? 'مهيأة' : 'غير مهيأة',
        connection.authenticationConfigured,
      ),
      (
        'مخزن الحالة',
        connection.storeHealthy ? 'سليم' : 'غير متاح',
        connection.storeHealthy,
      ),
      (
        'عمّال التنفيذ',
        connection.workersStarted ? 'قيد التشغيل' : 'متوقفون',
        connection.workersStarted,
      ),
      (
        'ChatGPT عبر HTTPS/OAuth',
        connection.chatgptLiveState,
        false,
      ),
      (
        'توافق مضيف التنفيذ',
        connection.executionHostCompatibility,
        true,
      ),
      (
        'توافق منفذ الأدوات',
        connection.toolExecutorCompatibility,
        true,
      ),
    ];
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 40),
      children: <Widget>[
        Text(
          'حالة الاتصالات',
          style: Theme.of(context)
              .textTheme
              .titleLarge
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 6),
        const Text(
          'لا تعرض هذه الصفحة رموز الوصول أو الأسرار أو معرّفات الفوترة.',
        ),
        const SizedBox(height: 18),
        ...facts.map(
          (fact) => Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: Icon(
                fact.$3 ? Icons.check_circle_outline : Icons.info_outline,
                color:
                    fact.$3 ? PalWakfTheme.successGreen : PalWakfTheme.royalRed,
              ),
              title: Text(fact.$1),
              trailing: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 240),
                child: Text(
                  fact.$2,
                  textAlign: TextAlign.end,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
          ),
        ),
        if (connection.lastSuccessfulCodexExecutionAt != null)
          ListTile(
            leading: const Icon(Icons.history_outlined),
            title: const Text('آخر تنفيذ Codex موثق'),
            trailing: Text(
              DateFormat('yyyy/MM/dd HH:mm', 'ar').format(
                connection.lastSuccessfulCodexExecutionAt!.toLocal(),
              ),
            ),
          ),
      ],
    );
  }
}

class _AlertTile extends StatelessWidget {
  const _AlertTile({required this.alert});

  final OperationalAlert alert;

  @override
  Widget build(BuildContext context) {
    final critical = alert.severity == 'critical';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(
                  critical ? Icons.error_outline : Icons.warning_amber,
                  color:
                      critical ? PalWakfTheme.royalRed : PalWakfTheme.waqfGold,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    alert.code,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
                Text(alert.severity),
              ],
            ),
            const SizedBox(height: 10),
            Text(alert.message),
            const SizedBox(height: 8),
            Text(
              'الإجراء المطلوب: ${alert.requiredAction}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 6),
            Text(
              '${alert.sourceKind} · ${alert.sourceId} · ${alert.freshness}',
              textDirection: TextDirection.ltr,
              style: Theme.of(context).textTheme.labelSmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _OperationalError extends StatelessWidget {
  const _OperationalError({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Row(
                children: <Widget>[
                  Icon(
                    Icons.error_outline,
                    color: Theme.of(context).colorScheme.error,
                  ),
                  const SizedBox(width: 12),
                  Expanded(child: Text(message)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _PageEmpty extends StatelessWidget {
  const _PageEmpty({
    required this.icon,
    required this.title,
    required this.detail,
  });

  final IconData icon;
  final String title;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(icon, size: 42),
            const SizedBox(height: 12),
            Text(
              title,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w800),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 6),
            Text(detail, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}
