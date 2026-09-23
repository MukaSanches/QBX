# Rodada 0002 — checksum Zstandard redundante

## Ideia

O Zstandard coloca um pequeno checksum dentro de cada frame comprimido. O QBX já protege os blocos e os arquivos com SHA-256. A hipótese era retirar essa verificação interna redundante para economizar espaço sem diminuir a proteção real do QBX.

## O que foi testado

Na candidata, apenas o checksum interno do frame Zstandard foi desligado. SHA-256 dos blocos, SHA-256 dos arquivos, ARK, round-trip, testes e benchmarks continuaram ativos.

## Resultado medido no Windows

| Medição | Antes | Candidata | Ganho |
|---|---:|---:|---:|
| QBX V3 resiliente | 1.246.219 bytes | 1.246.199 bytes | 20 bytes |
| Ponte universal → QBX | 792.694 bytes | 792.688 bytes | 6 bytes |

Também foi observado que o QBX V2 adaptativo caiu de 1.238.063 para 1.238.038 bytes, uma economia de 25 bytes.

## Segurança

- CI em Linux com Python 3.10: passou;
- CI em Linux com Python 3.12: passou;
- CI em Windows com Python 3.10: passou;
- CI em Windows com Python 3.12: passou;
- benchmark V3 e recuperação ARK: passou;
- benchmark da ponte universal: passou;
- executáveis Windows: compilados e testados;
- instalador Windows: gerado com sucesso.

## Decisão

**REJEITADA.**

A hipótese era válida e economizou alguns bytes, mas o laboratório exige pelo menos **32 bytes de ganho em um dos benchmarks principais**, sem regressão no outro. O maior ganho relevante foi 20 bytes.

Por isso a alteração técnica não entrou na `main`, não houve merge do código e a versão continua **3.2.0**.

Esse resultado fica registrado para que futuras rodadas não repitam a mesma ideia sem uma razão nova.
