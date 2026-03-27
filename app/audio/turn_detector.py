import time

class TurnDetector:
    def __init__(self, trailing_silence_seconds: float = 0.5):
        self.trailing_silence_seconds = trailing_silence_seconds
        self.last_speech_at: dict[str, float] = {}

    def mark_speech(self, session_id: str):
        self.last_speech_at[session_id] = time.time()

    def should_finalize(self, session_id: str, now: float) -> bool:
        last = self.last_speech_at.get(session_id)
        if last is None:
            return False
        return (now - last) >= self.trailing_silence_seconds

    def clear(self, session_id: str):
        self.last_speech_at.pop(session_id, None)
