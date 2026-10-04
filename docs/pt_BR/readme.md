# NVDAIAs – Converse com o ChatGPT, o Gemini e o Claude pelo NVDA

* Autor: Wellington Cruz
* Versão: 1.5.0
* Compatibilidade: NVDA 2024.1 ou posterior (testado até o NVDA 2026.2), Windows 10 e 11
* Licença: GNU General Public License, versão 2

O NVDAIAs abre uma janela acessível, dentro do NVDA, para você fazer perguntas ao **ChatGPT** (OpenAI), ao **Gemini** (Google) ou ao **Claude** (Anthropic) e ler as respostas sem sair do programa em que está trabalhando. Ele também pode **descrever imagens da tela** usando a IA.

Partes deste complemento foram escritas com auxílio de IA (Claude), com revisão e testes do autor.

## Antes de começar: o token de acesso

Os três serviços só permitem que programas de terceiros se conectem por meio de um **token de acesso**, também chamado de **chave de API**. Não existe uma forma oficial de entrar com o e-mail e a senha da sua conta do ChatGPT, do Gemini ou do Claude em outro programa. Por isso, a "tela de login" do NVDAIAs é a tela **Conectar conta**, onde você cola o token gerado no site de cada IA.

Você precisa de um token apenas para as IAs que quiser usar. Pode conectar uma, duas ou as três.

| IA | Onde gerar o token | Custo |
|---|---|---|
| ChatGPT | platform.openai.com/api-keys | Pago por uso. É cobrado à parte da assinatura do ChatGPT Plus; a conta da plataforma precisa ter crédito. |
| Gemini | aistudio.google.com/app/apikey | Tem um nível gratuito, com limites de uso. |
| Claude | console.anthropic.com/settings/keys | Pago por uso. É cobrado à parte da assinatura do Claude Pro; a conta do Console precisa ter crédito. |

A tela Conectar conta tem um botão que abre a página certa no navegador e mostra as instruções passo a passo para cada IA.

## Instalação

1. Baixe o arquivo `NVDAIAs-1.0.0.nvda-addon` (ou instale pela Loja de Complementos do NVDA, quando estiver publicado).
2. Pressione Enter sobre o arquivo e confirme a instalação.
3. Reinicie o NVDA quando ele pedir.

## Primeiro uso

1. Pressione **NVDA+Alt+I**.
2. Como ainda não há nenhuma IA conectada, a tela **Conectar conta** abre sozinha.
3. Na caixa **Inteligência artificial**, escolha ChatGPT, Gemini ou Claude.
4. Leia as **Instruções** (campo somente leitura; use as setas para ler linha por linha).
5. Pressione o botão **Abrir página para gerar o token**. A página abre no seu navegador. Entre na sua conta, crie a chave e copie.
6. Volte ao NVDA (Alt+Tab), cole o token no campo **Token (chave de API)** com Ctrl+V e pressione **Conectar**.
7. O NVDAIAs testa o token. Se estiver tudo certo, ele informa "Conectado" e guarda o token. A janela de conversa fica pronta para uso.

O teste de conexão apenas consulta a lista de modelos da sua conta. Ele não gasta créditos.

## A janela de conversa

Abra com **NVDA+Alt+I** ou pelo menu do NVDA > Ferramentas > **NVDAIAs - Conversar com IA**. O cursor já começa no campo Pergunta.

Ordem dos elementos com a tecla Tab:

1. **IA**: escolhe ChatGPT, Gemini ou Claude. Você pode trocar de IA no meio da conversa: a nova IA recebe todo o histórico.
2. **Modelo**: o modelo da IA escolhida. Você pode escolher da lista ou digitar o nome de outro modelo.
3. **Conversa**: árvore com dois ramos. O primeiro é **Conversas anteriores**, que começa recolhido. O segundo é **Conversa atual (N mensagens)**, que começa expandido e traz as mensagens desta conversa; cada item começa com "Você:" ou com o nome da IA. Os dois ramos recolhem e expandem com as setas para a esquerda e para a direita, ou com Enter. A Conversa atual se abre sozinha quando chega uma resposta nova.
4. **Pergunta**: campo onde você digita.
5. **Anexar arquivos** e **Enviar**, ao lado do campo Pergunta.
6. **Arquivos anexados**: lista que só aparece quando há arquivos esperando para ir com a próxima pergunta.
7. Botões: Cancelar envio, Ler mensagem, Copiar mensagem, **Ações da mensagem**, Nova conversa, Salvar conversa, Conectar conta, Configurações e Fechar.

