import numpy as np
from silero_vad import load_silero_vad, get_speech_timestamps
from app.audio.pcm import TARGET_SAMPLE_RATE

class SileroVAD:
    def __init__(self, threshold: float = 0.5, min_silence_ms: int = 500):
        self.model = load_silero_vad()
        self.threshold = threshold
        self.min_silence_ms = min_silence_ms

    def has_speech(self, audio_bytes: bytes) -> bool:
        if not audio_bytes:
            return False
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        timestamps = get_speech_timestamps(
            audio,
            self.model,
            sampling_rate=TARGET_SAMPLE_RATE,
            threshold=self.threshold,
            min_silence_duration_ms=self.min_silence_ms,
        )
        return bool(timestamps)
