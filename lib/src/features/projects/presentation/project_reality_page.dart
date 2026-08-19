import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/domain/operational_data_state.dart';
import '../../../core/presentation/preview_mode_ui.dart';
import '../../../core/theme/palwakf_theme.dart';
import '../../dashboard/application/dashboard_controller.dart';
import '../../orchestrator/application/operational_authorization.dart';
import '../application/external_projects_controller.dart';
import '../data/project_task_bridge_api_client.dart';
import '../domain/external_project_models.dart';

class ProjectRealityPage extends ConsumerStatefulWidget {
  const ProjectRealityPage({required this.projectId, super.key});

  final String projectId;

  @override
  ConsumerState<ProjectRealityPage> createState() => _ProjectRealityPageState();
}

class _ProjectRealityPageState extends ConsumerState<ProjectRealityPage> {
  @override
  void initState() {
    super.initState();
    Future<void>.microtask(
      () => ref
          .read(externalProjectsControllerProvider.notifier)
          .loadReality(widget.projectId),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(externalProjectsControllerProvider);
    final authorization = ref.watch(operationalAuthorizationProvider);
    final authorizationValue = authorization.asData?.value;
    final canDispatch = authorizationValue?.canDispatch ?? false;
    final canProbe = authorizationValue?.canProbeTools ?? false;
    final controller = ref.read(externalProjectsControllerProvider.notifier);
    final reality = state.realityByProject[widget.projectId];
    final availability = PreviewModeUi.resolveAvailability(
      loading: state.loading,
      sourceConfirmed: reality != null,
      hasData: reality != null,
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
            _RealityError(
              message: state.error!,
              onProbe:
                  canProbe ? () => controller.probe(widget.projectId) : null,
            ),
          Expanded(
            child: previewUnavailable
                ? const PreviewUnavailablePanel(
                    icon: Icons.radar_outlined,
                    title: 'بيانات واقع المشروع غير متاحة',
                    description:
                        'لا يمكن استنتاج غياب خط الأساس أو المهام أو الأدلة من معاينة غير متصلة.',
                  )
                : reality == null
                    ? _UnprobedState(
                        onProbe: canProbe
                            ? () => controller.probe(widget.projectId)
                            : null,
                      )
                    : _RealityView(
                        reality: reality,
                        canDispatch: canDispatch,
                        canProbe: canProbe,
                        onPrepare: (candidateId) async {
                          final prepared = await controller.prepareTask(
                            widget.projectId,
                            candidateId,
                          );
                          if (!context.mounted || !prepared) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'تم تجهيز الغلاف فقط. لم يتم إرسال أي مهمة.',
                              ),
                            ),
                          );
                        },
                        onCreateTask: (candidate) =>
                            _createCandidateTask(reality, candidate),
                      ),
          ),
        ],
      ),
    );
  }

  Future<void> _createCandidateTask(
    ProjectReality reality,
    CandidateWorkItem candidate,
  ) async {
    final draft = await showDialog<ProjectCandidateEngineeringTaskDraft>(
      context: context,
      builder: (context) => _CreateCandidateTaskDialog(
        reality: reality,
        candidate: candidate,
      ),
    );
    if (draft == null || !mounted) return;

    try {
      final created =
          await ref.read(projectTaskBridgeApiProvider).createEngineeringTask(
                reality.projectId,
                candidate.candidateId,
                draft,
              );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('تم إنشاء المهمة ${created.taskId}.')),
      );
      context.go(
        Uri(
          path: '/operations',
          queryParameters: <String, String>{
            'engineeringTaskId': created.taskId,
          },
        ).toString(),
      );
    } on ProjectTaskBridgeApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.message)),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString())),
      );
    }
  }
}

class _UnprobedState extends StatelessWidget {
  const _UnprobedState({required this.onProbe});

  final VoidCallback? onProbe;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          const Icon(Icons.radar, size: 46),
          const SizedBox(height: 12),
          Text(
            'لم يُنشأ خط أساس للواقع بعد',
            style: Theme.of(context)
                .textTheme
                .titleLarge
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 6),
          const Text('الفحص يقرأ GitHub ولا ينفذ أوامر المشروع.'),
          const SizedBox(height: 18),
          FilledButton.icon(
            onPressed: onProbe,
            icon: const Icon(Icons.visibility_outlined),
            label: const Text('ابدأ فحص القراءة'),
          ),
        ],
      ),
    );
  }
}

