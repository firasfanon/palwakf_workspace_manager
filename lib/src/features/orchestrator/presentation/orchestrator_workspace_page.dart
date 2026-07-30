import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/theme/palwakf_theme.dart';
import '../application/orchestrator_controller.dart';
import '../data/orchestrator_api_client.dart';
import '../domain/orchestrator_models.dart';
import 'service_auth_dialog.dart';

class OrchestratorWorkspacePage extends ConsumerStatefulWidget {
  const OrchestratorWorkspacePage({super.key});

  @override
  ConsumerState<OrchestratorWorkspacePage> createState() =>
      _OrchestratorWorkspacePageState();
}

class _OrchestratorWorkspacePageState
    extends ConsumerState<OrchestratorWorkspacePage> {
  @override
  void initState() {
    super.initState();
    Future<void>.microtask(
      () => ref.read(orchestratorControllerProvider.notifier).load(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(orchestratorControllerProvider);
    final controller = ref.read(orchestratorControllerProvider.notifier);
    return Scaffold(
      appBar: AppBar(
        title: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('مدير مساحة عمل PalWakf'),
            Text(
              'حلقة التشغيل الذاتي V1',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w400),
            ),
          ],
        ),
        actions: <Widget>[
          IconButton(
            tooltip: 'الصحة التشغيلية للأدوات',
            onPressed: () => context.go('/tools'),
            icon: const Icon(Icons.health_and_safety_outlined),
          ),
          IconButton(
            tooltip: 'مصادقة الخدمة',
            onPressed: () => showServiceAuthDialog(context, ref),
            icon: const Icon(Icons.lock_outline),
          ),
          IconButton(
            tooltip: 'تحديث',
            onPressed: state.loading ? null : controller.load,
            icon: const Icon(Icons.refresh),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: <Widget>[
            _CapabilityStrip(capabilities: state.capabilities),
            if (state.error != null)
              _RecoverableError(
                message: state.error!,
                recoverable: state.errorRecoverable,
                onRetry: controller.load,
              ),
            if (state.loading) const LinearProgressIndicator(minHeight: 2),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final queue = _TaskQueue(
                    state: state,
                    onSelect: controller.selectTask,
                    onCreate: () => _showNewTask(context),
                  );
                  final detail = _TaskDetail(
                    state: state,
                    controller: controller,
                  );
                  if (constraints.maxWidth < 760) {
                    return Column(
                      children: <Widget>[
                        SizedBox(height: 260, child: queue),
                        const Divider(height: 1),
                        Expanded(child: detail),
                      ],
                    );
                  }
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      SizedBox(width: 340, child: queue),
                      const VerticalDivider(width: 1),
                      Expanded(child: detail),
                    ],
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _showNewTask(BuildContext context) async {
    final draft = await showDialog<TaskDraft>(
      context: context,
      builder: (context) => const _NewTaskDialog(),
    );
    if (draft == null || !mounted) return;
    try {
      await ref.read(orchestratorControllerProvider.notifier).createTask(draft);
    } on OrchestratorApiException catch (error) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.message)),
      );
    }
  }
}

class _CapabilityStrip extends StatelessWidget {
  const _CapabilityStrip({required this.capabilities});

  final RuntimeCapabilities? capabilities;

  @override
  Widget build(BuildContext context) {
    final values = <({String label, bool enabled, IconData icon})>[
      (
        label: 'المسار الآلي',
        enabled: capabilities?.automaticAgentsAvailable ?? false,
        icon: Icons.auto_awesome_outlined,
      ),
      (
        label: 'ترحيل المستخدم',
        enabled: capabilities?.manualRelayFallback ?? false,
        icon: Icons.forward_to_inbox_outlined,
      ),
      (
        label: 'توجيه القدرات',
        enabled: capabilities?.capabilityRouting ?? false,
        icon: Icons.route_outlined,
      ),
      (
        label: 'تسوية الأدوات',
        enabled: capabilities?.reconciliation ?? false,
        icon: Icons.compare_arrows,
      ),
    ];
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          bottom: BorderSide(color: Theme.of(context).dividerColor),
        ),
      ),
      child: Wrap(
        spacing: 20,
        runSpacing: 8,
        children: values
            .map(
              (value) => Row(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Icon(
                    value.icon,
                    size: 17,
                    color: value.enabled
                        ? PalWakfTheme.successGreen
                        : PalWakfTheme.royalRed,
                  ),
                  const SizedBox(width: 7),
                  Text(value.label),
                  const SizedBox(width: 6),
                  Text(
                    value.enabled ? 'متاح' : 'محجوب',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      color: value.enabled
                          ? PalWakfTheme.successGreen
                          : PalWakfTheme.royalRed,
                    ),
                  ),
                ],
              ),
            )
            .toList(growable: false),
      ),
    );
  }
}

