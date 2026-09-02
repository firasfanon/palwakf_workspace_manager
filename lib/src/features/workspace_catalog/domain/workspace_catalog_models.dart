enum WorkspaceItemClass {
  palwakfGovernedProject,
  research,
  privateProject;

  String get arabicLabel => switch (this) {
        palwakfGovernedProject => 'مشروع PalWakf',
        research => 'بحث',
        privateProject => 'مشروع خاص',
      };

  String get workflowLabel => switch (this) {
        palwakfGovernedProject => 'مسار PalWakf',
        research => 'مسار مباشر',
        privateProject => 'مسار مباشر',
      };
}

class WorkspaceCatalogItem {
  const WorkspaceCatalogItem({
    required this.id,
    required this.title,
    required this.itemClass,
    required this.status,
    required this.category,
    required this.sourceLabel,
    this.technicalId,
    this.localName,
    this.group,
    this.locality,
    this.lastUpdated,
  });

  final String id;
  final String title;
  final WorkspaceItemClass itemClass;
  final String status;
  final String category;
  final String sourceLabel;
  final String? technicalId;
  final String? localName;
  final String? group;
  final String? locality;
  final String? lastUpdated;

  bool get governed => itemClass == WorkspaceItemClass.palwakfGovernedProject;

  bool matches(String rawQuery) {
    final query = rawQuery.trim().toLowerCase();
    if (query.isEmpty) return true;
    return <String?>[
      id,
      title,
      technicalId,
      localName,
      category,
      status,
      group,
      locality,
    ].whereType<String>().any((value) => value.toLowerCase().contains(query));
  }
}
