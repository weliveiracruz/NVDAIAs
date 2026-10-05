# SDD de testes do NVDAIAs

Documento de especificação dos testes (Software Design Document) do complemento NVDAIAs. Ele define **o que** é testado, **como** e **quando**, e vale para todas as versões a partir da 1.4.0.

## 1. Objetivo

Garantir, a cada nova versão, que o NVDAIAs:

1. **funciona**: conversa com ChatGPT, Gemini e Claude, anexos, histórico e ações das mensagens (testes funcionais, prefixo FUN);
2. **é acessível** para quem usa o NVDA e para quem tem baixa visão (testes de acessibilidade, prefixo ACE);
3. **não expõe o usuário**: tokens, conversas, arquivos e rede (testes de vulnerabilidade, prefixo SEG).

## 2. Escopo

* Código do complemento: `addon/` (plugin global, janelas, provedores, anexos, histórico, tema, tradução, manifesto).
* Empacotamento: `build.py` e o arquivo `.nvda-addon`.
* Fora do escopo automático, coberto pelo roteiro manual em `docs/TESTES.md`: fala real do NVDA, criptografia DPAPI no Windows e chamadas reais às três empresas com tokens de verdade.

## 3. Ambiente de teste

| Item | Como é feito |
|---|---|
| Interface | wxPython real (a mesma biblioteca do NVDA), com tela virtual (Xvfb) |
| NVDA | Módulos substituídos por simulações (`tests/nvda_stubs.py`), exceto o `guiHelper`, que é o original do NVDA |
| APIs das IAs | Servidor local que imita OpenAI, Gemini e Anthropic (`tests/mock_server.py`), conferindo autenticação e formato de cada requisição |
| Criptografia | Codificador de teste injetado no lugar do DPAPI, para verificar que nada fica em texto puro |
| Versões do Python | 3.11 (NVDA 2024.x), 3.12 e 3.13 (NVDA 2026.x) |
| Análise estática | `bandit` (segurança de código Python) e varredura de padrões proibidos |

## 4. Suítes

| Suíte | Arquivo | Tipo |
|---|---|---|
| Unidades | `tests/test_pure.py` | FUN, SEG (provedores, anexos, histórico, texto, credenciais) |
| Interface | `tests/test_gui.py` | FUN (janela de conversa, login, configurações, histórico, anexos, ações) |
| Tema | `tests/test_theme.py` | ACE (contraste, alto contraste, ordem de tabulação) |
| Tradução | `tests/test_translation.py` | ACE (interface em português, atalhos únicos) |
| Acessibilidade | `tests/test_accessibility.py` | ACE |
| Segurança | `tests/test_security.py` | SEG |
| Atualização | `tests/test_update.py` | FUN (tokens e histórico preservados na atualização) |
| Pacote | `tests/run_all.py` (etapa build) | FUN (manifesto e pacote válidos) |

O executor `tests/run_all.py` roda todas as suítes, conta testes, aprovados e falhas, compara com a execução anterior para contar as correções e grava o histórico em `reports/execucoes.json` e o resumo em `reports/ULTIMA-EXECUCAO.md`.

## 5. Casos de teste funcionais (FUN)

