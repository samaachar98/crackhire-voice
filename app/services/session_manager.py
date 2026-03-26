from app.models.session import VoiceSession, SessionState

class SessionManager:
    def __init__(self):
        self.sessions: dict[str, VoiceSession] = {}

    def get_or_create(self, session_id: str) -> VoiceSession:
        if session_id not in self.sessions:
            self.sessions[session_id] = VoiceSession(session_id=session_id, state=SessionState.LISTENING)
        return self.sessions[session_id]

    def set_state(self, session_id: str, state: SessionState) -> VoiceSession:
        session = self.get_or_create(session_id)
        session.state = state
        return session

    def remove(self, session_id: str):
        self.sessions.pop(session_id, None)
