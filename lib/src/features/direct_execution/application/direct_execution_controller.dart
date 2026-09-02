import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../workspace_catalog/domain/workspace_catalog_models.dart';
import '../data/direct_execution_api_client.dart';
import '../domain/direct_execution_models.dart';

final directExecutionControllerProvider =
    StateNotifierProvider<DirectExecutionController, DirectExecutionState>(
  (ref) => DirectExecutionController(ref.watch(directExecutionApiProvider)),
);

enum DirectExecutionPhase {
  idle,
  running,
  completed,
  failed,
}

class DirectExecutionState {
  const DirectExecutionState({
    this.phase = DirectExecutionPhase.idle,
    this.itemId,
    this.receipt,
    this.message,
    this.error,
  });

  final DirectExecutionPhase phase;
  final String? itemId;
  final DirectExecutionReceipt? receipt;
  final String? message;
  final String? error;

  bool get running => phase == DirectExecutionPhase.running;

  DirectExecutionState copyWith({
    DirectExecutionPhase? phase,
    String? itemId,
    DirectExecutionReceipt? receipt,
    String? message,
    String? error,
    bool clearReceipt = false,
    bool clearError = false,
  }) {
    return DirectExecutionState(
      phase: phase ?? this.phase,
      itemId: itemId ?? this.itemId,
      receipt: clearReceipt ? null : receipt ?? this.receipt,
      message: message ?? this.message,
      error: clearError ? null : error ?? this.error,
    );
  }
}

class DirectExecutionController extends StateNotifier<DirectExecutionState> {
  DirectExecutionController(this._api) : super(const DirectExecutionState());

  final DirectExecutionApi _api;

  Future<void> execute({
    required WorkspaceCatalogItem item,
    required String prompt,
  }) async {
    final normalizedPrompt = prompt.trim();
    if (normalizedPrompt.isEmpty) {
      state = const DirectExecutionState(
        phase: DirectExecutionPhase.failed,
        error: 'اكتب ما تريد إنجازه أولًا.',
      );
      return;
    }
    if (item.governed) {
      state = const DirectExecutionState(
        phase: DirectExecutionPhase.failed,
        error:
            'مشاريع PalWakf لا تستخدم المسار المباشر؛ يجب أن تمر عبر مسارها المحكوم.',
      );
      return;
    }

    final itemClass = switch (item.itemClass) {
      WorkspaceItemClass.research => DirectWorkspaceItemClass.research,
      WorkspaceItemClass.privateProject =>
        DirectWorkspaceItemClass.privateProject,
      WorkspaceItemClass.palwakfGovernedProject =>
        throw StateError('DIRECT_EXECUTION_REJECTS_PALWAKF_GOVERNED_CLASS'),
    };

    if (itemClass == DirectWorkspaceItemClass.privateProject &&
        (item.projectUid == null || item.projectUid!.isEmpty)) {
      state = const DirectExecutionState(
        phase: DirectExecutionPhase.failed,
        error: 'المشروع الخاص لا يملك معرف UID صالحًا للتنفيذ المباشر.',
      );
      return;
    }

    state = DirectExecutionState(
      phase: DirectExecutionPhase.running,
      itemId: item.id,
      message: itemClass == DirectWorkspaceItemClass.research
          ? 'يجري تنفيذ العمل داخل البحث مباشرة…'
          : 'يجري تنفيذ العمل داخل المشروع الخاص مباشرة…',
    );

    try {
      final receipt = await _api.execute(
        DirectExecutionDraft(
          itemId: item.id,
          itemClass: itemClass,
          projectUid: item.projectUid,
          technicalId: item.technicalId,
          title: item.title,
          prompt: normalizedPrompt,
          contextSummary: _contextSummary(item),
        ),
      );
      if (receipt.status == DirectExecutionStatus.completed) {
        state = DirectExecutionState(
          phase: DirectExecutionPhase.completed,
          itemId: item.id,
          receipt: receipt,
          message: 'اكتمل العمل عبر المسار المباشر.',
        );
      } else {
        state = DirectExecutionState(
          phase: DirectExecutionPhase.failed,
          itemId: item.id,
          receipt: receipt,
          message: 'لم يعتمد النظام نتيجة غير مكتملة.',
          error: _friendlyFailure(receipt.errorCode),
        );
      }
    } catch (error) {
      state = DirectExecutionState(
        phase: DirectExecutionPhase.failed,
        itemId: item.id,
        message: 'لم يعتمد النظام نتيجة غير مكتملة.',
        error: _friendlyFailure(error.toString()),
      );
    }
  }

  void reset() {
    state = const DirectExecutionState();
  }

  static String _contextSummary(WorkspaceCatalogItem item) {
    return <String?>[
      item.localName == null ? null : 'الاسم المحلي: ${item.localName}',
      item.group == null ? null : 'المجموعة: ${item.group}',
      item.locality == null ? null : 'الموقع: ${item.locality}',
      item.technicalId == null ? null : 'المعرف التقني: ${item.technicalId}',
      item.projectUid == null ? null : 'Project UID: ${item.projectUid}',
      'حالة السجل: ${item.status}',
    ].whereType<String>().join('\n');
  }

  static String _friendlyFailure(String? code) {
    final value = code ?? '';
    if (value.contains('DIRECT_EXECUTION_PROVIDER_UNAVAILABLE')) {
      return 'مزود التنفيذ المباشر غير متاح في هذه الجلسة. لم يتم تمرير الطلب إلى حوكمة PalWakf.';
    }
    if (value.contains('CONNECTION_FAILED')) {
      return 'تعذر الوصول إلى خدمة التنفيذ المباشر.';
    }
    if (value.contains('TIMEOUT')) {
      return 'انتهت مهلة التنفيذ المباشر قبل اكتمال النتيجة.';
    }
    return 'تعذر إكمال العمل المباشر. لم يتم تحويله إلى مسار PalWakf.';
  }
}
