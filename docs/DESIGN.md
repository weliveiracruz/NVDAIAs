# Design do NVDAIAs – tema "Laranja"

O tema visual das janelas do NVDAIAs é construído a partir de **design tokens**, guardados em um único arquivo: `addon/globalPlugins/NVDAIAs/design/tokens.json`. O código (`theme.py`) só lê os tokens: para mudar uma cor, um tamanho de fonte ou um espaçamento, basta alterar o JSON. Os testes (`tests/test_theme.py`) recalculam o contraste de cada par e falham se algum ficar abaixo do mínimo.

A paleta combina azul-marinho profundo, laranja quente e fundos em branco quente. O tema não usa logotipos nem nomes de marcas de terceiros, já que o complemento será publicado na Loja de Complementos do NVDA.

## Princípios

1. **Acessibilidade em primeiro lugar.** Todo texto tem contraste mínimo de 4,5:1 e todo indicador visual (molduras, faixas) tem 3:1, como pede a WCAG 2.2 nível AA.
2. **A cor nunca é a única informação.** A linha de situação diz em texto o que a cor mostra.
3. **O leitor de telas não muda.** Os botões são os nativos do Windows, e a ordem de tabulação e os rótulos são os mesmos da versão sem tema. O cabeçalho é só visual e não recebe foco.
4. **Respeito ao sistema.** Com o alto contraste do Windows ativo, o tema se desliga e as cores do sistema valem.
5. **Foco bem visível.** O campo com foco ganha uma moldura laranja de 3px, além do indicador normal do Windows, o que ajuda quem tem baixa visão.

## Cores

| Token | Valor | Uso |
|---|---|---|
| `brand.orange` | `#EC7000` | Faixa sob o cabeçalho |
| `brand.orangeStrong` | `#B85600` | Laranja forte (reserva para destaques) |
| `brand.navy` | `#002B5C` | Azul-marinho da marca |
| `surface.page` | `#F7F4F0` | Fundo das janelas |
| `surface.card` | `#FFFFFF` | Fundo da lista e dos campos |
| `surface.header` | `#002B5C` | Fundo do cabeçalho |
| `text.primary` | `#1C1C1C` | Texto principal |
| `text.secondary` | `#55524E` | Rótulos dos campos |
| `text.onHeader` | `#FFFFFF` | Título no cabeçalho |
| `text.onHeaderMuted` | `#C8D3E3` | Subtítulo no cabeçalho |
| `text.accent` | `#A84F00` | Títulos de grupos |
| `border.idle` | `#8A8580` | Moldura dos campos sem foco |
| `border.focus` | `#B85600` | Moldura do campo com foco |
| `status.ok` | `#1E6B30` | Situação: conectado |
| `status.busy` | `#A84F00` | Situação: respondendo |
| `status.error` | `#B3261E` | Situação: erro |
| `status.idle` | `#55524E` | Situação: não conectado |

## Contraste

| Par | Contraste | Mínimo |
|---|---|---|
| `text.primary` sobre `surface.page` | 15.54:1 | 4,5:1 |
| `text.primary` sobre `surface.card` | 17.04:1 | 4,5:1 |
| `text.secondary` sobre `surface.page` | 7.09:1 | 4,5:1 |
| `text.onHeader` sobre `surface.header` | 14.00:1 | 4,5:1 |
| `text.onHeaderMuted` sobre `surface.header` | 9.25:1 | 4,5:1 |
| `text.accent` sobre `surface.page` | 5.06:1 | 4,5:1 |
| `status.ok` sobre `surface.page` | 5.98:1 | 4,5:1 |
| `status.busy` sobre `surface.page` | 5.06:1 | 4,5:1 |
| `status.error` sobre `surface.page` | 5.96:1 | 4,5:1 |
| `status.idle` sobre `surface.page` | 7.09:1 | 4,5:1 |
| `border.focus` sobre `surface.page` | 4.38:1 | 3:1 |
| `border.idle` sobre `surface.page` | 3.33:1 | 3:1 |
| `brand.orange` sobre `surface.header` | 4.59:1 | 3:1 |

## Tipografia

Família: Segoe UI (fonte do Windows). Com a opção **Texto maior**, todos os tamanhos são multiplicados por 1,25.

| Token | Tamanho (pt) |
|---|---|
| `family` | Segoe UI |
| `size.title` | 16 |
| `size.subtitle` | 10 |
| `size.status` | 10 |
| `size.body` | 11 |
| `size.label` | 10 |

## Espaçamento e bordas

Espaços: `xs` 4px · `sm` 8px · `md` 12px · `lg` 16px · `xl` 24px

Bordas: `stripe` 4px · `idle` 1px · `focus` 3px · `gap` 4px

## Componentes

* **Cabeçalho** (`HeaderPanel`): faixa azul-marinho com o título (`size.title`, negrito, branco) e o subtítulo (`text.onHeaderMuted`), com uma faixa laranja de 4px na base.
* **Linha de situação** (`StatusLine`): texto em negrito com a IA, o modelo e o estado, colorido por `status.*`.
* **Moldura de foco** (`FocusFrames`): moldura de 1px `border.idle` em volta de IA, Modelo, Conversa e Pergunta, que passa a 3px `border.focus` no campo com foco.
* **Campos e lista**: fundo `surface.card`, texto `text.primary` em `size.body`.
* **Rótulos**: `text.secondary` em negrito, `size.label`.

## Layout da janela de conversa

1. Cabeçalho
2. Linha de situação
3. IA e Modelo, lado a lado
4. Conversa: árvore com **Conversas anteriores** (recolhido) no topo e as mensagens da conversa atual em seguida. Ocupa o espaço que sobrar quando a janela cresce.
5. Pergunta, com o botão Enviar ao lado
6. Cancelar envio, Ler mensagem, Copiar mensagem
7. Nova conversa, Salvar conversa, Conectar conta, Configurações, Fechar

## Prévias

As imagens abaixo foram geradas em Linux por `tests/screenshots.py`. Por isso, os botões e as caixas de combinação aparecem com o visual do Linux. No Windows eles têm a aparência normal do Windows, e as cores, o cabeçalho, as fontes e a moldura de foco são os mesmos.

* `design/chat-foco-pergunta.png`: janela de conversa com o foco na pergunta
* `design/chat-foco-lista.png`: foco na lista da conversa
* `design/chat-historico.png`: conversas anteriores expandidas
* `design/chat-aguardando.png`: aguardando a resposta
* `design/chat-erro.png`: depois de um erro
* `design/conectar-conta.png`: tela Conectar conta
* `design/chat-sem-tema.png`: com o tema desligado

![Janela de conversa com o foco na pergunta](design/chat-foco-pergunta.png)

![Conversas anteriores expandidas](design/chat-historico.png)

![Aguardando a resposta](design/chat-aguardando.png)

![Tela Conectar conta](design/conectar-conta.png)
