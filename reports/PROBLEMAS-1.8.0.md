# Relatório de problemas – versão 1.8.0

## Problemas no complemento

Nenhum encontrado pelos testes. O layout moderno passou em todas as suítes na primeira execução completa.

## Ajustes feitos durante o desenvolvimento (antes da execução completa)

| Item | O que foi visto nas prévias | Ajuste |
|---|---|---|
| Largura dos cartões | O cartão de IA e Modelo ocupava só a largura dos controles. | Os cartões passaram a ter o tamanho do grupo inteiro (`theme.Card` com o sizer do grupo), ocupando a largura da janela. |
| Anel de foco na tela Conectar conta | O anel laranja ficava sobre o fundo cinza, onde o laranja tem só 2,72:1 (abaixo de 3:1). | A tela ganhou dois cartões brancos; o anel só aparece em controles sobre cartão. Teste novo confere isso na janela de conversa. |
| Texto branco na barra laranja | Branco sobre o laranja da marca tem 3,05:1, o que só vale para texto grande em negrito. | Só o título fica na barra (18pt negrito); o subtítulo foi para o fundo da página. Teste novo confere o par como texto grande. |

## Problemas nos próprios testes

Nenhum.