| ID | Caso | Resultado esperado | Suíte |
|---|---|---|---|
| FUN-01 | Pergunta e resposta em cada IA | Resposta recebida e lida | pure, gui |
| FUN-02 | Histórico da conversa enviado a cada pergunta | IA recebe todas as mensagens | pure, gui |
| FUN-03 | Troca de IA no meio da conversa | Nova IA recebe o histórico | gui |
| FUN-04 | Tela Conectar conta | Token errado recusado, certo salvo | gui |
| FUN-05 | Erros: token, crédito, rede, tempo, modelo, bloqueio, servidor | Mensagem certa para cada um | pure, gui |
| FUN-06 | Cancelar envio | Pergunta e anexos voltam | gui |
| FUN-07 | Descrever objeto e tela | Imagem PNG enviada e descrição lida | gui |
| FUN-08 | Configurações | Token, modelo, instruções e opções salvos | gui |
| FUN-09 | Conversas anteriores | Salvas, listadas, reabertas com Enter, apagadas com Delete | pure, gui |
| FUN-10 | Anexar arquivos | Cada formato tratado conforme a tabela da documentação | pure, gui |
| FUN-11 | Ações da mensagem | Ler, copiar, excluir, traduzir, descrever imagem, melhorar resposta | gui |
| FUN-12 | Excluir mensagem | Pede confirmação, remove e atualiza o histórico | gui |
| FUN-13 | Manifesto e pacote | Manifesto válido para o NVDA e pacote gerado | run_all |
| FUN-14 | Compatibilidade de Python | Testes de unidade passam em 3.11, 3.12 e 3.13 | run_all |
| FUN-15 | Desinstalação de verdade | Tokens, histórico e cópia de atualização apagados | update |
| FUN-16 | Atualização detectada | Pela pasta da nova versão ou pelo estado do NVDA; tokens e histórico mantidos | update |
| FUN-17 | Atualização a partir das versões 1.0.0 a 1.4.0 | A cópia feita na instalação é restaurada quando a nova versão inicia | update |
| FUN-18 | Restauração segura | Nunca sobrescreve um token ou conversa mais novos | update |
| FUN-19 | Primeira instalação e falhas | Sem cópia desnecessária; falha na cópia não bloqueia a instalação | update |
| FUN-21 | Enviar feedback | Botão pede confirmação ("Dar feedback" ou "Cancelar"); só Dar feedback abre o formulário numa nova aba; falha do navegador mostra o endereço | gui |
| FUN-20 | Conversa atual em ramo | "Conversa atual (N mensagens)" recolhe e expande, abre quando chega resposta | gui |

## 6. Casos de teste de acessibilidade (ACE)

Referências: WCAG 2.2 nível AA, guia de complementos do NVDA e as práticas de acessibilidade do Windows.

| ID | Caso | Resultado esperado |
|---|---|---|
| ACE-01 | Nome acessível | Todo controle que recebe foco tem rótulo (texto antes dele ou o próprio texto, nos botões) |
| ACE-02 | Atalhos com Alt | Na janela de conversa e na tela de conexão, todo botão e rótulo tem letra de atalho, sem repetição, em inglês e português. Nas Configurações, os botões repetidos por IA não têm letras suficientes, então cada botão precisa de nome único (por exemplo, "Testar conexão do Gemini") |
| ACE-03 | Ordem de tabulação | IA, Modelo, Conversa, Pergunta, Anexar, Enviar, demais botões; Shift+Tab da Pergunta vai à Conversa |
| ACE-04 | Controles escondidos | Não entram na ordem de tabulação |
| ACE-05 | Teclado | Todas as funções funcionam só pelo teclado (Enter, Aplicações, Delete, Esc, setas) |
| ACE-06 | Anúncios | Envio, resposta, erro, anexo, exclusão, tradução, abertura de conversa e cancelamento são falados |
| ACE-07 | Foco | Depois de cada ação o foco fica em um controle da janela |
| ACE-08 | Contraste | Texto 4,5:1 e indicadores 3:1 |
| ACE-09 | Alto contraste | Tema desligado no alto contraste do Windows |
| ACE-10 | Cor não é a única informação | A linha de situação tem texto para cada estado |
| ACE-11 | Janela de leitura | HTML com títulos, listas e tabelas reais |
| ACE-12 | Menus | Itens com letra de atalho, sem repetição |
| ACE-13 | Texto maior | Opção aumenta as fontes |
| ACE-14 | Títulos de janela | Toda janela tem título próprio |
| ACE-15 | Comentários para tradutores | Toda frase traduzível tem comentário "Translators:" |
| ACE-16 | Tradução completa | Toda frase da interface traduzida para pt_BR, com os mesmos marcadores |
| ACE-17 | Fala limpa | Símbolos de Markdown removidos da leitura quando a opção está ligada |
| ACE-18 | Mensagens longas | Item da lista resumido, texto completo na janela de leitura |
| ACE-19 | Ramos da árvore | Conversas anteriores e Conversa atual dizem quantos itens têm; Enter e setas expandem e recolhem |

