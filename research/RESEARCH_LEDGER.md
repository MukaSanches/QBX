# Diário de pesquisa autônoma do QBX

Este arquivo é a memória simples do laboratório. Antes de iniciar uma ideia, o agente deve conferir o que já foi tentado.

| Rodada | Data | Hipótese / objetivo | Resultado | Versão gerada |
|---|---|---|---|---|
| 0001 | 2026-09-23 | Preparar o QBX para pesquisa cloud contínua, gates independentes, merge automático e instalador versionado | Infraestrutura criada; nenhuma alegação de ganho de compressão nesta rodada | Nenhuma: permanece 3.2.0 até uma melhoria de produto passar nos gates |
| 0002 | 2026-09-23 | Remover o checksum interno do Zstandard quando o bloco já é protegido pelo SHA-256 do QBX | Rejeitada: todos os testes passaram, mas o ganho foi só 20 bytes no V3 e 6 bytes na ponte, abaixo do mínimo de 32 bytes | Nenhuma: permanece 3.2.0 |
| 0003 | 2026-09-23 | Remover checksum e tamanho interno redundantes dos frames Zstandard, usando os metadados e SHA-256 do próprio QBX | Em validação | Nenhuma enquanto os gates não terminarem |

## Regra

Uma hipótese rejeitada não deve ser simplesmente repetida. Para tentar de novo, o relatório precisa explicar o que mudou na hipótese, no algoritmo, no conjunto de dados ou na evidência.
