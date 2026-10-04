# Relatório de testes – versão 1.5.0

Testes do SDD (`docs/SDD-TESTES.md`), executados por `tests/run_all.py` em 2026-10-04. Os dados brutos estão em `reports/execucoes.json` (execuções 6 e 7), e os problemas em `reports/PROBLEMAS-1.5.0.md`.

## Resultado final

| | Quantidade |
|---|---|
| **Testes existentes** | **408** (eram 375 na 1.4.0) |
| **Aprovados** | **408** |
| **Falharam** | **0** |
| **Testes que falharam em alguma execução e foram corrigidos** | **1** (T-05, erro no próprio teste) |
| **Execuções nesta versão** | **2** (7 no total, desde a 1.4.0) |
| **Problema do complemento corrigido** | P-09, tokens e histórico apagados na atualização (relatado pelo usuário) |

## Testes novos (33)

| Suíte | Novos | O que verificam |
|---|---|---|
| Atualização (`test_update.py`) | 17 | Desinstalação de verdade apaga tudo; atualização detectada pela pasta ou pelo estado do NVDA mantém tokens e histórico; atualização a partir da 1.4.0 é restaurada; restauração não sobrescreve dados mais novos; falhas não bloqueiam a instalação |
| Interface (`test_gui.py`) | 13 | Ramo "Conversa atual": rótulo com contagem, expandido por padrão, Enter e setas reais recolhem e expandem, reabre quando chega resposta, sem ações no próprio ramo, ordem dos ramos com e sem histórico |
| Acessibilidade (`test_accessibility.py`) | 3 | ACE-19: ramos dizem quantos itens têm; Enter expande e recolhe o ramo |

## Execuções

| Nº | Nesta versão | O que mudou antes | Testes | Aprovados | Falharam | Corrigidos |
|---|---|---|---|---|---|---|
| 6 | 1 | Correção P-09, ramo Conversa atual, suíte de atualização | 408 | 407 | 1 | – |
| 7 | 2 | Correção do teste T-05 | 408 | 408 | 0 | 1 |

## Fora do alcance dos testes automáticos

* A atualização real dentro do NVDA no Windows: instalar a 1.5.0 por cima da 1.4.0 e reiniciar. Os testes reproduzem a sequência do código do NVDA, mas vale conferir uma vez seguindo o roteiro de `docs/TESTES.md`.