class _RecoverableError extends StatelessWidget {
  const _RecoverableError({
    required this.message,
    required this.recoverable,
    required this.onRetry,
  });

  final String message;
  final bool recoverable;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
        child: Row(
          children: <Widget>[
            const Icon(Icons.error_outline),
            const SizedBox(width: 10),
            Expanded(child: Text(message)),
            if (recoverable)
              TextButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh, size: 18),
                label: const Text('إعادة المحاولة'),
              ),
          ],
        ),
      ),
    );
  }
}

class _TaskQueue extends StatelessWidget {
  const _TaskQueue({
    required this.state,
    required this.onSelect,
    required this.onCreate,
  });

  final OrchestratorWorkspaceState state;
  final ValueChanged<String> onSelect;
  final VoidCallback onCreate;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Theme.of(context).colorScheme.surface,
      child: Column(
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    'صف المهام',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                ),
                IconButton.filled(
                  tooltip: 'مهمة جديدة',
                  onPressed: onCreate,
                  icon: const Icon(Icons.add),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: state.tasks.isEmpty
                ? const _QueueEmpty()
                : ListView.separated(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    itemCount: state.tasks.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 2),
                    itemBuilder: (context, index) {
                      final task = state.tasks[index];
                      return _TaskQueueItem(
                        task: task,
                        selected: task.taskId == state.selectedTaskId,
                        onTap: () => onSelect(task.taskId),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _QueueEmpty extends StatelessWidget {
  const _QueueEmpty();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(Icons.inbox_outlined, size: 38),
            SizedBox(height: 10),
            Text('لا توجد مهام تشغيلية'),
          ],
        ),
      ),
    );
  }
}

class _TaskQueueItem extends StatelessWidget {
  const _TaskQueueItem({
    required this.task,
    required this.selected,
    required this.onTap,
  });

