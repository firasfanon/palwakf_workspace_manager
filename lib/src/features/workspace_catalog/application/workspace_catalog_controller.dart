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

class WorkspaceCatalogController extends StateNotifier<WorkspaceCatalogState> {
  WorkspaceCatalogController()
      : super(
          const WorkspaceCatalogState(
            items: AuthoritativeWorkspaceCatalogSnapshot.items,
          ),
        );

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

  bool registerPrivateProject({
    required String title,
    required String technicalId,
    String? localName,
  }) {
    final normalizedTitle = title.trim();
    final normalizedTechnicalId = technicalId.trim().toUpperCase();
    if (normalizedTitle.isEmpty || normalizedTechnicalId.isEmpty) return false;
    final itemId = 'private:$normalizedTechnicalId';
    if (state.items.any((item) => item.id == itemId)) return false;

    final local = localName?.trim();
    final item = WorkspaceCatalogItem(
      id: itemId,
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
    return true;
  }
}
