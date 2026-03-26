from time import perf_counter

class StageTimer:
    def __init__(self):
        self.marks = {}
    def start(self, key: str):
        self.marks[key] = perf_counter()
    def stop_ms(self, key: str) -> float:
        return round((perf_counter() - self.marks[key]) * 1000, 2) if key in self.marks else 0.0
