class PortfolioCommandCenterSnapshot {
  const PortfolioCommandCenterSnapshot({
    required this.generatedAt,
    required this.snapshotId,
    required this.truthState,
    required this.truthConfidence,
    required this.truthExplanation,
    required this.sourceHealth,
    required this.kpis,
    required this.projects,
    required this.recommendations,
    required this.dependencies,
    required this.criticalPath,
    required this.forecasts,
    required this.capabilities,
    required this.skills,
    required this.tools,
    required this.agents,
    required this.providers,
    required this.risks,
    required this.decisions,
    required this.recentChanges,
    required this.evidenceRefs,
    required this.authorityNotes,
  });

  final DateTime generatedAt;
  final String snapshotId;
  final String truthState;
  final int truthConfidence;
  final List<String> truthExplanation;
  final List<SourceHealthItem> sourceHealth;
  final List<PortfolioKpi> kpis;
  final List<ProjectIntelligence> projects;
  final List<PortfolioRecommendation> recommendations;
  final List<DependencyView> dependencies;
  final CriticalPathView criticalPath;
  final List<ProjectForecast> forecasts;
  final List<RegistryEntity> capabilities;
  final List<RegistryEntity> skills;
  final List<RegistryEntity> tools;
  final List<RegistryEntity> agents;
  final List<RegistryEntity> providers;
  final List<PortfolioRisk> risks;
  final List<PortfolioDecision> decisions;
  final List<ChangeItem> recentChanges;
  final List<String> evidenceRefs;
  final List<String> authorityNotes;

  factory PortfolioCommandCenterSnapshot.fromJson(Map<String, dynamic> json) {
    return PortfolioCommandCenterSnapshot(
      generatedAt: DateTime.parse(json['generated_at'].toString()),
      snapshotId: json['snapshot_id'].toString(),
      truthState: json['truth_state'].toString(),
      truthConfidence: (json['truth_confidence'] as num).toInt(),
      truthExplanation: _strings(json['truth_explanation_ar']),
      sourceHealth:
          _maps(json['source_health']).map(SourceHealthItem.fromJson).toList(),
      kpis: _maps(json['kpis']).map(PortfolioKpi.fromJson).toList(),
      projects:
          _maps(json['projects']).map(ProjectIntelligence.fromJson).toList(),
      recommendations: _maps(json['recommendations'])
          .map(PortfolioRecommendation.fromJson)
          .toList(),
      dependencies:
          _maps(json['dependencies']).map(DependencyView.fromJson).toList(),
      criticalPath: CriticalPathView.fromJson(
        json['critical_path'] as Map<String, dynamic>,
      ),
      forecasts:
          _maps(json['forecasts']).map(ProjectForecast.fromJson).toList(),
      capabilities:
          _maps(json['capabilities']).map(RegistryEntity.fromJson).toList(),
      skills: _maps(json['skills']).map(RegistryEntity.fromJson).toList(),
      tools: _maps(json['tools']).map(RegistryEntity.fromJson).toList(),
      agents: _maps(json['agents']).map(RegistryEntity.fromJson).toList(),
      providers: _maps(json['providers']).map(RegistryEntity.fromJson).toList(),
      risks: _maps(json['risks']).map(PortfolioRisk.fromJson).toList(),
      decisions:
          _maps(json['decisions']).map(PortfolioDecision.fromJson).toList(),
      recentChanges:
          _maps(json['recent_changes']).map(ChangeItem.fromJson).toList(),
      evidenceRefs: _strings(json['evidence_refs']),
      authorityNotes: _strings(json['authority_notes']),
    );
  }
}

List<Map<String, dynamic>> _maps(dynamic value) =>
    (value as List<dynamic>? ?? const <dynamic>[]).cast<Map<String, dynamic>>();

List<String> _strings(dynamic value) =>
    (value as List<dynamic>? ?? const <dynamic>[])
        .map((item) => item.toString())
        .toList(growable: false);

class SourceHealthItem {
  const SourceHealthItem({
    required this.sourceId,
    required this.labelAr,
    required this.state,
    required this.freshness,
    required this.detailAr,
    required this.authority,
    this.observedAt,
  });

