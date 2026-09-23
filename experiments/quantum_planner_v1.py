import itertools
import time

from qbx.quantum.qubo import build_qubo

GROUPS = [
    [100, 55, 48],
    [90, 44, 51],
    [120, 70, 63],
]

NAMES = ["RAW", "ZLIB", "LZMA"]

print("=== QBX QUANTUM ARCHIVE PLANNER ===")

t0 = time.perf_counter()
best = None
best_cost = float("inf")

for selection in itertools.product(range(3), repeat=len(GROUPS)):
    cost = sum(GROUPS[g][s] for g, s in enumerate(selection))
    if cost < best_cost:
        best_cost = cost
        best = selection

classical_time = time.perf_counter() - t0

print("\nEXACT CLASSICAL REFERENCE")
print("Selection:", [NAMES[x] for x in best])
print("Cost:", best_cost)
print("Time:", classical_time)

Q, constant, variables = build_qubo(GROUPS)

print("\nQUBO")
print("Variables:", len(variables))
print("Coefficients:", len(Q))
print("Constant:", constant)

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

n = len(variables)
qc = QuantumCircuit(n, n)
qc.h(range(n))
qc.measure(range(n), range(n))

backend = AerSimulator()

t0 = time.perf_counter()
result = backend.run(qc, shots=4096).result()
quantum_time = time.perf_counter() - t0

counts = result.get_counts()

def decode(bitstring):
    bits = bitstring[::-1]
    selection = []
    valid = True
    index = 0

    for group in GROUPS:
        group_bits = bits[index:index + len(group)]
        chosen = [i for i, bit in enumerate(group_bits) if bit == "1"]

        if len(chosen) != 1:
            valid = False
            break

        selection.append(chosen[0])
        index += len(group)

    if not valid:
        return None

    return tuple(selection)

best_quantum = None
best_quantum_cost = float("inf")
valid_shots = 0

for bits, shots in counts.items():
    selection = decode(bits)
    if selection is None:
        continue

    valid_shots += shots
    cost = sum(GROUPS[g][choice] for g, choice in enumerate(selection))

    if cost < best_quantum_cost:
        best_quantum_cost = cost
        best_quantum = selection

print("\nQUANTUM PIPELINE")
print("Backend:", backend.name)
print("Qubits:", n)
print("Shots:", 4096)
print("Valid shots:", valid_shots)
print("Execution:", quantum_time)

if best_quantum:
    print("Best sampled:", [NAMES[x] for x in best_quantum])
    print("Cost:", best_quantum_cost)
else:
    print("No valid one-hot solution sampled.")

print("\nCOMPARISON")
if best_quantum is not None:
    print("Exact optimum:", best_cost)
    print("Quantum sample:", best_quantum_cost)
    print("Optimal solution discovered:", best_quantum_cost == best_cost)

print("\nIMPORTANT")
print("This establishes QBX classical -> QUBO -> quantum-circuit -> measurement pipeline.")
print("It is NOT evidence of quantum advantage. QAOA/penalty encoding comes next.")
