import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/app/workspace_manager_app.dart';
import 'package:palwakf_workspace_manager/src/features/dashboard/application/dashboard_controller.dart';
import 'package:palwakf_workspace_manager/src/features/dashboard/data/dashboard_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/dashboard/domain/dashboard_models.dart';

class FakeDashboardApi implements DashboardApi {
  final now = DateTime.utc(2026, 7, 31, 12);

  @override
  Future<DashboardSummary> summary() async {
    return DashboardSummary(
      generatedAt: now,
      portfolioTotal: 1,
      portfolioReady: 1,
      portfolioAttentionRequired: 0,
      activeRepositoryWriters: 0,
      humanActionRequired: 1,
      tasks: const TaskStatusSummary(
        total: 3,
        queued: 0,
        running: 1,
        pendingVerification: 1,
        verified: 1,
        failed: 0,
        stale: 0,
        activeTaskIds: <String>['PALWAKF_TASK'],
        latestVerifiedTaskId: 'PALWAKF_VERIFIED',
      ),
      tools: const ToolHealthSummary(
        total: 4,
        healthy: 3,
        degraded: 0,
        blocked: 0,
        stale: 1,
        unknown: 0,
        requiredAttention: 1,
      ),
      alertCount: 1,
      criticalAlertCount: 0,
      projects: <PortfolioProjectSummary>[
        PortfolioProjectSummary(
          projectId: 'FIRASFANON_PAL_EYES',
          displayName: 'بعيون فلسطينية',
          repositoryFullName: 'firasfanon/Pal_Eyes',
          status: 'probed',
          readiness: 'READY',
          attentionRequired: false,
          freshness: 'FRESH',
          stack: <String>['Flutter', 'Dart'],
          ciStatus: 'NOT_CONFIGURED',
          deploymentStatus: 'NOT_DISCOVERED',
          driftStatus: 'UNCHANGED',
          blockers: <String>[],
          toolGapCount: 0,
          taskCount: 1,
          activeWriter: false,
          evidenceCount: 3,
          observedBranch: 'main',
          observedHead: 'c67ff5e28205aac57ff28e8b8120c3bac5de4488',
          topCandidateId: 'GIS_INPUTS',
          topCandidateTitle: 'التحقق من مدخلات مرشح GIS',
        ),
      ],
      connection: const ConnectionReadinessSummary(
        mode: 'LOCAL_SECURE_MODE',
        ready: true,
        authenticationConfigured: true,
        storeHealthy: true,
        workersStarted: true,
        localSecure: true,
        chatgptLiveState: 'PENDING_NOT_ACTIVATED',
        executionHostCompatibility: 'CURRENT_RUNTIME_BOUND',
        toolExecutorCompatibility: 'CURRENT_RUNTIME_BOUND',
      ),
      checkpoints: <ResumeCheckpointSummary>[
        ResumeCheckpointSummary(
          checkpointId: 'task-PALWAKF_TASK',
          taskId: 'PALWAKF_TASK',
          status: 'running',
          updatedAt: now,
          nextAction: 'Resume from the latest task event',
        ),
      ],
      actions: const <DashboardAction>[
        DashboardAction(
          actionId: 'review-alerts',
          label: 'Review operational alerts',
          route: '/alerts',
          enabled: true,
          authority: 'READ_ONLY_REVIEW',
        ),
      ],
    );
  }

  @override
  Future<List<RecentActivity>> activity({int limit = 30}) async =>
      <RecentActivity>[
        RecentActivity(
          activityId: 'task-1',
          kind: 'task_event',
          subjectId: 'PALWAKF_TASK',
          title: 'dispatch',
          detail: 'queued',
          occurredAt: now,
          status: 'running',
          provenance: 'OPERATOR_TASK_STORE',
        ),
      ];

  @override
  Future<List<OperationalAlert>> alerts() async => <OperationalAlert>[
        OperationalAlert(
          alertId: 'codex-stale',
          severity: 'warning',
          sourceKind: 'tool',
          sourceId: 'codex',
          code: 'HEALTH_EVIDENCE_STALE_OR_UNAVAILABLE',
          message: 'Operational health evidence is not fresh',
          requiredAction: 'Probe the adapter',
          observedAt: now,
          freshness: 'FRESH',
        ),
      ];

  @override
  Future<List<EvidenceIndexItem>> evidence({int limit = 50}) async =>
      const <EvidenceIndexItem>[
        EvidenceIndexItem(
          evidenceId: 'safe-report',
          associationKind: 'project',
          associationId: 'FIRASFANON_PAL_EYES',
          evidenceType: 'EXTERNAL_PROJECT_REALITY_REPORT_V1',
          safeReference: 'evidence/PAL_EYES_REALITY_REPORT_V1.json',
          status: 'PASS',
          provenance: 'REPOSITORY_EVIDENCE',
        ),
      ];
}

void main() {
  for (final size in <Size>[
    const Size(360, 800),
    const Size(768, 900),
    const Size(1024, 900),
    const Size(1440, 900),
  ]) {
    testWidgets('dashboard shell has no overflow at ${size.width.toInt()}px',
        (tester) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        ProviderScope(
          overrides: <Override>[
            dashboardApiProvider.overrideWithValue(FakeDashboardApi()),
          ],
          child: const WorkspaceManagerApp(),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('لوحة العمليات'), findsWidgets);
      expect(tester.takeException(), isNull);
      final scrollable = find.byType(Scrollable).last;
      await tester.scrollUntilVisible(
        find.text('بعيون فلسطينية'),
        500,
        scrollable: scrollable,
      );
      expect(find.text('بعيون فلسطينية'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('PENDING_NOT_ACTIVATED'),
        500,
        scrollable: scrollable,
      );
      expect(find.text('PENDING_NOT_ACTIVATED'), findsOneWidget);
      expect(find.text('Read-only Foundation'), findsNothing);
      expect(find.text('لا توجد بيانات تشغيلية'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  }
}
