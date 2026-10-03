# Changelog / Histórico de versões

## 1.2.0

* Previous conversations: the conversation list became a tree whose first item, "Previous conversations", starts collapsed. Each saved conversation is a collapsed branch with its messages; Enter on a conversation or on one of its messages reopens it to be continued (the AI receives the whole history). Conversations are saved automatically after each answer, encrypted with Windows DPAPI, and removed when the add-on is uninstalled. Delete removes one conversation. New options: keep previous conversations, maximum number, delete all.
* Conversas anteriores: a lista da conversa virou uma árvore cujo primeiro item, "Conversas anteriores", começa recolhido. Cada conversa salva é um ramo recolhido com as mensagens; Enter numa conversa ou numa mensagem dela reabre a conversa para continuar (a IA recebe todo o histórico). As conversas são salvas automaticamente após cada resposta, com criptografia do Windows (DPAPI), e apagadas ao desinstalar o complemento. Delete apaga uma conversa. Novas opções: guardar conversas anteriores, número máximo e apagar todas.

## 1.1.0

* Visual theme for the NVDAIAs windows built from design tokens (`addon/globalPlugins/NVDAIAs/design/tokens.json`): navy header, warm orange accents, larger fonts, status line and a thick focus frame. All colours meet WCAG 2.2 AA; the theme turns itself off in Windows high contrast. New options: use the visual theme, larger text. Chat window layout: AI and Model side by side, Send button next to the question.
* Tema visual nas janelas do NVDAIAs, construído com design tokens: cabeçalho azul-marinho, destaques em laranja, fontes maiores, linha de situação e moldura de foco grossa. Todas as cores atendem à WCAG 2.2 AA; o tema se desliga sozinho no alto contraste do Windows. Novas opções: usar o tema visual e texto maior. Janela de conversa: IA e Modelo lado a lado, botão Enviar ao lado da pergunta.

## 1.0.0

* First release: chat window with ChatGPT, Gemini and Claude; account connection screen with token; settings panel; description of the navigator object and of the screen; Portuguese (Brazil) translation.
* Primeira versão: janela de conversa com ChatGPT, Gemini e Claude; tela de conexão de conta com token; painel de configurações; descrição do objeto de navegação e da tela; tradução para português do Brasil.
