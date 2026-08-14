import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/domain/operational_data_state.dart';
import '../../../core/presentation/preview_mode_ui.dart';
import '../../../core/theme/palwakf_theme.dart';
import '../application/operational_authorization.dart';
import '../application/orchestrator_controller.dart';
import '../domain/orchestrator_models.dart';
import 'service_auth_dialog.dart';

class ToolHealthPage extends ConsumerStatefulWidget {
  const ToolHealthPage({super.key, this.adapterId});

  final String? adapterId;

  @override
  ConsumerState<ToolHealthPage> createState() => _ToolHealthPageState();
}

class _ToolHealthPageState extends ConsumerState<ToolHealthPage> {
  @override
  void initState() {
    super.initState();
    Future<void>.microtask(() {
      if (ref.read(orchestratorControllerProvider).tools.isEmpty) {
        ref.read(orchestratorControllerProvider.notifier).load();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(orchestratorControllerProvider);
    final authorization = ref.watch(operationalAuthorizationProvider);
    final canProbe = authorization.asData?.value.canProbeTools ?? false;
    ToolOperationalHealth? selected;
    for (final tool in state.tools) {
      if (tool.adapterId == widget.adapterId) selected = tool;
    }
    final availability = PreviewModeUi.resolveAvailability(
      loading: state.loading,
      sourceConfirmed: state.capabilities != null,
      hasData: state.tools.isNotEmpty,
      error: state.error,
    );
    final previewUnavailable =
        availability == OperationalDataAvailability.unavailable;
    return Material(
      child: Column(
        children: <Widget>[
          if (state.loading) const LinearProgressIndicator(minHeight: 2),
          if (previewUnavailable)
            const PreviewModeBanner()
          else if (state.error != null)
            _ErrorBand(
              message: state.error!,
              onAuthenticate: () => showServiceAuthDialog(context, ref),
            ),
          Expanded(
            child: previewUnavailable
                ? const PreviewUnavailablePanel(
                    icon: Icons.build_outlined,
                    title: 'بيانات الأدوات غير متاحة',
                    description:
                        'هذه معاينة بصرية ولا تعني أن سجل الأدوات أو التنبيهات فارغ أو أن القيم تساوي صفرًا.',
                  )
                : selected == null
                    ? _ToolHealthDashboard(
                        tools: state.tools,
                        alerts: state.toolAlerts,
                      )
                    : _ToolHealthDetail(
                        tool: selected,
                        alerts: state.toolAlerts
                            .where((alert) =>
                                alert.adapterId == selected!.adapterId)
                            .toList(growable: false),
                        onProbe: canProbe
                            ? () => ref
                                .read(orchestratorControllerProvider.notifier)
                                .probeTool(selected!.adapterId)
                            : null,
                      ),
          ),
        ],
      ),
    );
  }
}

class _ToolHealthDashboard extends StatelessWidget {
  const _ToolHealthDashboard({required this.tools, required this.alerts});

  final List<ToolOperationalHealth> tools;
  final List<ToolHealthAlert> alerts;

  @override
  Widget build(BuildContext context) {
    final required = tools.where((tool) => tool.requiredAdapter).length;
    final fresh = tools.where((tool) => tool.freshness.value == 'fresh').length;
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
      children: <Widget>[
        Wrap(
          spacing: 24,
          runSpacing: 12,
          children: <Widget>[
            _Metric(label: 'الأدوات المسجلة', value: '${tools.length}'),
            _Metric(label: 'مطلوبة للمشروع', value: '$required'),
            _Metric(label: 'دليل حديث', value: '$fresh'),
            _Metric(label: 'تنبيهات', value: '${alerts.length}'),
          ],
        ),
        if (alerts.isNotEmpty) ...<Widget>[
          const SizedBox(height: 22),
          Text('التنبيهات', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ...alerts.take(5).map((alert) => _AlertRow(alert: alert)),
        ],
        const SizedBox(height: 24),
        Text('سجل الأدوات', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        if (tools.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 48),
            child: Center(child: Text('لا توجد بيانات مصادق عليها')),
          ),
        ...tools.map(
          (tool) => _ToolRow(
            tool: tool,
            onTap: () => context.go('/tools/${tool.adapterId}'),
          ),
        ),
      ],
    );
  }
}

class _ToolHealthDetail extends StatelessWidget {
  const _ToolHealthDetail({
    required this.tool,
    required this.alerts,
    required this.onProbe,
  });

  final ToolOperationalHealth tool;
  final List<ToolHealthAlert> alerts;
  final VoidCallback? onProbe;

  @override
  Widget build(BuildContext context) {
    final facts = <(String, HealthFact)>[
      ('الاتصال', tool.connection),
      ('المصادقة', tool.authentication),
      ('الصلاحية', tool.permission),
      ('الاستحقاق', tool.entitlement),
      ('الحصة', tool.quota),
      ('الاستخدام', tool.usage),
      ('التكلفة', tool.cost),
      ('الرصيد', tool.balance),
      ('انتهاء الرصيد', tool.creditExpiry),
      ('التجديد', tool.renewal),
      ('حد المعدل', tool.rateLimit),
      ('حداثة الدليل', tool.freshness),
    ];
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 32),
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(tool.adapterId,
                      style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 4),
                  Text(tool.requiredAdapter ? 'أداة مطلوبة' : 'أداة اختيارية'),
                ],
              ),
            ),
            FilledButton.icon(
              onPressed: onProbe,
              icon: const Icon(Icons.sensors),
              label: const Text('فحص'),
            ),
          ],
        ),
        if (alerts.isNotEmpty) ...<Widget>[
          const SizedBox(height: 18),
          ...alerts.map((alert) => _AlertRow(alert: alert)),
        ],
        const SizedBox(height: 18),
        DecoratedBox(
          decoration: BoxDecoration(
            border: Border.all(color: Theme.of(context).dividerColor),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Column(
            children: facts
                .map((entry) => _FactRow(label: entry.$1, fact: entry.$2))
                .toList(growable: false),
          ),
        ),
        const SizedBox(height: 22),
        Text('إجراءات المشغل', style: Theme.of(context).textTheme.titleMedium),
        ...tool.operatorActions.map(
          (action) => ListTile(
            dense: true,
            leading: const Icon(Icons.chevron_left),
            title: Text(action),
          ),
        ),
        const SizedBox(height: 14),
        Text('الأدلة', style: Theme.of(context).textTheme.titleMedium),
        ...tool.evidence.map(
          (evidence) => ListTile(
            dense: true,
            leading: const Icon(Icons.receipt_long_outlined),
            title: Text(evidence),
          ),
        ),
      ],
    );
  }
}

