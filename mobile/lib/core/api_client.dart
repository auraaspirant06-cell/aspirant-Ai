import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'config.dart';

/// Secure REST client managing JWT + Refresh tokens inside Android Keystore.
class MaxApiClient {
  final String baseUrl;
  final FlutterSecureStorage _secureStorage;

  MaxApiClient({
    this.baseUrl = MaxConfig.defaultApiBaseUrl,
    FlutterSecureStorage? secureStorage,
  }) : _secureStorage = secureStorage ?? const FlutterSecureStorage();

  Future<String?> getAccessToken() => _secureStorage.read(key: 'access_token');

  Future<void> saveTokens(String access, String refresh) async {
    await _secureStorage.write(key: 'access_token', value: access);
    await _secureStorage.write(key: 'refresh_token', value: refresh);
  }

  Future<bool> login({required String email, required String password}) async {
    final uri = Uri.parse('$baseUrl/auth/login');
    final res = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'password': password,
        'device_name': 'MAX-Android',
        'device_platform': 'android',
      }),
    );
    if (res.statusCode == 200) {
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      await saveTokens(
        data['access_token'].toString(),
        data['refresh_token'].toString(),
      );
      return true;
    }
    return false;
  }

  Future<Map<String, dynamic>> sendChatOrVoice(String message, {bool isVoice = false}) async {
    final token = await getAccessToken();
    final endpoint = isVoice ? '/max/voice-command' : '/max/chat';
    final res = await http.post(
      Uri.parse('$baseUrl$endpoint'),
      headers: {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      },
      body: jsonEncode({'message': message, 'channel': isVoice ? 'voice' : 'chat'}),
    );
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> syncDelta({
    required List<Map<String, dynamic>> offlineNotes,
    required List<String> habitCheckins,
  }) async {
    final token = await getAccessToken();
    final res = await http.post(
      Uri.parse('$baseUrl/max/sync'),
      headers: {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      },
      body: jsonEncode({
        'offline_notes': offlineNotes,
        'habit_checkins': habitCheckins,
      }),
    );
    return jsonDecode(res.body) as Map<String, dynamic>;
  }
}
