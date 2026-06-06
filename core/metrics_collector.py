import os
import json
from collections import deque
from typing import Dict, List, Optional, Tuple

CYCLE_WINDOW_SIZE = 10
METRICS_FILE = "metrics_data.json"

class MetricsCollector:
    def __init__(self, metrics_file: str = METRICS_FILE):
        self.metrics_file = metrics_file
        self.failure_rates: deque = deque(maxlen=CYCLE_WINDOW_SIZE)
        self.novelty_scores: deque = deque(maxlen=CYCLE_WINDOW_SIZE)
        self.all_capability_types: set = set()
        self.cycle_data: List[Dict] = []
        self._load_metrics()

    def _load_metrics(self) -> None:
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, "r") as f:
                    data = json.load(f)
                    self.failure_rates = deque(data.get("failure_rates", []), maxlen=CYCLE_WINDOW_SIZE)
                    self.novelty_scores = deque(data.get("novelty_scores", []), maxlen=CYCLE_WINDOW_SIZE)
                    self.all_capability_types = set(data.get("all_capability_types", []))
                    self.cycle_data = data.get("cycle_data", [])
            except (json.JSONDecodeError, IOError):
                pass

    def _save_metrics(self) -> None:
        data = {
            "failure_rates": list(self.failure_rates),
            "novelty_scores": list(self.novelty_scores),
            "all_capability_types": list(self.all_capability_types),
            "cycle_data": self.cycle_data[-CYCLE_WINDOW_SIZE:]
        }
        try:
            with open(self.metrics_file, "w") as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass

    def record_cycle(self, failed_goals: int, total_goals: int, new_capability_types: List[str]) -> None:
        if total_goals == 0:
            failure_rate = 0.0
        else:
            failure_rate = failed_goals / total_goals
        self.failure_rates.append(failure_rate)

        if not new_capability_types:
            novelty_score = 0.0
        else:
            new_types = set(new_capability_types)
            previously_seen = len(self.all_capability_types)
            self.all_capability_types.update(new_types)
            if previously_seen == 0:
                novelty_score = 1.0 if new_types else 0.0
            else:
                novelty_score = len(new_types - self.all_capability_types) / len(new_types) if new_types else 0.0
        self.novelty_scores.append(novelty_score)

        cycle_entry = {
            "failure_rate": failure_rate,
            "novelty_score": novelty_score,
            "new_capability_types": list(new_capability_types)
        }
        self.cycle_data.append(cycle_entry)
        self._save_metrics()

    def get_average_failure_rate(self, window: int = CYCLE_WINDOW_SIZE) -> float:
        rates = list(self.failure_rates)[-window:]
        if not rates:
            return 0.0
        return sum(rates) / len(rates)

    def get_average_novelty_score(self, window: int = CYCLE_WINDOW_SIZE) -> float:
        scores = list(self.novelty_scores)[-window:]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def get_improvement_percentage(self) -> Optional[float]:
        if len(self.failure_rates) < 2:
            return None
        current_avg = self.get_average_failure_rate(window=min(5, len(self.failure_rates)))
        previous_avg = self.get_average_failure_rate(window=min(5, len(self.failure_rates) - 1))
        if previous_avg == 0:
            return 0.0 if current_avg == 0 else -100.0
        improvement = ((previous_avg - current_avg) / previous_avg) * 100
        return round(improvement, 2)

    def get_summary(self) -> Dict:
        return {
            "average_failure_rate": self.get_average_failure_rate(),
            "average_novelty_score": self.get_average_novelty_score(),
            "improvement_percentage": self.get_improvement_percentage(),
            "total_cycles_recorded": len(self.cycle_data),
            "total_capability_types": len(self.all_capability_types)
        }

    def reset(self) -> None:
        self.failure_rates.clear()
        self.novelty_scores.clear()
        self.all_capability_types.clear()
        self.cycle_data.clear()
        if os.path.exists(self.metrics_file):
            os.remove(self.metrics_file)