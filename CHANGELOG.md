# Changelog / Histórico de versões

## 1.7.0

* Continue with ChatGPT: sign in with your ChatGPT account and use your ChatGPT plan (Plus, Pro and others) without an API key, using OpenAI's official Sign in with ChatGPT for open-source apps (OAuth with PKCE in the browser, answer received only on 127.0.0.1, ID token checked, tokens encrypted with DPAPI and renewed automatically, revoked on sign out). Available on the Connect account screen and in the settings. The API token option stays; a setting chooses which one ChatGPT uses.
* The status line says when the ChatGPT plan is in use, with the account e-mail; new Manage ChatGPT usage button (only while using the plan). When the plan reaches its usage limit, Manage usage is offered as the main action. One-time notice "You're using your ChatGPT plan".
* Gemini and Claude have no official equivalent (Google offers no sign-in for third-party apps with a personal account; Anthropic does not allow third-party apps to use Claude subscriptions), so they keep using tokens.
* Fix: the credential file is now safe when written from background threads at the same time (P-10 in reports/PROBLEMAS-1.7.0.md).
* The ChatGPT sign-in uses only the parts of Python that NVDA ships; if it ever fails to load, the rest of the add-on keeps working with tokens (P-14).
* Continuar com o ChatGPT: entre com a sua conta do ChatGPT e use o seu plano do ChatGPT (Plus, Pro e outros) sem chave de API, pelo Entrar com o ChatGPT oficial da OpenAI para apps de código aberto (OAuth com PKCE no navegador, resposta recebida só em 127.0.0.1, token de identidade conferido, tokens criptografados com DPAPI e renovados sozinhos, revogados ao sair). Disponível na tela Conectar conta e nas configurações. A opção de token continua; uma opção escolhe qual o ChatGPT usa.
* A linha de situação diz quando o plano do ChatGPT está em uso, com o e-mail da conta; novo botão Gerenciar uso do ChatGPT (só com o plano em uso). Quando o plano atinge o limite de uso, Gerenciar uso é oferecido como ação principal. Aviso único "Você está usando o seu plano do ChatGPT".
* Gemini e Claude não têm algo oficial equivalente (o Google não oferece entrada com conta pessoal para apps de terceiros; a Anthropic não permite que apps de terceiros usem as assinaturas do Claude), então continuam usando tokens.
* Correção: o arquivo de credenciais agora é gravado com segurança quando duas tarefas em segundo plano escrevem ao mesmo tempo (P-10 em reports/PROBLEMAS-1.7.0.md).
* A entrada com o ChatGPT usa só as partes do Python que o NVDA traz; se um dia falhar ao carregar, o resto do complemento continua funcionando com tokens (P-14).

## 1.6.0

* "Send feedback" button in the chat window (Alt+D) and an unassigned "Send feedback" command in Input gestures. A standard message box says "The evaluation will open in a new tab of your browser" with the buttons Give feedback and Cancel; Give feedback opens the feedback form.
* Botão "Enviar feedback" na janela de conversa (Alt+D) e comando "Enviar feedback", sem atalho, em Definir comandos. Uma caixa de mensagem padrão avisa "A avaliação será aberta numa nova aba do seu navegador", com os botões Dar feedback e Cancelar; Dar feedback abre o formulário.

## 1.5.0

* Tokens and conversation history are kept when the add-on is updated. NVDA runs the uninstall task of the old version during an update, and versions 1.0.0 to 1.4.0 deleted the data there. Now the uninstall task only deletes on a real uninstall, and installing 1.5.0 makes a copy that is restored when it starts, so updating from older versions is safe too.
* The current conversation is a branch of the conversation tree ("Current conversation (N messages)"), after "Previous conversations", and can be collapsed and expanded with the arrows or Enter. It opens again when a new answer arrives.
* Os tokens e o histórico de conversas são mantidos na atualização do complemento. O NVDA roda a desinstalação da versão antiga durante a atualização, e as versões 1.0.0 a 1.4.0 apagavam os dados ali. Agora a desinstalação só apaga numa desinstalação de verdade, e a instalação da 1.5.0 faz uma cópia que é restaurada quando ela inicia, então a atualização a partir das versões antigas também é segura.
* A conversa atual é um ramo da árvore ("Conversa atual (N mensagens)"), depois de "Conversas anteriores", e pode ser recolhida e expandida com as setas ou Enter. Ela se abre de novo quando chega uma resposta nova.

## 1.4.0

