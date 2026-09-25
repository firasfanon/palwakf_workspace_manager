import 'package:flutter/material.dart';

/// Canonical PalWakf visual system.
///
/// The Workspace Command Center is the visual baseline for the product. Legacy
/// semantic names remain as compatibility aliases so domain widgets keep their
/// behavior while inheriting the unified palette.
abstract final class PalWakfTheme {
  static const Color workspaceBg = Color(0xFF03101C);
  static const Color workspacePanel = Color(0xFF071B2C);
  static const Color workspacePanelHigh = Color(0xFF0A2238);
  static const Color workspaceBorder = Color(0xFF123A59);
  static const Color workspaceText = Color(0xFFF3F8FC);
  static const Color workspaceMuted = Color(0xFF8EA9C1);
  static const Color workspaceCyan = Color(0xFF00C8FF);
  static const Color workspaceTeal = Color(0xFF00E3B2);
  static const Color workspaceGreen = Color(0xFF24E59A);
  static const Color workspaceBlue = Color(0xFF2F82FF);
  static const Color workspacePurple = Color(0xFF8E5CFF);
  static const Color workspaceOrange = Color(0xFFFFA726);
  static const Color workspaceRed = Color(0xFFFF4D67);
  static const Color workspaceSidebar = Color(0xFF020D17);

  // Compatibility aliases for existing domain widgets.
  static const Color sovereignBlue = workspaceBlue;
  static const Color waqfGold = workspaceOrange;
  static const Color royalRed = workspaceRed;
  static const Color successGreen = workspaceGreen;
  static const Color canvas = Color(0xFFF6F7F9);
  static const Color darkCanvas = workspaceBg;
  static const Color darkSurface = workspacePanel;
  static const Color darkSurfaceHigh = workspacePanelHigh;
  static const Color darkBorder = workspaceBorder;

  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(
      seedColor: workspaceBlue,
      brightness: Brightness.light,
    ).copyWith(
      primary: workspaceBlue,
      secondary: workspaceTeal,
      error: workspaceRed,
      surface: Colors.white,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: canvas,
      appBarTheme: const AppBarTheme(
        centerTitle: false,
        backgroundColor: workspaceBlue,
        foregroundColor: Colors.white,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: workspaceBlue.withValues(alpha: 0.12)),
        ),
      ),
    );
  }

  static ThemeData dark() {
    final scheme = ColorScheme.fromSeed(
      seedColor: workspaceTeal,
      brightness: Brightness.dark,
    ).copyWith(
      primary: workspaceTeal,
      onPrimary: const Color(0xFF00251D),
      secondary: workspaceCyan,
      onSecondary: const Color(0xFF001F2A),
      tertiary: workspacePurple,
      error: workspaceRed,
      surface: workspacePanel,
      onSurface: workspaceText,
      surfaceContainerHighest: workspacePanelHigh,
      onSurfaceVariant: workspaceMuted,
      outline: workspaceBorder,
      outlineVariant: workspaceBorder,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: workspaceBg,
      canvasColor: workspaceBg,
      dividerColor: workspaceBorder,
      splashColor: workspaceCyan.withValues(alpha: 0.08),
      highlightColor: workspaceTeal.withValues(alpha: 0.06),
      iconTheme: const IconThemeData(color: workspaceMuted),
      appBarTheme: const AppBarTheme(
        centerTitle: false,
        backgroundColor: workspaceBg,
        foregroundColor: workspaceText,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: workspacePanel,
        surfaceTintColor: Colors.transparent,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: workspaceBorder),
        ),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: workspaceSidebar,
        indicatorColor: workspaceBlue.withValues(alpha: 0.20),
        selectedIconTheme: const IconThemeData(color: workspaceCyan),
        selectedLabelTextStyle: const TextStyle(
          color: workspaceText,
          fontWeight: FontWeight.w800,
        ),
        unselectedIconTheme: const IconThemeData(color: workspaceMuted),
        unselectedLabelTextStyle: const TextStyle(color: workspaceMuted),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: workspaceSidebar,
        indicatorColor: workspaceBlue.withValues(alpha: 0.20),
        labelTextStyle: WidgetStateProperty.resolveWith<TextStyle?>(
          (states) => TextStyle(
            color: states.contains(WidgetState.selected)
                ? workspaceText
                : workspaceMuted,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w800
                : FontWeight.w600,
          ),
        ),
      ),
      drawerTheme: const DrawerThemeData(
        backgroundColor: workspaceSidebar,
        surfaceTintColor: Colors.transparent,
      ),
      chipTheme: ChipThemeData(
        backgroundColor: workspacePanelHigh,
        selectedColor: workspaceBlue.withValues(alpha: 0.20),
        labelStyle: const TextStyle(color: workspaceText),
        side: const BorderSide(color: workspaceBorder),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: workspacePanelHigh,
        hintStyle: const TextStyle(color: workspaceMuted),
        labelStyle: const TextStyle(color: workspaceMuted),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: workspaceBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: workspaceBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: workspaceCyan),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: workspaceBlue,
          foregroundColor: workspaceText,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: workspaceText,
          side: const BorderSide(color: workspaceBorder),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9)),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: workspaceCyan),
      ),
      dataTableTheme: const DataTableThemeData(
        headingTextStyle: TextStyle(
          color: workspaceText,
          fontWeight: FontWeight.w800,
        ),
        dataTextStyle: TextStyle(color: workspaceText),
        dividerThickness: 0.7,
      ),
      snackBarTheme: const SnackBarThemeData(
        backgroundColor: workspacePanelHigh,
        contentTextStyle: TextStyle(color: workspaceText),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: workspaceTeal,
        linearTrackColor: workspacePanelHigh,
      ),
    );
  }
}
