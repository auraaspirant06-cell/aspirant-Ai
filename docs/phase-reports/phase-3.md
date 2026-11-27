# Phase 3 Report — Female Voice Assistant

## Completed & Verified Features

- **Female Neural Voice Catalog (`src/aspirant/voice/profiles.py`, `providers/tts_providers.py`)**:
  - Default free female Indian neural voices via `edge-tts` (`en-IN-NeerjaNeural`, `hi-IN-SwaraNeural`, `mr-IN-AarohiNeural`, `bn-IN-TanishaaNeural`, `gu-IN-DhwaniNeural`, `ta-IN-PallaviNeural`, `te-IN-ShrutiNeural`, `kn-IN-SapnaNeural`, `ml-IN-SobhanaNeural`, `ur-IN-GulNeural`).
  - Expressive cloud TTS via `gemini-3.8-flash-tts` (`Kore` female voice + `speech_metadata` emotion annotations).
  - 100% offline Windows SAPI5 female voice fallback (tested live rendering WAV speech).
  - Configurable speaking speed (`0.75x`–`1.50x`), pitch (`-20 Hz`..`+20 Hz`), and emotion presets.
- **Multilingual Speech Recognition (`src/aspirant/providers/stt_providers.py`)**:
  - `gemini-3.5-transcribe`, OpenAI/Groq Whisper endpoints, and lazy-loaded CPU `int8` `faster-whisper` offline fallback (unloaded on idle to protect the 8 GB RAM budget).
- **Audio Engine & Wake Word (`src/aspirant/voice/audio_io.py`, `wakeword.py`, `pipeline.py`)**:
  - `"Hey Aspirant"` wake-word matcher, Push-to-Talk, and Hands-Free continuous modes.
  - WebRTC VAD + adaptive background noise floor tracking (`NoiseAdaptiveVAD`).
  - Instant barge-in speech interruption (`AudioPlaybackController.interrupt()`).
  - Voice-driven personality switching wired into `ChatService`.
- **Live Voice Assistant UI (`src/aspirant/ui/views/voice_view.py`)**:
  - Animated `VoiceOrbWidget`, mode buttons, prosody sliders, noise suppression toggle, and spoken test runner.

## Pending (Phases 4–9)

- Phase 4: Secure PC automation, File Manager, screen vision, inspected commands & Playwright Edge.
- Phases 5–9: Coding Studio, Indian Gov Services, Image/Video Studios, Memory/Security Optimization, Packaging.
