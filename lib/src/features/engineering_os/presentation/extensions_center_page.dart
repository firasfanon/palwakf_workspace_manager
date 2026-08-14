import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/engineering_os_controller.dart';
import '../domain/engineering_os_models.dart';

class ExtensionsCenterPage extends ConsumerStatefulWidget {
  const ExtensionsCenterPage({super.key});

  @override
  ConsumerState<ExtensionsCenterPage> createState() =>
      _ExtensionsCenterPageState();
}

class _ExtensionsCenterPageState extends ConsumerState<ExtensionsCenterPage>
    with SingleTickerProviderStateMixin {
  late final TabController tabs;

  static const kinds = <(String, String, IconData)>[
    ('SKILL', 'المهارات', Icons.extension_outlined),
    ('AGENT', 'الوكلاء', Icons.smart_toy_outlined),
    ('TOOL', 'الأدوات', Icons.build_circle_outlined),
    ('PROVIDER', 'المزودون', Icons.psychology_alt_outlined),
  ];

  @override
  void initState() {
    super.initState();
    tabs = TabController(length: kinds.length, vsync: this);
    Future<void>.microtask(
      () => ref.read(engineeringOsControllerProvider.notifier).load(),
    );
  }

  @override
  void dispose() {
    tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(engineeringOsControllerProvider);
    return Column(
      children: <Widget>[
        if (state.loading) const LinearProgressIndicator(minHeight: 2),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 12),
          child: Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 16,
            runSpacing: 12,
            children: <Widget>[
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'مركز التوسعات',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Open Source First · كل إضافة خارجية تبدأ بالحجر والمراجعة.',
                  ),
                ],
              ),
              Wrap(
                spacing: 8,
                children: <Widget>[
                  Chip(
                    avatar: const Icon(Icons.security_outlined, size: 17),
                    label: Text(
                      '${state.summary?.quarantinedExtensions ?? 0} بالحجر',
                    ),
                  ),
                  IconButton.outlined(
                    tooltip: 'تحديث',
                    onPressed:
                        ref.read(engineeringOsControllerProvider.notifier).load,
                    icon: const Icon(Icons.refresh),
                  ),
                  FilledButton.icon(
                    onPressed: () => _showAddExtension(context),
                    icon: const Icon(Icons.add),
                    label: const Text('إضافة توسعة'),
                  ),
                ],
              ),
            ],
          ),
        ),
        TabBar(
          controller: tabs,
          tabs: kinds
              .map((kind) => Tab(icon: Icon(kind.$3), text: kind.$2))
              .toList(growable: false),
        ),
        if (state.error != null)
          Material(
            color: Theme.of(context).colorScheme.errorContainer,
            child: ListTile(
              leading: const Icon(Icons.error_outline),
              title: Text(state.error!),
            ),
          ),
        Expanded(
          child: TabBarView(
            controller: tabs,
            children: kinds
                .map(
                  (kind) => _ExtensionGrid(
                    items: state.extensions
                        .where((item) => item.kind == kind.$1)
                        .toList(growable: false),
                    emptyLabel: 'لا توجد ${kind.$2} مسجلة',
                  ),
                )
                .toList(growable: false),
          ),
        ),
      ],
    );
  }

  Future<void> _showAddExtension(BuildContext context) async {
    final draft = await showDialog<NewExtensionDraft>(
      context: context,
      builder: (context) => const _NewExtensionDialog(),
    );
    if (draft == null || !mounted) return;
    try {
      await ref
          .read(engineeringOsControllerProvider.notifier)
          .registerExtension(draft);
    } catch (error) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.toString())));
    }
  }
}

class _ExtensionGrid extends StatelessWidget {
  const _ExtensionGrid({required this.items, required this.emptyLabel});

  final List<ExtensionRecord> items;
  final String emptyLabel;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const Icon(Icons.extension_off_outlined, size: 46),
            const SizedBox(height: 10),
            Text(emptyLabel),
            const SizedBox(height: 4),
            const Text('يمكن إضافة GitHub / MCP / Local / API مع حجر افتراضي.'),
          ],
        ),
      );
    }
    return GridView.builder(
      padding: const EdgeInsets.all(20),
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 390,
        mainAxisExtent: 260,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
      ),
      itemCount: items.length,
      itemBuilder: (context, index) => _ExtensionCard(item: items[index]),
    );
  }
}

class _ExtensionCard extends StatelessWidget {
  const _ExtensionCard({required this.item});
  final ExtensionRecord item;