  final String sourceId;
  final String labelAr;
  final String state;
  final String freshness;
  final String detailAr;
  final String authority;
  final DateTime? observedAt;

  factory SourceHealthItem.fromJson(Map<String, dynamic> json) =>
      SourceHealthItem(
        sourceId: json['source_id'].toString(),
        labelAr: json['label_ar'].toString(),
        state: json['state'].toString(),
        freshness: json['freshness'].toString(),
        detailAr: json['detail_ar'].toString(),
        authority: json['authority'].toString(),
        observedAt: DateTime.tryParse(json['observed_at']?.toString() ?? ''),
      );
}

class PortfolioKpi {
  const PortfolioKpi({
    required this.kpiId,
    required this.labelAr,
    required this.value,
    required this.status,
    required this.confidence,
    required this.explanationAr,
  });

  final String kpiId;
  final String labelAr;
  final String value;
  final String status;
  final double confidence;
  final String explanationAr;

  factory PortfolioKpi.fromJson(Map<String, dynamic> json) => PortfolioKpi(
        kpiId: json['kpi_id'].toString(),
        labelAr: json['label_ar'].toString(),
        value: json['value'].toString(),
        status: json['status'].toString(),
        confidence: (json['confidence'] as num).toDouble(),
        explanationAr: json['explanation_ar'].toString(),
      );
}

class ScoreFactor {
  const ScoreFactor({
    required this.factor,
    required this.value,
    required this.weight,
    required this.explanationAr,
  });

  final String factor;
  final int value;
  final int weight;
  final String explanationAr;

  factory ScoreFactor.fromJson(Map<String, dynamic> json) => ScoreFactor(
        factor: json['factor'].toString(),
        value: (json['value'] as num).toInt(),
        weight: (json['weight'] as num).toInt(),
        explanationAr: json['explanation_ar'].toString(),
      );
}

class ProjectForecast {
  const ProjectForecast({
    required this.projectId,
    required this.status,
    required this.confidence,
    required this.conditionsAr,
    required this.basis,
    this.p50,
    this.p80,
  });

  final String projectId;
  final String status;
  final String? p50;
  final String? p80;
  final double confidence;
  final List<String> conditionsAr;
  final String basis;

  factory ProjectForecast.fromJson(Map<String, dynamic> json) =>
      ProjectForecast(
        projectId: json['project_id'].toString(),
        status: json['status'].toString(),
        p50: json['p50']?.toString(),
        p80: json['p80']?.toString(),
        confidence: (json['confidence'] as num).toDouble(),
        conditionsAr: _strings(json['conditions_ar']),
        basis: json['basis'].toString(),
      );
}

class ProjectIntelligence {
  const ProjectIntelligence({
    required this.projectId,
    required this.displayName,
    required this.repositoryFullName,
    required this.truthState,
    required this.currentStatus,
    required this.readiness,
    required this.maturityState,
    required this.scopeProgressBasis,
    required this.priorityScore,
    required this.priorityFactors,
    required this.nextActionAr,
    required this.blockers,
    required this.ciStatus,
    required this.deploymentStatus,
    required this.driftStatus,
    required this.evidenceCount,
    required this.taskCount,
    required this.toolGapCount,
    required this.forecast,
    required this.evidenceRefs,
    this.scopeProgressPercent,
    this.observedBranch,
    this.observedHead,
    this.lastVerifiedAt,
  });

  final String projectId;
  final String displayName;
  final String repositoryFullName;
  final String truthState;
  final String currentStatus;
  final String readiness;
  final String maturityState;
  final double? scopeProgressPercent;
  final String scopeProgressBasis;
  final int priorityScore;
  final List<ScoreFactor> priorityFactors;
  final String nextActionAr;
  final List<String> blockers;
  final String? observedBranch;
  final String? observedHead;
  final String ciStatus;
  final String deploymentStatus;
  final String driftStatus;
  final int evidenceCount;
  final int taskCount;
  final int toolGapCount;
  final DateTime? lastVerifiedAt;
  final ProjectForecast forecast;
  final List<String> evidenceRefs;