  final OperatorTask task;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final formatter = DateFormat('HH:mm  yyyy/MM/dd', 'ar');
    return Material(
      color: selected
          ? Theme.of(context).colorScheme.primaryContainer
          : Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  _StatusDot(status: task.status),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      task.taskId,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 7),
              Text(
                '${task.projectId} · ${task.branch}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 5),
              Row(
                children: <Widget>[
                  Expanded(
                    child: Text(
                      task.status.arabicLabel,
                      style: Theme.of(context).textTheme.labelMedium,
                    ),
                  ),
                  Text(
                    formatter.format(task.updatedAt.toLocal()),
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                ],
              ),
              if (task.blocker != null) ...<Widget>[
                const SizedBox(height: 6),
                Text(
                  task.blocker!,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: PalWakfTheme.royalRed,
                    fontSize: 12,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.status});

  final OrchestratorTaskStatus status;

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      OrchestratorTaskStatus.verified => PalWakfTheme.successGreen,
      OrchestratorTaskStatus.running => PalWakfTheme.waqfGold,
      OrchestratorTaskStatus.pendingVerification => Colors.teal,
      OrchestratorTaskStatus.pending => Colors.blueGrey,
      _ => PalWakfTheme.royalRed,
    };
    return Container(
      width: 9,
      height: 9,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

class _TaskDetail extends StatelessWidget {
  const _TaskDetail({required this.state, required this.controller});

  final OrchestratorWorkspaceState state;
  final OrchestratorController controller;

  @override
  Widget build(BuildContext context) {
    final task = state.selectedTask;
    if (task == null) {
      return Center(
        child: _RuntimeCapabilitiesCard(
          capabilities: state.capabilities,
        ),
      );
    }
    return DefaultTabController(
      length: 4,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          _TaskHeader(task: task, controller: controller),
          const TabBar(
            isScrollable: true,
            tabs: <Widget>[
              Tab(icon: Icon(Icons.dashboard_outlined), text: 'التفاصيل'),
              Tab(icon: Icon(Icons.route_outlined), text: 'خطة الأدوات'),
              Tab(icon: Icon(Icons.forward_to_inbox_outlined), text: 'الترحيل'),
              Tab(icon: Icon(Icons.timeline_outlined), text: 'الأحداث'),
            ],
          ),
          Expanded(
            child: TabBarView(
              children: <Widget>[
                _OverviewTab(task: task),
                _ToolPlanTab(
                  plan: state.toolPlan,
                  invocations: state.invocations,
                  reconciliation: state.reconciliation,
                  onPlan: controller.planTools,
                ),
                _RelayTab(
                  task: task,
                  package: state.manualPackage,
                  controller: controller,
                ),
                _EventsTab(task: task),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RuntimeCapabilitiesCard extends StatelessWidget {
  const _RuntimeCapabilitiesCard({required this.capabilities});

  final RuntimeCapabilities? capabilities;

  @override
  Widget build(BuildContext context) {
    final values = <String, bool>{
      'Task lifecycle': capabilities?.taskLifecycle ?? false,
      'Manual relay': capabilities?.manualRelayFallback ?? false,
      'Capability routing': capabilities?.capabilityRouting ?? false,
      'Tool trace': capabilities?.toolDecisionTrace ?? false,
      'Reconciliation': capabilities?.reconciliation ?? false,
      'Automatic Agents': capabilities?.automaticAgentsAvailable ?? false,
      'Database': capabilities?.databaseConnected ?? false,
      'Production mutation': capabilities?.productionMutation ?? false,
    };
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 540),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              const _SectionTitle(
                icon: Icons.memory_outlined,
                title: 'Runtime Capabilities',
              ),
              const SizedBox(height: 8),
              const Text('اختر مهمة أو أنشئ مهمة جديدة لبدء العمل.'),
              const SizedBox(height: 16),
              ...values.entries.map(
                (entry) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        entry.value
                            ? Icons.check_circle_outline
                            : Icons.block_outlined,
                        size: 18,
                        color: entry.value
                            ? PalWakfTheme.successGreen
                            : PalWakfTheme.royalRed,
                      ),
                      const SizedBox(width: 8),
                      Expanded(child: Text(entry.key)),
                      Text(
                        entry.value ? 'متاح' : 'محجوب',
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TaskHeader extends StatelessWidget {
  const _TaskHeader({required this.task, required this.controller});

  final OperatorTask task;
  final OrchestratorController controller;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  task.taskId,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
              _StatusBadge(status: task.status),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              FilledButton.icon(
                onPressed: task.status == OrchestratorTaskStatus.cancelled
                    ? null
                    : controller.dispatch,
                icon: const Icon(Icons.send_outlined),
                label: const Text('إرسال'),
              ),
              OutlinedButton.icon(
                onPressed: task.status == OrchestratorTaskStatus.failed ||
                        task.status == OrchestratorTaskStatus.awaitingApproval
                    ? controller.continueTask
                    : null,
                icon: const Icon(Icons.play_arrow),
                label: const Text('متابعة'),
              ),
              OutlinedButton.icon(
                onPressed: task.status == OrchestratorTaskStatus.verified ||
                        task.status == OrchestratorTaskStatus.cancelled
                    ? null
                    : controller.cancel,
                icon: const Icon(Icons.cancel_outlined),
                label: const Text('إلغاء'),
              ),
              OutlinedButton.icon(
                onPressed:
                    task.status == OrchestratorTaskStatus.pendingVerification
                        ? () => _showVerificationDialog(context, controller)
                        : null,
                icon: const Icon(Icons.fact_check_outlined),
                label: const Text('تحقق مستقل'),
              ),
              IconButton(
                tooltip: 'تحديث المهمة',
                onPressed: controller.refreshSelected,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _showVerificationDialog(
    BuildContext context,
    OrchestratorController controller,
  ) async {
    final input = TextEditingController();
    final receipt = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('إيصال التحقق المستقل'),
        content: TextField(
          controller: input,
          decoration: const InputDecoration(
            labelText: 'CI / verification receipt',
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, input.text.trim()),
            child: const Text('تسجيل'),
          ),
        ],
      ),
    );
    input.dispose();
    if (receipt != null && receipt.length >= 8) {
      await controller.verify(receipt);
    }
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status});

  final OrchestratorTaskStatus status;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        status.arabicLabel,
        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
      ),
    );
  }
}

class _OverviewTab extends StatelessWidget {
  const _OverviewTab({required this.task});

  final OperatorTask task;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: <Widget>[
        const _SectionTitle(
            icon: Icons.gavel_outlined, title: 'السلطة والنطاق'),
        _KeyValueGrid(
          values: <String, String>{
            'المشروع': task.projectId,
            'المستودع': task.repository,
            'الفرع': task.branch,
            'مرجع التفويض': task.authorityReference,
            'Sandbox': task.sandbox,
            'Idempotency': task.idempotencyKey,
          },
        ),
        const SizedBox(height: 22),
        const _SectionTitle(
          icon: Icons.description_outlined,
          title: 'وصف المهمة',
        ),
        Text(task.prompt),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: task.constraints
              .map((value) => Chip(label: Text(value)))
              .toList(),
        ),
        const SizedBox(height: 22),
        const _SectionTitle(icon: Icons.commit_outlined, title: 'حالة المصدر'),
        _KeyValueGrid(
          values: <String, String>{
            'HEAD المتوقع': task.expectedHead,
            'HEAD قبل التنفيذ': task.beforeHead ?? 'غير متاح',
            'HEAD بعد التنفيذ': task.afterHead ?? 'غير متاح',
            'Thread': task.threadId ?? 'غير متاح',
            'Receipt': task.executionReceipt ?? 'غير متاح',
            'آخر حدث': task.lastEvent,
          },
        ),
        if (task.changedFiles.isNotEmpty) ...<Widget>[
          const SizedBox(height: 22),
          const _SectionTitle(
            icon: Icons.folder_open_outlined,
            title: 'الملفات المتغيرة',
          ),
          ...task.changedFiles.map(
            (value) => ListTile(
              dense: true,
              leading: const Icon(Icons.insert_drive_file_outlined, size: 18),
              title: Text(value),
            ),
          ),
        ],
      ],
    );
  }
}

class _ToolPlanTab extends StatelessWidget {
  const _ToolPlanTab({
    required this.plan,
    required this.invocations,
    required this.reconciliation,
    required this.onPlan,
  });

  final ToolPlan? plan;
  final List<ToolInvocation> invocations;
  final ToolReconciliation? reconciliation;
  final VoidCallback onPlan;

  @override
  Widget build(BuildContext context) {
    if (plan == null) {
      return Center(
        child: FilledButton.icon(
          onPressed: onPlan,
          icon: const Icon(Icons.route_outlined),
          label: const Text('إنشاء خطة الأدوات'),
        ),
      );
    }
    return ListView(
      padding: const EdgeInsets.all(20),
      children: <Widget>[
        const _ProjectToolProfileBand(),
        const SizedBox(height: 18),
        if (plan!.dispatchBlocked)
          _WarningBand(message: plan!.blockers.join(' · ')),
        const _SectionTitle(
          icon: Icons.account_tree_outlined,
          title: 'قرارات الاختيار',
        ),
        const SizedBox(height: 8),
        ...plan!.decisions.map(
          (decision) => _ToolDecisionRow(decision: decision),
        ),
        const SizedBox(height: 22),
        const _SectionTitle(
          icon: Icons.timeline_outlined,
          title: 'المخطط مقابل المنفذ',
        ),
        const SizedBox(height: 8),
        if (invocations.isEmpty)
          const Text('لا توجد invocation receipts بعد.')
        else
          ...invocations.map(
            (invocation) => ListTile(
              dense: true,
              leading: const Icon(Icons.check_circle_outline, size: 20),
              title: Text(invocation.adapterId),
              subtitle: Text(invocation.capabilityId),
              trailing: Text(invocation.status),
            ),
          ),
        if (reconciliation != null) ...<Widget>[
          const Divider(),
          _KeyValueGrid(
            values: <String, String>{
              'المخطط': reconciliation!.planned.join(', '),
              'المنفذ': reconciliation!.actual.join(', '),
              'المفقود': reconciliation!.missing.join(', '),
              'غير المتوقع': reconciliation!.unexpected.join(', '),
              'الحالة': reconciliation!.reconciled ? 'متطابق' : 'غير متصالح',
            },
          ),
        ],
      ],
    );
  }
}

class _ProjectToolProfileBand extends StatelessWidget {
  const _ProjectToolProfileBand();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border.all(color: Theme.of(context).dividerColor),
        borderRadius: BorderRadius.circular(6),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Project Tool Profile',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
          SizedBox(height: 6),
          Text('Flutter · Python · FastAPI · GitHub Actions · Vercel'),
          SizedBox(height: 4),
          Text('محظور: relational.runtime / Supabase'),
        ],
      ),
    );
  }
}

