import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/orchestrator_controller.dart';

Future<void> showServiceAuthDialog(
  BuildContext context,
  WidgetRef ref,
) async {
  final controller = TextEditingController();
  final token = await showDialog<String>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Row(
        children: <Widget>[
          Icon(Icons.lock_outline),
          SizedBox(width: 10),
          Text('مصادقة الخدمة'),
        ],
      ),
      content: TextField(
        controller: controller,
        autofocus: true,
        obscureText: true,
        decoration: const InputDecoration(
          labelText: 'رمز الوصول',
          prefixIcon: Icon(Icons.key_outlined),
        ),
        onSubmitted: (value) => Navigator.of(context).pop(value),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('إلغاء'),
        ),
        FilledButton.icon(
          onPressed: () => Navigator.of(context).pop(controller.text),
          icon: const Icon(Icons.login),
          label: const Text('اتصال'),
        ),
      ],
    ),
  );
  controller.dispose();
  if (token == null || token.trim().isEmpty) return;
  ref.read(orchestratorTokenProvider.notifier).state = token.trim();
  await ref.read(orchestratorControllerProvider.notifier).load();
}
