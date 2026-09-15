import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/presentation/preview_mode_ui.dart';
import '../../orchestrator/application/operational_authorization.dart';
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
    ('SKILL', 'ط§ظ„ظ…ظ‡ط§ط±ط§طھ', Icons.extension_outlined),
    ('AGENT', 'ط§ظ„ظˆظƒظ„ط§ط،', Icons.smart_toy_outlined),
    ('TOOL', 'ط§ظ„ط£ط¯ظˆط§طھ', Icons.build_circle_outlined),
    ('PROVIDER', 'ط§ظ„ظ…ط²ظˆط¯ظˆظ†', Icons.psychology_alt_outlined),
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
    final authorization = ref.watch(operationalAuthorizationProvider);
    final canDispatch = authorization.asData?.value.canDispatch ?? false;
    final dataAvailable = state.summary != null && state.error == null;
    final previewUnavailable = PreviewModeUi.isVisualPreview &&
        state.error != null &&
        state.summary == null;
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
                    'ظ…ط±ظƒط² ط§ظ„طھظˆط³ط¹ط§طھ',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'ط§ظ„ط£ظˆظ„ظˆظٹط© ظ„ظ„ظ…طµط§ط¯ط± ط§ظ„ظ…ظپطھظˆط­ط©ط› ظƒظ„ ط¥ط¶ط§ظپط© ط®ط§ط±ط¬ظٹط© طھط¨ط¯ط£ ط¨ط§ظ„ط­ط¬ط± ظˆط§ظ„ظ…ط±ط§ط¬ط¹ط©.',
                  ),
                ],
              ),
              Wrap(
                spacing: 8,
                children: <Widget>[
                  Chip(
                    avatar: const Icon(Icons.security_outlined, size: 17),
                    label: Text(
                      '${PreviewModeUi.metricValue(
                        state.summary?.quarantinedExtensions ?? 0,
                        dataAvailable: dataAvailable,
                      )} ط¨ط§ظ„ط­ط¬ط±',
                    ),
                  ),
                  IconButton.outlined(
                    tooltip: 'طھط­ط¯ظٹط«',
                    onPressed:
                        ref.read(engineeringOsControllerProvider.notifier).load,
                    icon: const Icon(Icons.refresh),
                  ),
                  FilledButton.icon(
                    onPressed: previewUnavailable || !canDispatch
                        ? null
                        : () => _showAddExtension(context),
                    icon: const Icon(Icons.add),
                    label: const Text('ط¥ط¶ط§ظپط© طھظˆط³ط¹ط©'),
                  ),
                ],
              ),
            ],
          ),
        ),
        const Padding(
          padding: EdgeInsets.fromLTRB(20, 0, 20, 12),
          child: _SkillAdmissionPolicyBanner(),
        ),
        TabBar(
          controller: tabs,
          tabs: kinds
              .map((kind) => Tab(icon: Icon(kind.$3), text: kind.$2))
              .toList(growable: false),
        ),
        if (previewUnavailable)
          const PreviewModeBanner()
        else if (state.error != null)
          Material(
            color: Theme.of(context).colorScheme.errorContainer,
            child: ListTile(
              leading: const Icon(Icons.error_outline),
              title: Text(state.error!),
            ),
          ),
        Expanded(
          child: previewUnavailable
              ? const PreviewUnavailablePanel(
                  icon: Icons.extension_outlined,
                  title: 'ط¨ظٹط§ظ†ط§طھ ط§ظ„طھظˆط³ط¹ط§طھ ط؛ظٹط± ظ…طھط§ط­ط©',
                  description:
                      'ظ‡ط°ظ‡ ظ…ط¹ط§ظٹظ†ط© ط¨طµط±ظٹط© ظˆظ„ط§ طھط¹ظ†ظٹ ط£ظ† ط³ط¬ظ„ط§طھ ط§ظ„ظ…ظ‡ط§ط±ط§طھ ط£ظˆ ط§ظ„ظˆظƒظ„ط§ط، ط£ظˆ ط§ظ„ط£ط¯ظˆط§طھ ط£ظˆ ط§ظ„ظ…ط²ظˆط¯ظٹظ† ظپط§ط±ط؛ط©.',
                )
              : TabBarView(
                  controller: tabs,
                  children: kinds
                      .map(
                        (kind) => _ExtensionGrid(
                          items: state.extensions
                              .where((item) => item.kind == kind.$1)
                              .toList(growable: false),
                          emptyLabel: 'ظ„ط§ طھظˆط¬ط¯ ${kind.$2} ظ…ط³ط¬ظ„ط©',
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

class _SkillAdmissionPolicyBanner extends StatelessWidget {
  const _SkillAdmissionPolicyBanner();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            const Row(
              children: <Widget>[
                Icon(Icons.verified_user_outlined),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'بوابة قبول المهارات الخارجية — PREL5-031 / PREL5-067',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            const Text(
              'اكتشاف ← تثبيت المصدر والهاش ← الترخيص ← الأمن ← السلطة ← Sandbox/Eval ← مراجعة Mind ← قرار Workspace',
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                Chip(label: Text('Agent Skills Standard: ADOPT')),
                Chip(label: Text('Bulk install: NO')),
                Chip(label: Text('Auto promotion: NO')),
                Chip(label: Text('Self authorization: NO')),
                Chip(label: Text('Figma = Design Authority')),
              ],
            ),
          ],
        ),
      ),
    );
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
            const Text(
                'ظٹظ…ظƒظ† ط¥ط¶ط§ظپط© ظ…طµط¯ط± ظ…ظ† GitHub ط£ظˆ MCP ط£ظˆ Local ط£ظˆ API ظ…ط¹ ط­ط¬ط± ط§ظپطھط±ط§ط¶ظٹ.'),
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
                        '${item.version} آ· ${item.sourceKind}',
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
                  ? 'ظ„ط§ طھظˆط¬ط¯ ظ‚ط¯ط±ط§طھ ظ…ط¹ظ„ظ†ط©'
                  : item.capabilities.take(3).join(' آ· '),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (item.declaredRoles.isNotEmpty) ...<Widget>[
              const SizedBox(height: 4),
              Text(
                item.declaredRoles
                    .take(3)
                    .map(
                      (role) =>
                          '$role: ${item.roleAuthorities[role] ?? "NOT_AUTHORIZED"}',
                    )
                    .join(' آ· '),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
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
  final declaredRoles = TextEditingController();
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
      declaredRoles,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('ط¥ط¶ط§ظپط© طھظˆط³ط¹ط©'),
      content: SizedBox(
        width: 580,
        child: Form(
          key: key,
          child: SingleChildScrollView(
            child: Column(
              children: <Widget>[
                _field(id, 'Extension ID', ltr: true),
                _field(name, 'ط§ظ„ط§ط³ظ…'),
                _field(version, 'ط§ظ„ط¥طµط¯ط§ط±', ltr: true),
                DropdownButtonFormField<String>(
                  initialValue: kind,
                  decoration: const InputDecoration(labelText: 'ط§ظ„ظ†ظˆط¹'),
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
                  decoration: const InputDecoration(labelText: 'ط§ظ„ظ…طµط¯ط±'),
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
                  title: const Text('ظ…ظپطھظˆط­ ط§ظ„ظ…طµط¯ط±'),
                  subtitle: const Text(
                    'ط§ظ„ط£ظˆظ„ظˆظٹط© ظ„ظ„ظ…ظپطھظˆط­ ط§ظ„ظ…طµط¯ط± ظˆط§ظ„ظ‚ط§ط¨ظ„ ظ„ظ„ظپط­طµ ظˆط§ظ„طھط·ظˆظٹط±.',
                  ),
                  onChanged: (value) => setState(() => openSource = value),
                ),
                _field(
                  license,
                  openSource
                      ? 'License (ظ…ط·ظ„ظˆط¨)'
                      : 'License (ط§ط®طھظٹط§ط±ظٹ)',
                  ltr: true,
                ),
                _field(capabilities, 'Capabilities ظ…ظپطµظˆظ„ط© ط¨ظپط§طµظ„ط©',
                    ltr: true),
                _field(
                  declaredRoles,
                  'ط§ظ„ط£ط¯ظˆط§ط± ط§ظ„ظ…ط·ظ„ظˆط¨ط© (ط§ط®طھظٹط§ط±ظٹ) ظ…ظپطµظˆظ„ط© ط¨ظپط§طµظ„ط©',
                  ltr: true,
                ),
                const Align(
                  alignment: Alignment.centerRight,
                  child: Text(
                    'ط§ظ„ط£ط¯ظˆط§ط± ط§ظ„ظ…ط¹ظ„ظ†ط© ظ„ط§ طھظ…ظ†ط­ طµظ„ط§ط­ظٹط©ط› ظƒظ„ طھظˆط³ط¹ط© ط®ط§ط±ط¬ظٹط© طھط¨ظ‚ظ‰ ط؛ظٹط± ظ…طµط±ط­ ظ„ظ‡ط§ ط£ط«ظ†ط§ط، ط§ظ„ط­ط¬ط±.',
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('ط¥ظ„ط؛ط§ط،'),
        ),
        FilledButton(
            onPressed: _submit,
            child: const Text('ط¥ط¯ط®ط§ظ„ ط¥ظ„ظ‰ ط§ظ„ط­ط¬ط±')),
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
          final required = !label.contains('ط§ط®طھظٹط§ط±ظٹ') &&
              !label.startsWith('Capabilities');
          if (required && (value ?? '').trim().isEmpty) return 'ظ…ط·ظ„ظˆط¨';
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
        declaredRoles: declaredRoles.text
            .split(',')
            .map((value) => value.trim())
            .where((value) => value.isNotEmpty)
            .toList(growable: false),
      ),
    );
  }
}