  @override
  Widget build(BuildContext context) {
    final quarantined = item.lifecycle == 'QUARANTINED';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              children: <Widget>[
                CircleAvatar(child: Icon(_icon(item.kind))),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        item.name,
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                      Text(
                        '${item.version} · ${item.sourceKind}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            SelectableText(
              item.sourceReference,
              textDirection: TextDirection.ltr,
              maxLines: 2,
            ),
            const Spacer(),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: <Widget>[
                Chip(label: Text(item.openSource ? 'Open Source' : 'External')),
                if (item.license != null) Chip(label: Text(item.license!)),
                Chip(label: Text(item.riskClass)),
                Chip(
                  avatar: Icon(
                    quarantined
                        ? Icons.shield_outlined
                        : Icons.check_circle_outline,
                    size: 16,
                  ),
                  label: Text(item.lifecycle),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              item.capabilities.isEmpty
                  ? 'لا توجد قدرات معلنة'
                  : item.capabilities.take(3).join(' · '),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }

  IconData _icon(String kind) {
    switch (kind) {
      case 'SKILL':
        return Icons.extension_outlined;
      case 'AGENT':
        return Icons.smart_toy_outlined;
      case 'TOOL':
        return Icons.build_circle_outlined;
      default:
        return Icons.psychology_alt_outlined;
    }
  }
}

class _NewExtensionDialog extends StatefulWidget {
  const _NewExtensionDialog();

  @override
  State<_NewExtensionDialog> createState() => _NewExtensionDialogState();
}

class _NewExtensionDialogState extends State<_NewExtensionDialog> {
  final key = GlobalKey<FormState>();
  final id = TextEditingController();
  final name = TextEditingController();
  final version = TextEditingController(text: '0.1.0');
  final source = TextEditingController();
  final license = TextEditingController();
  final capabilities = TextEditingController();
  String kind = 'SKILL';
  String sourceKind = 'GITHUB';
  bool openSource = true;

  @override
  void dispose() {
    for (final controller in <TextEditingController>[
      id,
      name,
      version,
      source,
      license,
      capabilities,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('إضافة توسعة'),
      content: SizedBox(
        width: 580,
        child: Form(
          key: key,
          child: SingleChildScrollView(
            child: Column(
              children: <Widget>[
                _field(id, 'Extension ID', ltr: true),
                _field(name, 'الاسم'),
                _field(version, 'الإصدار', ltr: true),
                DropdownButtonFormField<String>(
                  initialValue: kind,
                  decoration: const InputDecoration(labelText: 'النوع'),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem(value: 'SKILL', child: Text('Skill')),
                    DropdownMenuItem(value: 'AGENT', child: Text('Agent')),
                    DropdownMenuItem(value: 'TOOL', child: Text('Tool')),
                    DropdownMenuItem(
                      value: 'PROVIDER',
                      child: Text('Provider'),
                    ),
                  ],
                  onChanged: (value) => setState(() => kind = value ?? 'SKILL'),
                ),
                const SizedBox(height: 10),
                DropdownButtonFormField<String>(
                  initialValue: sourceKind,
                  decoration: const InputDecoration(labelText: 'المصدر'),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem(value: 'GITHUB', child: Text('GitHub')),
                    DropdownMenuItem(value: 'MCP', child: Text('MCP')),
                    DropdownMenuItem(value: 'LOCAL', child: Text('Local')),
                    DropdownMenuItem(value: 'API', child: Text('API')),
                    DropdownMenuItem(
                      value: 'INTERNAL',
                      child: Text('Internal'),
                    ),
                  ],
                  onChanged: (value) =>
                      setState(() => sourceKind = value ?? 'GITHUB'),
                ),
                _field(source, 'Source reference', ltr: true),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  value: openSource,
                  title: const Text('مفتوح المصدر'),
                  subtitle: const Text(
                    'الأولوية للمفتوح المصدر والقابل للفحص والتطوير.',
                  ),
                  onChanged: (value) => setState(() => openSource = value),
                ),
                _field(
                  license,
                  openSource ? 'License (مطلوب)' : 'License (اختياري)',
                  ltr: true,
                ),
                _field(capabilities, 'Capabilities مفصولة بفاصلة', ltr: true),
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
        FilledButton(onPressed: _submit, child: const Text('إدخال إلى الحجر')),
      ],
    );
  }

  Widget _field(
    TextEditingController controller,
    String label, {
    bool ltr = false,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextFormField(
        controller: controller,
        textDirection: ltr ? TextDirection.ltr : null,
        decoration: InputDecoration(labelText: label),
        validator: (value) {
          final required =
              !label.contains('اختياري') && !label.startsWith('Capabilities');
          if (required && (value ?? '').trim().isEmpty) return 'مطلوب';
          return null;
        },
      ),
    );
  }

  void _submit() {
    if (!key.currentState!.validate()) return;
    Navigator.pop(
      context,
      NewExtensionDraft(
        extensionId: id.text.trim(),
        kind: kind,
        name: name.text.trim(),
        version: version.text.trim(),
        sourceKind: sourceKind,
        sourceReference: source.text.trim(),
        openSource: openSource,
        license: license.text.trim().isEmpty ? null : license.text.trim(),
        capabilities: capabilities.text
            .split(',')
            .map((value) => value.trim())
            .where((value) => value.isNotEmpty)
            .toList(growable: false),
      ),
    );
  }
}
