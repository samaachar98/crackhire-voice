from typing import Protocol, Any

class Orchestrator(Protocol):
    async def run_turn(self, session_id: str, audio_bytes: bytes, interruption: Any): ...