  factory ProjectIntelligence.fromJson(Map<String, dynamic> json) =>
      ProjectIntelligence(
        projectId: json['project_id'].toString(),
        displayName: json['display_name'].toString(),
        repositoryFullName: json['repository_full_name'].toString(),
        truthState: json['truth_state'].toString(),
        currentStatus: json['current_status'].toString(),
        readiness: json['readiness'].toString(),
        maturityState: json['maturity_state'].toString(),
        scopeProgressPercent:
            (json['scope_progress_percent'] as num?)?.toDouble(),
        scopeProgressBasis: json['scope_progress_basis'].toString(),
        priorityScore: (json['priority_score'] as num).toInt(),
        priorityFactors:
            _maps(json['priority_factors']).map(ScoreFactor.fromJson).toList(),
        nextActionAr: json['next_action_ar'].toString(),
        blockers: _strings(json['blockers']),
        observedBranch: json['observed_branch']?.toString(),
        observedHead: json['observed_head']?.toString(),
        ciStatus: json['ci_status'].toString(),
        deploymentStatus: json['deployment_status'].toString(),
        driftStatus: json['drift_status'].toString(),
        evidenceCount: (json['evidence_count'] as num).toInt(),
        taskCount: (json['task_count'] as num).toInt(),
        toolGapCount: (json['tool_gap_count'] as num).toInt(),
        lastVerifiedAt:
            DateTime.tryParse(json['last_verified_at']?.toString() ?? ''),
        forecast:
            ProjectForecast.fromJson(json['forecast'] as Map<String, dynamic>),
        evidenceRefs: _strings(json['evidence_refs']),
      );
}

class PortfolioRecommendation {
  const PortfolioRecommendation({
    required this.recommendationId,
    required this.type,
    required this.subjectId,
    required this.reasonAr,
    required this.evidenceRefs,
    required this.affectedProjects,
    required this.unlockCount,
    required this.riskIfDeferredAr,
    required this.estimatedEffort,
    required this.confidence,
    required this.status,
    required this.authority,
  });

  final String recommendationId;
  final String type;
  final String subjectId;
  final String reasonAr;
  final List<String> evidenceRefs;
  final List<String> affectedProjects;
  final int unlockCount;
  final String riskIfDeferredAr;
  final String estimatedEffort;
  final double confidence;
  final String status;
  final String authority;

  factory PortfolioRecommendation.fromJson(Map<String, dynamic> json) =>
      PortfolioRecommendation(
        recommendationId: json['recommendation_id'].toString(),
        type: json['type'].toString(),
        subjectId: json['subject_id'].toString(),
        reasonAr: json['reason_ar'].toString(),
        evidenceRefs: _strings(json['evidence_refs']),
        affectedProjects: _strings(json['affected_projects']),
        unlockCount: (json['unlock_count'] as num).toInt(),
        riskIfDeferredAr: json['risk_if_deferred_ar'].toString(),
        estimatedEffort: json['estimated_effort'].toString(),
        confidence: (json['confidence'] as num).toDouble(),
        status: json['status'].toString(),
        authority: json['authority'].toString(),
      );
}

class DependencyView {
  const DependencyView({
    required this.edgeId,
    required this.producerProjectId,
    required this.consumerProjectId,
    required this.kind,
    required this.contractId,
    required this.version,
    required this.status,
    required this.evidence,
  });

  final String edgeId;
  final String producerProjectId;
  final String consumerProjectId;
  final String kind;
  final String contractId;
  final String version;
  final String status;
  final List<String> evidence;

  factory DependencyView.fromJson(Map<String, dynamic> json) => DependencyView(
        edgeId: json['edge_id'].toString(),
        producerProjectId: json['producer_project_id'].toString(),
        consumerProjectId: json['consumer_project_id'].toString(),
        kind: json['kind'].toString(),
        contractId: json['contract_id'].toString(),
        version: json['version'].toString(),
        status: json['status'].toString(),
        evidence: _strings(json['evidence']),
      );
}

class CriticalPathView {
  const CriticalPathView({
    required this.status,
    required this.projectIds,
    required this.reasonAr,
    required this.evidenceRefs,
    this.mostBlockingProjectId,
  });