Como o campo Pergunta vem logo depois da lista, **Shift+Tab no campo Pergunta leva direto para a lista da conversa**, e Tab na lista volta para a pergunta.

### Ações da mensagem

Na árvore Conversa, **Enter** sobre uma mensagem da conversa atual abre o menu de ações. A tecla **Aplicações**, **Shift+F10** e o botão **Ações da mensagem** (Alt+E) abrem o mesmo menu. Use as setas e Enter, ou a letra de cada opção:

| Opção | O que faz | Aparece em |
|---|---|---|
| **Ler mensagem** (L) | Abre a mensagem inteira na janela de leitura, com títulos, listas e links. Esc fecha. | Todas as mensagens |
| **Copiar** (C) | Copia o texto da mensagem | Todas as mensagens |
| **Excluir** (E) | Apaga a mensagem da conversa e do histórico, depois de confirmar | Mensagens da conversa atual |
| **Traduzir para** (T) | Submenu com 12 idiomas; pede à IA a tradução da mensagem, que chega como nova resposta | Mensagens da conversa atual |
| **Descrever esta imagem com mais detalhes** (I) | Pede à IA uma descrição muito mais completa da imagem | Mensagens com imagem e as respostas a elas |
| **Melhorar esta resposta** (M) | Pede à IA uma versão mais clara, completa e organizada da resposta | Respostas da IA |

Nas mensagens de conversas anteriores, o menu (Aplicações ou Shift+F10) tem Ler mensagem, Copiar e Abrir esta conversa para continuar. O Enter nelas continua reabrindo a conversa.

As ações que pedem algo à IA (traduzir, descrever, melhorar) aparecem na conversa como uma pergunta nova, com resposta. Enquanto uma resposta está sendo esperada, essas ações pedem para você aguardar.

### Anexar arquivos

O botão **Anexar arquivos** (Alt+X), logo depois do campo Pergunta (Tab a partir dele), abre a janela padrão do Windows para escolher arquivos. Ela mostra todos os formatos, e você pode marcar vários arquivos de uma vez.

| Tipo de arquivo | O que acontece | IAs |
|---|---|---|
| Imagens (JPG, PNG, GIF, WebP; BMP, TIFF e outras são convertidas para PNG) | Enviada como imagem | ChatGPT, Gemini e Claude |
| PDF | Enviado como documento; a IA lê o texto e as imagens das páginas | ChatGPT, Gemini e Claude |
| Word (.docx), Excel (.xlsx), PowerPoint (.pptx, com as anotações), OpenDocument (.odt, .ods, .odp), EPUB, RTF, HTML | O texto é extraído no seu computador e enviado | ChatGPT, Gemini e Claude |
| Texto, CSV, JSON, XML, Markdown, código-fonte, legendas e qualquer outro arquivo de texto | Enviado como texto | ChatGPT, Gemini e Claude |
| Áudio (MP3, WAV, M4A, OGG, FLAC...) e vídeo (MP4, MOV, WEBM...) | Enviado para a IA ouvir ou assistir | Só o Gemini |
| Office antigo (.doc, .xls, .ppt) | Não é lido. O NVDAIAs pede para salvar como .docx, .xlsx, .pptx ou PDF | - |
| Programas, arquivos compactados e outros binários | Não é lido. O NVDAIAs explica e sugere converter | - |

Como funciona:

* Depois de anexar, o NVDA diz o nome dos arquivos e quantos vão com a próxima pergunta. Eles aparecem na lista **Arquivos anexados**, abaixo da pergunta (Alt+U), com o tipo e o tamanho. **Delete** remove o arquivo selecionado.
* Pode enviar sem digitar nada: o NVDAIAs pede para a IA analisar e resumir os arquivos. Ou escreva a pergunta, por exemplo "Compare os números do relatório com a planilha".
* Se a IA escolhida não aceitar o arquivo (áudio com ChatGPT ou Claude), ou se houver erro ou cancelamento, a pergunta e os arquivos voltam para você tentar de novo.
* Os arquivos ficam na conversa: a mensagem mostra "[anexos: ...]", as perguntas seguintes podem falar deles, e eles são guardados no histórico.
* Limites: 20 MB por arquivo. Textos muito longos são cortados em 300 mil caracteres, e o NVDA avisa.

