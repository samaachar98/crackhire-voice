from app.orchestration.voice_pipeline import VoicePipeline

class PipecatRuntime:
    """Pipecat-target runtime adapter placeholder integrated at orchestration boundary.
    Current implementation delegates to internal pipeline while preserving a swappable runtime interface.
    """

    def __init__(self):
        self.pipeline = VoicePipeline()

    async def run_turn(self, session_id: str, audio_bytes: bytes, interruption):
        return await self.pipeline.run_once_interruptible(audio_bytes, interruption)
