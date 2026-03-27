import time

class TurnDetector:
    def __init__(self, trailing_silence_seconds: float = 0.5, min_speech_bytes: int = 16000):
        self.trailing_silence_seconds = trailing_silence_seconds
        self.min_speech_bytes = min_speech_bytes
        self.last_speech_at: dict[str, float] = {}
        self.speech_started: dict[str, bool] = {}
        self.bytes_seen: dict[str, int] = {}

    def mark_speech(self, session_id: str, byte_count: int):
        self.last_speech_at[session_id] = time.time()
        self.speech_started[session_id] = True
        self.bytes_seen[session_id] = self.bytes_seen.get(session_id, 0) + byte_count

    def should_finalize(self, session_id: str, now: float) -> bool:
        last = self.last_speech_at.get(session_id)
        started = self.speech_started.get(session_id, False)
        byte_count = self.bytes_seen.get(session_id, 0)
        if last is None or not started:
            return False
        if byte_count < self.min_speech_bytes:
            return False
        return (now - last) >= self.trailing_silence_seconds

    def clear(self, session_id: str):
        self.last_speech_at.pop(session_id, None)
        self.speech_started.pop(session_id, None)
        self.bytes_seen.pop(session_id, None)
