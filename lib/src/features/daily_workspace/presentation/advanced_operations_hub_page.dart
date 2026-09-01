import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AdvancedOperationsHubPage extends StatelessWidget {
  const AdvancedOperationsHubPage({super.key});

  static const actions = <_AdvancedAction>[
    _AdvancedAction(
      'لوحة العمليات',
      'الحالة التشغيلية الموثقة ومؤشرات النظام.',
      '/dashboard',
      Icons.dashboard_outlined,
    ),
    _AdvancedAction(
      'المهام الهندسية',
      'إدارة Parent Tasks والنطاقات والـWIP.',
      '/tasks',
      Icons.task_alt_outlined,
    ),
    _AdvancedAction(
      'مركز التشغيل',
      'Runs والتفويض وخطة الأدوات والأحداث.',
      '/operations',
      Icons.settings_suggest_outlined,
    ),
    _AdvancedAction(
      'الأدوات',
      'صحة الأدوات والاتصال والصلاحيات.',
      '/tools',
      Icons.build_outlined,
    ),
    _AdvancedAction(
      'التنبيهات',
      'التنبيهات التشغيلية التي تحتاج متابعة.',
      '/alerts',
      Icons.notifications_outlined,
    ),
    _AdvancedAction(
      'الأدلة',
      'Evidence ونتائج التحقق المرتبطة بالعمل.',
      '/evidence',
      Icons.fact_check_outlined,
    ),
    _AdvancedAction(
      'التوسعات',
      'إدارة التوسعات والقدرات الإضافية.',
      '/extensions',
      Icons.extension_outlined,
    ),
    _AdvancedAction(
      'الاتصالات',
      'إعداد الخدمة والاتصالات التشغيلية.',
      '/settings/connections',
      Icons.cable_outlined,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return ListView(
      key: const ValueKey<String>('advanced-operations-hub'),
      padding: const EdgeInsets.all(24),
      children: <Widget>[
        Text(
          'الإدارة المتقدمة',
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 6),
        const Text(
          'هذه المنطقة مخصصة للتشخيص والحوكمة والتفاصيل التقنية. '
          'العمل اليومي يبدأ من الصفحة الرئيسية.',
        ),
        const SizedBox(height: 20),
        LayoutBuilder(
          builder: (context, constraints) {
            final width = constraints.maxWidth;
            final columns = width >= 1100
                ? 3
                : width >= 700
                    ? 2
                    : 1;
            final cardWidth =
                (width - ((columns - 1) * 12)) / columns.toDouble();

            return Wrap(
              spacing: 12,
              runSpacing: 12,
              children: actions
                  .map(
                    (action) => SizedBox(
                      width: cardWidth,
                      child: Card(
                        child: InkWell(
                          borderRadius: BorderRadius.circular(12),
                          onTap: () => context.go(action.route),
                          child: Padding(
                            padding: const EdgeInsets.all(18),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Icon(action.icon, size: 28),
                                const SizedBox(height: 12),
                                Text(
                                  action.label,
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleMedium
                                      ?.copyWith(fontWeight: FontWeight.w700),
                                ),
                                const SizedBox(height: 5),
                                Text(action.description),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  )
                  .toList(growable: false),
            );
          },
        ),
      ],
    );
  }
}

class _AdvancedAction {
  const _AdvancedAction(
    this.label,
    this.description,
    this.route,
    this.icon,
  );

  final String label;
  final String description;
  final String route;
  final IconData icon;
}
