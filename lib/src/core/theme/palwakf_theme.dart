import 'package:flutter/material.dart';

abstract final class PalWakfTheme {
  static const Color sovereignBlue = Color(0xFF123B66);
  static const Color waqfGold = Color(0xFFC89B3C);
  static const Color royalRed = Color(0xFFB22222);
  static const Color successGreen = Color(0xFF18794E);
  static const Color canvas = Color(0xFFF6F7F9);
  static const Color darkCanvas = Color(0xFF07111D);
  static const Color darkSurface = Color(0xFF0D1A29);
  static const Color darkSurfaceHigh = Color(0xFF142338);
  static const Color darkBorder = Color(0xFF29405D);

  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(
      seedColor: sovereignBlue,
      brightness: Brightness.light,
    ).copyWith(
      primary: sovereignBlue,
      secondary: waqfGold,
      error: royalRed,
      surface: Colors.white,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: canvas,
      appBarTheme: const AppBarTheme(
        centerTitle: false,
        backgroundColor: sovereignBlue,
        foregroundColor: Colors.white,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: BorderSide(color: sovereignBlue.withValues(alpha: 0.10)),
        ),
      ),
    );
  }

  static ThemeData dark() {
    final scheme = ColorScheme.fromSeed(
      seedColor: waqfGold,
      brightness: Brightness.dark,
    ).copyWith(
      primary: waqfGold,
      onPrimary: const Color(0xFF211804),
      secondary: const Color(0xFF78A9D7),
      onSecondary: const Color(0xFF061625),
      error: const Color(0xFFFF7B72),
      surface: darkSurface,
      onSurface: const Color(0xFFE7EDF5),
      surfaceContainerHighest: darkSurfaceHigh,
      onSurfaceVariant: const Color(0xFFB9C7D8),
      outline: darkBorder,
      outlineVariant: const Color(0xFF20344D),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: darkCanvas,
      canvasColor: darkCanvas,
      dividerColor: darkBorder,
      appBarTheme: const AppBarTheme(
        centerTitle: false,
        backgroundColor: Color(0xFF0A2745),
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: darkSurface,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: darkBorder),
        ),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: const Color(0xFF091522),
        indicatorColor: waqfGold.withValues(alpha: 0.18),
        selectedIconTheme: const IconThemeData(color: waqfGold),
        selectedLabelTextStyle: const TextStyle(
          color: waqfGold,
          fontWeight: FontWeight.w700,
        ),
        unselectedIconTheme: const IconThemeData(color: Color(0xFFB9C7D8)),
        unselectedLabelTextStyle: const TextStyle(color: Color(0xFFB9C7D8)),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: const Color(0xFF091522),
        indicatorColor: waqfGold.withValues(alpha: 0.18),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: darkSurfaceHigh,
        selectedColor: waqfGold.withValues(alpha: 0.18),
        side: const BorderSide(color: darkBorder),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: darkSurfaceHigh,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: darkBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: darkBorder),
        ),
      ),
    );
  }
}
