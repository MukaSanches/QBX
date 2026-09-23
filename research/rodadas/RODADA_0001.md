# Rodada 0001 — Tornar a pesquisa contínua e verificável

**Data:** 23/09/2026  
**Versão de partida:** QBX 3.2.0

## Pergunta da rodada

Antes de deixar uma IA mudar o compressor sozinha, conseguimos criar um processo em que ela seja obrigada a provar a melhoria antes do merge?

## O que encontrei

O QBX 3.2.0 já tinha uma base boa para isso:

- testes automáticos em Linux e Windows;
- benchmark V3;
- benchmark da Universal Archive Bridge;
- verificação de recuperação ARK;
- compilação do aplicativo Windows;
- geração de instalador;
- GitHub Release automática.

O problema principal para uma evolução autônoma era operacional: vários pontos da build ainda tinham `3.2.0` escrito diretamente. Isso faria futuras versões continuarem tentando gerar arquivos com o nome antigo.

## O que esta rodada muda

A rodada 0001 cria a infraestrutura para:

1. usar um pesquisador de IA cloud;
2. guardar memória das hipóteses;
3. testar a versão atual antes do experimento;
4. testar a versão experimental depois;
5. comparar os dois resultados;
6. rejeitar automaticamente mudanças sem ganho mensurável;
7. validar Linux e Windows;
8. fazer merge automático apenas depois dos gates;
9. aumentar o número da versão apenas quando houver mudança aprovada;
10. gerar o instalador e a GitHub Release com o número novo.

## Resultado científico desta rodada

**Não estou declarando que a compressão melhorou nesta rodada.**

A finalidade aqui é tornar as próximas rodadas mais confiáveis. A versão de produto deve continuar 3.2.0 até uma hipótese de melhoria passar por todos os gates.

## Primeiras hipóteses para as próximas rodadas

### H1 — ampliar de forma controlada os candidatos de compressão

Hoje o AGRP mede um conjunto definido de níveis de Zstandard, Deflate e LZMA. Uma futura rodada pode testar níveis adicionais e conservar somente os candidatos que realmente entram na fronteira de Pareto.

### H2 — explorar melhor blocos altamente correlacionados

ARK já usa relações entre blocos para recuperação. Vale testar, separadamente, se alguma representação delta reversível pode também reduzir bytes no caminho primário, sempre mantendo SHA-256 e round-trip perfeito.

### H3 — melhorar agrupamento antes da escolha ARK

O agrupamento atual usa tamanho de bloco como um sinal simples. Uma métrica barata de similaridade pode encontrar parceiros melhores, mas só será aceita se melhorar resiliência/custo sem explodir tempo ou memória.

Essas hipóteses são apenas propostas de teste. Nenhuma delas é tratada como descoberta até existir evidência reproduzível.
