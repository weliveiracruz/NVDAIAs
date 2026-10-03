# Instruções para quem trabalha neste repositório (pessoas e agentes de IA)

## Regra obrigatória: testes a cada nova versão

Toda nova versão do NVDAIAs, ou seja, toda mudança no campo `version` de `addon/manifest.ini`, **precisa** passar pelo processo do SDD de testes (`docs/SDD-TESTES.md`, seção 9) antes de ser publicada:

1. Atualize `version` e `changelog` em `addon/manifest.ini` e `addon/locale/pt_BR/manifest.ini`, e também o `CHANGELOG.md`.
2. Escreva ou atualize os testes das funções novas ou alteradas:
   * funcionais em `tests/test_pure.py` ou `tests/test_gui.py`;
   * de acessibilidade em `tests/test_accessibility.py`;
   * de vulnerabilidade em `tests/test_security.py`;
   * e acrescente os casos novos nas tabelas do `docs/SDD-TESTES.md`.
3. Rode todas as suítes: `python3 tests/run_all.py --note "o que mudou"`. Precisa de Linux com `python3-wxgtk4.0`, `xvfb`, `gettext` e `pip install bandit`.
4. Se algo falhar:
   * registre cada problema em `reports/PROBLEMAS-<versão>.md` (ID do teste, gravidade, causa e correção);
   * separe os problemas do complemento (P-xx) dos problemas dos testes (T-xx);
   * corrija e rode de novo até chegar a **0 falhas**.
5. Gere `reports/RELATORIO-TESTES-<versão>.md` com: testes existentes, aprovados, falhas, quantos foram corrigidos e quantas execuções foram feitas. Os números saem de `reports/execucoes.json`.
6. Faça commit de `reports/execucoes.json`, `reports/ULTIMA-EXECUCAO.md` e dos relatórios junto com a versão.
7. Só então crie a tag `v<versão>`. A automação do GitHub (`.github/workflows/release.yml`) roda todas as suítes de novo e **não publica** a versão se algum teste falhar.

Nunca apague nem edite à mão execuções antigas em `reports/execucoes.json`: o histórico conta quantas vezes os testes foram executados.

## Outras regras do projeto

* Código só com a biblioteca padrão do Python e os módulos do NVDA: sem dependências externas e sem DLLs.
* Indentação com tabulação, como no código do NVDA.
* Todo texto da interface passa por `_()`, com um comentário `# Translators:` na linha anterior e o texto começando na mesma linha de `_(`, e é traduzido em `addon/locale/pt_BR/LC_MESSAGES/nvda.po`.
* Letras de atalho (&) únicas em cada janela, em inglês e em português.
* Cores só pelos tokens de `addon/globalPlugins/NVDAIAs/design/tokens.json`, com o contraste verificado por `tests/test_theme.py`.
* Nunca registrar tokens no log, na fala ou em mensagens de erro.
