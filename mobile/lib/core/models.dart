/// Domain models shared across offline SQLite storage and live REST sync.
class MaxNote {
  final String id;
  final String title;
  final String content;
  final String aiSummary;
  final bool synced;

  const MaxNote({
    required this.id,
    required this.title,
    required this.content,
    this.aiSummary = '',
    this.synced = false,
  });

  Map<String, Object?> toDb() => {
        'id': id,
        'title': title,
        'content': content,
        'ai_summary': aiSummary,
        'synced': synced ? 1 : 0,
      };

  factory MaxNote.fromMap(Map<String, Object?> map) => MaxNote(
        id: map['id'].toString(),
        title: map['title'].toString(),
        content: map['content'].toString(),
        aiSummary: (map['ai_summary'] ?? '').toString(),
        synced: map['synced'] == 1 || map['synced'] == true,
      );
}

class MaxHabit {
  final String id;
  final String title;
  final String cadence;
  final int streak;
  final bool pendingCheckin;

  const MaxHabit({
    required this.id,
    required this.title,
    this.cadence = 'daily',
    this.streak = 0,
    this.pendingCheckin = false,
  });

  Map<String, Object?> toDb() => {
        'id': id,
        'title': title,
        'cadence': cadence,
        'streak': streak,
        'pending_checkin': pendingCheckin ? 1 : 0,
      };

  factory MaxHabit.fromMap(Map<String, Object?> map) => MaxHabit(
        id: map['id'].toString(),
        title: map['title'].toString(),
        cadence: (map['cadence'] ?? 'daily').toString(),
        streak: int.tryParse(map['streak'].toString()) ?? 0,
        pendingCheckin: map['pending_checkin'] == 1 || map['pending_checkin'] == true,
      );
}

class MaxReminder {
  final String id;
  final String title;
  final String dueAt;
  final bool completed;

  const MaxReminder({
    required this.id,
    required this.title,
    required this.dueAt,
    this.completed = false,
  });

  factory MaxReminder.fromMap(Map<String, Object?> map) => MaxReminder(
        id: map['id'].toString(),
        title: map['title'].toString(),
        dueAt: (map['due_at'] ?? '').toString(),
        completed: map['completed'] == 1 || map['completed'] == true,
      );
}
