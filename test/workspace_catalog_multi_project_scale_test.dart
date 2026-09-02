import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palwakf_workspace_manager/src/features/workspace_catalog/application/workspace_catalog_controller.dart';
import 'package:palwakf_workspace_manager/src/features/workspace_catalog/data/authoritative_workspace_catalog_snapshot.dart';
import 'package:palwakf_workspace_manager/src/features/workspace_catalog/domain/workspace_catalog_models.dart';
import 'package:palwakf_workspace_manager/src/features/workspace_catalog/presentation/workspace_catalog_page.dart';

void main() {
  test('real catalog snapshot has 16 governed projects and 80 research items',
      () {
    final items = AuthoritativeWorkspaceCatalogSnapshot.items;
    expect(items.length, 96);
    expect(
      items
          .where(
            (item) =>
                item.itemClass == WorkspaceItemClass.palwakfGovernedProject,
          )
          .length,
      16,
    );
    expect(
      items
          .where((item) => item.itemClass == WorkspaceItemClass.research)
          .length,
      80,
    );
    expect(
      items
          .where((item) => item.itemClass == WorkspaceItemClass.privateProject)
          .length,
      0,
    );
    expect(items.any((item) => item.title.contains('مثال')), isFalse);
  });

  test('private project identity is UUID based, immutable, and isolated', () {
    const uid = '7f2b9b6e-0a4e-4a62-9f15-7d4d91e8c521';
    final controller = WorkspaceCatalogController(projectUidFactory: () => uid);
    final result = controller.registerPrivateProject(
      title: 'مشروعي الخاص',
      technicalId: 'MY_PRIVATE_PROJECT',
      localName: 'my_private_project',
    );
    expect(result.created, isTrue);
    expect(controller.state.privateCount, 1);
    final item = result.item!;
    expect(item.itemClass, WorkspaceItemClass.privateProject);
    expect(item.governed, isFalse);
    expect(item.projectUid, uid);
    expect(item.id, 'private:$uid');
    expect(item.technicalId, 'MY_PRIVATE_PROJECT');
    expect(item.sourceLabel, contains('إدخال صريح'));

    controller.select('project:PALWAKF_WORKSPACE_MANAGER');
    expect(controller.byId('private:$uid')!.projectUid, uid);

    final duplicateTechnicalId = controller.registerPrivateProject(
      title: 'نسخة أخرى',
      technicalId: 'my_private_project',
    );
    expect(duplicateTechnicalId.created, isFalse);
    expect(
      duplicateTechnicalId.error,
      PrivateProjectRegistrationError.duplicateTechnicalId,
    );
    expect(controller.state.privateCount, 1);
  });

  testWidgets('catalog renders scale search filters and real counts',
      (tester) async {
    tester.view.physicalSize = const Size(1440, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: Scaffold(body: WorkspaceCatalogPage()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey<String>('workspace-catalog-page')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey<String>('workspace-catalog-search')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey<String>('filter-palwakf-projects')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey<String>('filter-research')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey<String>('filter-private-projects')),
      findsOneWidget,
    );
    expect(find.textContaining('مشاريع PalWakf (16)'), findsOneWidget);
    expect(find.textContaining('الأبحاث (80)'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  test(
      'daily surface integrates catalog and does not route research into governed execution',
      () {
    final source = File(
      'lib/src/features/daily_workspace/presentation/'
      'daily_workspace_home_page.dart',
    ).readAsStringSync();
    expect(source, contains('workspaceCatalogProvider'));
    expect(source, contains('تنفيذ الأبحاث والمشاريع الخاصة'));
    expect(source, contains('DropdownMenu<String>'));
  });

  test(
      'projects route is user catalog while technical registry remains advanced',
      () {
    final source =
        File('lib/src/app/workspace_manager_app.dart').readAsStringSync();
    expect(source, contains("path: '/projects'"));
    expect(source, contains('WorkspaceCatalogPage'));
    expect(source, contains("path: '/advanced/projects-registry'"));
    expect(source, contains('ExternalProjectsPage'));
  });
  testWidgets(
      'private project intake is inline and updates count card and recents',
      (tester) async {
    tester.view.physicalSize = const Size(1440, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: Scaffold(body: WorkspaceCatalogPage()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey<String>('add-private-project')));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey<String>('private-project-inline-intake')),
      findsOneWidget,
    );

    await tester.enterText(
      find.byKey(const ValueKey<String>('private-project-title-field')),
      'مشروع عقاري خاص',
    );
    await tester.enterText(
      find.byKey(const ValueKey<String>('private-project-technical-id-field')),
      'PRIVATE_REAL_ESTATE',
    );
    await tester.enterText(
      find.byKey(const ValueKey<String>('private-project-local-name-field')),
      'private_real_estate',
    );
    await tester.tap(
      find.byKey(const ValueKey<String>('private-project-register')),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('مشاريعي الخاصة (1)'), findsOneWidget);
    expect(find.text('مشروع عقاري خاص'), findsWidgets);
    expect(find.text('معرف داخلي ثابت'), findsOneWidget);
    expect(
      find.byKey(const ValueKey<String>('private-project-inline-intake')),
      findsNothing,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('inline private intake exposes validation without creating data',
      (tester) async {
    tester.view.physicalSize = const Size(800, 600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: Scaffold(body: WorkspaceCatalogPage()),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey<String>('add-private-project')));
    await tester.pumpAndSettle();

    final registerButton =
        find.byKey(const ValueKey<String>('private-project-register'));
    expect(registerButton, findsOneWidget);
    await tester.ensureVisible(registerButton);
    await tester.pumpAndSettle();
    await tester.tap(registerButton);
    await tester.pumpAndSettle();

    final validationError =
        find.byKey(const ValueKey<String>('private-project-validation-error'));
    expect(validationError, findsOneWidget);
    await tester.ensureVisible(validationError);
    await tester.pumpAndSettle();
    expect(find.textContaining('أدخل اسم المشروع'), findsOneWidget);
    expect(find.textContaining('مشاريعي الخاصة (0)'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
