# Relatório de testes – versão 1.7.0

Testes do SDD (`docs/SDD-TESTES.md`), executados por `tests/run_all.py` em 2026-10-04 (execuções 10 e 11 de `reports/execucoes.json`). Os problemas estão em `reports/PROBLEMAS-1.7.0.md`.

## Resultado final

| | Quantidade |
|---|---|
| **Testes existentes** | **591** (eram 423 na 1.6.0) |
| **Aprovados** | **591** |
| **Falharam** | **0** |
| **Problemas encontrados e corrigidos** | **9** (4 no complemento: P-10 a P-13; 5 nos testes: T-08 a T-12) |
| **Execuções completas nesta versão** | **2** (11 no total, desde a 1.4.0). As falhas foram encontradas rodando as suítes uma a uma durante o desenvolvimento, antes das execuções completas. |

## Testes novos (168)

| Suíte | Novos | O que verificam |
|---|---|---|
| Unidades (×3 versões do Python) | 30 cada | Entrada completa contra o servidor de teste; reaproveitamento do client_id e do host id; PKCE; acesso negado; resposta com outro state ignorada; cancelamento; navegador que não abre; nonce e assinatura errados; escopo do plano obrigatório; sessão criptografada; token de identidade (emissor, destinatário, validade, nonce, assinatura, alg none e HS256); chave RSA fraca; descoberta apontando para outro servidor; renovação, rotação e refresh token reutilizado; saída com revogação; perguntas, histórico, anexos e recusa de áudio; modelos do plano; 401 com nova tentativa; 8 erros do plano; eventos do fluxo (stream); servidor local só em 127.0.0.1; gravação simultânea de credenciais (P-10) |
| Interface | 42 | Botão Continuar com o ChatGPT (só para o ChatGPT, logo depois da caixa IA), janela de espera, navegador em auth.openai.com, aviso de primeiro uso uma vez só, modelos do plano, linha de situação, pergunta pelo plano, Gerenciar uso, limite de uso com Gerenciar uso como ação principal, segunda entrada, cancelamento, grupo do ChatGPT nas configurações (situação, botões, opção do plano, testar conexão, modelos guardados à parte), sair do ChatGPT com revogação |
| Tradução | 2 | Botão, instruções e janela de espera em português; atalhos únicos na janela de espera; mensagens de erro novas sem marcadores |
| Acessibilidade | 18 | ACE-20 e as verificações gerais (nome, atalhos, título, foco, anúncios, linha de situação, ordem de tabulação) aplicadas à tela de conexão, à janela de espera e à janela de conversa com o plano em uso |
| Segurança | 16 | SEG-22 a SEG-26: endereços da OpenAI em HTTPS, único HTTP é o 127.0.0.1/callback, sem segredo de cliente, PKCE com state e nonce aleatórios, recusa de resposta forjada, log silencioso, tempo limite, tokens criptografados e fora do log, fala e nvda.ini, tokens de identidade forjados recusados, token do plano não segue redirecionamento, revogação ao sair |

## Execuções

| Nº | Nesta versão | O que mudou antes | Testes | Aprovados | Falharam |
|---|---|---|---|---|---|
| 10 | 1 | Continuar com o ChatGPT, correções P-10 a P-12 e T-08 a T-12 | 591 | 591 | 0 |
| 11 | 2 | Endereços da descoberta da OpenAI aceitos também em outros hosts openai.com com HTTPS (antes só o mesmo host), com teste novo dentro de uma unidade existente | 591 | 591 | 0 |

## Fora do alcance dos testes automáticos

A entrada real com uma conta do ChatGPT, a API real do plano, a criptografia DPAPI e a fala do NVDA. O servidor de teste imita o protocolo publicado pela OpenAI (developers.openai.com/siwc/token-sharing-open-source), que ainda está em prévia e pode mudar. Siga o passo 12 de `docs/TESTES.md` com uma conta Plus ou Pro antes de criar a tag.