  final String status;
  final List<String> projectIds;
  final String? mostBlockingProjectId;
  final String reasonAr;
  final List<String> evidenceRefs;

  factory CriticalPathView.fromJson(Map<String, dynamic> json) =>
      CriticalPathView(
        status: json['status'].toString(),
        projectIds: _strings(json['project_ids']),
        mostBlockingProjectId: json['most_blocking_project_id']?.toString(),
        reasonAr: json['reason_ar'].toString(),
        evidenceRefs: _strings(json['evidence_refs']),
      );
}

class RegistryEntity {
  const RegistryEntity({
    required this.entityId,
    required this.nameAr,
    required this.category,
    required this.lifecycle,
    required this.status,
    required this.descriptionAr,
    required this.owner,
    required this.evidenceRefs,
    this.deferredReasonAr,
    this.reopenTriggerAr,
  });

  final String entityId;
  final String nameAr;
  final String category;
  final String lifecycle;
  final String status;
  final String descriptionAr;
  final String owner;
  final List<String> evidenceRefs;
  final String? deferredReasonAr;
  final String? reopenTriggerAr;

  factory RegistryEntity.fromJson(Map<String, dynamic> json) => RegistryEntity(
        entityId: json['entity_id'].toString(),
        nameAr: json['name_ar'].toString(),
        category: json['category'].toString(),
        lifecycle: json['lifecycle'].toString(),
        status: json['status'].toString(),
        descriptionAr: json['description_ar'].toString(),
        owner: json['owner'].toString(),
        evidenceRefs: _strings(json['evidence_refs']),
        deferredReasonAr: json['deferred_reason_ar']?.toString(),
        reopenTriggerAr: json['reopen_trigger_ar']?.toString(),
      );
}

class PortfolioRisk {
  const PortfolioRisk({
    required this.riskId,
    required this.severity,
    required this.subjectId,
    required this.summaryAr,
    required this.requiredActionAr,
    this.evidenceRef,
  });

  final String riskId;
  final String severity;
  final String subjectId;
  final String summaryAr;
  final String requiredActionAr;
  final String? evidenceRef;

  factory PortfolioRisk.fromJson(Map<String, dynamic> json) => PortfolioRisk(
        riskId: json['risk_id'].toString(),
        severity: json['severity'].toString(),
        subjectId: json['subject_id'].toString(),
        summaryAr: json['summary_ar'].toString(),
        requiredActionAr: json['required_action_ar'].toString(),
        evidenceRef: json['evidence_ref']?.toString(),
      );
}

class PortfolioDecision {
  const PortfolioDecision({
    required this.decisionId,
    required this.kind,
    required this.summaryAr,
    required this.requiresHumanAction,
    required this.status,
    this.projectId,
    this.authorityReference,
  });

  final String decisionId;
  final String kind;
  final String? projectId;
  final String summaryAr;
  final bool requiresHumanAction;
  final String status;
  final String? authorityReference;

  factory PortfolioDecision.fromJson(Map<String, dynamic> json) =>
      PortfolioDecision(
        decisionId: json['decision_id'].toString(),
        kind: json['kind'].toString(),
        projectId: json['project_id']?.toString(),
        summaryAr: json['summary_ar'].toString(),
        requiresHumanAction: json['requires_human_action'] == true,
        status: json['status'].toString(),
        authorityReference: json['authority_reference']?.toString(),
      );
}

class ChangeItem {
  const ChangeItem({
    required this.changeId,
    required this.subjectId,
    required this.title,
    required this.detail,
    required this.occurredAt,
    required this.status,
    required this.provenance,
  });

  final String changeId;
  final String subjectId;
  final String title;
  final String detail;
  final DateTime occurredAt;
  final String status;
  final String provenance;

  factory ChangeItem.fromJson(Map<String, dynamic> json) => ChangeItem(
        changeId: json['change_id'].toString(),
        subjectId: json['subject_id'].toString(),
        title: json['title'].toString(),
        detail: json['detail'].toString(),
        occurredAt: DateTime.parse(json['occurred_at'].toString()),
        status: json['status'].toString(),
        provenance: json['provenance'].toString(),
      );
}
