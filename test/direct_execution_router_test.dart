import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/direct_execution/application/direct_execution_controller.dart';
import 'package:palwakf_workspace_manager/src/features/direct_execution/data/direct_execution_api_client.dart';
import 'package:palwakf_workspace_manager/src/features/direct_execution/domain/direct_execution_models.dart';
import 'package:palwakf_workspace_manager/src/features/workspace_catalog/domain/workspace_catalog_models.dart';

void main() {
  test('research uses direct API and carries research identity', () async {
    final api = _FakeDirectApi();
    final controller = DirectExecutionController(api);
    const item = WorkspaceCatalogItem(
      id: 'research:PAL-EYES-CENSUS-009',
      title: 'كنيسة القيامة',
      itemClass: WorkspaceItemClass.research,
      status: 'مسجل',
      category: 'بحث',
      sourceLabel: 'Drive',
      locality: 'القدس',
    );

    await controller.execute(item: item, prompt: 'لخّص نقطة الاستئناف.');

    expect(api.calls, 1);
    expect(api.lastDraft!.itemId, item.id);
    expect(api.lastDraft!.itemClass, DirectWorkspaceItemClass.research);
    expect(controller.state.phase, DirectExecutionPhase.completed);
    expect(controller.state.receipt!.palwakfGovernanceUsed, isFalse);
    expect(controller.state.receipt!.engineeringTaskUsed, isFalse);
    expect(controller.state.receipt!.operatorAuthorizationUsed, isFalse);
    expect(controller.state.receipt!.toolPlanUsed, isFalse);
  });

  test('private project keeps immutable project UID in direct request',
      () async {
    final api = _FakeDirectApi();
    final controller = DirectExecutionController(api);
    const uid = '56aa02ac-7f7f-40f5-ba59-02cfed407d6a';
    const item = WorkspaceCatalogItem(
      id: 'private:$uid',
      projectUid: uid,
      technicalId: 'SLEEPQUALITY_APP',
      title: 'جودة النوم',
      itemClass: WorkspaceItemClass.privateProject,
      status: 'مسجل في هذه الجلسة',
      category: 'مشروع خاص',
      sourceLabel: 'session',
    );

    await controller.execute(item: item, prompt: 'اقترح المهمة التالية.');

    expect(api.calls, 1);
    expect(api.lastDraft!.projectUid, uid);
    expect(api.lastDraft!.technicalId, 'SLEEPQUALITY_APP');
    expect(api.lastDraft!.itemClass, DirectWorkspaceItemClass.privateProject);
  });

  test('PalWakf governed item never reaches direct API', () async {
    final api = _FakeDirectApi();
    final controller = DirectExecutionController(api);
    const item = WorkspaceCatalogItem(
      id: 'project:PALWAKF_WORKSPACE_MANAGER',
      technicalId: 'PALWAKF_WORKSPACE_MANAGER',
      title: 'PalWakf Workspace Manager',
      itemClass: WorkspaceItemClass.palwakfGovernedProject,
      status: 'مسجل',
      category: 'مشروع PalWakf',
      sourceLabel: 'Drive',
    );

    await controller.execute(item: item, prompt: 'نفّذ العمل.');

    expect(api.calls, 0);
    expect(controller.state.phase, DirectExecutionPhase.failed);
    expect(controller.state.error, contains('لا تستخدم المسار المباشر'));
  });

  test('home router branches direct classes before governed controller', () {
    final source = File(
      'lib/src/features/daily_workspace/presentation/'
      'daily_workspace_home_page.dart',
    ).readAsStringSync();

    expect(source, contains('directExecutionControllerProvider'));
    expect(source, contains('direct-confirm-execution'));
    expect(source, contains('المسار المباشر مستقل عن حوكمة PalWakf'));
    expect(
      source,
      isNot(contains('تنفيذ الأبحاث والمشاريع الخاصة سيُختبر في بوابة')),
    );
  });

  test('direct backend has no governed execution imports', () {
    final source = File(
      'orchestrator/src/palwakf_orchestrator/direct_execution_service.py',
    ).readAsStringSync();

    expect(source, isNot(contains('engineering_os')));
    expect(source, isNot(contains('operator_service')));
    expect(source, isNot(contains('tool-plan')));
    expect(source, contains('tools=[]'));
  });
}

class _FakeDirectApi implements DirectExecutionApi {
  int calls = 0;
  DirectExecutionDraft? lastDraft;

  @override
  Future<DirectExecutionReceipt> execute(DirectExecutionDraft draft) async {
    calls += 1;
    lastDraft = draft;
    return DirectExecutionReceipt(
      sessionId: 'session-$calls',
      itemId: draft.itemId,
      itemClass: draft.itemClass.wireValue,
      projectUid: draft.projectUid,
      technicalId: draft.technicalId,
      title: draft.title,
      route: 'DIRECT',
      status: DirectExecutionStatus.completed,
      providerId: 'fake-direct',
      model: 'test-model',
      promptSha256: 'hash',
      output: 'DIRECT_OK',
      palwakfGovernanceUsed: false,
      engineeringTaskUsed: false,
      operatorAuthorizationUsed: false,
      toolPlanUsed: false,
    );
  }

  @override
  Future<DirectExecutionReceipt> status(String sessionId) {
    throw UnimplementedError();
  }
}
