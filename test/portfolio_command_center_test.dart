import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/portfolio_intelligence/application/portfolio_intelligence_controller.dart';
import 'package:palwakf_workspace_manager/src/features/portfolio_intelligence/data/portfolio_intelligence_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/portfolio_intelligence/domain/portfolio_intelligence_models.dart';
import 'package:palwakf_workspace_manager/src/features/portfolio_intelligence/presentation/portfolio_command_center_page.dart';

class FakePortfolioApi implements PortfolioIntelligenceApi {
  FakePortfolioApi(this.snapshot);
  final PortfolioCommandCenterSnapshot snapshot;

  @override
  Future<PortfolioCommandCenterSnapshot> overview() async => snapshot;
}

PortfolioCommandCenterSnapshot makeSnapshot() {
  return PortfolioCommandCenterSnapshot.fromJson(<String, dynamic>{
    'generated_at': '2026-09-23T00:00:00Z',
    'snapshot_id': 'snapshot-test',
    'truth_state': 'DEGRADED',
    'truth_confidence': 72,
    'truth_explanation_ar': <String>['UNKNOWN لا يعني غياب البيانات.'],
    'source_health': <Map<String, dynamic>>[
      <String, dynamic>{
        'source_id': 'WORKSPACE_RUNTIME',
        'label_ar': 'واقع التشغيل المحلي',
        'state': 'HEALTHY',
        'freshness': 'LIVE',
        'detail_ar': 'Orchestrator متصل.',
        'authority': 'LOCAL_EXECUTION_REALITY',
        'observed_at': '2026-09-23T00:00:00Z',
      },
      <String, dynamic>{
        'source_id': 'WORKSPACE_DRIVE_SOVEREIGN',
        'label_ar': 'Workspace Drive السيادي',
        'state': 'UNKNOWN',
        'freshness': 'NO_LIVE_RUNTIME_ADAPTER',
        'detail_ar': 'UNKNOWN لا يعني غياب الوثائق.',
        'authority': 'WORKSPACE_DRIVE_SOVEREIGN',
        'observed_at': null,
      },
    ],
    'kpis': <Map<String, dynamic>>[
      <String, dynamic>{
        'kpi_id': 'truth_confidence',
        'label_ar': 'ثقة الحقيقة',
        'value': '72%',
        'status': 'DEGRADED',
        'confidence': 1.0,
        'explanation_ar': 'مؤشر Source Health وليس نسبة إنجاز.',
        'evidence_refs': <String>[],
      },
    ],
    'projects': <Map<String, dynamic>>[
      <String, dynamic>{
        'project_id': 'PALWAKF_WORKSPACE_MANAGER',
        'display_name': 'PalWakf Workspace Manager',
        'repository_full_name': 'firasfanon/palwakf_workspace_manager',
        'truth_state': 'VERIFIED',
        'current_status': 'registered',
        'readiness': 'READY',
        'maturity_state': 'VERIFIED_RUNTIME',
        'scope_progress_percent': null,
        'scope_progress_basis':
            'UNAVAILABLE_NO_CANONICAL_SCOPE_PROFILE_IN_RUNTIME',
        'priority_score': 25,
        'priority_factors': <Map<String, dynamic>>[
          <String, dynamic>{
            'factor': 'BLOCKING_IMPACT',
            'value': 0,
            'weight': 35,
            'explanation_ar': 'لا يوجد مانع صريح.',
          },
        ],
        'next_action_ar': 'NO_ACTION — لا توجد إشارة تفرض تطويرًا جديدًا.',
        'blockers': <String>[],
        'observed_branch': 'main',
        'observed_head': '493f5e9c89714adb989583f9aa652416f61b50bd',
        'ci_status': 'SUCCESS',
        'deployment_status': 'READY',
        'drift_status': 'ALIGNED',
        'evidence_count': 4,
        'task_count': 1,
        'tool_gap_count': 0,
        'last_verified_at': '2026-09-23T00:00:00Z',
        'forecast': <String, dynamic>{
          'project_id': 'PALWAKF_WORKSPACE_MANAGER',
          'status': 'UNAVAILABLE',
          'p50': null,
          'p80': null,
          'confidence': 0.2,
          'conditions_ar': <String>['لا توجد عينة cycle-time كافية.'],
          'basis': 'NO_FABRICATED_ETA_WITHOUT_HISTORICAL_CYCLE_TIME',
        },
        'evidence_refs': <String>[],
      },
    ],
    'recommendations': <Map<String, dynamic>>[
      <String, dynamic>{
        'recommendation_id': 'decision-1',
        'type': 'DECIDE_NOW',
        'subject_id': 'D1',
        'reason_ar': 'قرار بشري مطلوب.',
        'evidence_refs': <String>[],
        'affected_projects': <String>['PALWAKF_WORKSPACE_MANAGER'],
        'unlock_count': 1,
        'risk_if_deferred_ar': 'يبقى المسار منتظرًا.',
        'estimated_effort': 'LOW',
        'confidence': 0.95,
        'status': 'PROPOSED',
        'authority': 'ADVISORY_ONLY',
      },
    ],
    'dependencies': <Map<String, dynamic>>[],
    'critical_path': <String, dynamic>{
      'status': 'UNAVAILABLE',
      'project_ids': <String>[],
      'most_blocking_project_id': null,
      'reason_ar': 'لا يتم اختلاق dependency graph عند غياب المصدر المعتمد.',
      'evidence_refs': <String>[],
    },
    'forecasts': <Map<String, dynamic>>[],
    'capabilities': <Map<String, dynamic>>[
      <String, dynamic>{
        'entity_id': 'CAP_GITHUB',
        'name_ar': 'GitHub — حقيقة الكود',
        'category': 'CAPABILITY',
        'lifecycle': 'VERIFIED',
        'status': 'READY',
        'description_ar': 'قدرة لا تمنح سلطة.',
        'owner': 'PALWAKF_WORKSPACE_MANAGER',
        'evidence_refs': <String>[],
        'deferred_reason_ar': null,
        'reopen_trigger_ar': null,
      },
    ],
    'skills': <Map<String, dynamic>>[
      <String, dynamic>{
        'entity_id': 'SKILL_REGISTRY_RUNTIME_PROJECTION',
        'name_ar': 'سجل المهارات المؤسسية',
        'category': 'SKILL',
        'lifecycle': 'DEFERRED_RUNTIME_PROJECTION',
        'status': 'NOT_IMPORTED_TO_RUNTIME',
        'description_ar': 'لا تُختلق قائمة Canonical غير مستوردة.',
        'owner': 'PALWAKF_MIND_ASSISTANT',
        'evidence_refs': <String>[],
        'deferred_reason_ar': 'لا يوجد live adapter.',
        'reopen_trigger_ar': 'Import محكوم.',
      },
    ],
    'tools': <Map<String, dynamic>>[],
    'agents': <Map<String, dynamic>>[],
    'providers': <Map<String, dynamic>>[
      <String, dynamic>{
        'entity_id': 'PROVIDER_CODEX',
        'name_ar': 'Codex',
        'category': 'PROVIDER',
        'lifecycle': 'HOLD',
        'status': 'SUSPENDED_BY_POLICY',
        'description_ar': 'غير مفوض للتطوير.',
        'owner': 'PALWAKF_WORKSPACE_MANAGER',
        'evidence_refs': <String>[],
        'deferred_reason_ar': 'CODEX_DEVELOPMENT_SUSPENDED',
        'reopen_trigger_ar': 'SEPARATE_EXPLICIT_PROGRAM_DECISION',
      },
    ],
    'risks': <Map<String, dynamic>>[],
    'decisions': <Map<String, dynamic>>[],
    'recent_changes': <Map<String, dynamic>>[],
    'evidence_refs': <String>['evidence/safe.json'],
    'authority_notes': <String>[
      'RECOMMENDATIONS_DO_NOT_AUTHORIZE_EXECUTION',
      'CAPABILITY_IS_NOT_AUTHORITY',
      'UNKNOWN_IS_NOT_FALSE',
    ],
    'provenance': <String>['PORTFOLIO_INTELLIGENCE_READ_ONLY_PROJECTION_V1'],
  });
}

