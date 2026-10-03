# Relatório de testes – versão 1.4.0

Testes definidos no SDD (`docs/SDD-TESTES.md`) e executados por `tests/run_all.py` em 2026-10-03. Os dados brutos de cada execução estão em `reports/execucoes.json`, e a lista de problemas em `reports/PROBLEMAS-1.4.0.md`.

## Resultado final

| | Quantidade |
|---|---|
| **Testes existentes** | **375** |
| **Aprovados** | **375** |
| **Falharam** | **0** |
| **Testes que falharam em alguma execução e foram corrigidos** | **11** |
| **Execuções** | **5** |

Dos 11 testes corrigidos, 8 falharam por problemas no complemento (P-01 a P-08). Os outros 3 falharam por erros nos próprios testes (T-01 e T-02). Os erros T-03 e T-04 não falhavam: eram testes fracos, que passavam sem detectar os problemas P-04 e P-05. Depois de reforçados, passaram a falhar até a correção.

## Testes por tipo

| Tipo | Suítes | Testes |
|---|---|---|
| Funcionais (FUN) | unidades em Python 3.11, 3.12 e 3.13 (3 × 39), interface (141), pacote (2) | 260 |
| Acessibilidade (ACE) | tema (27), tradução (7), acessibilidade (46) | 80 |
| Vulnerabilidade (SEG) | segurança (35) | 35 |
| **Total** | | **375** |

As unidades em Python também incluem testes de segurança de baixo nível: arquivos de histórico, anexos recusados e chave ausente.

## Execuções

| Nº | O que mudou antes | Testes | Aprovados | Falharam | Corrigidos em relação à anterior |
|---|---|---|---|---|---|
| 1 | Primeira rodada com as suítes novas | 350 | 343 | 7 | – |
| 2 | Correção dos próprios testes (T-01 a T-04), sem mexer no complemento | 374 | 366 | 8 | 2 |
| 3 | Correções P-01 a P-08 no complemento | 375 | 374 | 1 | 6 |
| 4 | Comentário de tradução que faltava (fim de P-02) | 375 | 375 | 0 | 1 |
| 5 | Verificação final depois da documentação, do `CLAUDE.md` e da automação do GitHub | 375 | 375 | 0 | 0 |

O total de testes variou entre as execuções por quatro motivos:
* Na execução 1, a suíte de acessibilidade parou no meio (T-02) e só contou 22 dos 46 testes.
* Na execução 3, a suíte de segurança ganhou 1 teste: com o limite de tamanho criado em P-06, passou a rodar também a verificação de que uma resposta acima dele é recusada.
* Na execução 3, o teste "todo botão com tecla de atalho" das Configurações foi substituído por "todo botão com nome único" (P-03).
* O contador de "corrigidos" do executor só compara testes com o mesmo nome. Por isso a soma dele (2 + 6 + 1 = 9) é menor que os 11 corrigidos: o teste que travou a suíte e o teste renomeado das Configurações não entram nessa soma.

## Testes que falharam e foram corrigidos

| Teste | Falhou nas execuções | Causa | Corrigido na execução |
|---|---|---|---|
| Tema: ordem de tabulação com tema | 1 | T-01 (teste desatualizado) | 2 |
| Tema: ordem de tabulação sem tema | 1 | T-01 (teste desatualizado) | 2 |
| Acessibilidade: suíte até o fim | 1 | T-02 (erro no teste) | 2 |
| Tradução: atalhos únicos na janela de conversa | 1, 2 | P-01 | 3 |
| ACE-16 interface toda traduzida | 2 | P-01 | 3 |
| ACE-02 botões das Configurações | 1, 2 | P-03 | 3 |
| SEG-09 bomba zip | 2 | P-04 (descoberto depois de T-03) | 3 |
| SEG-19 redirecionamento com a chave | 2 | P-05 (descoberto depois de T-04) | 3 |
| SEG-18 limite de tamanho da resposta | 1, 2 | P-06 | 3 |
| SEG-13 análise estática (bandit) | 1, 2 | P-07 e P-08 | 3 |
| ACE-15 comentários para tradutores | 2, 3 | P-02 | 4 |

## Problemas corrigidos no complemento

| ID | Gravidade | Resumo |
|---|---|---|
| P-01 | Média | Textos do menu de ações sem tradução, com o atalho Alt+I repetido |
| P-02 | Baixa | 18 textos sem comentário para tradutores |
| P-03 | Média | 12 botões das Configurações com nomes repetidos e sem atalho |
| P-04 | **Alta** | Bomba zip podia esgotar a memória do NVDA |
| P-05 | **Alta** | Redirecionamento reenviava a chave de API para outro endereço |
| P-06 | Média | Resposta sem limite de tamanho |
| P-07 | Média | Conexão aceitava qualquer esquema de endereço |
| P-08 | Média | XML de documentos sem bloqueio de DTD e entidades |

## O que os testes automáticos não cobrem

Estes pontos continuam no roteiro manual de `docs/TESTES.md`:
* fala real do NVDA;
* criptografia DPAPI no Windows;
* menus nativos do Windows abertos com Enter e com a tecla Aplicações;
* chamadas reais às três IAs com tokens de verdade.