class _ToolRow extends StatelessWidget {
  const _ToolRow({required this.tool, required this.onTap});

  final ToolOperationalHealth tool;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final isFresh = tool.freshness.value == 'fresh';
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 14),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: Theme.of(context).dividerColor),
          ),
        ),
        child: Row(
          children: <Widget>[
            Icon(
              isFresh ? Icons.check_circle_outline : Icons.schedule_outlined,
              color: isFresh
                  ? PalWakfTheme.successGreen
                  : Theme.of(context).colorScheme.tertiary,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    tool.displayName,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  Text(
                    '${tool.authentication.displayValue} · ${tool.quota.displayValue}',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            if (tool.requiredAdapter)
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 8),
                child: Text('مطلوبة'),
              ),
            const Icon(Icons.chevron_left),
          ],
        ),
      ),
    );
  }
}

class _FactRow extends StatelessWidget {
  const _FactRow({required this.label, required this.fact});

  final String label;
  final HealthFact fact;

  @override
  Widget build(BuildContext context) {
    final observed = fact.observedAt == null
        ? 'بلا وقت رصد'
        : DateFormat('yyyy-MM-dd HH:mm').format(fact.observedAt!.toLocal());
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          SizedBox(width: 130, child: Text(label)),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  fact.displayValue,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                Text(
                  '${_provenanceLabel(fact.provenance)} · $observed',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                if (fact.note != null)
                  Text(fact.note!,
                      style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 150,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(value, style: Theme.of(context).textTheme.headlineSmall),
          Text(label),
        ],
      ),
    );
  }
}

class _AlertRow extends StatelessWidget {
  const _AlertRow({required this.alert});

  final ToolHealthAlert alert;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: Theme.of(context)
            .colorScheme
            .errorContainer
            .withValues(alpha: 0.35),
        border: Border(
          bottom: BorderSide(color: Theme.of(context).dividerColor),
        ),
      ),
      child: Row(
        children: <Widget>[
          Icon(Icons.warning_amber, color: Theme.of(context).colorScheme.error),
          const SizedBox(width: 10),
          Expanded(child: Text('${alert.adapterId}: ${alert.message}')),
        ],
      ),
    );
  }
}

class _ErrorBand extends StatelessWidget {
  const _ErrorBand({required this.message, required this.onAuthenticate});

  final String message;
  final VoidCallback onAuthenticate;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.errorContainer,
      child: ListTile(
        leading: const Icon(Icons.lock_outline),
        title: Text(message),
        trailing: TextButton.icon(
          onPressed: onAuthenticate,
          icon: const Icon(Icons.key_outlined),
          label: const Text('مصادقة'),
        ),
      ),
    );
  }
}

String _provenanceLabel(String value) {
  return switch (value) {
    'VERIFIED_PROVIDER_API' => 'واجهة المزود',
    'VERIFIED_RUNTIME_PROBE' => 'فحص تشغيل موثق',
    'VERIFIED_PLATFORM_UI' => 'واجهة المنصة',
    'USER_REPORTED' => 'إفادة المستخدم',
    'ESTIMATED_FROM_USAGE' => 'تقدير من الاستخدام',
    'NOT_EXPOSED_BY_PROVIDER' => 'غير متاح من المزود',
    'NOT_APPLICABLE' => 'غير منطبق',
    'STALE' => 'دليل قديم',
    _ => value,
  };
}
