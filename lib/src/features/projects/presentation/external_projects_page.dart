import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/domain/operational_data_state.dart';
import '../../../core/presentation/preview_mode_ui.dart';
import '../application/external_projects_controller.dart';
import '../domain/external_project_models.dart';

class ExternalProjectsPage extends ConsumerStatefulWidget {
  const ExternalProjectsPage({super.key});

  @override
  ConsumerState<ExternalProjectsPage> createState() =>
      _ExternalProjectsPageState();
}

class _ExternalProjectsPageState extends ConsumerState<ExternalProjectsPage> {
  @override
  void initState() {
    super.initState();
    Future<void>.microtask(
      () => ref.read(externalProjectsControllerProvider.notifier).load(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(externalProjectsControllerProvider);
    final controller = ref.read(externalProjectsControllerProvider.notifier);
    final availability = PreviewModeUi.resolveAvailability(
      loading: state.loading,
      sourceConfirmed: state.loaded,
      hasData: state.projects.isNotEmpty,
      error: state.error,
    );
    final previewUnavailable =
        availability == OperationalDataAvailability.unavailable;
    final writesEnabled = PreviewModeUi.canMutate(availability);
    return Material(
      child: Column(
        children: <Widget>[
          if (state.loading) const LinearProgressIndicator(minHeight: 2),
          if (previewUnavailable)
            const PreviewModeBanner()
          else if (state.error != null)
            _ErrorBand(message: state.error!, onRetry: controller.load),
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final intake = _ProjectIntakePanel(
                  onSubmit: controller.intake,
                  enabled: writesEnabled,
                );
                final registry = _ProjectRegistry(
                  projects: state.projects,
                  availability: availability,
                );
                if (constraints.maxWidth < 820) {
                  return ListView(
                    children: <Widget>[
                      intake,
                      const Divider(height: 1),
                      SizedBox(height: 520, child: registry),
                    ],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    SizedBox(width: 350, child: intake),
                    const VerticalDivider(width: 1),
                    Expanded(child: registry),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _ProjectIntakePanel extends StatefulWidget {
  const _ProjectIntakePanel({
    required this.onSubmit,
    required this.enabled,
  });

  final Future<ExternalProject?> Function(ProjectIntakeDraft draft) onSubmit;
  final bool enabled;

  @override
  State<_ProjectIntakePanel> createState() => _ProjectIntakePanelState();
}

class _ProjectIntakePanelState extends State<_ProjectIntakePanel> {
  final _formKey = GlobalKey<FormState>();
  final _repository = TextEditingController(text: 'firasfanon/Pal_Eyes');
  final _displayName = TextEditingController(text: 'بعيون فلسطينية');
  final _localPath = TextEditingController();
  var _adapter = 'github_repository';

  @override
  void dispose() {
    _repository.dispose();
    _displayName.dispose();
    _localPath.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Text(
              'إدخال مشروع',
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 6),
            const Text('سلطة القراءة فقط ثابتة، ولا تنشئ فرعًا أو مهمة تنفيذ.'),
            const SizedBox(height: 20),
            TextFormField(
              enabled: widget.enabled,
              controller: _repository,
              textDirection: TextDirection.ltr,
              decoration: const InputDecoration(
                labelText: 'GitHub owner/repository',
                prefixIcon: Icon(Icons.code),
              ),
              validator: (value) {
                final parts = (value ?? '').trim().split('/');
                return parts.length == 2 &&
                        parts.every((part) => part.isNotEmpty)
                    ? null
                    : 'أدخل مستودعًا بصيغة owner/repository';
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              enabled: widget.enabled,
              controller: _displayName,
              decoration: const InputDecoration(
                labelText: 'اسم العرض',
                prefixIcon: Icon(Icons.badge_outlined),
              ),
              validator: (value) =>
                  (value ?? '').trim().isEmpty ? 'الاسم مطلوب' : null,
            ),
            const SizedBox(height: 16),
            SegmentedButton<String>(
              segments: const <ButtonSegment<String>>[
                ButtonSegment<String>(
                  value: 'github_repository',
                  icon: Icon(Icons.cloud_outlined),
                  label: Text('GitHub'),
                ),
                ButtonSegment<String>(
                  value: 'local_git',
                  icon: Icon(Icons.folder_outlined),
                  label: Text('محلي مسموح'),
                ),
              ],
              selected: <String>{_adapter},
              onSelectionChanged: widget.enabled
                  ? (values) {
                      setState(() => _adapter = values.single);
                    }
                  : null,
            ),
            if (_adapter == 'local_git') ...<Widget>[
              const SizedBox(height: 12),
              TextFormField(
                enabled: widget.enabled,
                controller: _localPath,
                textDirection: TextDirection.ltr,
                decoration: const InputDecoration(
                  labelText: 'المسار الموجود في allowlist',
                  prefixIcon: Icon(Icons.folder_open_outlined),
                ),
                validator: (value) =>
                    (value ?? '').trim().isEmpty ? 'المسار مطلوب' : null,
              ),
            ],
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: widget.enabled ? _submit : null,
              icon: const Icon(Icons.playlist_add),
              label: Text(
                widget.enabled ? 'تسجيل دون فحص' : 'متاح في التشغيل المتصل فقط',
              ),
            ),
            const SizedBox(height: 14),
            const _AuthorityFact(
              icon: Icons.visibility_outlined,
              label: 'READ_ONLY_ZERO_MUTATION',
            ),
            const _AuthorityFact(
              icon: Icons.storage_outlined,
              label: 'Supabase محظور',
            ),
            const _AuthorityFact(
              icon: Icons.rocket_launch_outlined,
              label: 'لا ترقية Production',
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final created = await widget.onSubmit(
      ProjectIntakeDraft(
        repositoryFullName: _repository.text.trim(),
        displayName: _displayName.text.trim(),
        adapter: _adapter,
        localRepositoryPath:
            _adapter == 'local_git' ? _localPath.text.trim() : null,
      ),
    );
    if (!mounted || created == null) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('تم التسجيل. الفحص يحتاج أمرًا مستقلًا.')),
    );
  }
}

class _AuthorityFact extends StatelessWidget {
  const _AuthorityFact({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Row(
        children: <Widget>[
          Icon(icon, size: 17),
          const SizedBox(width: 8),
          Expanded(child: Text(label)),
        ],
      ),
    );
  }
}

class _ProjectRegistry extends StatefulWidget {
  const _ProjectRegistry({
    required this.projects,
    required this.availability,
  });

  final List<ExternalProject> projects;
  final OperationalDataAvailability availability;

  @override
  State<_ProjectRegistry> createState() => _ProjectRegistryState();
}

class _ProjectRegistryState extends State<_ProjectRegistry> {
  String _query = '';
  String _status = 'all';
  String _sort = 'name';

  @override
  Widget build(BuildContext context) {
    if (widget.availability == OperationalDataAvailability.unavailable) {
      return const PreviewUnavailablePanel(
        icon: Icons.hub_outlined,
        title: 'بيانات المشاريع غير متاحة',
        description:
            'هذه معاينة بصرية ولا تعني أن سجل المشاريع فارغ. ستظهر المشاريع بعد الاتصال بمصدر الحقيقة.',
      );
    }
    if (widget.projects.isEmpty) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(Icons.inventory_2_outlined, size: 42),
            SizedBox(height: 10),
            Text('لا توجد مشاريع خارجية مسجلة'),
          ],
        ),
      );
    }
    final statuses = widget.projects.map((item) => item.status).toSet().toList()
      ..sort();
    final visible = widget.projects.where((project) {
      final query = _query.trim().toLowerCase();
      final matchesQuery = query.isEmpty ||
          project.displayName.toLowerCase().contains(query) ||
          project.repositoryFullName.toLowerCase().contains(query) ||
          project.stack.any((value) => value.toLowerCase().contains(query));
      return matchesQuery && (_status == 'all' || project.status == _status);
    }).toList(growable: true);
    visible.sort((left, right) {
      return switch (_sort) {
        'status' => left.status.compareTo(right.status),
        'head' => (left.observedHead ?? '').compareTo(right.observedHead ?? ''),
        _ => left.displayName.compareTo(right.displayName),
      };
    });
    return Column(
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 8),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final search = TextField(
                decoration: const InputDecoration(
                  labelText: 'بحث في المشاريع',
                  prefixIcon: Icon(Icons.search),
                ),
                onChanged: (value) => setState(() => _query = value),
              );
              final controls = Row(
                children: <Widget>[
                  Expanded(
                    child: DropdownButtonFormField<String>(
                      isExpanded: true,
                      initialValue: _status,
                      decoration: const InputDecoration(labelText: 'الحالة'),
                      items: <DropdownMenuItem<String>>[
                        const DropdownMenuItem(
                          value: 'all',
                          child: Text('كل الحالات'),
                        ),
                        ...statuses.map(
                          (status) => DropdownMenuItem(
                            value: status,
                            child: Text(status),
                          ),
                        ),
                      ],
                      onChanged: (value) =>
                          setState(() => _status = value ?? 'all'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: DropdownButtonFormField<String>(
                      isExpanded: true,
                      initialValue: _sort,
                      decoration: const InputDecoration(labelText: 'الترتيب'),
                      items: const <DropdownMenuItem<String>>[
                        DropdownMenuItem(
                          value: 'name',
                          child: Text('الاسم'),
                        ),
                        DropdownMenuItem(
                          value: 'status',
                          child: Text('الحالة'),
                        ),
                        DropdownMenuItem(
                          value: 'head',
                          child: Text('HEAD'),
                        ),
                      ],
                      onChanged: (value) =>
                          setState(() => _sort = value ?? 'name'),
                    ),
                  ),
                ],
              );
              if (constraints.maxWidth < 620) {
                return Column(
                  children: <Widget>[
                    search,
                    const SizedBox(height: 10),
                    controls,
                  ],
                );
              }
              return Row(
                children: <Widget>[
                  Expanded(flex: 2, child: search),
                  const SizedBox(width: 10),
                  Expanded(flex: 2, child: controls),
                ],
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
          child: Align(
            alignment: AlignmentDirectional.centerStart,
            child: Text('${visible.length} من ${widget.projects.length}'),
          ),
        ),
        Expanded(
          child: visible.isEmpty
              ? const Center(child: Text('لا توجد نتائج مطابقة.'))
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                  itemCount: visible.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (context, index) {
                    final project = visible[index];
                    return Card(
                      child: InkWell(
                        onTap: () =>
                            context.go('/projects/${project.projectId}'),
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Row(
                            children: <Widget>[
                              CircleAvatar(
                                child: Icon(
                                  project.adapter == 'local_git'
                                      ? Icons.folder_outlined
                                      : Icons.cloud_outlined,
                                ),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: <Widget>[
                                    Text(
                                      project.displayName,
                                      style: const TextStyle(
                                          fontWeight: FontWeight.w800),
                                    ),
                                    const SizedBox(height: 3),
                                    Text(
                                      project.repositoryFullName,
                                      textDirection: TextDirection.ltr,
                                    ),
                                    const SizedBox(height: 7),
                                    Wrap(
                                      spacing: 8,
                                      runSpacing: 6,
                                      children: <Widget>[
                                        Chip(label: Text(project.status)),
                                        if (project.defaultBranch != null)
                                          Chip(
                                              label:
                                                  Text(project.defaultBranch!)),
                                        ...project.stack.map(
                                          (value) => Chip(label: Text(value)),
                                        ),
                                      ],
                                    ),
                                    if (project.observedHead !=
                                        null) ...<Widget>[
                                      const SizedBox(height: 7),
                                      Text(
                                        project.observedHead!,
                                        textDirection: TextDirection.ltr,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodySmall,
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                              const Icon(Icons.chevron_left),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

class _ErrorBand extends StatelessWidget {
  const _ErrorBand({required this.message, required this.onRetry});

  final String message;
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
            IconButton(
              tooltip: 'إعادة المحاولة',
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
      ),
    );
  }
}
