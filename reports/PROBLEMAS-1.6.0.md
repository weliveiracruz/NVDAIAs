# Relatório de problemas – versão 1.6.0

## Problemas no complemento

Nenhum. O botão Enviar feedback passou em todos os testes funcionais, de acessibilidade e de segurança já na primeira execução.

## Problemas nos próprios testes

| ID | Teste | Problema | Correção |
|---|---|---|---|
| T-06 | Interface: estilo da caixa de mensagem de feedback | O teste exigia o sinalizador `wx.OK_DEFAULT`, mas no wxPython ele vale 0 (OK já é o botão padrão), então a verificação sempre falhava. | O teste agora confere que existem os botões OK e Cancelar e que Cancelar **não** é o padrão. |
| T-07 | Interface: foco depois de excluir mensagem e depois de cancelar o feedback | As duas verificações terminavam em `or True` e passavam sempre, sem verificar nada. A primeira vinha da versão 1.4.0. | Removido o `or True`. As duas verificações agora conferem o foco de verdade e passam. |