* Message actions: Enter (or the Applications key / Shift+F10) on a message of the current conversation, or the new "Actions for this message" button, opens a menu with Read message, Copy, Delete, Translate to (12 languages), Describe this image in more detail (messages with images) and Improve this answer (answers). Messages of previous conversations get Read, Copy and Open this conversation.
* Security fixes found by the new test plan: zip bombs and XML with DTD/entities in attached documents are refused; API keys are never re-sent by HTTP redirects; answers limited to 32 MB; only HTTPS addresses (P-04 to P-08 in reports/PROBLEMAS-1.4.0.md).
* Accessibility fixes: settings buttons have unique names with the AI name; complete Portuguese translation; translator comments for every text.
* Test plan (docs/SDD-TESTES.md) with 375 functional, accessibility and security tests, run by tests/run_all.py before every release (reports/RELATORIO-TESTES-1.4.0.md).
* Ações da mensagem: Enter (ou a tecla Aplicações / Shift+F10) numa mensagem da conversa atual, ou o novo botão "Ações da mensagem", abre um menu com Ler mensagem, Copiar, Excluir, Traduzir para (12 idiomas), Descrever esta imagem com mais detalhes (mensagens com imagem) e Melhorar esta resposta (respostas). Mensagens de conversas anteriores têm Ler, Copiar e Abrir esta conversa.
* Correções de segurança encontradas pelo novo plano de testes: bombas zip e XML com DTD/entidades em documentos anexados são recusados; a chave de API nunca é reenviada por redirecionamento; respostas limitadas a 32 MB; só endereços HTTPS.
* Correções de acessibilidade: botões das configurações com nomes únicos, com o nome da IA; tradução completa; comentário para tradutores em todos os textos.
* Plano de testes (docs/SDD-TESTES.md) com 375 testes funcionais, de acessibilidade e de segurança, rodados por tests/run_all.py antes de cada versão.

## 1.3.0

* Attach files button next to the question field, accepting any file (several at once). Images and PDF go to the three AIs; Word, Excel, PowerPoint (.docx, .xlsx, .pptx), OpenDocument, EPUB, RTF, HTML, CSV, code and other text files are read on this computer and sent as text; audio and video go to Gemini. Old Office formats (.doc, .xls, .ppt) and binary files get a clear message. Files can be sent without typing a question, are listed under the question (Delete removes), come back after an error or cancel, and stay in the conversation and in the history.
* Botão Anexar arquivos ao lado do campo de pergunta, aceitando qualquer arquivo (vários de uma vez). Imagens e PDF vão para as três IAs; Word, Excel, PowerPoint (.docx, .xlsx, .pptx), OpenDocument, EPUB, RTF, HTML, CSV, código e outros textos são lidos no computador e enviados como texto; áudio e vídeo vão para o Gemini. Formatos antigos do Office (.doc, .xls, .ppt) e arquivos binários recebem uma mensagem clara. Dá para enviar sem digitar pergunta; os arquivos aparecem abaixo da pergunta (Delete remove), voltam depois de erro ou cancelamento e ficam na conversa e no histórico.

## 1.2.0

* Previous conversations: the conversation list became a tree whose first item, "Previous conversations", starts collapsed. Each saved conversation is a collapsed branch with its messages; Enter on a conversation or on one of its messages reopens it to be continued (the AI receives the whole history). Conversations are saved automatically after each answer, encrypted with Windows DPAPI, and removed when the add-on is uninstalled. Delete removes one conversation. New options: keep previous conversations, maximum number, delete all.
* Conversas anteriores: a lista da conversa virou uma árvore cujo primeiro item, "Conversas anteriores", começa recolhido. Cada conversa salva é um ramo recolhido com as mensagens; Enter numa conversa ou numa mensagem dela reabre a conversa para continuar (a IA recebe todo o histórico). As conversas são salvas automaticamente após cada resposta, com criptografia do Windows (DPAPI), e apagadas ao desinstalar o complemento. Delete apaga uma conversa. Novas opções: guardar conversas anteriores, número máximo e apagar todas.

## 1.1.0

* Visual theme for the NVDAIAs windows built from design tokens (`addon/globalPlugins/NVDAIAs/design/tokens.json`): navy header, warm orange accents, larger fonts, status line and a thick focus frame. All colours meet WCAG 2.2 AA; the theme turns itself off in Windows high contrast. New options: use the visual theme, larger text. Chat window layout: AI and Model side by side, Send button next to the question.
* Tema visual nas janelas do NVDAIAs, construído com design tokens: cabeçalho azul-marinho, destaques em laranja, fontes maiores, linha de situação e moldura de foco grossa. Todas as cores atendem à WCAG 2.2 AA; o tema se desliga sozinho no alto contraste do Windows. Novas opções: usar o tema visual e texto maior. Janela de conversa: IA e Modelo lado a lado, botão Enviar ao lado da pergunta.

## 1.0.0

* First release: chat window with ChatGPT, Gemini and Claude; account connection screen with token; settings panel; description of the navigator object and of the screen; Portuguese (Brazil) translation.
* Primeira versão: janela de conversa com ChatGPT, Gemini e Claude; tela de conexão de conta com token; painel de configurações; descrição do objeto de navegação e da tela; tradução para português do Brasil.
