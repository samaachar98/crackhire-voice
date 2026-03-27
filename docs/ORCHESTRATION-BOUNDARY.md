# Orchestration Boundary Design

## Goal
Define where Pipecat-oriented orchestration fits relative to transports, providers, and session lifecycle.

## Boundary
Transport layer responsibilities:
- WebRTC / WS connection lifecycle
- audio ingress / egress
- session-bound track management
- low-level interruption signal propagation

Orchestration layer responsibilities:
- turn execution
- state transitions tied to turn lifecycle
- STT -> LLM -> TTS sequencing
- interruption-aware cancellation boundaries
- timing/metrics aggregation

Provider layer responsibilities:
- Whisper STT implementation
- MiniMax LLM implementation
- Piper TTS implementation
- provider-specific retries/errors/timeouts

Session layer responsibilities:
- session registry
- state machine
- turn ids / request ids
- cleanup / disconnect handling

## Pipecat target placement
Pipecat should sit inside the orchestration boundary, not replace the whole app.
That means:
- transports remain app-controlled
- provider config remains app-controlled
- session manager remains app-controlled
- Pipecat becomes the runtime/pipeline engine for turn execution

## Interface contract
Transport -> Orchestration input:
- session_id
- normalized PCM audio bytes
- interruption event

Orchestration -> Transport output:
- transcript
- response text
- synthesized audio bytes/stream
- metrics
- final state

## Immediate implementation rule
Before integrating Pipecat runtime, preserve this boundary so the repo does not collapse back into a monolith.


## Current integration status
- WebRTC turn execution now routes through `app/orchestration/pipecat_runtime.py`
- provider wiring (Whisper / MiniMax / Piper) is owned by the runtime adapter
- transport calls runtime, not providers directly
- this is the current bridge step before a fuller Pipecat-native runtime replacement
