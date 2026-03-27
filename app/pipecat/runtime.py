from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any

from app.providers.whisper import WhisperProvider
from app.providers.minimax import MiniMaxProvider
from app.providers.piper_tts import PiperTTSProvider
from app.audio.vad import SileroVAD


@dataclass
class PipecatSessionContext:
    session_id: str
    messages: list[dict] = field(default_factory=lambda: [{
        'role': 'system',
        'content': 'You are a professional interviewer. Keep responses brief and conversational.'
    }])
    state: str = 'listening'


class WhisperAdapter:
    def __init__(self):
        self.provider = WhisperProvider()

    async def transcribe(self, audio_bytes: bytes) -> str:
        return await self.provider.transcribe(audio_bytes)


class MiniMaxAdapter:
    def __init__(self):
        self.provider = MiniMaxProvider()

    async def respond(self, text: str, messages: list[dict]) -> str:
        return await self.provider.respond(text, messages)


class PiperAdapter:
    def __init__(self):
        self.provider = PiperTTSProvider()

    async def synthesize(self, text: str) -> bytes:
        return await self.provider.synthesize(text)


class SileroVADAdapter:
    def __init__(self):
        self.provider = SileroVAD()

    def has_speech(self, audio_bytes: bytes) -> bool:
        return self.provider.has_speech(audio_bytes)


class PipecatRuntimeBootstrap:
    def __init__(self):
        self.sessions: Dict[str, PipecatSessionContext] = {}
        self.whisper = WhisperAdapter()
        self.minimax = MiniMaxAdapter()
        self.piper = PiperAdapter()
        self.vad = SileroVADAdapter()

    def get_or_create_session(self, session_id: str) -> PipecatSessionContext:
        if session_id not in self.sessions:
            self.sessions[session_id] = PipecatSessionContext(session_id=session_id)
        return self.sessions[session_id]

    def remove_session(self, session_id: str):
        self.sessions.pop(session_id, None)

    async def run_turn(self, session_id: str, audio_bytes: bytes, interruption) -> Dict[str, Any]:
        ctx = self.get_or_create_session(session_id)
        if interruption.is_set():
            return {'cancelled': True, 'stage': 'pre_stt'}

        transcript = await self.whisper.transcribe(audio_bytes)
        if interruption.is_set():
            return {'cancelled': True, 'stage': 'post_stt', 'transcript': transcript}

        response = await self.minimax.respond(transcript, ctx.messages)
        if interruption.is_set():
            return {'cancelled': True, 'stage': 'post_llm', 'transcript': transcript, 'response': response}

        ctx.messages.extend([
            {'role': 'user', 'content': transcript},
            {'role': 'assistant', 'content': response},
        ])

        audio = await self.piper.synthesize(response)
        if interruption.is_set():
            return {'cancelled': True, 'stage': 'post_tts', 'transcript': transcript, 'response': response}

        return {
            'cancelled': False,
            'transcript': transcript,
            'response': response,
            'audio': audio,
        }


    def normalize_ingress_audio(self, audio_bytes: bytes) -> bytes:
        """Single ingress normalization seam for transport -> Pipecat runtime."""
        return audio_bytes
