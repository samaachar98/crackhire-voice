class TurnManager:
    def __init__(self):
        self.active_turns: dict[str, int] = {}

    def start_turn(self, session_id: str, turn_id: int):
        self.active_turns[session_id] = turn_id

    def is_current(self, session_id: str, turn_id: int) -> bool:
        return self.active_turns.get(session_id) == turn_id

    def clear(self, session_id: str):
        self.active_turns.pop(session_id, None)