class _RealityView extends ConsumerWidget {
  const _RealityView({
    required this.reality,
    required this.canDispatch,
    required this.canProbe,
    required this.onPrepare,
    required this.onCreateTask,
  });

  final ProjectReality reality;
  final bool canDispatch;
  final bool canProbe;
  final Future<void> Function(String candidateId) onPrepare;
  final Future<void> Function(CandidateWorkItem candidate) onCreateTask;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dashboard = ref.watch(dashboardControllerProvider);
    final dashboardAvailable = dashboard.summary != null;
    final projectSummary = dashboard.summary?.projects
        .where((item) => item.projectId == reality.projectId)
        .firstOrNull;
    final evidence = dashboard.evidence
        .where(
          (item) =>
              item.associationId == reality.projectId ||
              item.safeReference.contains(reality.projectId),
        )
        .toList(growable: false);
    return DefaultTabController(
      length: 6,
      child: Column(
        children: <Widget>[
          Row(
            children: <Widget>[
              IconButton(
                tooltip: 'العودة إلى المشاريع',
                onPressed: () => Navigator.of(context).canPop()
                    ? Navigator.of(context).pop()
                    : null,
                icon: const Icon(Icons.arrow_forward),
              ),
              Expanded(
                child: TabBar(
                  isScrollable: true,
                  tabs: const <Widget>[
                    Tab(text: 'نظرة عامة'),
                    Tab(text: 'الواقع'),
                    Tab(text: 'المهام'),
                    Tab(text: 'ملف الأدوات'),
                    Tab(text: 'العمل المرشح'),
                    Tab(text: 'الأدلة'),
                  ],
                ),
              ),
              IconButton(
                tooltip: 'فحص قراءة فقط',
                onPressed: canProbe
                    ? () => ref
                        .read(externalProjectsControllerProvider.notifier)
                        .probe(reality.projectId)
                    : null,
                icon: const Icon(Icons.radar),
              ),
            ],
          ),
          Expanded(
            child: TabBarView(
              children: <Widget>[
                _ProjectTab(
                  children: <Widget>[
                    _RealityHeader(reality: reality),
                    const Divider(height: 34),
                    _Section(
                      title: 'الحالة التشغيلية',
                      icon: Icons.monitor_heart_outlined,
                      child: Column(
                        children: <Widget>[
                          _ProjectFact(
                            label: 'الجاهزية',
                            value: projectSummary?.readiness ?? 'UNKNOWN',
                          ),
                          _ProjectFact(
                            label: 'المهام',
                            value: dashboardAvailable
                                ? '${projectSummary?.taskCount ?? 0}'
                                : '—',
                          ),
                          _ProjectFact(
                            label: 'فجوات الأدوات',
                            value: dashboardAvailable
                                ? '${projectSummary?.toolGapCount ?? 0}'
                                : '—',
                          ),
                          _ProjectFact(
                            label: 'كاتب مستودع نشط',
                            value: !dashboardAvailable
                                ? '—'
                                : projectSummary?.activeWriter ?? false
                                    ? 'نعم'
                                    : 'لا',
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                _ProjectTab(
                  children: <Widget>[
                    _Section(
                      title: 'المكدس والأوامر',
                      icon: Icons.terminal,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: <Widget>[
                              ...reality.stack
                                  .map((value) => Chip(label: Text(value))),
                              ...reality.packageManagers.map(
                                (value) => Chip(label: Text(value)),
                              ),
                            ],
                          ),
                          ...reality.commands.map(
                            (command) => ListTile(
                              contentPadding: EdgeInsets.zero,
                              title: SelectableText(
                                command.command,
                                textDirection: TextDirection.ltr,
                              ),
                              subtitle: Text(
                                '${command.purpose} · ${command.evidence}',
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Divider(height: 34),
                    _Section(
                      title: 'CI والنشر',
                      icon: Icons.account_tree_outlined,
                      child: Column(
                        children: <Widget>[
                          _ProjectFact(
                            label: 'CI',
                            value: reality.ciStatus,
                          ),
                          _ProjectFact(
                            label: 'النشر',
                            value: reality.deploymentStatus,
                          ),
                          _ProjectFact(
                            label: 'الانحراف',
                            value: reality.driftStatus,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                _ProjectTab(
                  children: <Widget>[
                    _Section(
                      title: 'مهام المشروع',
                      icon: Icons.task_alt_outlined,
                      child: !dashboardAvailable
                          ? const Text('بيانات مهام المشروع غير متاحة.')
                          : projectSummary == null ||
                                  projectSummary.taskCount == 0
                              ? const Text('لا توجد مهام مرتبطة في المخزن.')
                              : Column(
                                  children: <Widget>[
                                    _ProjectFact(
                                      label: 'إجمالي المهام',
                                      value: '${projectSummary.taskCount}',
                                    ),
                                    _ProjectFact(
                                      label: 'المرشح الأعلى',
                                      value: projectSummary.topCandidateTitle ??
                                          'UNKNOWN',
                                    ),
                                  ],
                                ),
                    ),
                  ],
                ),
                _ProjectTab(
                  children: <Widget>[
                    _Section(
                      title: 'قرار الأدوات',
                      icon: Icons.route_outlined,
                      child: Column(
                        children: reality.capabilityProfile.all
                            .map(
                              (decision) =>
                                  _ToolDecisionTile(decision: decision),
                            )
                            .toList(growable: false),
                      ),
                    ),
                  ],
                ),
                _ProjectTab(
                  children: <Widget>[
                    _Section(
                      title: 'مرشحو العمل التالي',
                      icon: Icons.format_list_numbered,
                      child: Column(
                        children: reality.candidates
                            .map(
                              (candidate) => _CandidateCard(
                                candidate: candidate,
                                enabled: canDispatch,
                                onPrepare: () =>
                                    onPrepare(candidate.candidateId),
                                onCreate: () => onCreateTask(candidate),
                              ),
                            )
                            .toList(growable: false),
                      ),
                    ),
                  ],
                ),
                _ProjectTab(
                  children: <Widget>[
                    _Section(
                      title: 'الأدلة الآمنة',
                      icon: Icons.fact_check_outlined,
                      child: !dashboardAvailable
                          ? const Text('بيانات الأدلة غير متاحة.')
                          : evidence.isEmpty
                              ? const Text('لا توجد مراجع دليل مرتبطة وآمنة.')
                              : Column(
                                  children: evidence
                                      .map(
                                        (item) => ListTile(
                                          contentPadding: EdgeInsets.zero,
                                          title: Text(item.evidenceType),
                                          subtitle: SelectableText(
                                            item.safeReference,
                                            textDirection: TextDirection.ltr,
                                          ),
                                          trailing: Text(item.status),
                                        ),
                                      )
                                      .toList(growable: false),
                                ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ProjectTab extends StatelessWidget {
  const _ProjectTab({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 40),
      children: children,
    );
  }
}

class _ProjectFact extends StatelessWidget {
  const _ProjectFact({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(label),
      trailing: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 280),
        child: Text(
          value,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          textAlign: TextAlign.end,
        ),
      ),
    );
  }
}

class _RealityHeader extends StatelessWidget {
  const _RealityHeader({required this.reality});

  final ProjectReality reality;

  @override
  Widget build(BuildContext context) {
    final drifted = reality.driftStatus == 'HEAD_DRIFT';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                reality.repositoryFullName,
                textDirection: TextDirection.ltr,
                style: Theme.of(context)
                    .textTheme
                    .headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
            ),
            Chip(
              avatar: Icon(
                drifted ? Icons.warning_amber : Icons.verified_outlined,
                size: 17,
              ),
              label: Text(reality.driftStatus),
              side: BorderSide(
                color:
                    drifted ? PalWakfTheme.royalRed : PalWakfTheme.successGreen,
              ),
            ),
          ],
        ),
        const SizedBox(height: 14),
        _FactGrid(
          facts: <String, String>{
            'الفرع الافتراضي': reality.defaultBranch,
            'الفرع المرصود': reality.observedBranch,
            'الرؤية': reality.visibility,
            'الملفات': '${reality.scannedFiles}/${reality.totalFiles}',
            'HEAD': reality.observedHead,
            'Reality fingerprint': reality.baselineFingerprint,
          },
        ),
        const SizedBox(height: 12),
        Row(
          children: <Widget>[
            Icon(
              reality.ignoredSecretPolicyPresent
                  ? Icons.shield_outlined
                  : Icons.warning_amber,
              size: 18,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                reality.ignoredSecretPolicyPresent
                    ? 'سياسة تجاهل ملفات الأسرار مرصودة؛ لم تُقرأ قيمها.'
                    : 'لم تُثبت سياسة تجاهل ملفات الأسرار.',
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    required this.title,
    required this.icon,
    required this.child,
  });

  final String title;
  final IconData icon;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Row(
          children: <Widget>[
            Icon(icon, size: 20),
            const SizedBox(width: 8),
            Text(
              title,
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
          ],
        ),
        const SizedBox(height: 12),
        child,
      ],
    );
  }
}

class _ToolDecisionTile extends StatelessWidget {
  const _ToolDecisionTile({required this.decision});

  final ProjectToolDecision decision;

  @override
  Widget build(BuildContext context) {
    final blocked = decision.disposition == 'blocked';
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        blocked ? Icons.block_outlined : Icons.build_outlined,
        color: blocked ? PalWakfTheme.royalRed : null,
      ),
      title: Text(decision.adapterId),
      subtitle: Text(decision.reason),
      trailing: Text(
        decision.disposition,
        style: TextStyle(
          color: blocked ? PalWakfTheme.royalRed : null,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _CandidateCard extends StatelessWidget {
  const _CandidateCard({
    required this.candidate,
    required this.enabled,
    required this.onPrepare,
    required this.onCreate,
  });

  final CandidateWorkItem candidate;
  final bool enabled;
  final VoidCallback onPrepare;
  final VoidCallback onCreate;

  @override
  Widget build(BuildContext context) {
    final disabled = candidate.blocked || !enabled;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              children: <Widget>[
                CircleAvatar(
                  radius: 16,
                  child: Text('${candidate.rank}'),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    candidate.title,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(candidate.rationale),
            const SizedBox(height: 8),
            Text(
              'معيار القبول: ${candidate.acceptanceTest}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 12),
            Wrap(
              alignment: WrapAlignment.end,
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                OutlinedButton.icon(
                  onPressed: disabled ? null : onPrepare,
                  icon: const Icon(Icons.drafts_outlined),
                  label: const Text('تجهيز غلاف مهمة'),
                ),
                FilledButton.icon(
                  key: ValueKey<String>(
                    'create-engineering-task-${candidate.candidateId}',
                  ),
                  onPressed: disabled ? null : onCreate,
                  icon: const Icon(Icons.add_task),
                  label: const Text('إنشاء مهمة تشغيلية'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _CreateCandidateTaskDialog extends StatefulWidget {
  const _CreateCandidateTaskDialog({
    required this.reality,
    required this.candidate,
  });

  final ProjectReality reality;
  final CandidateWorkItem candidate;

  @override
  State<_CreateCandidateTaskDialog> createState() =>
      _CreateCandidateTaskDialogState();
}

class _CreateCandidateTaskDialogState
    extends State<_CreateCandidateTaskDialog> {
  final formKey = GlobalKey<FormState>();
  late final TextEditingController taskId;
  final owner = TextEditingController(text: 'firas');
  final actor = TextEditingController(text: 'firas');
  final provider = TextEditingController();
  late final TextEditingController scopes;
  String actorType = 'HUMAN';

  @override
  void initState() {
    super.initState();
    taskId = TextEditingController(
      text: _suggestTaskId(widget.candidate.candidateId),
    );
    scopes = TextEditingController(text: _suggestScopes(widget.reality));
  }

  @override
  void dispose() {
    taskId.dispose();
    owner.dispose();
    actor.dispose();
    provider.dispose();
    scopes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final branchPreview = taskId.text.trim().isEmpty
        ? 'task/<TASK_ID>'
        : 'task/${taskId.text.trim()}';
    return AlertDialog(
      title: const Text('إنشاء مهمة تشغيلية من المرشح'),
      content: SizedBox(
        width: 680,
        child: Form(
          key: formKey,
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Text(
                  widget.candidate.title,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 12),
                _readonly('المستودع', widget.reality.repositoryFullName),
                _readonly('HEAD المرصود', widget.reality.observedHead),
                _readonly('الفرع المشتق', branchPreview),
                const SizedBox(height: 12),
                _field(taskId, 'Task ID', ltr: true, onChanged: (_) {
                  setState(() {});
                }),
                _field(owner, 'Owner'),
                _field(actor, 'Actor'),
                DropdownButtonFormField<String>(
                  initialValue: actorType,
                  decoration: const InputDecoration(labelText: 'Actor Type'),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem(value: 'HUMAN', child: Text('Human')),
                    DropdownMenuItem(value: 'AGENT', child: Text('Agent')),
                    DropdownMenuItem(value: 'LLM', child: Text('LLM')),
                  ],
                  onChanged: (value) =>
                      setState(() => actorType = value ?? 'HUMAN'),
                ),
                const SizedBox(height: 10),
                _field(provider, 'Provider ID (اختياري)', ltr: true),
                _field(scopes, 'نطاقات التعديل مفصولة بفاصلة', ltr: true),
                const SizedBox(height: 8),
                const Text(
                  'المشروع والمستودع وHEAD والفرع لا تُرسل كسلطة من الواجهة؛ يشتقها الخادم من واقع المشروع المرصود.',
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
        FilledButton(
          onPressed: _submit,
          child: const Text('إنشاء المهمة'),
        ),
      ],
    );
  }

  Widget _readonly(String label, String value) {
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      title: Text(label),
      subtitle: SelectableText(
        value,
        textDirection: TextDirection.ltr,
      ),
    );
  }

  Widget _field(
    TextEditingController controller,
    String label, {
    bool ltr = false,
    ValueChanged<String>? onChanged,
  }) {
    final optional = label.contains('اختياري');
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextFormField(
        controller: controller,
        textDirection: ltr ? TextDirection.ltr : null,
        onChanged: onChanged,
        decoration: InputDecoration(labelText: label),
        validator: (value) {
          if (optional) return null;
          return (value ?? '').trim().isEmpty ? 'مطلوب' : null;
        },
      ),
    );
  }

  void _submit() {
    if (!formKey.currentState!.validate()) return;
    final parsedScopes = scopes.text
        .split(',')
        .map((value) => value.trim())
        .where((value) => value.isNotEmpty)
        .toList(growable: false);
    if (parsedScopes.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('يجب تحديد نطاق تعديل واحد على الأقل.')),
      );
      return;
    }
    Navigator.pop(
      context,
      ProjectCandidateEngineeringTaskDraft(
        taskId: taskId.text.trim(),
        ownerId: owner.text.trim(),
        actorId: actor.text.trim(),
        actorType: actorType,
        providerId: provider.text.trim().isEmpty ? null : provider.text.trim(),
        scopePatterns: parsedScopes,
      ),
    );
  }

  static String _suggestTaskId(String candidateId) {
    var normalized =
        candidateId.toUpperCase().replaceAll(RegExp(r'[^A-Z0-9_-]'), '-');
    if (normalized.length < 3) {
      normalized = 'TASK-$normalized';
    }
    if (!RegExp(r'^[A-Z0-9]').hasMatch(normalized)) {
      normalized = 'TASK-$normalized';
    }
    return normalized.length <= 128 ? normalized : normalized.substring(0, 128);
  }

  static String _suggestScopes(ProjectReality reality) {
    final stack = reality.stack.map((value) => value.toLowerCase()).toSet();
    final values = <String>[];
    if (stack.contains('flutter') || stack.contains('dart')) {
      values.addAll(<String>['lib/**', 'test/**']);
    }
    if (stack.contains('python')) {
      values.addAll(<String>['src/**', 'tests/**']);
    }
    return values.toSet().join(',');
  }
}

class _FactGrid extends StatelessWidget {
  const _FactGrid({required this.facts});

  final Map<String, String> facts;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth >= 760
            ? (constraints.maxWidth - 16) / 2
            : constraints.maxWidth;
        return Wrap(
          spacing: 16,
          runSpacing: 12,
          children: facts.entries
              .map(
                (entry) => SizedBox(
                  width: width,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        entry.key,
                        style: Theme.of(context).textTheme.labelSmall,
                      ),
                      const SizedBox(height: 3),
                      SelectableText(
                        entry.value,
                        textDirection: entry.key.contains('HEAD') ||
                                entry.key.contains('fingerprint')
                            ? TextDirection.ltr
                            : TextDirection.rtl,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                    ],
                  ),
                ),
              )
              .toList(growable: false),
        );
      },
    );
  }
}

class _RealityError extends StatelessWidget {
  const _RealityError({required this.message, required this.onProbe});

  final String message;
  final VoidCallback? onProbe;

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
            TextButton.icon(
              onPressed: onProbe,
              icon: const Icon(Icons.radar),
              label: const Text('فحص'),
            ),
          ],
        ),
      ),
    );
  }
}
