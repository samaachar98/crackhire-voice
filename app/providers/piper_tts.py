import io
import wave
from pathlib import Path
from piper import PiperVoice
from app.core.config import settings

class PiperTTSProvider:
    def __init__(self):
        self._voice = None

    def _load_voice(self):
        if self._voice is None:
            voice_file = Path(settings.piper_voice_path) / f"{settings.piper_voice}.onnx"
            if voice_file.exists():
                self._voice = PiperVoice(str(voice_file))
        return self._voice

    async def synthesize(self, text: str) -> bytes:
        voice = self._load_voice()
        if not voice:
            return b''
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav:
            voice.synthesize_wav(text, wav)
        buf.seek(0)
        return buf.getvalue()
