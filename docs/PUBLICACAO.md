# Como publicar o NVDAIAs na Loja de Complementos do NVDA

A Loja de Complementos do NVDA é alimentada pelo repositório público `nvaccess/addon-datastore`, no GitHub. A publicação é feita por um formulário (issue) nesse repositório, que aponta para o arquivo `.nvda-addon` hospedado em algum endereço https. O caminho mais simples é usar o próprio GitHub para hospedar o código e o arquivo.

## 1. Teste no seu NVDA antes de publicar

Siga o roteiro de `docs/TESTES.md`, na parte "Teste no Windows com o NVDA". Os testes automáticos rodam fora do Windows; só o teste no seu computador confirma a criptografia dos tokens (DPAPI), a captura de tela e as teclas no Windows de verdade.

## 2. Crie o repositório no GitHub

1. Entre em github.com e crie um repositório público chamado `NVDAIAs`.
2. Se o seu usuário do GitHub não for `weliveiracruz`, troque o endereço na linha `url` do arquivo `addon/manifest.ini` pelo endereço do seu repositório. O endereço precisa começar com `https://`.
3. Envie a pasta do projeto para o repositório. No Prompt de Comando, dentro de `C:\git\ADDONS NVDA\NVDAIAs`:

```
git remote add origin https://github.com/SEU-USUARIO/NVDAIAs.git
git push -u origin main
```

O projeto já vem com o histórico do git iniciado e o primeiro commit feito.

## 3. Gere a versão (release)

O projeto tem uma automação do GitHub (`.github/workflows/release.yml`) que roda todos os testes, gera o pacote e cria a página de versão com o arquivo para download. Para disparar, crie uma tag com o número da versão:

```
git tag v1.0.0
git push origin v1.0.0
```

Em alguns minutos, a aba **Releases** do repositório terá a versão 1.0.0 com o arquivo `NVDAIAs-1.0.0.nvda-addon`. O endereço de download fica assim:

`https://github.com/SEU-USUARIO/NVDAIAs/releases/download/v1.0.0/NVDAIAs-1.0.0.nvda-addon`

Alternativa sem automação: rode `python build.py` (precisa do Python instalado no Windows), crie a release manualmente na aba Releases do GitHub e anexe o arquivo de `dist\`.

## 4. Envie para a Loja

1. Abra `https://github.com/nvaccess/addon-datastore/issues/new/choose` e escolha **Add-on registration**.
2. Preencha:
   * **Download URL**: o endereço do passo 3 (precisa começar com `https://` e terminar com `.nvda-addon`).
   * **Source URL**: `https://github.com/SEU-USUARIO/NVDAIAs`
   * **Publisher**: o seu nome, por exemplo `Wellington Cruz`.
   * **License name**: `GPL v2`; **License URL**: `https://www.gnu.org/licenses/old-licenses/gpl-2.0.html`
   * **Channel**: `stable`.
3. Envie. Uma automação valida o pacote (manifesto, versões do NVDA e verificação de vírus no VirusTotal) e abre um pull request.
4. Como é o primeiro complemento deste publicador, a equipe da NV Access aprova manualmente. O prazo informado é de até duas semanas. Acompanhe os comentários no issue: se a validação apontar erro, corrija, gere uma nova versão e envie de novo.
5. Depois de aprovado, o NVDAIAs aparece na Loja de Complementos (menu do NVDA > Ferramentas > Loja de complementos).

## 5. Próximas versões

1. Atualize o número em `version` no `addon/manifest.ini` (por exemplo `1.0.1`), o `changelog` do manifesto e o `CHANGELOG.md`.
2. Quando sair uma nova versão do NVDA, teste e atualize `lastTestedNVDAVersion`. A primeira versão de cada ano do NVDA (2027.1, por exemplo) costuma quebrar a compatibilidade dos complementos: o NVDAIAs só será aceito nela depois de testado e com `lastTestedNVDAVersion` atualizado.
3. Faça commit, crie a tag (`git tag v1.0.1` e `git push origin v1.0.1`) e envie o novo endereço de download pelo mesmo formulário **Add-on registration**. Atualizações de um publicador já aprovado normalmente não passam por nova aprovação manual.

## Observações para a revisão

* A pasta `addon` segue a estrutura padrão de complementos do NVDA: `manifest.ini`, `globalPlugins/NVDAIAs/`, `doc/<idioma>/readme.html`, `locale/pt_BR/` (tradução da interface e do manifesto) e `installTasks.py`.
* O código não usa bibliotecas externas nem DLLs: só a biblioteca padrão do Python e os módulos do próprio NVDA. Por isso funciona no NVDA 64 bits (2026.1 em diante) e nas versões anteriores a partir da 2024.1.
* O complemento fica desativado nas telas seguras do Windows, como recomenda a NV Access.
* O código foi escrito com auxílio de IA, e o readme informa isso, como outros autores têm feito a pedido da revisão da Loja.
