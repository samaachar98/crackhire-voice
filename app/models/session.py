from enum import Enum
from pydantic import BaseModel

class SessionState(str, Enum):
    IDLE = 'idle'
    LISTENING = 'listening'
    PROCESSING = 'processing'
    SPEAKING = 'speaking'
    INTERRUPTED = 'interrupted'
    ERROR = 'error'

class VoiceSession(BaseModel):
    session_id: str
    state: SessionState = SessionState.IDLE
    turns: int = 0