class _ToolDecisionRow extends StatelessWidget {
  const _ToolDecisionRow({required this.decision});

  final ToolDecision decision;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).dividerColor),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  decision.capabilityId,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Text(
                decision.selectedAdapterId ?? 'مستبعد',
                style: TextStyle(
                  color: decision.blocked
                      ? PalWakfTheme.royalRed
                      : PalWakfTheme.sovereignBlue,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 5),
          Text(decision.selectedReason),
          if (decision.approvalRequired)
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text(
                'يتطلب موافقة بشرية',
                style: TextStyle(color: PalWakfTheme.royalRed),
              ),
            ),
          ...decision.exclusions.map(
            (exclusion) => Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                '${exclusion.adapterId}: ${exclusion.reason}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RelayTab extends StatelessWidget {
  const _RelayTab({
    required this.task,
    required this.package,
    required this.controller,
  });

  final OperatorTask task;
  final ManualDispatchPackage? package;
  final OrchestratorController controller;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: <Widget>[
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.errorContainer,
            borderRadius: BorderRadius.circular(6),
          ),
          child: const Row(
            children: <Widget>[
              Icon(Icons.info_outline),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'USER RELAY FALLBACK لا يثبت قبول الاتصال الآلي ولا يغلق بوابة Agents.',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        const _SectionTitle(
          icon: Icons.forward_to_inbox_outlined,
          title: 'حزمة الإرسال اليدوي',
        ),
        const SizedBox(height: 8),
        if (!task.manualFallbackAvailable)
          const Text('يتاح المسار اليدوي بعد تسجيل فشل آلي أو اختيار صريح.')
        else if (package == null)
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: FilledButton.icon(
              onPressed: controller.generateManualPackage,
              icon: const Icon(Icons.inventory_2_outlined),
              label: const Text('إنشاء الحزمة'),
            ),
          )
        else ...<Widget>[
          _KeyValueGrid(
            values: <String, String>{
              'Receipt': package!.receipt,
              'Envelope SHA-256': package!.canonicalHash,
              'وقت الإنشاء': package!.generatedAt.toLocal().toIso8601String(),
            },
          ),
          const SizedBox(height: 12),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: FilledButton.tonalIcon(
              onPressed: () {
                Clipboard.setData(
                  ClipboardData(
                    text: const JsonEncoder.withIndent('  ')
                        .convert(package!.envelope),
                  ),
                );
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('تم نسخ الحزمة')),
                );
              },
              icon: const Icon(Icons.copy_outlined),
              label: const Text('نسخ الحزمة'),
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              OutlinedButton.icon(
                onPressed: controller.markManualDispatched,
                icon: const Icon(Icons.outbox_outlined),
                label: const Text('تم الترحيل'),
              ),
              OutlinedButton.icon(
                onPressed: () => _recordAcknowledgement(context),
                icon: const Icon(Icons.link_outlined),
                label: const Text('تسجيل إقرار Codex'),
              ),
              OutlinedButton.icon(
                onPressed:
                    task.threadId == null ? null : () => _importResult(context),
                icon: const Icon(Icons.file_download_done_outlined),
                label: const Text('استيراد النتيجة'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SelectableText(
            const JsonEncoder.withIndent('  ').convert(package!.envelope),
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
          ),
        ],
      ],
    );
  }

  Future<void> _recordAcknowledgement(BuildContext context) async {
    final input = TextEditingController(text: task.threadId);
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('إقرار Codex'),
        content: TextField(
          controller: input,
          decoration:
              const InputDecoration(labelText: 'Thread / task reference'),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, input.text.trim()),
            child: const Text('تسجيل'),
          ),
        ],
      ),
    );
    input.dispose();
    if (value != null && value.length >= 4) {
      await controller.recordManualAcknowledgement(value);
    }
  }

  Future<void> _importResult(BuildContext context) async {
    final input = TextEditingController(
      text: const JsonEncoder.withIndent('  ').convert(
        <String, dynamic>{
          'thread_reference': task.threadId,
          'before_head': task.expectedHead,
          'after_head': '',
          'commit_sha': '',
          'result_summary': '',
          'changed_files': <String>[],
          'tests': <String>[],
          'evidence': <String>[],
        },
      ),
    );
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('استيراد نتيجة منظمة'),
        content: SizedBox(
          width: 640,
          child: TextField(
            controller: input,
            minLines: 12,
            maxLines: 20,
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
          ),
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, input.text),
            child: const Text('استيراد'),
          ),
        ],
      ),
    );
    input.dispose();
    if (value == null) return;
    try {
      await controller.importManualResult(
        jsonDecode(value) as Map<String, dynamic>,
      );
    } on FormatException {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('JSON غير صالح')),
      );
    }
  }
}

