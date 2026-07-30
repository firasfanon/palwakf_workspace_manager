import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

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
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          tooltip: 'مساحة التشغيل',
          onPressed: () => context.go('/'),
          icon: const Icon(Icons.arrow_forward),
        ),
        title: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('المشاريع الخارجية'),
            Text(
              'قراءة الواقع دون تعديل المصدر',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w400),
            ),
          ],
        ),
        actions: <Widget>[
          IconButton(
            tooltip: 'تحديث السجل',
            onPressed: state.loading ? null : controller.load,
            icon: const Icon(Icons.refresh),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: <Widget>[
            if (state.loading) const LinearProgressIndicator(minHeight: 2),
            if (state.error != null)
              _ErrorBand(message: state.error!, onRetry: controller.load),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final intake = _ProjectIntakePanel(
                    onSubmit: controller.intake,
                  );
                  final registry = _ProjectRegistry(projects: state.projects);
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
      ),
    );
  }
}

class _ProjectIntakePanel extends StatefulWidget {
  const _ProjectIntakePanel({required this.onSubmit});

  final Future<ExternalProject?> Function(ProjectIntakeDraft draft) onSubmit;

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
              onSelectionChanged: (values) {
                setState(() => _adapter = values.single);
              },
            ),
            if (_adapter == 'local_git') ...<Widget>[
              const SizedBox(height: 12),
              TextFormField(
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
              onPressed: _submit,
              icon: const Icon(Icons.playlist_add),
              label: const Text('تسجيل دون فحص'),
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

class _ProjectRegistry extends StatelessWidget {
  const _ProjectRegistry({required this.projects});

  final List<ExternalProject> projects;

  @override
  Widget build(BuildContext context) {
    if (projects.isEmpty) {
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
    return ListView.separated(
      padding: const EdgeInsets.all(20),
      itemCount: projects.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final project = projects[index];
        return Card(
          child: InkWell(
            onTap: () => context.go('/projects/${project.projectId}'),
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
                          style: const TextStyle(fontWeight: FontWeight.w800),
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
                              Chip(label: Text(project.defaultBranch!)),
                            ...project.stack.map(
                              (value) => Chip(label: Text(value)),
                            ),
                          ],
                        ),
                        if (project.observedHead != null) ...<Widget>[
                          const SizedBox(height: 7),
                          Text(
                            project.observedHead!,
                            textDirection: TextDirection.ltr,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.bodySmall,
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
