# Relatório de testes – versão 1.6.0

Testes do SDD (`docs/SDD-TESTES.md`), executados por `tests/run_all.py` em 2026-10-04 (execuções 8 e 9 de `reports/execucoes.json`). Os problemas estão em `reports/PROBLEMAS-1.6.0.md`.

## Resultado final

| | Quantidade |
|---|---|
| **Testes existentes** | **423** (eram 408 na 1.5.0) |
| **Aprovados** | **423** |
| **Falharam** | **0** |
| **Testes que falharam em alguma execução e foram corrigidos** | **1** (T-06, erro no próprio teste; renomeado na correção, por isso o executor mostra 0 corrigidos) |
| **Verificações que nunca falhavam e passaram a verificar de verdade** | **2** (T-07) |
| **Execuções nesta versão** | **2** (9 no total, desde a 1.4.0) |
| **Problemas no complemento** | **0** |

## Testes novos (15)

| Suíte | Novos | O que verificam |
|---|---|---|
| Interface | 12 | Posição do botão (entre Configurações e Fechar), rótulo com Alt+D, confirmação antes de abrir, Cancelar não abre nada, foco volta ao botão, Dar feedback abre o formulário, anúncio, falha do navegador mostra o endereço, comando de Definir comandos, caixa de mensagem padrão com botões renomeados |
| Segurança | 3 | SEG-22: formulário em HTTPS no docs.google.com; navegador só abre endereços fixos; páginas de token em HTTPS |

As verificações de acessibilidade da janela de conversa (nome acessível, atalhos únicos em inglês e em português, ordem de tabulação) passaram a cobrir o botão novo automaticamente.

## Execuções

| Nº | Nesta versão | O que mudou antes | Testes | Aprovados | Falharam |
|---|---|---|---|---|---|
| 8 | 1 | Botão Enviar feedback | 423 | 422 | 1 |
| 9 | 2 | Correções nos testes T-06 e T-07 | 423 | 423 | 0 |

## Fora do alcance dos testes automáticos

A caixa de mensagem nativa do Windows e a abertura real do navegador. Os testes verificam o que é pedido ao Windows (botões, textos, endereço), mas vale abrir uma vez no NVDA.