class _EventsTab extends StatelessWidget {
  const _EventsTab({required this.task});

  final OperatorTask task;

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.all(20),
      itemCount: task.events.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        final event = task.events.reversed.elementAt(index);
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Padding(
              padding: const EdgeInsets.only(top: 5),
              child: _StatusDot(status: event.status),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    event.type,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  Text(event.message),
                  Text(
                    event.occurredAt.toLocal().toIso8601String(),
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.icon, required this.title});

  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Icon(icon, size: 20, color: PalWakfTheme.sovereignBlue),
        const SizedBox(width: 8),
        Text(
          title,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
      ],
    );
  }
}

class _KeyValueGrid extends StatelessWidget {
  const _KeyValueGrid({required this.values});

  final Map<String, String> values;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth >= 700
            ? (constraints.maxWidth - 12) / 2
            : constraints.maxWidth;
        return Wrap(
          spacing: 12,
          runSpacing: 8,
          children: values.entries
              .map(
                (entry) => SizedBox(
                  width: width,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          entry.key,
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                        const SizedBox(height: 2),
                        SelectableText(
                          entry.value.isEmpty ? '—' : entry.value,
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                ),
              )
              .toList(growable: false),
        );
      },
    );
  }
}

class _WarningBand extends StatelessWidget {
  const _WarningBand({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(10),
      color: Theme.of(context).colorScheme.errorContainer,
      child: Row(
        children: <Widget>[
          const Icon(Icons.block_outlined),
          const SizedBox(width: 8),
          Expanded(child: Text(message)),
        ],
      ),
    );
  }
}

