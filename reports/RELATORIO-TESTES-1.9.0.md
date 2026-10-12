# Relatório de testes – versão 1.9.0

Testes do SDD (`docs/SDD-TESTES.md`), executados por `tests/run_all.py` em 2026-10-12 (execuções 15 e 16 de `reports/execucoes.json`). Os problemas estão em `reports/PROBLEMAS-1.9.0.md`.

## Resultado final

| | Quantidade |
|---|---|
| **Testes existentes** | **645** (eram 614 na 1.8.0) |
| **Aprovados** | **645** |
| **Falharam** | **0** |
| **Problemas encontrados e corrigidos** | **2**, ambos nos próprios testes (T-14, T-15), achados rodando as suítes uma a uma antes da execução completa |
| **Execuções completas nesta versão** | **2** (16 no total, desde a 1.4.0) |
| **Problemas no complemento** | **0** |

## Testes novos (31)

| Suíte | Novos | O que verificam |
|---|---|---|
| Unidades (×3 versões do Python) | 5 cada | Groq: resposta, histórico, cabeçalho e modelo padrão; endereços HTTPS e página do token; lista só com modelos de chat ativos; texto e imagem aceitos, PDF recusado sem enviar; erros de token, limite diário e modelo |
| Interface | 15 | Caixa "IA para conectar ou configurar" com as quatro IAs; só a IA escolhida aparece; rótulo do token muda; troca anunciada; IAs escondidas fora da tabulação; testar conexão, atualizar modelos e salvar o token do Groq; tela Conectar conta com as instruções do Groq; pergunta respondida pelo Groq; PDF recusado com mensagem clara |
| Tradução | 1 | Caixa e nome do Groq em português |

As suítes de segurança (endereços HTTPS, tempo limite, token fora do log) e de acessibilidade (nomes, atalhos únicos, nomes únicos nos botões das configurações) passaram a cobrir o Groq e a nova caixa automaticamente.

## Execuções

| Nº | Nesta versão | O que mudou antes | Testes | Aprovados | Falharam |
|---|---|---|---|---|---|
| 15 | 1 | Groq, caixa da IA a configurar, correções T-14 e T-15 | 645 | 645 | 0 |
| 16 | 2 | Documentação | 645 | 645 | 0 |

O pacote 1.9.0 também foi carregado com os módulos do Python que o NVDA pode não trazer bloqueados: carregou sem erros.

## Fora do alcance dos testes automáticos

A API real do Groq com uma chave de verdade (o servidor de teste imita o formato publicado), a aparência no Windows e a leitura real pelo NVDA.