### Conversas anteriores

Toda conversa é guardada automaticamente. O primeiro item da árvore **Conversa** é **Conversas anteriores (N)**, que começa recolhido:

1. Na árvore, pressione Home para ir até esse item e Seta para a direita para expandir.
2. Cada conversa anterior aparece com a data, as IAs usadas, a primeira pergunta e o número de mensagens, também recolhida. Expanda com Seta para a direita para ler as mensagens com as setas. Ctrl+C copia uma mensagem.
3. **Enter** em uma conversa anterior, ou em qualquer mensagem dela, reabre essa conversa como a conversa atual. O foco vai para o campo Pergunta e você continua de onde parou: a IA recebe todas as mensagens anteriores.
4. A conversa que estava aberta antes vai para a lista de conversas anteriores, então nada se perde.
5. **Nova conversa** guarda a conversa atual no histórico e começa outra em branco.
6. **Delete** sobre uma conversa anterior apaga essa conversa, depois de confirmar.

### Aparência

A janela tem um tema visual pensado também para quem tem baixa visão: cabeçalho azul-marinho com o nome do complemento, fundo claro, destaques em laranja, fontes maiores e uma **moldura laranja grossa em volta do campo que está com o foco**. Logo abaixo do cabeçalho, uma **linha de situação** mostra a IA, o modelo e o estado: conectado, respondendo, ou que a última pergunta falhou. As cores só repetem o que o texto já diz.

O tema se desliga sozinho quando o alto contraste do Windows está ativo. Também pode ser desligado nas configurações, onde há ainda a opção de texto maior. Os botões continuam sendo os botões padrão do Windows, para o NVDA apresentá-los como sempre.

### Teclas da janela

| Onde | Tecla | O que faz |
|---|---|---|
| Campo Pergunta | Enter | Envia a pergunta |
| Campo Pergunta | Shift+Enter | Cria uma nova linha sem enviar |
| Campo Pergunta | Shift+Tab | Vai para a lista da conversa |
| Conversa | Setas para cima e para baixo | Passa pelos itens |
| Conversa | Seta para a direita / para a esquerda | Expande / recolhe "Conversas anteriores", "Conversa atual" ou uma conversa anterior |
| Conversa, ramo "Conversas anteriores" ou "Conversa atual" | Enter | Expande ou recolhe o ramo |
| Conversa, mensagem da conversa atual | Enter, tecla Aplicações ou Shift+F10 | Abre o menu **Ações da mensagem** (veja abaixo) |
| Conversa, conversa anterior ou mensagem dela | Enter | Reabre aquela conversa para continuar |
| Conversa | Ctrl+C | Copia a mensagem selecionada (atual ou anterior) |
| Conversa, conversa anterior | Delete | Apaga a conversa do histórico (pede confirmação) |
| Qualquer lugar | Esc | Fecha a janela (a conversa atual continua aberta e já está salva no histórico) |

Cada botão também tem uma letra de atalho com Alt, que o NVDA anuncia ao focalizar o botão. Por exemplo, Alt+N envia, Alt+L lê a mensagem e Alt+V vai para a lista da conversa.

### O que acontece ao enviar

* O NVDA diz "Enviado para o Claude" (ou a IA escolhida).
* Enquanto a IA pensa, o último item da lista diz "Claude está respondendo…" e um bipe curto toca a cada 1,5 segundo.
* Quando a resposta chega, toca um bipe agudo e o NVDA lê a resposta. Pressione Ctrl para interromper a leitura.
* A resposta entra na lista da conversa. Para ler com calma, vá até a lista e pressione Enter.
* Se der erro, um bipe grave toca, o NVDA explica o problema e a sua pergunta volta para o campo, para você tentar de novo.

