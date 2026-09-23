# Rodada 0003 — reduzir metadados redundantes do Zstandard

## Hipótese

A rodada 0002 mostrou que retirar apenas o checksum interno economizou 20 bytes no benchmark V3, mas não atingiu o mínimo de 32 bytes.

Nesta rodada há uma mudança nova: o frame Zstandard deixa de repetir **duas informações que o QBX já possui**:

1. checksum interno do frame;
2. tamanho original do conteúdo.

O QBX continua armazenando o tamanho original no registro do bloco e continua verificando o conteúdo recuperado com SHA-256.

## Por que pode funcionar

Na linguagem simples: é como retirar duas etiquetas repetidas de cada pacote, mantendo a etiqueta principal e a conferência forte do armazém.

O descompactador do QBX já informa ao Zstandard qual é o tamanho esperado, então o tamanho não precisa estar repetido dentro do frame.

## Linha de base

- QBX V3 resiliente: **1.246.219 bytes**;
- ponte universal → QBX: **792.694 bytes**.

Para ser aceita, a candidata precisa manter os dois resultados sem aumento e economizar pelo menos **32 bytes em um deles**, além de passar por integridade, CI e build real do Windows.

## Estado

**Em validação.**


## Resultado final

| Medição | Antes | QBX 3.2.1 candidata | Ganho |
|---|---:|---:|---:|
| QBX V3 resiliente | 1.246.219 bytes | 1.246.179 bytes | **40 bytes** |
| Ponte universal → QBX | 792.694 bytes | 792.682 bytes | **12 bytes** |
| QBX V2 adaptativo | 1.238.063 bytes | 1.238.017 bytes | **46 bytes** |

## Validação

- Linux + Python 3.10: passou;
- Linux + Python 3.12: passou;
- Windows + Python 3.10: passou;
- Windows + Python 3.12: passou;
- benchmark QBX V3 e recuperação ARK: passou;
- benchmark da ponte universal: passou;
- executável de linha de comando: passou;
- aplicativo gráfico: passou;
- abertura real da interface: passou;
- instalador Windows: gerado com sucesso.

## Decisão

**APROVADA para QBX 3.2.1.**

O ganho é pequeno em termos absolutos, mas é real, reproduzível e supera o mínimo científico de 32 bytes no benchmark V3. Nenhum byte do conteúdo original foi perdido, e os mecanismos de integridade do QBX continuam ativos.
