"""Track OpenAI API token usage and estimated cost."""

from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List

# Approximate pricing per 1M tokens (USD) — gpt-4o-mini
PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    "whisper-1": {"input": 0.006, "output": 0.0},  # per minute approx
}


@dataclass
class TokenUsage:
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_estimate: float


@dataclass
class TokenTracker:
    _lock: Lock = field(default_factory=Lock)
    _records: List[TokenUsage] = field(default_factory=list)
    _totals: Dict[str, int] = field(
        default_factory=lambda: {"prompt": 0, "completion": 0, "cost": 0.0}
    )

    def record(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        pricing = PRICING.get(model, {"input": 0.15, "output": 0.60})
        cost = (
            prompt_tokens * pricing["input"] / 1_000_000
            + completion_tokens * pricing["output"] / 1_000_000
        )
        usage = TokenUsage(model, prompt_tokens, completion_tokens, cost)
        with self._lock:
            self._records.append(usage)
            self._totals["prompt"] += prompt_tokens
            self._totals["completion"] += completion_tokens
            self._totals["cost"] += cost
        return cost

    def get_summary(self) -> dict:
        with self._lock:
            by_model: Dict[str, dict] = {}
            for r in self._records:
                if r.model not in by_model:
                    by_model[r.model] = {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "cost_estimate": 0.0,
                        "calls": 0,
                    }
                by_model[r.model]["prompt_tokens"] += r.prompt_tokens
                by_model[r.model]["completion_tokens"] += r.completion_tokens
                by_model[r.model]["cost_estimate"] += r.cost_estimate
                by_model[r.model]["calls"] += 1
            return {
                "total_prompt_tokens": self._totals["prompt"],
                "total_completion_tokens": self._totals["completion"],
                "total_cost_usd": round(self._totals["cost"], 6),
                "by_model": by_model,
                "total_calls": len(self._records),
            }


token_tracker = TokenTracker()
