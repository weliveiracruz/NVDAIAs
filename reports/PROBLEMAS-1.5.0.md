# Relatório de problemas – versão 1.5.0

## Problemas no complemento

| ID | Origem | Gravidade | Problema | Correção |
|---|---|---|---|---|
| P-09 | Relato do usuário | **Alta** | **Tokens e histórico apagados na atualização do complemento.** Ao atualizar, o NVDA remove a versão antiga no reinício e roda o `onUninstall` dela (`addonHandler.Addon.completeRemove`, com `runUninstallTask=True`). As versões 1.0.0 a 1.4.0 apagavam ali, sem distinção, o arquivo de tokens e a pasta do histórico. | `onUninstall` só apaga numa desinstalação de verdade. A atualização é detectada pela pasta `NVDAIAs.pendingInstall` ou pelo estado `PENDING_INSTALL` do NVDA. Para atualizações vindas das versões 1.0.0 a 1.4.0, cujo `onUninstall` antigo ainda vai rodar, o `onInstall` da 1.5.0 copia tokens e histórico para `NVDAIAs-backup`, e a nova versão restaura a cópia ao iniciar, sem sobrescrever nada mais novo, e depois a apaga. |

**Por que os testes não pegaram P-09:** o caso SEG-16 verificava que a desinstalação apaga tudo, mas o SDD não tinha nenhum caso para a atualização, em que o NVDA usa a mesma rotina. Para cobrir isso, foi criada a suíte `tests/test_update.py`, com os casos FUN-15 a FUN-19, que reproduz a sequência real do NVDA, inclusive com o `onUninstall` das versões antigas.

## Problemas nos próprios testes

| ID | Teste | Problema | Correção |
|---|---|---|---|
| T-05 | ACE-05 (Enter no ramo Conversa atual) | O teste mandava Enter sem pôr o foco na árvore: o Enter ia para o campo Pergunta. | O teste põe o foco na árvore antes de mandar o Enter. |

## Situação

O problema P-09 foi corrigido e é verificado pelas 17 verificações da suíte de atualização. O T-05 foi corrigido na execução 2 desta versão.
