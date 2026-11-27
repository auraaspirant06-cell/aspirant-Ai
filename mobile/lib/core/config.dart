/// Runtime endpoints and brand palette constants for MAX Mobile Companion.
class MaxConfig {
  static const String appTitle = 'MAX — Aspirant AI';
  static const String tagline = 'Intelligence Beyond Assistance';
  static const String defaultApiBaseUrl = String.fromEnvironment(
    'ASPIRANT_API_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );
  static const int primaryBlueHex = 0xFF0EA5E9;
  static const int accentPurpleHex = 0xFF8B5CF6;
  static const int deepBlackHex = 0xFF05070E;
  static const int surfaceCardHex = 0xFF0B1020;
}
