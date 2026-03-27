# Pipecat Native Plan

## Goal
Shift `crackhire-voice` toward Pipecat-native realtime operation for lower latency.

## Immediate plan
### Phase A
- update architecture docs
- treat current custom transport/orchestration as transitional
- define Pipecat-native target in repo

### Phase B
- add Pipecat runtime bootstrap module
- map current providers into Pipecat-oriented pipeline adapters
- define WebRTC/Pipecat integration seam

### Phase C
- move live voice path onto Pipecat-native execution
- keep existing code only where needed for wrappers/ops

## Notes
This is a direction correction toward latency-first architecture.
