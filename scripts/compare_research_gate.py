from __future__ import annotations

import argparse
import json
from pathlib import Path


MIN_SAVING_BYTES = 32


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def value(report: dict, *keys):
    current = report
    for key in keys:
        current = current[key]
    return current


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-v3", required=True)
    parser.add_argument("--candidate-v3", required=True)
    parser.add_argument("--baseline-bridge", required=True)
    parser.add_argument("--candidate-bridge", required=True)
    parser.add_argument("--report", default="research/GATE_ATUAL.md")
    args = parser.parse_args()

    base_v3 = load(args.baseline_v3)
    cand_v3 = load(args.candidate_v3)
    base_bridge = load(args.baseline_bridge)
    cand_bridge = load(args.candidate_bridge)

    if not base_v3.get("gate") or not base_bridge.get("gate"):
        raise SystemExit("A linha de base falhou. A rodada não pode ser julgada com segurança.")
    if not cand_v3.get("gate") or not cand_bridge.get("gate"):
        raise SystemExit("A versão experimental falhou nos gates de integridade.")

    base_v3_bytes = int(value(base_v3, "profiles", "qbx_v3_resilient", "archive_bytes"))
    cand_v3_bytes = int(value(cand_v3, "profiles", "qbx_v3_resilient", "archive_bytes"))
    base_bridge_bytes = int(value(base_bridge, "optimized_qbx", "archive_bytes"))
    cand_bridge_bytes = int(value(cand_bridge, "optimized_qbx", "archive_bytes"))

    v3_saved = base_v3_bytes - cand_v3_bytes
    bridge_saved = base_bridge_bytes - cand_bridge_bytes

    no_regression = cand_v3_bytes <= base_v3_bytes and cand_bridge_bytes <= base_bridge_bytes
    measurable_gain = max(v3_saved, bridge_saved) >= MIN_SAVING_BYTES
    accepted = no_regression and measurable_gain

    report = f"""# Gate automático da rodada

## Comparação de tamanho

| Teste | Antes | Depois | Diferença |
|---|---:|---:|---:|
| QBX V3 resiliente | {base_v3_bytes} bytes | {cand_v3_bytes} bytes | {v3_saved:+d} bytes economizados |
| Ponte universal -> QBX | {base_bridge_bytes} bytes | {cand_bridge_bytes} bytes | {bridge_saved:+d} bytes economizados |

## Integridade

- Gate V3 experimental: {'PASSOU' if cand_v3.get('gate') else 'FALHOU'}
- Gate da ponte universal: {'PASSOU' if cand_bridge.get('gate') else 'FALHOU'}
- Regressão de tamanho nos dois testes: {'NÃO' if no_regression else 'SIM'}
- Ganho mínimo exigido: {MIN_SAVING_BYTES} bytes em pelo menos um benchmark

## Decisão

**{'APROVADA' if accepted else 'REJEITADA'}**

{'A alteração pode seguir para CI e build do Windows.' if accepted else 'A alteração não será mesclada automaticamente. Uma rodada futura pode tentar outra hipótese.'}
"""
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(report)

    if not accepted:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
