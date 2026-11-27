import 'package:flutter/material.dart';
import 'core/api_client.dart';
import 'core/config.dart';
import 'core/local_db.dart';
import 'core/models.dart';
import 'core/sync_service.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MaxCompanionApp());
}

class MaxCompanionApp extends StatelessWidget {
  const MaxCompanionApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: MaxConfig.appTitle,
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(MaxConfig.deepBlackHex),
        colorScheme: const ColorScheme.dark(
          primary: Color(MaxConfig.primaryBlueHex),
          secondary: Color(MaxConfig.accentPurpleHex),
          surface: Color(MaxConfig.surfaceCardHex),
        ),
      ),
      home: const MaxHomeScreen(),
    );
  }
}

class MaxHomeScreen extends StatefulWidget {
  const MaxHomeScreen({super.key});

  @override
  State<MaxHomeScreen> createState() => _MaxHomeScreenState();
}

class _MaxHomeScreenState extends State<MaxHomeScreen> {
  final _localDb = MaxLocalDatabase();
  late final MaxApiClient _api = MaxApiClient();
  late final MaxSyncService _sync = MaxSyncService(api: _api, localDb: _localDb);

  final _promptController = TextEditingController();
  int _tabIndex = 0;
  String _syncStatus = 'Offline-ready SQLite storage';
  final List<Map<String, String>> _messages = [
    {'role': 'max', 'text': 'Hey! MAX is ready for voice commands, daily planning, and notes.'},
  ];
  List<MaxHabit> _habits = const [
    MaxHabit(id: 'h1', title: 'Morning Deep Focus', streak: 4),
    MaxHabit(id: 'h2', title: 'Evening Review & Sync', streak: 2),
  ];
  List<MaxNote> _notes = const [
    MaxNote(
      id: 'n1',
      title: 'Aspirant AI Sync Note',
      content: 'Offline changes automatically reconcile with NOVA and MJ.',
      aiSummary: 'Auto-reconciliation enabled for MAX.',
    ),
  ];

  Future<void> _sendPrompt({bool isVoice = false}) async {
    final text = _promptController.text.trim();
    if (text.isEmpty) return;
    _promptController.clear();
    setState(() {
      _messages.add({'role': 'you', 'text': text});
    });
    try {
      final res = await _api.sendChatOrVoice(text, isVoice: isVoice);
      setState(() {
        _messages.add({'role': 'max', 'text': (res['reply'] ?? 'Queued.').toString()});
      });
    } catch (_) {
      final note = MaxNote(
        id: 'offline-${DateTime.now().millisecondsSinceEpoch}',
        title: isVoice ? 'Offline Voice Memo' : 'Quick Mobile Note',
        content: text,
        aiSummary: text.length > 80 ? '${text.substring(0, 80)}...' : text,
      );
      await _localDb.upsertNote(note);
      final refreshed = await _localDb.listNotes();
      setState(() {
        _notes = refreshed;
        _messages.add({'role': 'max', 'text': 'Saved offline to SQLite; will sync automatically.'});
      });
    }
  }

  Future<void> _triggerSync() async {
    final ok = await _sync.syncNow();
    if (ok) {
      final notes = await _localDb.listNotes();
      final habits = await _localDb.listHabits();
      setState(() {
        _notes = notes;
        if (habits.isNotEmpty) _habits = habits;
        _syncStatus = 'Synced with Aspirant Cloud';
      });
    } else {
      setState(() {
        _syncStatus = 'Offline mode — local queue preserved';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final screens = [
      _buildChatView(),
      _buildPlannerView(),
      _buildNotesView(),
    ];
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(MaxConfig.surfaceCardHex),
        title: Row(
          children: [
            Image.asset('assets/brand/max-mark.png', width: 28, height: 28),
            const SizedBox(width: 10),
            const Text('MAX Companion', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Sync across devices',
            onPressed: _triggerSync,
            icon: const Icon(Icons.sync),
          ),
        ],
      ),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            color: const Color(MaxConfig.surfaceCardHex),
            child: Text(_syncStatus, style: const TextStyle(fontSize: 12, color: Color(0xFF38BDF8))),
          ),
          Expanded(child: screens[_tabIndex]),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tabIndex,
        onDestinationSelected: (idx) => setState(() => _tabIndex = idx),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.mic_none), label: 'Voice & Chat'),
          NavigationDestination(icon: Icon(Icons.check_circle_outline), label: 'Planner'),
          NavigationDestination(icon: Icon(Icons.notes), label: 'AI Notes'),
        ],
      ),
    );
  }

  Widget _buildChatView() {
    return Column(
      children: [
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(14),
            itemCount: _messages.length,
            itemBuilder: (_, idx) {
              final m = _messages[idx];
              final isUser = m['role'] == 'you';
              return Align(
                alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                child: Container(
                  margin: const EdgeInsets.symmetric(vertical: 4),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: isUser ? const Color(0xFF0284C7) : const Color(MaxConfig.surfaceCardHex),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Text(m['text'] ?? ''),
                ),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _promptController,
                  decoration: const InputDecoration(
                    hintText: 'Ask MAX or capture voice memo...',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                onPressed: () => _sendPrompt(isVoice: true),
                icon: const Icon(Icons.mic, color: Color(MaxConfig.accentPurpleHex)),
              ),
              IconButton(
                onPressed: () => _sendPrompt(isVoice: false),
                icon: const Icon(Icons.send, color: Color(MaxConfig.primaryBlueHex)),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildPlannerView() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Habit Streaks', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        for (final h in _habits)
          Card(
            color: const Color(MaxConfig.surfaceCardHex),
            child: ListTile(
              title: Text(h.title),
              subtitle: Text('${h.cadence} • Streak: ${h.streak} days'),
              trailing: IconButton(
                icon: const Icon(Icons.add_task, color: Color(0xFF10B981)),
                onPressed: () async {
                  final updated = MaxHabit(
                    id: h.id,
                    title: h.title,
                    cadence: h.cadence,
                    streak: h.streak + 1,
                    pendingCheckin: true,
                  );
                  await _localDb.upsertHabit(updated);
                  setState(() {
                    _habits = _habits.map((item) => item.id == h.id ? updated : item).toList();
                  });
                },
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildNotesView() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _notes.length,
      itemBuilder: (_, idx) {
        final note = _notes[idx];
        return Card(
          color: const Color(MaxConfig.surfaceCardHex),
          child: ListTile(
            title: Text(note.title),
            subtitle: Text(note.aiSummary.isNotEmpty ? note.aiSummary : note.content),
          ),
        );
      },
    );
  }
}