Future<void> pumpCommandCenter(
  WidgetTester tester,
  Size size,
) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  await tester.pumpWidget(
    ProviderScope(
      overrides: <Override>[
        portfolioIntelligenceApiProvider.overrideWithValue(
          FakePortfolioApi(makeSnapshot()),
        ),
      ],
      child: const MaterialApp(
        home: Directionality(
          textDirection: TextDirection.rtl,
          child: PortfolioCommandCenterPage(),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('command center is responsive on narrow RTL', (tester) async {
    await pumpCommandCenter(tester, const Size(390, 844));

    expect(find.text('مركز قيادة المشاريع والقدرات'), findsOneWidget);
    expect(find.text('حالة مصادر البيانات والأنظمة'), findsOneWidget);
    expect(find.text('المؤشرات التنفيذية للمحفظة'), findsOneWidget);
    expect(find.text('أهم المشاريع الاستراتيجية'), findsOneWidget);
    expect(find.textContaining('غير متاح'), findsWidgets);
    expect(find.text('ADVISORY_ONLY'), findsOneWidget);
    expect(find.text('SUSPENDED_BY_POLICY'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('command center is responsive on desktop RTL', (tester) async {
    await pumpCommandCenter(tester, const Size(1440, 1000));

    expect(
      find.byKey(
        const ValueKey<String>('project-PALWAKF_WORKSPACE_MANAGER'),
      ),
      findsOneWidget,
    );
    expect(find.text('PalWakf Workspace Manager'), findsWidgets);
    expect(find.text('Workspace Drive السيادي'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  test('parser preserves unknown and unavailable semantics', () {
    final snapshot = makeSnapshot();

    expect(snapshot.truthState, 'DEGRADED');
    expect(
      snapshot.sourceHealth
          .firstWhere((item) => item.sourceId == 'WORKSPACE_DRIVE_SOVEREIGN')
          .state,
      'UNKNOWN',
    );
    expect(snapshot.projects.single.scopeProgressPercent, isNull);
    expect(snapshot.projects.single.forecast.p50, isNull);
    expect(snapshot.criticalPath.status, 'UNAVAILABLE');
    expect(snapshot.recommendations.single.authority, 'ADVISORY_ONLY');
  });
}
