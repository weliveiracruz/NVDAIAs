# Testes do NVDAIAs

## Testes automáticos (já executados)

A partir da versão 1.4.0, o plano completo de testes está no **SDD de testes** (`docs/SDD-TESTES.md`), com os casos funcionais (FUN), de acessibilidade (ACE) e de vulnerabilidade (SEG). Para rodar todas as suítes e gerar o relatório: `python3 tests/run_all.py`. O resultado da última execução fica em `reports/ULTIMA-EXECUCAO.md`, o histórico de execuções em `reports/execucoes.json` e o relatório de cada versão em `reports/RELATORIO-TESTES-<versão>.md`.

O resumo abaixo é das versões anteriores.

Os testes ficam na pasta `tests` e rodam em Linux, com o wxPython de verdade (a mesma biblioteca de interface do NVDA) e um servidor local que imita as APIs do ChatGPT, do Gemini e do Claude, conferindo cabeçalhos de autenticação e o formato de cada requisição. Os módulos do NVDA são substituídos por versões simuladas, exceto o `guiHelper`, que é o arquivo original do NVDA.

Para rodar tudo: `tests/run_all.sh` (precisa de `python3-wxgtk4.0` e `xvfb`). A automação do GitHub roda os mesmos testes a cada envio.

Resultado na versão 1.3.0:

* `tests/test_pure.py`: 39 testes, todos aprovados em Python 3.11, 3.12 e 3.13 (versões usadas pelo NVDA 2024.1 até o 2026.x).
  * Pergunta e resposta nas três IAs, histórico com várias mensagens, envio de imagem.
  * Token errado, token vazio, falta de crédito, servidor sobrecarregado, resposta inválida, modelo inexistente, resposta bloqueada, sem internet e tempo esgotado: cada um vira a mensagem de erro certa.
  * Lista de modelos de cada IA e teste de conexão sem gasto de créditos.
  * Conversão de Markdown para texto falado e para HTML, incluindo bloqueio de links `javascript:` e de HTML injetado.
  * Gravação dos tokens: o arquivo não contém o token em texto puro e arquivo corrompido não trava o complemento.
  * Anexos: imagens, PDF, áudio e vídeo, textos em UTF-8, Windows-1252 e UTF-16, CSV, código, HTML, RTF, Word, Excel, PowerPoint com anotações, OpenDocument e EPUB; recusa de Office antigo, programas, arquivos compactados, arquivos vazios e grandes demais; formato certo de anexo para cada IA; áudio só no Gemini, sem enviar nada às outras.
  * Histórico de conversas: gravação criptografada, leitura com imagens, ordem da mais recente, limite de conversas, arquivo corrompido ignorado e bloqueio de nomes de arquivo perigosos.
* `tests/test_gui.py`: 119 verificações, todas aprovadas, incluindo teclas reais (eventos de teclado do sistema):
  * Primeiro uso abre a tela Conectar conta; token errado é recusado; token certo é salvo e a IA vira a padrão.
  * Ordem de tabulação: IA, Modelo, Conversa, Pergunta, botões. **Shift+Tab na Pergunta leva à lista da Conversa.**
  * Enter envia, Shift+Enter cria nova linha, Enter na lista abre a mensagem, Ctrl+C copia, Esc fecha.
  * Resposta lida automaticamente, item "está respondendo…" durante a espera, troca de IA no meio da conversa com histórico, cancelamento, erro devolve a pergunta ao campo.
  * Descrição do objeto de navegação com captura de tela real em PNG e redução de imagens grandes.
  * Painel de configurações: situação do token, testar conexão, atualizar modelos, salvar token, modelo, instruções com várias linhas e opções, remover token.
  * Conversas anteriores: item no topo recolhido, uma conversa por ramo, mensagens ao expandir, Enter numa mensagem antiga reabre a conversa e manda o foco para a Pergunta, a IA recebe o histórico, a conversa continuada é salva no mesmo registro, Delete apaga, setas reais expandem e recolhem.
  * Anexar arquivos: botão logo depois da Pergunta (Tab real), lista de anexos escondida quando vazia, arquivo ilegível recusado com mensagem, Delete remove, envio sem digitar, IA recebe PDF e texto, anexos reenviados nas perguntas seguintes e salvos no histórico, áudio recusado pelo Claude devolve pergunta e arquivo, Gemini aceita o áudio, cancelamento devolve os arquivos.
  * Conversa mantida ao fechar e reabrir a janela, desativação em telas seguras, remoção limpa ao desligar o complemento.
* `tests/test_theme.py`: 27 verificações de contraste das cores (WCAG 2.2 AA), alto contraste, tema ligado e desligado e ordem de tabulação.
* `tests/test_translation.py`: interface em português do Brasil, sem letras de atalho repetidas em nenhuma janela.
* `build.py` valida o `manifest.ini` (também conferido com a especificação de manifesto do código-fonte do NVDA) e gera o pacote.

## O que só pode ser testado no Windows com o NVDA

Os testes automáticos não substituem estes pontos:

* A criptografia dos tokens com a proteção de dados do Windows (DPAPI).
* A conexão real com as três empresas, usando os seus tokens.
* A fala e as teclas no NVDA de verdade, incluindo a janela de leitura.
* A captura de tela no Windows.

## Teste no Windows com o NVDA (roteiro)

1. Instale o pacote mais recente da pasta `dist` (Enter sobre o arquivo) e reinicie o NVDA.
2. Pressione NVDA+Alt+I. A tela Conectar conta deve abrir. Escolha Gemini (tem nível gratuito), abra a página, gere a chave, cole e pressione Conectar. Deve aparecer "Conectado ao Gemini".
3. Na janela de conversa, digite "Qual é a capital do Brasil?" e pressione Enter. Deve ouvir "Enviado para o Gemini", bipes curtos e depois a resposta.
4. Pressione Shift+Tab: o foco deve ir para a árvore Conversa. Use as setas e pressione Enter numa resposta: o menu Ações da mensagem deve abrir. Teste Ler mensagem (abre a janela de leitura; Esc fecha), Traduzir para > inglês e Melhorar esta resposta. Teste também a tecla Aplicações e Ctrl+C.
5. Feche a janela com Esc, reinicie o NVDA e abra de novo com NVDA+Alt+I. Pressione Shift+Tab, Home e Seta para a direita: "Conversas anteriores" deve mostrar a conversa do passo 3. Expanda, desça até uma mensagem e pressione Enter: a conversa volta a ser a atual e o foco vai para a Pergunta.
6. Pressione Tab para voltar à pergunta. Pergunte "E a da Argentina?" para conferir que a IA lembra da conversa.
7. Pressione Tab no campo Pergunta até Anexar arquivos, escolha um PDF e um .docx e pergunte "Resuma estes arquivos". Teste também um MP3 com o Gemini.
8. Pressione Esc, abra o Bloco de Notas, pressione NVDA+Alt+D. A descrição do objeto deve ser lida.
9. Repita os passos 2 e 3 com o ChatGPT e o Claude, se tiver os tokens.
10. Abra menu do NVDA > Preferências > Configurações > NVDAIAs. Use Testar conexão e Atualizar lista de modelos em cada IA.
11. Confira a criptografia: abra a pasta `%APPDATA%\nvda` (pressione Windows+R, digite `%APPDATA%\nvda` e Enter) e abra `NVDAIAs-credentials.json` no Bloco de Notas. Cada token deve aparecer como um texto longo que começa com `AQAAANCMnd8BFdERjHoAwE`, que é a assinatura da criptografia do Windows (DPAPI).
12. Se algo falhar, abra o log do NVDA (NVDA+F1) e procure por "NVDAIAs".
