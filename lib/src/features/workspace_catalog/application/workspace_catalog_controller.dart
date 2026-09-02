import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/authoritative_workspace_catalog_snapshot.dart';
import '../domain/workspace_catalog_models.dart';

final workspaceCatalogProvider =
    StateNotifierProvider<WorkspaceCatalogController, WorkspaceCatalogState>(
  (ref) => WorkspaceCatalogController(),
);

class WorkspaceCatalogState {
  const WorkspaceCatalogState({
    required this.items,
    this.selectedItemId = 'project:PALWAKF_WORKSPACE_MANAGER',
    this.recentIds = const <String>[],
  });

  final List<WorkspaceCatalogItem> items;
  final String? selectedItemId;
  final List<String> recentIds;

  WorkspaceCatalogItem? get selectedItem {
    for (final item in items) {
      if (item.id == selectedItemId) return item;
    }
    return null;
  }

  List<WorkspaceCatalogItem> get recentItems {
    final byId = <String, WorkspaceCatalogItem>{
      for (final item in items) item.id: item,
    };
    return recentIds
        .map((id) => byId[id])
        .whereType<WorkspaceCatalogItem>()
        .toList();
  }

  int countOf(WorkspaceItemClass itemClass) =>
      items.where((item) => item.itemClass == itemClass).length;

  int get governedCount => countOf(WorkspaceItemClass.palwakfGovernedProject);
  int get researchCount => countOf(WorkspaceItemClass.research);
  int get privateCount => countOf(WorkspaceItemClass.privateProject);
  int get totalCount => items.length;

  WorkspaceCatalogState copyWith({
    List<WorkspaceCatalogItem>? items,
    String? selectedItemId,
    List<String>? recentIds,
  }) {
    return WorkspaceCatalogState(
      items: items ?? this.items,
      selectedItemId: selectedItemId ?? this.selectedItemId,
      recentIds: recentIds ?? this.recentIds,
    );
  }
}

enum PrivateProjectRegistrationError {
  none,
  titleRequired,
  technicalIdRequired,
  invalidTechnicalId,
  duplicateTechnicalId,
}

class PrivateProjectRegistrationResult {
  const PrivateProjectRegistrationResult._({
    required this.error,
    this.item,
  });

  const PrivateProjectRegistrationResult.created(WorkspaceCatalogItem item)
      : this._(error: PrivateProjectRegistrationError.none, item: item);

  const PrivateProjectRegistrationResult.failed(
    PrivateProjectRegistrationError error,
  ) : this._(error: error);

  final PrivateProjectRegistrationError error;
  final WorkspaceCatalogItem? item;

  bool get created =>
      item != null && error == PrivateProjectRegistrationError.none;

  String get message => switch (error) {
        PrivateProjectRegistrationError.none =>
          'تم تسجيل المشروع الخاص في هذه الجلسة.',
        PrivateProjectRegistrationError.titleRequired =>
          'أدخل اسم المشروع قبل التسجيل.',
        PrivateProjectRegistrationError.technicalIdRequired =>
          'أدخل المعرف التقني قبل التسجيل.',
        PrivateProjectRegistrationError.invalidTechnicalId =>
          'المعرف التقني يجب أن يبدأ بحرف لاتيني ويحتوي أحرفًا كبيرة أو أرقامًا أو شرطة سفلية فقط.',
        PrivateProjectRegistrationError.duplicateTechnicalId =>
          'المعرف التقني مستخدم بالفعل داخل مساحة العمل.',
      };
}

class WorkspaceCatalogController extends StateNotifier<WorkspaceCatalogState> {
  WorkspaceCatalogController({String Function()? projectUidFactory})
      : _projectUidFactory = projectUidFactory ?? _generateUuidV4,
        super(
          const WorkspaceCatalogState(
            items: AuthoritativeWorkspaceCatalogSnapshot.items,
          ),
        );

  final String Function() _projectUidFactory;

  void select(String itemId) {
    if (!state.items.any((item) => item.id == itemId)) return;
    final recent = <String>[
      itemId,
      ...state.recentIds.where((id) => id != itemId),
    ].take(8).toList(growable: false);
    state = state.copyWith(selectedItemId: itemId, recentIds: recent);
  }

  WorkspaceCatalogItem? byId(String itemId) {
    for (final item in state.items) {
      if (item.id == itemId) return item;
    }
    return null;
  }

  bool technicalIdExists(String technicalId) {
    final normalized = technicalId.trim().toUpperCase();
    return state.items.any(
      (item) => item.technicalId?.trim().toUpperCase() == normalized,
    );
  }

  PrivateProjectRegistrationResult registerPrivateProject({
    required String title,
    required String technicalId,
    String? localName,
  }) {
    final normalizedTitle = title.trim();
    final normalizedTechnicalId = technicalId.trim().toUpperCase();
    if (normalizedTitle.isEmpty) {
      return const PrivateProjectRegistrationResult.failed(
        PrivateProjectRegistrationError.titleRequired,
      );
    }
    if (normalizedTechnicalId.isEmpty) {
      return const PrivateProjectRegistrationResult.failed(
        PrivateProjectRegistrationError.technicalIdRequired,
      );
    }
    if (!RegExp(r'^[A-Z][A-Z0-9_]{2,63}$').hasMatch(normalizedTechnicalId)) {
      return const PrivateProjectRegistrationResult.failed(
        PrivateProjectRegistrationError.invalidTechnicalId,
      );
    }
    if (technicalIdExists(normalizedTechnicalId)) {
      return const PrivateProjectRegistrationResult.failed(
        PrivateProjectRegistrationError.duplicateTechnicalId,
      );
    }

    final projectUid = _nextUniqueProjectUid();
    final itemId = 'private:$projectUid';
    final local = localName?.trim();
    final item = WorkspaceCatalogItem(
      id: itemId,
      projectUid: projectUid,
      title: normalizedTitle,
      technicalId: normalizedTechnicalId,
      localName: local == null || local.isEmpty ? null : local,
      itemClass: WorkspaceItemClass.privateProject,
      category: 'مشروع خاص',
      status: 'مسجل في هذه الجلسة',
      sourceLabel: AuthoritativeWorkspaceCatalogSnapshot.privateSource,
    );
    state = state.copyWith(
      items: <WorkspaceCatalogItem>[...state.items, item],
    );
    select(item.id);
    return PrivateProjectRegistrationResult.created(item);
  }

  String _nextUniqueProjectUid() {
    for (var attempt = 0; attempt < 8; attempt += 1) {
      final uid = _projectUidFactory().toLowerCase();
      if (_isUuidV4(uid) &&
          !state.items.any(
            (item) => item.projectUid == uid || item.id == 'private:$uid',
          )) {
        return uid;
      }
    }
    throw StateError('PROJECT_UID_GENERATION_FAILED');
  }

  static bool _isUuidV4(String value) => RegExp(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
      ).hasMatch(value);

  static String _generateUuidV4() {
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final hex =
        bytes.map((value) => value.toRadixString(16).padLeft(2, '0')).join();
    return '${hex.substring(0, 8)}-'
        '${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-'
        '${hex.substring(16, 20)}-'
        '${hex.substring(20, 32)}';
  }
}
