from typing import Any

def make_event(event_type: str, session_id: str, turn_id: int, payload: dict[str, Any]):
    return {
        'version': 1,
        'type': event_type,
        'session_id': session_id,
        'turn_id': turn_id,
        'payload': payload,
    }
