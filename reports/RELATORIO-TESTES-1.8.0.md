# Relatório de testes – versão 1.8.0

Testes do SDD (`docs/SDD-TESTES.md`), executados por `tests/run_all.py` em 2026-10-05 (execução 14 de `reports/execucoes.json`). Os problemas estão em `reports/PROBLEMAS-1.8.0.md`.

## Resultado final

| | Quantidade |
|---|---|
| **Testes existentes** | **614** (eram 600 na 1.7.0) |
| **Aprovados** | **614** |
| **Falharam** | **0** |
| **Testes que falharam e foram corrigidos** | **0** |
| **Execuções completas nesta versão** | **1** (14 no total, desde a 1.4.0) |
| **Problemas no complemento** | **0** (3 ajustes de visual feitos antes da execução, vistos nas prévias) |

## Testes novos (14, suíte do tema)

Contraste do título sobre a barra laranja como texto grande; contraste dos chips (texto escuro sobre fundo claro de cada estado), do texto secundário e dos links sobre o cartão; cores válidas; tokens de raio; fonte cai para uma instalada; título com tamanho de texto grande; chip com fundo colorido (conectado e erro); três cartões na janela de conversa, dois deles com título; todo controle com anel de foco sobre um cartão branco; cartões sem sobreposição; rótulos com a cor do cartão; cabeçalho com título na barra e subtítulo na página; dois cartões na tela Conectar conta, com a ordem de tabulação igual.

Os testes de acessibilidade (nomes, atalhos, ordem de tabulação, títulos) e de tradução continuam passando sem mudança, o que mostra que o layout novo não mexeu no que o NVDA lê.

## Execuções

| Nº | Nesta versão | O que mudou antes | Testes | Aprovados | Falharam |
|---|---|---|---|---|---|
| 14 | 1 | Layout moderno e tom de voz | 614 | 614 | 0 |

Depois da execução, o pacote 1.8.0 foi carregado com os módulos do Python que o NVDA pode não trazer bloqueados: carregou sem erros.

## Fora do alcance dos testes automáticos

A aparência no Windows (as prévias são geradas no Linux, então botões e caixas aparecem com o visual do Linux) e a leitura real pelo NVDA. Vale abrir a janela de conversa, a tela Conectar conta e as configurações uma vez no Windows.
