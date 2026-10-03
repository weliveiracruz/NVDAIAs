# Relatório de problemas – versão 1.4.0

Problemas encontrados pelas suítes do SDD (`docs/SDD-TESTES.md`) nas execuções 1 e 2 de 2026-10-03, antes de qualquer correção no complemento. As contagens de cada execução estão em `reports/execucoes.json`.

## Resumo

| | Quantidade |
|---|---|
| Problemas no complemento | 8 (2 altos, 5 médios, 1 baixo) |
| Problemas nos próprios testes | 4 |
| Execução 1 | 350 testes, 343 aprovados, 7 falhas; a suíte de acessibilidade parou no meio |
| Execução 2 (testes corrigidos, complemento ainda sem correção) | 374 testes, 366 aprovados, 8 falhas |

## Problemas no complemento

| ID | Teste | Gravidade | Problema | Correção |
|---|---|---|---|---|
| P-01 | ACE-16, ACE-02 (tradução) | Média | Os textos novos do menu de ações (botão "Ações da mensagem", idiomas, "Copiar", "Abrir esta conversa") não estavam traduzidos. Na interface em português, Alt+I ficou repetido em "&IA" e "Act&ions for this message". | Traduzir todos os textos, com o atalho Alt+E para "Açõ&es da mensagem". |
| P-02 | ACE-15 | Baixa | 18 textos traduzíveis sem comentário para tradutores. O comentário ficava antes de `_(` com o texto na linha seguinte, e o `xgettext` não o associava. Além disso, os 12 idiomas compartilhavam um único comentário. | Colocar o texto na mesma linha de `_(`, um comentário para cada idioma e comentários separados para o título e o subtítulo da tela Conectar conta (dois textos na mesma linha só recebiam um comentário). |
| P-03 | ACE-02 (Configurações) | Média | Os 12 botões dos grupos de IA ("Abrir página para gerar o token", "Testar conexão", "Remover token salvo" e "Atualizar lista de modelos", três vezes cada) não tinham tecla de atalho e tinham nomes idênticos nos três grupos. Ao tabular, o leitor de telas dizia "Testar conexão" sem dizer de qual IA. | Nome único em cada botão, com o nome da IA (por exemplo, "Testar conexão do Gemini"). Não há letras suficientes para dar atalho único a 12 botões repetidos, então o critério ACE-02 das Configurações passou a ser "nome único para cada botão". O SDD foi atualizado. |
| P-04 | SEG-09 | **Alta** | Bomba zip: um .docx de 79 KB que se expande para 80 MB era lido inteiro na memória do NVDA, aceito e cortado. Com arquivos maiores, isso pode esgotar a memória e travar o leitor de telas. | Antes de ler, verificar o tamanho descompactado (no máximo 40 MB no total e por arquivo interno) e a taxa de compressão. |
| P-05 | SEG-19 | **Alta** | Redirecionamento: nas requisições GET (Testar conexão, Atualizar lista de modelos), uma resposta 307 fazia o Python reenviar a chave de API (cabeçalhos `Authorization` e `x-api-key`) para outro endereço, até sem HTTPS. | Recusar qualquer redirecionamento. As APIs não redirecionam, e um redirecionamento vira erro de servidor. |
| P-06 | SEG-18 | Média | Não havia limite para o tamanho da resposta: uma resposta gigante seria lida inteira na memória. | Ler a resposta em blocos, com limite de 32 MB. |
| P-07 | SEG-13 (bandit B310) | Média | A função que abre a conexão aceitava qualquer esquema de endereço (`file://`, `ftp://`) se o endereço base fosse alterado. | Aceitar só `https://`. O `http://` é aceito apenas para o próprio computador (127.0.0.1 e localhost, usados nos testes). |
| P-08 | SEG-13 (bandit B314) | Média | O XML dos documentos (Word, Excel, PowerPoint, OpenDocument) era analisado sem bloquear DTD e entidades. A proteção contra "billion laughs" e XXE dependia da versão da biblioteca expat embutida no Python do NVDA. | Recusar XML com `<!DOCTYPE` ou `<!ENTITY` antes de analisar. Documentos do Office não usam DTD. |

## Problemas nos próprios testes

| ID | Teste | Problema | Correção |
|---|---|---|---|
| T-01 | test_theme (ordem de tabulação) | A expectativa não incluía o botão novo "Ações da mensagem". | Expectativa atualizada. |
| T-02 | test_accessibility | O teste usava o menu depois de destruído (`RuntimeError`), e a suíte parava no meio. | O teste passou a guardar os itens do menu ao abrir. |
| T-03 | SEG-09 | **Falso positivo:** o documento de teste tinha só espaços, recusado por estar "vazio", não pelo tamanho. Isso escondia o problema P-04. | Documento de teste com texto real. |
| T-04 | SEG-19 | Testava só POST, que o Python não redireciona. Isso escondia o problema P-05. | Passou a testar também GET (Testar conexão). |

## Situação

Todos os 8 problemas do complemento e os 4 problemas dos testes foram corrigidos. P-01 e P-03 a P-08 foram confirmados na execução 3; P-02 só ficou completo na execução 4, porque o subtítulo da tela Conectar conta ainda estava sem comentário na execução 3. O relatório final, com as contagens, está em `reports/RELATORIO-TESTES-1.4.0.md`.