## 7. Casos de teste de vulnerabilidade (SEG)

Referências: OWASP Top 10, OWASP ASVS (armazenamento, comunicação, validação de entrada) e as recomendações da NV Access para complementos.

| ID | Caso | Resultado esperado |
|---|---|---|
| SEG-01 | Token em repouso | Arquivo de credenciais sem o token em texto puro; nada no nvda.ini |
| SEG-02 | Vazamento de token | Token nunca aparece no log, na fala, em mensagens de erro nem no histórico |
| SEG-03 | TLS | Verificação de certificado e de nome do servidor ligadas; nenhum atalho que desligue |
| SEG-04 | Tempo limite | Toda requisição tem tempo limite |
| SEG-05 | Endereços | Endereços padrão só em HTTPS |
| SEG-06 | Injeção de HTML | Scripts, eventos, links `javascript:` e `data:` e nomes de arquivo maliciosos não chegam à janela de leitura |
| SEG-07 | Travessia de pasta | Identificador de conversa com `../` é recusado |
| SEG-08 | Histórico em repouso | Conversas e anexos criptografados no disco |
| SEG-09 | Bomba zip | Documento compactado que explode ao abrir é recusado sem consumir memória |
| SEG-10 | Expansão de entidades XML | Documento com "billion laughs" não trava o NVDA |
| SEG-11 | Entidade externa XML (XXE) | Arquivos do computador não são lidos por um documento malicioso |
| SEG-12 | Injeção no endereço da API | Nome de modelo com `/` ou `?` não altera o endereço |
| SEG-13 | Análise estática | `bandit` sem problemas de severidade média ou alta sem justificativa |
| SEG-14 | Funções perigosas | Nenhum eval, exec, pickle, shell ou subprocess no complemento |
| SEG-15 | Telas seguras | Complemento desativado na tela de logon e no controle de conta |
| SEG-16 | Desinstalação | Tokens e histórico apagados |
| SEG-17 | Tamanho de anexo | Arquivo acima do limite recusado antes de ser lido |
| SEG-18 | Resposta gigante | Resposta acima do limite é recusada sem esgotar a memória |
| SEG-19 | Redirecionamento | A chave de API nunca é reenviada a outro endereço por redirecionamento |
| SEG-20 | Captura de tela | Só acontece por comando explícito do usuário |
| SEG-21 | Tamanho dos detalhes de erro | Detalhes de erro limitados, sem inundar a fala |
| SEG-22 | Endereços abertos no navegador | Só endereços fixos em HTTPS: formulário de feedback e páginas de token |

## 8. Critérios de aprovação

* **Uma versão só pode ser publicada com 0 falhas** em todas as suítes.
* Falha de SEG ou ACE é sempre bloqueante.
* Cada problema encontrado vira um item no relatório de problemas (`reports/PROBLEMAS-<versão>.md`), com ID do teste, gravidade, causa e correção.

## 9. Processo a cada nova versão

1. Atualizar `version` no `addon/manifest.ini` e o `CHANGELOG.md`.
2. Rodar `python tests/run_all.py` (no Linux com `python3-wxgtk4.0` e `xvfb`; a automação do GitHub faz o mesmo).
3. Se houver falhas: registrar em `reports/PROBLEMAS-<versão>.md`, corrigir e rodar de novo até 0 falhas.
4. Guardar `reports/execucoes.json` e `reports/ULTIMA-EXECUCAO.md` no commit da versão.
5. Só então criar a tag `v<versão>`. A automação do GitHub roda tudo de novo e não publica a versão se algo falhar.
