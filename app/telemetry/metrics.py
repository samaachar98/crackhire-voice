from time import perf_counter
from collections import defaultdict

class StageTimer:
    def __init__(self):
        self.marks = {}
    def start(self, key: str):
        self.marks[key] = perf_counter()
    def stop_ms(self, key: str) -> float:
        return round((perf_counter() - self.marks[key]) * 1000, 2) if key in self.marks else 0.0

class MetricsStore:
    def __init__(self):
        self.samples = defaultdict(list)
    def add(self, key: str, value: float):
        self.samples[key].append(value)
    def summary(self):
        def p95(vals):
            if not vals:
                return 0.0
            vals = sorted(vals)
            idx = max(0, min(len(vals)-1, int(round(0.95 * (len(vals)-1)))))
            return vals[idx]
        return {
            k: {
                'count': len(v),
                'p50': sorted(v)[len(v)//2] if v else 0.0,
                'p95': p95(v),
                'last': v[-1] if v else 0.0,
            }
            for k, v in self.samples.items()
        }

metrics_store = MetricsStore()