Os símbolos de formatação que as IAs costumam usar (#, asteriscos, barras de tabela) são retirados na lista e na leitura automática. Na janela de leitura (Enter na lista), a formatação vira títulos, listas e links de verdade.

## Descrever a tela

| Comando | O que faz |
|---|---|
| NVDA+Alt+D | Tira uma foto do **objeto de navegação** atual (por exemplo, uma imagem, um botão ou um gráfico) e pede para a IA descrever |
| NVDA+Shift+Alt+D | Tira uma foto da **tela inteira** (monitor em que está a janela ativa) e pede para a IA descrever |

A janela de conversa abre com a pergunta e a imagem, e a descrição é lida quando chegar. Você pode fazer perguntas sobre a imagem em seguida, por exemplo "qual é a cor do botão?", porque a imagem fica no histórico da conversa.

Para descrever só uma parte da tela, mova o objeto de navegação até ela com os comandos de navegação de objetos do NVDA antes de pressionar NVDA+Alt+D.

Os três serviços aceitam imagens nos modelos atuais. Se o modelo escolhido não aceitar imagens, a IA vai responder com um erro.

## Comandos globais

| Comando | Ação |
|---|---|
| NVDA+Alt+I | Abre a janela de conversa |
| NVDA+Alt+D | Descreve o objeto de navegação |
| NVDA+Shift+Alt+D | Descreve a tela inteira |
| (sem atalho) | Abre as configurações do NVDAIAs |

Todos os comandos podem ser alterados em menu do NVDA > Preferências > Definir comandos, na categoria **NVDAIAs**.

## Configurações

Menu do NVDA > Preferências > Configurações > categoria **NVDAIAs**. Também pelo botão Configurações da janela de conversa.

* **IA padrão**: a IA usada quando a janela abre.
* Para **cada IA** (ChatGPT, Gemini e Claude):
  * **Situação**: diz se há um token salvo e mostra só os 4 últimos caracteres dele.
  * **Novo token**: cole aqui para trocar o token. Vazio mantém o salvo.
  * **Abrir página do token** (da IA do grupo).
  * **Testar conexão com** a IA: confere o token sem gastar créditos e avisa se o modelo escolhido não existe na sua conta.
  * **Remover token salvo** da IA.
  * **Modelo** e **Atualizar lista de modelos**: baixa da IA a lista de modelos que a sua conta pode usar.
  * Cada botão leva o nome da IA, por exemplo "Testar conexão com o Gemini", para o leitor de telas dizer de qual IA ele é.
* **Instruções enviadas à IA em todas as perguntas**: o texto que orienta a IA. O padrão pede respostas no idioma da pergunta, em parágrafos curtos, sem tabelas nem emojis, pensando em quem usa leitor de telas. O botão **Restaurar instruções padrão** volta ao texto original.
* **Ler as respostas automaticamente quando chegarem** (ligado por padrão).
* **Bipar enquanto aguarda a resposta** (ligado por padrão).
* **Remover símbolos de formatação ao ler as respostas** (ligado por padrão).
* **Guardar as conversas anteriores** (ligado por padrão), **Número máximo de conversas anteriores** (padrão 100; as mais antigas são apagadas) e o botão **Apagar todas as conversas anteriores**.
* **Usar o tema visual nas janelas do NVDAIAs** (ligado por padrão): cores, cabeçalho e moldura de foco.
* **Texto maior nas janelas do NVDAIAs** (desligado por padrão): aumenta as fontes em 25%.
* **Tamanho máximo da resposta em tokens (Claude)**: o Claude exige esse limite. Padrão 4096.
* **Tempo limite para aguardar a resposta**: em segundos. Padrão 120.

Os tokens só são gravados quando você pressiona OK ou Aplicar.

## Privacidade e segurança

* Os tokens **não** ficam no arquivo de configuração do NVDA (nvda.ini). Eles são guardados no arquivo `NVDAIAs-credentials.json`, na pasta de configuração do NVDA, **criptografados com a proteção de dados do Windows (DPAPI)**. Só o seu usuário do Windows, neste computador, consegue abrir. Se o arquivo for copiado para outro computador, os tokens não funcionam lá.
* **Atualizar o complemento mantém os tokens e o histórico.** Só a desinstalação de verdade apaga os tokens e o histórico.
* O que você digita, o histórico da conversa e as imagens de tela que você pedir para descrever são enviados diretamente do seu computador para a IA escolhida (OpenAI, Google ou Anthropic), por conexão segura (HTTPS). Não passam por nenhum outro servidor. Cada empresa trata esses dados conforme a política de privacidade dela.
* Cuidado ao descrever a tela: tudo o que estiver visível na área capturada é enviado, inclusive dados pessoais.
* O complemento não funciona nas telas seguras do Windows (tela de logon e controle de conta de usuário).
* As conversas são salvas automaticamente depois de cada resposta, na pasta `NVDAIAs-history` da configuração do NVDA, **criptografadas com a proteção de dados do Windows**, como os tokens. As imagens de tela descritas e os arquivos anexados também ficam guardados na conversa.
* Os arquivos anexados são enviados diretamente para a IA escolhida, como as perguntas. Você pode apagar uma conversa com Delete, apagar todas nas configurações ou desligar o histórico. Ao atualizar o complemento, o histórico é mantido; ao desinstalar, ele é apagado. **Salvar conversa** continua gravando um arquivo de texto comum, sem criptografia.

## Mensagens de erro

| Mensagem | O que fazer |
|---|---|
| "não aceitou o token" | O token foi digitado errado, foi apagado no site ou expirou. Gere outro e cole em Configurações ou em Conectar conta. |
| "limite de uso atingido ou conta sem crédito" | Coloque crédito na conta da plataforma (ChatGPT e Claude) ou aguarde o limite gratuito renovar (Gemini). |
| "o modelo escolhido não está disponível" | Use Atualizar lista de modelos nas configurações e escolha um modelo da lista. |
| "Não foi possível conectar" | Verifique a internet, o proxy ou o firewall. |
| "demorou demais para responder" | Tente de novo ou aumente o tempo limite. |
| "problema temporário" | O serviço está sobrecarregado. Tente em alguns instantes. |
| "bloqueada pelo provedor" | A IA se recusou a responder ou o filtro de segurança dela bloqueou a pergunta. |

## Histórico de versões

### 1.5.0

* Tokens e histórico de conversas mantidos na atualização do complemento, inclusive vindo das versões 1.0.0 a 1.4.0.
* A conversa atual virou um ramo da árvore, "Conversa atual (N mensagens)", que pode ser recolhido e expandido.

### 1.4.0

* Ações da mensagem (Enter, tecla Aplicações ou botão): ler, copiar, excluir, traduzir para 12 idiomas, descrever imagem com mais detalhes e melhorar resposta.
* Correções de segurança e de acessibilidade encontradas pelo novo plano de testes.

### 1.3.0

* Botão Anexar arquivos ao lado do campo Pergunta, aceitando qualquer arquivo. Imagens e PDF vão para as três IAs; Word, Excel, PowerPoint, OpenDocument, EPUB, RTF, HTML, CSV, código e outros textos são lidos no computador e enviados como texto; áudio e vídeo vão para o Gemini.

### 1.2.0

* Conversas anteriores: o primeiro item da árvore da conversa, recolhido por padrão, traz as conversas salvas. Cada uma se expande para mostrar as mensagens, e Enter em qualquer uma delas reabre a conversa para continuar.
* As conversas são salvas automaticamente, com criptografia do Windows. Delete apaga uma conversa.
* Novas opções: guardar conversas anteriores, número máximo e apagar todas.

### 1.1.0

* Tema visual nas janelas do NVDAIAs, construído com design tokens: cabeçalho azul-marinho, destaques em laranja, fontes maiores, linha de situação e moldura de foco grossa. Todas as cores atendem à WCAG 2.2 AA e o tema se desliga sozinho no alto contraste do Windows.
* Novas opções: usar o tema visual e texto maior.
* Janela de conversa: IA e Modelo lado a lado e botão Enviar ao lado da pergunta.

### 1.0.0

* Primeira versão: janela de conversa com ChatGPT, Gemini e Claude; tela de conexão de conta com token; painel de configurações; descrição do objeto de navegação e da tela; tradução para português do Brasil.
