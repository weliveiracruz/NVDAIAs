# Relatório de problemas – versão 1.7.0

Problemas encontrados ao rodar as suítes durante o desenvolvimento do "Continuar com o ChatGPT", antes das execuções completas nº 10 e 11 de `tests/run_all.py`. Todos foram corrigidos; as duas execuções completas terminaram com 0 falhas.

## Problemas no complemento

| ID | Teste | Gravidade | Problema | Causa | Correção |
|---|---|---|---|---|---|
| P-10 | Interface: "no errors logged" (falhava às vezes); unidade nova `test_store_safe_with_threads` | Média | Duas gravações simultâneas no arquivo de credenciais podiam falhar com erro inesperado e perder uma gravação. | `CredentialStore` usava sempre o mesmo arquivo temporário e não tinha trava. Com o ChatGPT, a entrada e a renovação do token gravam em segundo plano, ao mesmo tempo que a interface. | Trava única para todas as instâncias do processo e arquivo temporário com o número da tarefa. O teste novo grava de 6 tarefas ao mesmo tempo e falha com o código antigo. |
| P-11 | Interface: "cancel stops the sign-in and is announced" | Baixa | Ao terminar, uma janela de espera do "Continuar com o ChatGPT" apagava a referência de outra janela de espera que tivesse aberto depois. | `SignInDialog._close` zerava `_running` sem conferir de quem era. | Só zera quando a janela que fecha é a registrada. |
| P-13 | Revisão de código (sem falha de teste) | Média | A entrada falharia se a OpenAI publicasse as chaves públicas ou a revogação em outro host dela (por exemplo, keys.openai.com). | A descoberta só aceitava endereços no mesmo host do auth.openai.com. | Aceita o mesmo host ou HTTPS em host openai.com; outros hosts continuam recusados (teste de unidade com 5 casos). |
| P-12 | Interface: "cancel stops the sign-in and is announced" | Baixa | Cancelar a entrada podia não valer se o navegador voltasse no mesmo instante. | A espera conferia a resposta do navegador antes de conferir o cancelamento. | O cancelamento é conferido primeiro, a cada 0,2 segundo. |

## Problemas nos próprios testes

| ID | Teste | Problema | Correção |
|---|---|---|---|
| T-08 | Interface: "browser opened on auth.openai.com authorize" | Conferia o endereço aberto antes de a tarefa em segundo plano abrir o navegador. | A verificação passou para depois da espera. |
| T-09 | Interface: "no errors logged" | A mensagem de falha com os detalhes do erro quebrava a formatação do relatório. | Detalhes convertidos para texto; o stub do log agora guarda o rastreamento do erro, que ajudou a achar o P-10. |
| T-10 | Acessibilidade: ACE-06, ACE-10, ACE-20 | A sessão do ChatGPT tinha sido criada antes de o teste trocar o endereço da OpenAI pelo servidor de teste, e o navegador simulado tentou o endereço real. | O teste recria a sessão depois de trocar o endereço. |
| T-11 | Acessibilidade: "ACE-07 focus on the explanation while waiting" | O navegador simulado respondia tão rápido que a janela de espera fechava antes da conferência do foco. | Navegador simulado com 1,5 segundo de demora nessa verificação. |
| T-12 | Segurança: SEG-22 | O teste aceitava só dois lugares que abrem o navegador; a 1.7.0 tem um terceiro (entrada e uso do ChatGPT), esperado. | O teste agora lista os três arquivos permitidos pelo nome e confere o endereço de uso em HTTPS. |

## Pendências esperadas

| Teste | Situação |
|---|---|
| ACE-16 tradução completa | Falhou na primeira rodada porque as 36 frases novas ainda não estavam no `nvda.po`. Traduzidas antes da execução completa. |
