import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';
import 'models.dart';

/// Offline-first SQLite repository persisting MAX notes, habits, and reminders.
class MaxLocalDatabase {
  Database? _db;

  Future<Database> _open() async {
    if (_db != null) return _db!;
    final dbPath = p.join(await getDatabasesPath(), 'aspirant_max.db');
    _db = await openDatabase(
      dbPath,
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE notes(
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            ai_summary TEXT NOT NULL,
            synced INTEGER NOT NULL DEFAULT 0
          )
        ''');
        await db.execute('''
          CREATE TABLE habits(
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            cadence TEXT NOT NULL,
            streak INTEGER NOT NULL DEFAULT 0,
            pending_checkin INTEGER NOT NULL DEFAULT 0
          )
        ''');
        await db.execute('''
          CREATE TABLE reminders(
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            due_at TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0
          )
        ''');
      },
    );
    return _db!;
  }

  Future<void> upsertNote(MaxNote note) async {
    final db = await _open();
    await db.insert('notes', note.toDb(), conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<List<MaxNote>> listNotes() async {
    final db = await _open();
    final rows = await db.query('notes');
    return rows.map((r) => MaxNote.fromMap(r)).toList();
  }

  Future<List<MaxNote>> pendingSyncNotes() async {
    final db = await _open();
    final rows = await db.query('notes', where: 'synced = 0');
    return rows.map((r) => MaxNote.fromMap(r)).toList();
  }

  Future<void> upsertHabit(MaxHabit habit) async {
    final db = await _open();
    await db.insert('habits', habit.toDb(), conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<List<MaxHabit>> listHabits() async {
    final db = await _open();
    final rows = await db.query('habits');
    return rows.map((r) => MaxHabit.fromMap(r)).toList();
  }

  Future<void> replaceSyncedState({
    required List<MaxNote> notes,
    required List<MaxHabit> habits,
    required List<MaxReminder> reminders,
  }) async {
    final db = await _open();
    await db.transaction((txn) async {
      await txn.delete('notes');
      for (final n in notes) {
        await txn.insert('notes', MaxNote(
          id: n.id,
          title: n.title,
          content: n.content,
          aiSummary: n.aiSummary,
          synced: true,
        ).toDb());
      }
      await txn.delete('habits');
      for (final h in habits) {
        await txn.insert('habits', h.toDb());
      }
      await txn.delete('reminders');
      for (final r in reminders) {
        await txn.insert('reminders', {
          'id': r.id,
          'title': r.title,
          'due_at': r.dueAt,
          'completed': r.completed ? 1 : 0,
        });
      }
    });
  }
}
