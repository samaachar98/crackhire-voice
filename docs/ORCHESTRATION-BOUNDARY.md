# Orchestration Boundary Design

## Updated architecture decision
We are now targeting a **Pipecat-native realtime path** for lowest possible latency.

## New direction
Pipecat should own most of the realtime voice pipeline:
- transport/runtime flow
- realtime processing pipeline
- VAD/STT/LLM/TTS sequencing
- interruption-aware streaming behavior

The app should still own:
- config and secret loading
- health/readiness endpoints
- deployment/ops wrappers
- auth/product-specific integration points

## Why this changed
The project priority is low-latency speech-to-speech behavior.
Compared to app-owned transport + internal orchestration, a more Pipecat-native path reduces glue layers and coordination overhead.

## Target stack
- Pipecat-native realtime path
- WebRTC primary transport
- WebSocket fallback only if needed
- Silero VAD
- OpenAI Whisper STT
- MiniMax M2.7 LLM
- Piper local TTS

## Migration note
Current repo contains custom transport/orchestration scaffolding from earlier work.
That code is transitional and should be progressively replaced or absorbed into the Pipecat-native path where appropriate.
