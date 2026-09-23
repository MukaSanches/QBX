"""
QBX Quantum Archive Planner.

Maps representation-selection into a QUBO-style objective.
One-hot constraint:
    exactly one representation must be selected per block group.

This module intentionally keeps the mathematical model independent
from any particular quantum provider.
"""

def build_qubo(cost_groups, penalty=None):
    if penalty is None:
        penalty = max(
            (abs(c) for g in cost_groups for c in g),
            default=1.0
        ) * 10 + 1

    Q={}
    names=[]
    for g, costs in enumerate(cost_groups):
        vars=[]
        for j,cost in enumerate(costs):
            v=f"x_{g}_{j}"
            vars.append(v)
            names.append(v)
            Q[(v,v)] = Q.get((v,v),0.0) + float(cost) - penalty

        for i in range(len(vars)):
            for j in range(i+1,len(vars)):
                a,b=vars[i],vars[j]
                Q[(a,b)] = Q.get((a,b),0.0) + 2*penalty

    constant=penalty*len(cost_groups)
    return Q, constant, names
