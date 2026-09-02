import '../../engineering_os/domain/engineering_os_models.dart';
import '../application/daily_workspace_controller.dart';

class UserWorkspaceInsights {
  UserWorkspaceInsights._(this.tasks);

  factory UserWorkspaceInsights.fromTasks(List<EngineeringTask> tasks) {
    return UserWorkspaceInsights._(List<EngineeringTask>.unmodifiable(tasks));
  }

  final List<EngineeringTask> tasks;

  Set<String> get projectIds => tasks.map((task) => task.projectId).toSet();

  int get projectCount => projectIds.length;

  List<EngineeringTask> get activeTasks => tasks
      .where((task) => _activeStatuses.contains(task.status))
      .toList(growable: false);

  int get activeWorkCount => activeTasks.length;

  List<EngineeringTask> get attentionTasks => tasks
      .where((task) => _attentionStatuses.contains(task.status))
      .toList(growable: false);

  int get attentionCount => attentionTasks.length;

  List<EngineeringTask> get completedTasks => tasks
      .where(
        (task) =>
            task.status == 'INTEGRATED' ||
            task.integrationStatus == 'INTEGRATED',
      )
      .toList(growable: false);

  int get completedCount => completedTasks.length;

  List<EngineeringTask> get continuationTasks {
    final values = <EngineeringTask>[
      ...attentionTasks,
      ...activeTasks.where((task) => !attentionTasks.contains(task)),
      ...tasks.where(
        (task) =>
            !attentionTasks.contains(task) &&
            !activeTasks.contains(task) &&
            !completedTasks.contains(task),
      ),
    ];
    return values.take(6).toList(growable: false);
  }

  List<UserProjectSummary> get projectSummaries {
    final result = <UserProjectSummary>[];
    for (final projectId in projectIds) {
      final projectTasks =
          tasks.where((task) => task.projectId == projectId).toList();
      final activeCount = projectTasks
          .where((task) => _activeStatuses.contains(task.status))
          .length;
      final attentionCount = projectTasks
          .where((task) => _attentionStatuses.contains(task.status))
          .length;
      final completedCount = projectTasks
          .where(
            (task) =>
                task.status == 'INTEGRATED' ||
                task.integrationStatus == 'INTEGRATED',
          )
          .length;
      final stageLabel = attentionCount > 0
          ? 'يحتاج مراجعة'
          : activeCount > 0
              ? 'قيد العمل'
              : projectTasks.isNotEmpty && completedCount == projectTasks.length
                  ? 'مكتمل'
                  : 'مسجل';
      result.add(
        UserProjectSummary(
          projectId: projectId,
          label: DailyWorkspaceController.friendlyProjectLabel(projectId),
          workCount: projectTasks.length,
          activeCount: activeCount,
          attentionCount: attentionCount,
          completedCount: completedCount,
          stageLabel: stageLabel,
        ),
      );
    }
    result.sort((a, b) {
      final attention = b.attentionCount.compareTo(a.attentionCount);
      if (attention != 0) return attention;
      return b.activeCount.compareTo(a.activeCount);
    });
    return result;
  }

  UserWorkspaceSuggestion? get primarySuggestion {
    if (attentionTasks.isNotEmpty) {
      final task = attentionTasks.first;
      return UserWorkspaceSuggestion(
        title: 'يوجد عمل يحتاج انتباهك',
        message:
            'راجع «${DailyWorkspaceController.friendlyTaskTitle(task)}» قبل متابعة بقية العمل.',
        task: task,
        actionLabel: 'راجع العمل',
      );
    }

    if (activeTasks.isNotEmpty) {
      final task = activeTasks.first;
      return UserWorkspaceSuggestion(
        title: 'يمكنك المتابعة من حيث توقفت',
        message:
            '«${DailyWorkspaceController.friendlyTaskTitle(task)}» جاهز للاستئناف.',
        task: task,
        actionLabel: 'استئناف',
      );
    }

    if (tasks.isNotEmpty) {
      final task = tasks.first;
      return UserWorkspaceSuggestion(
        title: 'ابدأ من عمل مسجل',
        message:
            'يمكنك بدء «${DailyWorkspaceController.friendlyTaskTitle(task)}» من الصفحة الرئيسية.',
        task: task,
        actionLabel: 'فتح العمل',
      );
    }

    return null;
  }

  static String stageLabel(EngineeringTask task) {
    if (task.status == 'INTEGRATED' || task.integrationStatus == 'INTEGRATED') {
      return 'مكتمل';
    }
    return switch (task.status) {
      'WIP_REMOTE_CHECKPOINTED' => 'محفوظ للمتابعة',
      'IN_REVIEW' || 'NEEDS_REVIEW' => 'جاهز للمراجعة',
      'BLOCKED' => 'متوقف',
      'AWAITING_APPROVAL' => 'بانتظار موافقتك',
      'RUNNING' || 'IN_PROGRESS' => 'قيد العمل',
      'READY' => 'جاهز',
      'CANCELLED' => 'ملغى',
      _ => DailyWorkspaceController.friendlyTaskStatus(task.status),
    };
  }

  static String activityLabel(EngineeringTask task) {
    if (task.status == 'INTEGRATED' || task.integrationStatus == 'INTEGRATED') {
      return 'اكتمل العمل';
    }
    return switch (task.status) {
      'WIP_REMOTE_CHECKPOINTED' => 'تم حفظ آخر تقدم ويمكن المتابعة',
      'IN_REVIEW' || 'NEEDS_REVIEW' => 'العمل جاهز للمراجعة',
      'BLOCKED' => 'العمل متوقف ويحتاج إجراء',
      'AWAITING_APPROVAL' => 'ينتظر موافقتك',
      'RUNNING' || 'IN_PROGRESS' => 'العمل قيد التنفيذ',
      'READY' => 'العمل جاهز للبدء',
      _ => DailyWorkspaceController.friendlyTaskStatus(task.status),
    };
  }

  static bool needsAttention(EngineeringTask task) =>
      _attentionStatuses.contains(task.status);

  static const Set<String> _activeStatuses = <String>{
    'READY',
    'WIP_REMOTE_CHECKPOINTED',
    'RUNNING',
    'IN_PROGRESS',
    'IN_REVIEW',
    'NEEDS_REVIEW',
    'AWAITING_APPROVAL',
    'BLOCKED',
  };

  static const Set<String> _attentionStatuses = <String>{
    'BLOCKED',
    'AWAITING_APPROVAL',
    'IN_REVIEW',
    'NEEDS_REVIEW',
  };
}

class UserProjectSummary {
  const UserProjectSummary({
    required this.projectId,
    required this.label,
    required this.workCount,
    required this.activeCount,
    required this.attentionCount,
    required this.completedCount,
    required this.stageLabel,
  });

  final String projectId;
  final String label;
  final int workCount;
  final int activeCount;
  final int attentionCount;
  final int completedCount;
  final String stageLabel;
}

class UserWorkspaceSuggestion {
  const UserWorkspaceSuggestion({
    required this.title,
    required this.message,
    required this.task,
    required this.actionLabel,
  });

  final String title;
  final String message;
  final EngineeringTask task;
  final String actionLabel;
}