class _NewTaskDialog extends StatefulWidget {
  const _NewTaskDialog();

  @override
  State<_NewTaskDialog> createState() => _NewTaskDialogState();
}

class _NewTaskDialogState extends State<_NewTaskDialog> {
  final _formKey = GlobalKey<FormState>();
  final _taskId = TextEditingController();
  final _head = TextEditingController();
  final _authority = TextEditingController();
  final _prompt = TextEditingController();
  final _constraints = TextEditingController(
    text: 'NO_PRODUCTION, NO_DATABASE, PRESERVE_AUTHORITY',
  );
  final _idempotency = TextEditingController();
  int _maxTurns = 4;
  int _timeout = 300;
  String _sandbox = 'workspace-write';

  @override
  void dispose() {
    _taskId.dispose();
    _head.dispose();
    _authority.dispose();
    _prompt.dispose();
    _constraints.dispose();
    _idempotency.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('مهمة تشغيلية جديدة'),
      content: SizedBox(
        width: 680,
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            child: Column(
              children: <Widget>[
                _field(_taskId, 'معرّف المهمة'),
                _field(_head, 'HEAD المتوقع (40 محرفًا)'),
                _field(_authority, 'مرجع التفويض'),
                _field(
                  _prompt,
                  'وصف المهمة',
                  minLines: 3,
                  maxLines: 7,
                ),
                _field(_constraints, 'القيود، مفصولة بفاصلة'),
                _field(_idempotency, 'مفتاح idempotency'),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  initialValue: _sandbox,
                  decoration: const InputDecoration(labelText: 'Sandbox'),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem(
                      value: 'read-only',
                      child: Text('قراءة فقط'),
                    ),
                    DropdownMenuItem(
                      value: 'workspace-write',
                      child: Text('كتابة مساحة العمل'),
                    ),
                  ],
                  onChanged: (value) => _sandbox = value ?? _sandbox,
                ),
                const SizedBox(height: 12),
                Row(
                  children: <Widget>[
                    Expanded(
                      child: TextFormField(
                        initialValue: '$_maxTurns',
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'الحد الأقصى للجولات',
                        ),
                        onChanged: (value) =>
                            _maxTurns = int.tryParse(value) ?? 0,
                        validator: (value) =>
                            (int.tryParse(value ?? '') ?? 0) < 1
                                ? 'مطلوب'
                                : null,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextFormField(
                        initialValue: '$_timeout',
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'المهلة بالثواني',
                        ),
                        onChanged: (value) =>
                            _timeout = int.tryParse(value) ?? 0,
                        validator: (value) =>
                            (int.tryParse(value ?? '') ?? 0) < 30
                                ? '30 ثانية على الأقل'
                                : null,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('إلغاء'),
        ),
        FilledButton.icon(
          onPressed: _submit,
          icon: const Icon(Icons.add_task),
          label: const Text('إنشاء'),
        ),
      ],
    );
  }

  Widget _field(
    TextEditingController controller,
    String label, {
    int minLines = 1,
    int maxLines = 1,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: controller,
        minLines: minLines,
        maxLines: maxLines,
        decoration: InputDecoration(labelText: label),
        validator: (value) =>
            value == null || value.trim().isEmpty ? 'هذا الحقل مطلوب' : null,
      ),
    );
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    final draft = TaskDraft(
      taskId: _taskId.text,
      projectId: 'PALWAKF_WORKSPACE_MANAGER',
      repository: 'firasfanon/palwakf_workspace_manager',
      branch: 'agent/workspace-manager-foundation-v1',
      expectedHead: _head.text,
      authorityReference: _authority.text,
      prompt: _prompt.text,
      constraints: _constraints.text
          .split(',')
          .map((value) => value.trim())
          .where((value) => value.isNotEmpty)
          .toList(growable: false),
      sandbox: _sandbox,
      maxTurns: _maxTurns,
      timeoutSeconds: _timeout,
      idempotencyKey: _idempotency.text,
      automaticFailureCode: 'OPENAI_API_PROJECT_INSUFFICIENT_QUOTA',
    );
    final errors = draft.validate();
    if (errors.isNotEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(errors.values.first)),
      );
      return;
    }
    Navigator.pop(context, draft);
  }
}
