from dataclasses import dataclass

@dataclass(frozen=True)
class Strategy:
    name: str
    size: int
    decode_ms: float
    memory_mb: float

def objective(s: Strategy, size_weight=1.0, time_weight=0.0, memory_weight=0.0):
    return (
        size_weight*s.size +
        time_weight*s.decode_ms +
        memory_weight*s.memory_mb
    )

def classical_plan(groups, max_decode_ms=None, max_memory_mb=None):
    """
    Baseline solver. Each group contains alternative representations.
    This becomes the reference against which QUBO/QAOA is measured.
    """
    result=[]
    for group in groups:
        valid=[
            s for s in group
            if (max_decode_ms is None or s.decode_ms <= max_decode_ms)
            and (max_memory_mb is None or s.memory_mb <= max_memory_mb)
        ]
        if not valid:
            raise ValueError("No feasible strategy")
        result.append(min(valid,key=objective))
    return result
