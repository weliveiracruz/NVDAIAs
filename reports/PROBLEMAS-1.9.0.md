# Relatório de problemas – versão 1.9.0

## Problemas no complemento

Nenhum encontrado pelos testes.

## Mudança de escopo

| Item | Situação |
|---|---|
| GitHub Models | Pedido junto com o Groq, mas **não implementado**: o GitHub desligou o serviço (API, catálogo e playground) em 30/07/2026. A recomendação anterior se baseou em comparativos desatualizados. |

## Problemas nos próprios testes

| ID | Teste | Problema | Correção |
|---|---|---|---|
| T-14 | Interface: "hidden AIs are out of the tab order" | O teste procurava os botões só entre os filhos diretos do painel, mas os botões de cada IA ficam dentro do quadro (StaticBox) do grupo, então a verificação falhava sem haver defeito. | O teste agora percorre os quadros, como o NVDA faz com a tecla Tab, e confere os dois lados: a IA escondida fica fora e a IA escolhida fica dentro. |
| T-15 | Unidades: anexos para cada IA | O teste mandava PDF para todas as IAs da lista; o Groq não lê PDF e recusa antes de enviar, como esperado. | O teste do PDF cobre ChatGPT, Gemini e Claude; o Groq tem testes próprios (aceita texto e imagem, recusa PDF sem enviar nada) e entrou no teste de áudio e vídeo. |
