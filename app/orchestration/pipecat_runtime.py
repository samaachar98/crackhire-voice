from app.providers.whisper import WhisperProvider
from app.providers.minimax import MiniMaxProvider
from app.providers.piper_tts import PiperTTSProvider
from app.telemetry.metrics import StageTimer, metrics_store

class PipecatRuntime:
    """Pipecat-target runtime adapter.
    Structured as runtime-owned provider wiring so it can later be swapped with a real Pipecat pipeline.
    """

    def __init__(self):
        self.stt = WhisperProvider()
        self.llm = MiniMaxProvider()
        self.tts = PiperTTSProvider()
        self.messages = [{
            'role': 'system',
            'content': 'You are a professional interviewer. Keep responses brief and conversational.'
        }]

    async def run_turn(self, session_id: str, audio_bytes: bytes, interruption):
        if interruption.is_set():
            return {'cancelled': True, 'stage': 'pre_stt'}

        timer = StageTimer()
        timer.start('stt')
        transcript = await self.stt.transcribe(audio_bytes)
        stt_ms = timer.stop_ms('stt')
        metrics_store.add('stt_ms', stt_ms)
        if interruption.is_set():
            return {'cancelled': True, 'stage': 'post_stt', 'transcript': transcript, 'metrics': {'stt_ms': stt_ms}}

        timer.start('llm')
        response = await self.llm.respond(transcript, self.messages)
        llm_ms = timer.stop_ms('llm')
        metrics_store.add('llm_ms', llm_ms)
        if interruption.is_set():
            return {'cancelled': True, 'stage': 'post_llm', 'transcript': transcript, 'response': response, 'metrics': {'stt_ms': stt_ms, 'llm_ms': llm_ms}}

        self.messages.extend([
            {'role': 'user', 'content': transcript},
            {'role': 'assistant', 'content': response},
        ])

        timer.start('tts')
        audio = await self.tts.synthesize(response)
        tts_ms = timer.stop_ms('tts')
        metrics_store.add('tts_ms', tts_ms)
        metrics_store.add('total_ms', round(stt_ms + llm_ms + tts_ms, 2))
        if interruption.is_set():
            return {'cancelled': True, 'stage': 'post_tts', 'transcript': transcript, 'response': response, 'metrics': {'stt_ms': stt_ms, 'llm_ms': llm_ms, 'tts_ms': tts_ms}}

        return {
            'cancelled': False,
            'transcript': transcript,
            'response': response,
            'audio': audio,
            'metrics': {
                'stt_ms': stt_ms,
                'llm_ms': llm_ms,
                'tts_ms': tts_ms,
                'total_ms': round(stt_ms + llm_ms + tts_ms, 2),
            }
        }
