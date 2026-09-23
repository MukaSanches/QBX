# Laboratório Autônomo do QBX

Este documento explica, sem jargão desnecessário, como o ciclo automático funciona.

## Em uma frase

O GitHub acorda um pesquisador de IA na nuvem, ele tenta uma melhoria, o próprio GitHub testa a ideia e só permite uma nova versão quando os testes comprovam que o produto continua íntegro e houve ganho mensurável.

## Ciclo

```text
versão atual
   ↓
pesquisador cloud
   ↓
uma hipótese
   ↓
alteração experimental
   ↓
testes de integridade
   ↓
benchmarks
   ↓
comparação com a versão anterior
   ↓
não melhorou ──> registra resultado e encerra a rodada
   ↓
melhorou
   ↓
aumenta versão
   ↓
branch + Pull Request
   ↓
CI Linux/Windows
   ↓
build completo do Windows
   ↓
merge automático
   ↓
novo instalador + nova GitHub Release
   ↓
próxima rodada
```

## Frequência

A automação é programada para iniciar uma nova rodada todos os dias e também pode ser iniciada manualmente.

Ela não fica consumindo IA 24 horas por dia. Ela "acorda", trabalha em uma rodada, encerra e volta no próximo horário. Isso reduz custo e evita processos presos.

## O que impede uma alteração ruim de entrar

A IA não recebe permissão lógica para decidir sozinha que venceu.

Depois do trabalho dela, scripts independentes verificam:

- testes Python;
- round-trip sem perda;
- SHA-256 e recuperação ARK;
- benchmark V3;
- benchmark da Universal Archive Bridge;
- comparação de tamanho contra a linha de base da mesma máquina;
- CI em Linux e Windows;
- compilação do programa Windows;
- autoteste da interface;
- abertura real da interface;
- geração do instalador.

Se qualquer gate falhar, a mudança não é mesclada automaticamente.

## Nova versão

O número só aumenta depois de uma alteração de produto aprovada.

Exemplo:

```text
3.2.0
  ↓ melhoria comprovada
3.2.1
  ↓ melhoria comprovada
3.2.2
```

Uma rodada sem ganho não vira uma versão falsa.

## Instalador

Depois do merge aprovado, o workflow de Windows lê o arquivo `VERSION` e gera automaticamente:

- `QBX-Setup-X.Y.Z.exe`;
- `QBX-Portable-X.Y.Z.zip`;
- `SHA256SUMS.txt`;
- resultados dos benchmarks;
- GitHub Release correspondente.

## IA usada

O laboratório foi preparado para o Gemini CLI oficial executado dentro do GitHub Actions. A IA roda na nuvem; nada precisa ficar rodando no notebook do usuário.

O acesso gratuito depende das cotas disponibilizadas pelo provedor. Quando a cota acabar, a rodada falha sem alterar a main e poderá tentar novamente na próxima execução.

## Uma configuração manual necessária

O GitHub precisa receber uma chave chamada `GEMINI_API_KEY` como Secret de Actions. A chave não deve ser colocada no código nem em arquivos do repositório.

Sem essa chave, a automação não toca no produto. Ela apenas informa que a configuração está pendente.
