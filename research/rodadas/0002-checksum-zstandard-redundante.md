# Rodada 0002 — checksum Zstandard redundante

## Ideia em linguagem simples

O Zstandard pode colocar um pequeno checksum dentro de cada bloco comprimido. O QBX já possui uma proteção mais forte: cada bloco é identificado e conferido por SHA-256, e os arquivos reconstruídos também são conferidos por SHA-256.

A hipótese desta rodada é simples: retirar apenas o checksum interno redundante do Zstandard para economizar alguns bytes por bloco, mantendo todas as verificações próprias do QBX.

## O que foi alterado

Somente a criação dos candidatos Zstandard do planejador adaptativo foi alterada: `write_checksum=True` passou para `write_checksum=False`.

Não foram removidos:

- SHA-256 dos blocos;
- SHA-256 dos arquivos;
- verificação de descompressão;
- ARK;
- testes;
- benchmarks;
- proteção contra corrupção.

## Linha de base antes do experimento

No último build Windows validado antes desta rodada:

- QBX V3 resiliente: **1.246.219 bytes**;
- ponte universal, QBX otimizado: **792.694 bytes**.

## Estado

**Em validação.**

Ainda não existe alegação de melhoria. O GitHub precisa executar os testes, os dois benchmarks e a build real do Windows. Só haverá nova versão se o resultado ficar menor, sem regressão e com integridade total.
