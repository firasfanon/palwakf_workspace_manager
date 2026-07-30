import 'package:flutter/material.dart';

import '../../../core/theme/palwakf_theme.dart';

class WorkspaceDashboardPage extends StatelessWidget {
  const WorkspaceDashboardPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('مدير مساحة عمل PalWakf'),
        actions: const <Widget>[
          Padding(
            padding: EdgeInsetsDirectional.only(end: 16),
            child: Center(child: Text('Foundation V1')),
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1180),
            child: ListView(
              padding: const EdgeInsets.all(24),
              children: <Widget>[
                const _FoundationBanner(),
                const SizedBox(height: 24),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final columns = constraints.maxWidth >= 900 ? 3 : 1;
                    final width =
                        (constraints.maxWidth - ((columns - 1) * 16)) / columns;
                    return Wrap(
                      spacing: 16,
                      runSpacing: 16,
                      children: <Widget>[
                        _StatusCard(
                          width: width,
                          title: 'مصدر الكود',
                          value: 'GitHub',
                          detail: 'المستودعات هي الحقيقة التقنية.',
                          icon: Icons.account_tree_outlined,
                        ),
                        _StatusCard(
                          width: width,
                          title: 'حالة التشغيل',
                          value: 'Read-only Foundation',
                          detail: 'لا توجد كتابة قاعدة بيانات أو إنتاج.',
                          icon: Icons.verified_user_outlined,
                        ),
                        _StatusCard(
                          width: width,
                          title: 'محرك الاستئناف',
                          value: 'عقود أولية',
                          detail: 'Reality + Drift + Authorization Gates.',
                          icon: Icons.restart_alt,
                        ),
                      ],
                    );
                  },
                ),
                const SizedBox(height: 24),
                const _EmptyOperationalState(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _FoundationBanner extends StatelessWidget {
  const _FoundationBanner();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const Icon(
              Icons.shield_outlined,
              size: 42,
              color: PalWakfTheme.waqfGold,
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'الذاكرة التشغيلية السيادية للمحفظة',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                          color: PalWakfTheme.sovereignBlue,
                        ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'هذه النسخة تؤسس العقود والنطاق فقط. لا تعرض بيانات تشغيلية '
                    'حقيقية ولا تنفذ أي Mutation.',
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  const _StatusCard({
    required this.width,
    required this.title,
    required this.value,
    required this.detail,
    required this.icon,
  });

  final double width;
  final String title;
  final String value;
  final String detail;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Icon(icon, color: PalWakfTheme.sovereignBlue),
              const SizedBox(height: 16),
              Text(title, style: Theme.of(context).textTheme.labelLarge),
              const SizedBox(height: 6),
              Text(
                value,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const SizedBox(height: 8),
              Text(detail),
            ],
          ),
        ),
      ),
    );
  }
}

class _EmptyOperationalState extends StatelessWidget {
  const _EmptyOperationalState();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          children: <Widget>[
            const Icon(Icons.inventory_2_outlined, size: 48),
            const SizedBox(height: 12),
            Text(
              'لم تُربط بيانات تشغيلية بعد',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            const Text(
              'سيبدأ Project Intake لاحقًا بقراءة هوية المستودع والـBaseline '
              'وملف التوريث والأدلة عبر محولات قراءة فقط.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
