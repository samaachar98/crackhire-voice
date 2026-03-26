# Voice Architecture KT

Last updated: 2026-03-26 UTC

## Correct Product Direction
The required architecture is:
- **WebRTC as primary transport**
- **WebSocket only as fallback / debug path**
- **Pipecat orchestration as target orchestration layer**
- **Silero VAD** for production turn detection
- **OpenAI Whisper** for STT
- **MiniMax M2.7** for LLM
- **Piper local** for TTS

## Important correction
Current repo still contains a WS-based execution path for continuity and testing.
That is **not the final target architecture**.
Final target remains:
1. WebRTC first
2. Pipecat-oriented orchestration
3. WS fallback only

## Current implemented status
### Done
- modular repo refactor
- Whisper provider
- MiniMax provider
- Piper provider
- orchestration module
- session model/manager
- telemetry timer

### Missing / not yet implemented
- real WebRTC media path
- Pipecat runtime integration
- Silero VAD integration
- barge-in at transport/audio layer
- WS demoted to fallback-only path

## Priority updates
### P0 priorities (corrected)
1. WebRTC transport primary
2. Pipecat orchestration integration
3. Session manager/state machine
4. Whisper/MiniMax/Piper provider hardening
5. telemetry and readiness
6. WS fallback contract only after primary path is defined

## Rule
Do not mistake current WS implementation for final architecture.
WS exists temporarily; WebRTC + Pipecat remain the real destination.
