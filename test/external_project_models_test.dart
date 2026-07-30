import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/projects/domain/external_project_models.dart';

void main() {
  test(
      'project reality preserves head, fingerprint, tool decisions, and candidates',
      () {
    final reality = ProjectReality.fromJson(
      <String, dynamic>{
        'project_id': 'FIRASFANON_PAL_EYES',
        'repository_full_name': 'firasfanon/Pal_Eyes',
        'default_branch': 'main',
        'observed_branch': 'main',
        'observed_head': 'c67ff5e28205aac57ff28e8b8120c3bac5de4488',
        'drift_status': 'BASELINE_CREATED',
        'visibility': 'public',
        'stack': <String>['Dart', 'Flutter'],
        'package_managers': <String>['pub'],
        'toolchain_versions': <String, dynamic>{
          'dart': '>=3.10.0 <4.0.0',
        },
        'commands': <Map<String, dynamic>>[
          <String, dynamic>{
            'command': 'flutter test',
            'purpose': 'test',
            'evidence': 'docs/11_LOCAL_RUN_AND_VALIDATION.md',
          },
        ],
        'ci': <Map<String, dynamic>>[],
        'ci_status': 'NOT_CONFIGURED',
        'deployments': <Map<String, dynamic>>[
          <String, dynamic>{
            'provider': 'vercel',
            'status': 'NOT_DISCOVERED',
            'evidence': 'read-only inventory',
          },
        ],
        'deployment_status': 'NOT_DISCOVERED',
        'tree': <String, dynamic>{
          'total_files': 291,
          'scanned_files': 291,
          'secret_risk_file_names': <String>['.env.example'],
          'ignored_secret_policy_present': true,
        },
        'indicators': <String, dynamic>{
          'flutter': true,
          'supabase': true,
        },
        'capability_profile': <String, dynamic>{
          'profile_version': 'PROJECT_CAPABILITY_PROFILE_V1',
          'selected_tools': <Map<String, dynamic>>[],
          'conditional_tools': <Map<String, dynamic>>[],
          'excluded_tools': <Map<String, dynamic>>[],
          'blocked_tools': <Map<String, dynamic>>[
            <String, dynamic>{
              'adapter_id': 'supabase',
              'disposition': 'blocked',
              'reason': 'Task authority excludes connection.',
              'evidence': <String>['task:SUPABASE_EXCLUDED'],
            },
          ],
        },
        'candidate_work_items': <Map<String, dynamic>>[
          <String, dynamic>{
            'rank': 1,
            'candidate_id': 'PAL_EYES_GIS_CANDIDATE_VALIDATION',
            'title': 'Validate GIS candidate input',
            'rationale': 'Current input uses placeholders.',
            'acceptance_test': 'Reject placeholder coordinates.',
            'evidence': <String>['gis_review_screen.dart'],
            'blocked': false,
          },
        ],
        'blockers': <String>[],
        'baseline_fingerprint':
            'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
      },
    );

    expect(reality.observedHead, startsWith('c67ff5'));
    expect(reality.capabilityProfile.blocked.single.adapterId, 'supabase');
    expect(
      reality.candidates.single.candidateId,
      'PAL_EYES_GIS_CANDIDATE_VALIDATION',
    );
    expect(reality.ignoredSecretPolicyPresent, isTrue);
  });
}
