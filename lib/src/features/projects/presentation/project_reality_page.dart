import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/palwakf_theme.dart';
import '../application/external_projects_controller.dart';
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
    final controller = ref.read(externalProjectsControllerProvider.notifier);
    final reality = state.realityByProject[widget.projectId];
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          tooltip: 'سجل المشاريع',
          onPressed: () => context.go('/projects'),
          icon: const Icon(Icons.arrow_forward),
        ),
        title: const Text('حقيقة المشروع'),
        actions: <Widget>[
          IconButton(
            tooltip: 'فحص قراءة فقط',
            onPressed:
                state.loading ? null : () => controller.probe(widget.projectId),
            icon: const Icon(Icons.radar),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: <Widget>[
            if (state.loading) const LinearProgressIndicator(minHeight: 2),
            if (state.error != null)
              _RealityError(
                message: state.error!,
                onProbe: () => controller.probe(widget.projectId),
              ),
            Expanded(
              child: reality == null
                  ? _UnprobedState(
                      onProbe: () => controller.probe(widget.projectId),
                    )
                  : _RealityView(
                      reality: reality,
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
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _UnprobedState extends StatelessWidget {
  const _UnprobedState({required this.onProbe});

  final VoidCallback onProbe;

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

class _RealityView extends StatelessWidget {
  const _RealityView({required this.reality, required this.onPrepare});

  final ProjectReality reality;
  final Future<void> Function(String candidateId) onPrepare;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 40),
      children: <Widget>[
        _RealityHeader(reality: reality),
        const Divider(height: 34),
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
                  ...reality.stack.map((value) => Chip(label: Text(value))),
                  ...reality.packageManagers.map(
                    (value) => Chip(
                      avatar: const Icon(Icons.inventory_2_outlined, size: 16),
                      label: Text(value),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              ...reality.commands.map(
                (command) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.chevron_left),
                  title: SelectableText(
                    command.command,
                    textDirection: TextDirection.ltr,
                  ),
                  subtitle: Text('${command.purpose} · ${command.evidence}'),
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
              if (reality.ci.isEmpty)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.remove_circle_outline),
                  title: const Text('لا توجد GitHub Actions workflows'),
                  trailing: Text(reality.ciStatus),
                )
              else
                ...reality.ci.map(
                  (item) => ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.checklist_outlined),
                    title: Text(item.name),
                    subtitle: Text(item.provider),
                    trailing: Text(item.conclusion ?? item.status),
                  ),
                ),
              ...reality.deployments.map(
                (item) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.rocket_launch_outlined),
                  title: Text(item.provider),
                  subtitle: Text(item.evidence),
                  trailing: Text(item.status),
                ),
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.fact_check_outlined),
                title: const Text('حالة النشر المجمعة'),
                trailing: Text(reality.deploymentStatus),
              ),
            ],
          ),
        ),
        const Divider(height: 34),
        _Section(
          title: 'قرار الأدوات',
          icon: Icons.route_outlined,
          child: Column(
            children: reality.capabilityProfile.all
                .map((decision) => _ToolDecisionTile(decision: decision))
                .toList(growable: false),
          ),
        ),
        const Divider(height: 34),
        _Section(
          title: 'مرشحو العمل التالي',
          icon: Icons.format_list_numbered,
          child: Column(
            children: reality.candidates
                .map(
                  (candidate) => _CandidateCard(
                    candidate: candidate,
                    onPrepare: () => onPrepare(candidate.candidateId),
                  ),
                )
                .toList(growable: false),
          ),
        ),
      ],
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
  const _CandidateCard({required this.candidate, required this.onPrepare});

  final CandidateWorkItem candidate;
  final VoidCallback onPrepare;

  @override
  Widget build(BuildContext context) {
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
            Align(
              alignment: AlignmentDirectional.centerEnd,
              child: FilledButton.tonalIcon(
                onPressed: candidate.blocked ? null : onPrepare,
                icon: const Icon(Icons.drafts_outlined),
                label: const Text('تجهيز غلاف مهمة'),
              ),
            ),
          ],
        ),
      ),
    );
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
  final VoidCallback onProbe;

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
