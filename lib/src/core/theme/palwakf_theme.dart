import 'package:flutter/material.dart';

abstract final class PalWakfTheme {
  static const Color sovereignBlue = Color(0xFF123B66);
  static const Color waqfGold = Color(0xFFC89B3C);
  static const Color royalRed = Color(0xFFB22222);
  static const Color successGreen = Color(0xFF18794E);
  static const Color canvas = Color(0xFFF6F7F9);

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
}
