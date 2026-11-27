import 'api_client.dart';
import 'local_db.dart';
import 'models.dart';

/// Coordinates offline-first persistence and delta reconciliation with the FastAPI MAX API.
class MaxSyncService {
  final MaxApiClient api;
  final MaxLocalDatabase localDb;

  MaxSyncService({required this.api, required this.localDb});

  Future<bool> syncNow() async {
    try {
      final unsyncedNotes = await localDb.pendingSyncNotes();
      final habits = await localDb.listHabits();
      final pendingCheckins =
          habits.where((h) => h.pendingCheckin).map((h) => h.id).toList();

      final payload = await api.syncDelta(
        offlineNotes: unsyncedNotes
            .map((n) => {'id': n.id, 'title': n.title, 'content': n.content})
            .toList(),
        habitCheckins: pendingCheckins,
      );

      final notes = ((payload['notes'] as List?) ?? [])
          .cast<Map<String, dynamic>>()
          .map((m) => MaxNote.fromMap({...m, 'synced': true}))
          .toList();
      final syncedHabits = ((payload['habits'] as List?) ?? [])
          .cast<Map<String, dynamic>>()
          .map((m) => MaxHabit.fromMap(m))
          .toList();
      final reminders = ((payload['reminders'] as List?) ?? [])
          .cast<Map<String, dynamic>>()
          .map((m) => MaxReminder.fromMap(m))
          .toList();

      await localDb.replaceSyncedState(
        notes: notes,
        habits: syncedHabits,
        reminders: reminders,
      );
      return true;
    } catch (_) {
      return false;
    }
  }
}
