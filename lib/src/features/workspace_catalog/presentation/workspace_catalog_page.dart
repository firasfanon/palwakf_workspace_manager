import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../application/workspace_catalog_controller.dart';
import '../domain/workspace_catalog_models.dart';

class WorkspaceCatalogPage extends ConsumerStatefulWidget {
  const WorkspaceCatalogPage({super.key});

  @override
  ConsumerState<WorkspaceCatalogPage> createState() =>
      _WorkspaceCatalogPageState();
}

class _WorkspaceCatalogPageState extends ConsumerState<WorkspaceCatalogPage> {
  final _queryController = TextEditingController();
  final _privateTitleController = TextEditingController();
  final _privateTechnicalIdController = TextEditingController();
  final _privateLocalNameController = TextEditingController();
  WorkspaceItemClass? _classFilter;
  String _statusFilter = 'all';
  bool _privateIntakeExpanded = false;
  String? _privateIntakeError;

  @override
  void dispose() {
    _queryController.dispose();
    _privateTitleController.dispose();
    _privateTechnicalIdController.dispose();
    _privateLocalNameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final catalog = ref.watch(workspaceCatalogProvider);
    final statuses = catalog.items.map((item) => item.status).toSet().toList()
      ..sort();
    final visible = catalog.items.where((item) {
      final classMatch = _classFilter == null || item.itemClass == _classFilter;
      final statusMatch =
          _statusFilter == 'all' || item.status == _statusFilter;
      return classMatch && statusMatch && item.matches(_queryController.text);
    }).toList(growable: false);

    return ListView(
      key: const ValueKey<String>('workspace-catalog-page'),
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 28),
      children: <Widget>[
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1480),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                _Header(
                  catalog: catalog,
                  onAddPrivate: _togglePrivateProjectIntake,
                ),
                const SizedBox(height: 18),
                _SourceBand(catalog: catalog),
                if (_privateIntakeExpanded) ...<Widget>[
                  const SizedBox(height: 14),
                  _PrivateProjectInlineIntake(
                    titleController: _privateTitleController,
                    technicalIdController: _privateTechnicalIdController,
                    localNameController: _privateLocalNameController,
                    errorText: _privateIntakeError,
                    onCancel: _togglePrivateProjectIntake,
                    onRegister: _registerPrivateProject,
                  ),
                ],
                const SizedBox(height: 18),
                TextField(
                  key: const ValueKey<String>('workspace-catalog-search'),
                  controller: _queryController,
                  onChanged: (_) => setState(() {}),
                  decoration: const InputDecoration(
                    labelText: 'ابحث في المشاريع والأبحاث',
                    hintText:
                        'الاسم العربي، المعرف التقني، الاسم المحلي، المحافظة أو الحالة',
                    prefixIcon: Icon(Icons.search),
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: <Widget>[
                    FilterChip(
                      label: const Text('الكل'),
                      selected: _classFilter == null,
                      onSelected: (_) => setState(() => _classFilter = null),
                    ),
                    FilterChip(
                      key: const ValueKey<String>('filter-palwakf-projects'),
                      label: Text('مشاريع PalWakf (${catalog.governedCount})'),
                      selected: _classFilter ==
                          WorkspaceItemClass.palwakfGovernedProject,
                      onSelected: (_) => setState(
                        () => _classFilter =
                            WorkspaceItemClass.palwakfGovernedProject,
                      ),
                    ),
                    FilterChip(
                      key: const ValueKey<String>('filter-research'),
                      label: Text('الأبحاث (${catalog.researchCount})'),
                      selected: _classFilter == WorkspaceItemClass.research,
                      onSelected: (_) => setState(
                        () => _classFilter = WorkspaceItemClass.research,
                      ),
                    ),
                    FilterChip(
                      key: const ValueKey<String>('filter-private-projects'),
                      label: Text('مشاريعي الخاصة (${catalog.privateCount})'),
                      selected:
                          _classFilter == WorkspaceItemClass.privateProject,
                      onSelected: (_) => setState(
                        () => _classFilter = WorkspaceItemClass.privateProject,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  key: const ValueKey<String>('workspace-status-filter'),
                  initialValue: _statusFilter,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'الحالة',
                    border: OutlineInputBorder(),
                  ),
                  items: <DropdownMenuItem<String>>[
                    const DropdownMenuItem<String>(
                      value: 'all',
                      child: Text('كل الحالات'),
                    ),
                    ...statuses.map(
                      (status) => DropdownMenuItem<String>(
                        value: status,
                        child: Text(
                          status,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
                  ],
                  onChanged: (value) =>
                      setState(() => _statusFilter = value ?? 'all'),
                ),
                if (catalog.recentItems.isNotEmpty) ...<Widget>[
                  const SizedBox(height: 22),
                  Text(
                    'الأخيرة في هذه الجلسة',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: catalog.recentItems
                        .map(
                          (item) => ActionChip(
                            avatar: Icon(_iconFor(item.itemClass), size: 18),
                            label: Text(item.title),
                            onPressed: () => _openForWork(item),
                          ),
                        )
                        .toList(growable: false),
                  ),
                ],
                const SizedBox(height: 22),
                Row(
                  children: <Widget>[
                    Expanded(
                      child: Text(
                        '${visible.length} عنصرًا',
                        style:
                            Theme.of(context).textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.w800,
                                ),
                      ),
                    ),
                    Flexible(
                      child: Text(
                        '96 عنصرًا موثقًا عند بناء الدفعة + المشاريع الخاصة التي تسجلها أنت',
                        textAlign: TextAlign.end,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final columns = constraints.maxWidth >= 1240
                        ? 4
                        : constraints.maxWidth >= 900
                            ? 3
                            : constraints.maxWidth >= 600
                                ? 2
                                : 1;
                    const gap = 12.0;
                    final width =
                        (constraints.maxWidth - gap * (columns - 1)) / columns;
                    return Wrap(
                      spacing: gap,
                      runSpacing: gap,
                      children: visible
                          .map(
                            (item) => SizedBox(
                              width: width,
                              child: _CatalogCard(
                                item: item,
                                selected: catalog.selectedItemId == item.id,
                                onOpen: () => _openForWork(item),
                              ),
                            ),
                          )
                          .toList(growable: false),
                    );
                  },
                ),
                const SizedBox(height: 18),
                Text(
                  'المشاريع الخاصة لا تُنشأ تلقائيًا. «إضافة مشروع خاص» تسجل إدخال المستخدم في الجلسة الحالية فقط؛ لا تتم الكتابة إلى Drive أو GitHub في هذه الدفعة.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  void _openForWork(WorkspaceCatalogItem item) {
    ref.read(workspaceCatalogProvider.notifier).select(item.id);
    context.go('/home?itemId=${Uri.encodeComponent(item.id)}');
  }

  void _togglePrivateProjectIntake() {
    setState(() {
      _privateIntakeExpanded = !_privateIntakeExpanded;
      _privateIntakeError = null;
    });
  }

  void _registerPrivateProject() {
    final result =
        ref.read(workspaceCatalogProvider.notifier).registerPrivateProject(
              title: _privateTitleController.text,
              technicalId: _privateTechnicalIdController.text,
              localName: _privateLocalNameController.text,
            );
    if (!result.created) {
      setState(() => _privateIntakeError = result.message);
      return;
    }

    final item = result.item!;
    _privateTitleController.clear();
    _privateTechnicalIdController.clear();
    _privateLocalNameController.clear();
    _queryController.clear();
    setState(() {
      _privateIntakeExpanded = false;
      _privateIntakeError = null;
      _classFilter = WorkspaceItemClass.privateProject;
      _statusFilter = 'all';
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'تم تسجيل «${item.title}». المعرف الداخلي الثابت: ${item.projectUid}',
        ),
      ),
    );
  }
}

class _PrivateProjectInlineIntake extends StatelessWidget {
  const _PrivateProjectInlineIntake({
    required this.titleController,
    required this.technicalIdController,
    required this.localNameController,
    required this.errorText,
    required this.onCancel,
    required this.onRegister,
  });

  final TextEditingController titleController;
  final TextEditingController technicalIdController;
  final TextEditingController localNameController;
  final String? errorText;
  final VoidCallback onCancel;
  final VoidCallback onRegister;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      key: const ValueKey<String>('private-project-inline-intake'),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              children: <Widget>[
                const Icon(Icons.person_add_alt_1_outlined),
                const SizedBox(width: 9),
                Expanded(
                  child: Text(
                    'إضافة مشروع خاص',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'مسار مباشر لا يرث حوكمة PalWakf. ينشئ Workspace معرفًا داخليًا UUID ثابتًا عند التسجيل، بينما يبقى المعرف التقني اسمًا مقروءًا وفريدًا داخل مساحة العمل.',
              style: theme.textTheme.bodySmall,
            ),
            if (errorText != null) ...<Widget>[
              const SizedBox(height: 12),
              Material(
                color: theme.colorScheme.errorContainer,
                borderRadius: BorderRadius.circular(8),
                child: Padding(
                  padding: const EdgeInsets.all(10),
                  child: Text(
                    errorText!,
                    key: const ValueKey<String>(
                      'private-project-validation-error',
                    ),
                    style: TextStyle(color: theme.colorScheme.onErrorContainer),
                  ),
                ),
              ),
            ],
            const SizedBox(height: 14),
            LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 880;
                final fields = <Widget>[
                  TextField(
                    key: const ValueKey<String>('private-project-title-field'),
                    controller: titleController,
                    decoration: const InputDecoration(
                      labelText: 'اسم المشروع',
                      hintText: 'مثال: إدارة العقارات الخاصة',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  TextField(
                    key: const ValueKey<String>(
                      'private-project-technical-id-field',
                    ),
                    controller: technicalIdController,
                    textDirection: TextDirection.ltr,
                    textCapitalization: TextCapitalization.characters,
                    decoration: const InputDecoration(
                      labelText: 'المعرف التقني الفريد',
                      hintText: 'PRIVATE_REAL_ESTATE_MANAGER',
                      helperText: 'A-Z، أرقام، وشرطة سفلية. يبدأ بحرف.',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  TextField(
                    key: const ValueKey<String>(
                      'private-project-local-name-field',
                    ),
                    controller: localNameController,
                    textDirection: TextDirection.ltr,
                    decoration: const InputDecoration(
                      labelText: 'الاسم المحلي — اختياري',
                      hintText: 'private_real_estate_manager',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ];
                if (!wide) {
                  final children = <Widget>[];
                  for (var index = 0; index < fields.length; index += 1) {
                    children.add(fields[index]);
                    if (index != fields.length - 1) {
                      children.add(const SizedBox(height: 10));
                    }
                  }
                  return Column(children: children);
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Expanded(child: fields[0]),
                    const SizedBox(width: 10),
                    Expanded(child: fields[1]),
                    const SizedBox(width: 10),
                    Expanded(child: fields[2]),
                  ],
                );
              },
            ),
            const SizedBox(height: 14),
            Wrap(
              alignment: WrapAlignment.end,
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                TextButton(
                  key: const ValueKey<String>('private-project-cancel'),
                  onPressed: onCancel,
                  child: const Text('إلغاء'),
                ),
                FilledButton.icon(
                  key: const ValueKey<String>('private-project-register'),
                  onPressed: onRegister,
                  icon: const Icon(Icons.add_circle_outline),
                  label: const Text('تسجيل المشروع'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.catalog,
    required this.onAddPrivate,
  });

  final WorkspaceCatalogState catalog;
  final VoidCallback onAddPrivate;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final title = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'مشاريعي وأبحاثي',
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              'ابحث وانتقل بين مشاريع PalWakf والأبحاث والمشاريع الخاصة من مكان واحد.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
        );
        final action = FilledButton.tonalIcon(
          key: const ValueKey<String>('add-private-project'),
          onPressed: onAddPrivate,
          icon: const Icon(Icons.add),
          label: const Text('إضافة مشروع خاص'),
        );
        if (constraints.maxWidth < 720) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              title,
              const SizedBox(height: 12),
              action,
            ],
          );
        }
        return Row(
          children: <Widget>[
            Expanded(child: title),
            action,
          ],
        );
      },
    );
  }
}

class _SourceBand extends StatelessWidget {
  const _SourceBand({required this.catalog});

  final WorkspaceCatalogState catalog;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Wrap(
          spacing: 20,
          runSpacing: 10,
          children: <Widget>[
            _Count(
              icon: Icons.account_balance_outlined,
              value: catalog.governedCount,
              label: 'مشروع PalWakf',
            ),
            _Count(
              icon: Icons.menu_book_outlined,
              value: catalog.researchCount,
              label: 'بحث حقيقي',
            ),
            _Count(
              icon: Icons.person_outline,
              value: catalog.privateCount,
              label: 'مشروع خاص',
            ),
            const Chip(
              avatar: Icon(Icons.verified_outlined, size: 17),
              label: Text('لا توجد بيانات وهمية'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Count extends StatelessWidget {
  const _Count({
    required this.icon,
    required this.value,
    required this.label,
  });

  final IconData icon;
  final int value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Icon(icon, size: 20),
        const SizedBox(width: 7),
        Text(
          '$value',
          style: const TextStyle(fontWeight: FontWeight.w900),
        ),
        const SizedBox(width: 4),
        Text(label),
      ],
    );
  }
}

class _CatalogCard extends StatelessWidget {
  const _CatalogCard({
    required this.item,
    required this.selected,
    required this.onOpen,
  });

  final WorkspaceCatalogItem item;
  final bool selected;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      elevation: selected ? 2 : 0,
      child: InkWell(
        onTap: onOpen,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Icon(_iconFor(item.itemClass), color: scheme.primary),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Text(
                      item.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: <Widget>[
                  Chip(label: Text(item.itemClass.arabicLabel)),
                  Chip(label: Text(item.itemClass.workflowLabel)),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                item.status,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall,
              ),
              if (item.itemClass ==
                  WorkspaceItemClass.privateProject) ...<Widget>[
                const SizedBox(height: 6),
                if (item.technicalId != null)
                  Text(
                    item.technicalId!,
                    textDirection: TextDirection.ltr,
                    style: Theme.of(context).textTheme.labelSmall,
                  ),
                if (item.projectUid != null) ...<Widget>[
                  const SizedBox(height: 4),
                  Text(
                    'معرف داخلي ثابت',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                  ),
                  SelectableText(
                    item.projectUid!,
                    key: ValueKey<String>('project-uid-${item.projectUid}'),
                    textDirection: TextDirection.ltr,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          fontFamily: 'monospace',
                          color: scheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ],
              if (item.group != null || item.locality != null) ...<Widget>[
                const SizedBox(height: 6),
                Text(
                  <String>[
                    if (item.group != null) item.group!,
                    if (item.locality != null) item.locality!,
                  ].join(' · '),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                ),
              ],
              const SizedBox(height: 12),
              Align(
                alignment: AlignmentDirectional.centerStart,
                child: TextButton.icon(
                  onPressed: onOpen,
                  icon: const Icon(Icons.arrow_back_rounded),
                  label: const Text('اختيار للعمل'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

IconData _iconFor(WorkspaceItemClass itemClass) => switch (itemClass) {
      WorkspaceItemClass.palwakfGovernedProject =>
        Icons.account_balance_outlined,
      WorkspaceItemClass.research => Icons.menu_book_outlined,
      WorkspaceItemClass.privateProject => Icons.person_outline,
    };
