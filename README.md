<p align="center">
  <img src="docs/images/logo.png" width="200" alt="Nexo">
</p>

<h1 align="center">Nexo<br><sub><sup><sup><sub>Copyright (©) 2026 Erik Pimenta</sub></sup></sup></sub></h1>

<p align="center">
  Plataforma de agentes de IA em que cada agente responde só com a própria base de conhecimento (PDF, Word, EPUB, PowerPoint, planilhas, textos e mais)<br>
  e pode atender clientes pelo WhatsApp. Cada resposta cita o trecho e a página de onde saiu. Se a informação não estiver na base, o Nexo diz que não encontrou.
</p>

<p align="center">
  <b>Versão 3.0.0</b><br>
  Aplicativo para Windows (Nexo-Setup.exe) · pywebview + WebView2 · PyInstaller · Inno Setup · Python 3.11+ · FastAPI · LlamaIndex · ChromaDB ou Qdrant · Reranking HuggingFace ou Cohere · Ollama, OpenAI ou compatíveis (Groq, OpenRouter, Gemini, LM Studio) · WhatsApp (Evolution API ou Cloud API) · Widget para sites · API compatível com OpenAI · React 19 · TypeScript
</p>

---

> **Manual completo:** [`Manual-Nexo.pdf`](Manual-Nexo.pdf) explica a instalação do aplicativo para Windows, o assistente de configuração, cada tela, os agentes, as bases de conhecimento, o WhatsApp, o widget para sites, a API compatível com OpenAI, as integrações, a arquitetura, a API, a avaliação da recuperação e a solução de problemas, passo a passo (cópia em [`docs/`](docs/Manual-Nexo.pdf)).

> **Banco de dados:** [`Banco-de-Dados-Nexo.pdf`](Banco-de-Dados-Nexo.pdf) traz o diagrama de relacionamentos, o diagrama completo da arquitetura de dados (todas as tabelas com todas as colunas, as ligações com as contas, o banco vetorial, os arquivos e o aplicativo), todas as tabelas com campos, tipos, chaves e restrições (inclusive bases, agentes, WhatsApp e widgets), os índices, a migração automática, o banco vetorial e a troca segura de embeddings, os arquivos de contas, ajustes e segredos, as consultas do painel de qualidade e como trocar o SQLite por outro banco (cópia em [`docs/`](docs/Banco-de-Dados-Nexo.pdf)).

<p align="center">
  <img src="docs/images/tela-chats.png" alt="Chats com vários agentes lado a lado">
</p>

## Novidades da 3.0

A 3.0.0 transforma o Nexo num aplicativo para Windows. Ele é instalado pelo `Nexo-Setup.exe`, aparece na pesquisa do Windows e no menu Iniciar e abre numa janela própria, sem navegador. A versão web que abria no navegador, os scripts `iniciar.cmd` e `iniciar.sh` e o Docker saíram.

| Novidade | Como funciona |
|---|---|
| **Instalador para Windows** | `Nexo-Setup-3.0.0.exe` instala por usuário, sem pedir administrador, em `%LOCALAPPDATA%\Programs\Nexo`, com atalho no menu Iniciar (encontrado pela pesquisa do Windows), atalho opcional na área de trabalho, `Win + R` → `nexo` e desinstalador em **Configurações → Aplicativos**. |
| **Janela própria** | O painel abre numa janela do Windows (WebView2). O servidor interno sobe só em `127.0.0.1`, numa porta livre, e o painel só é entregue para a janela do aplicativo: aberto num navegador, ele responde que o Nexo abre só pelo aplicativo. |
| **Já vem configurado** | Na primeira abertura, o Nexo cria a **Base de teste** e o **Agente de teste**, indexa os arquivos de exemplo e usa o **Llama 3.1 pelo Ollama**. O assistente de configuração fica disponível em **Sistema e conta**. |
| **Arquivos na janela** | PDFs abrem numa janela do Nexo, já na página citada; os outros formatos abrem no programa padrão do Windows. Downloads (backup, exportações) pedem onde salvar. |
| **Restaurar pela tela** | **Sistema e conta → Manutenção → Restaurar backup** escolhe o `.zip`, fecha o Nexo, guarda os dados atuais numa cópia e abre de novo com o backup. |
| **Instância única** | Abrir o Nexo de novo traz a janela que já está aberta para a frente. Fechar com documentos na fila pede confirmação; a indexação continua na próxima abertura. |
| **Dados do usuário** | Tudo fica em `%LOCALAPPDATA%\Nexo` (`data`, `modelos`, `logs`). Atualizar o aplicativo não mexe nos dados; desinstalar pergunta se deve apagá-los. |
| **Janela centralizada** | Abre no centro do monitor, no tamanho que cabe na área útil, inclusive em telas pequenas ou com escala de 125% e 150%. |
| **Tema claro e escuro** | Botão de tema na entrada, no assistente, no menu e na paleta de comandos. Até a primeira troca, segue o Windows; a barra de título da janela acompanha. |
| **Zoom de 75%** | A interface abre no equivalente a 75% de um navegador. `Ctrl` + roda do mouse ajusta na hora. |
| **Ícone** | Quadrado preto com bordas levemente arredondadas e o N branco, em todos os tamanhos do Windows. |
| **Release automática** | Publicar uma release no GitHub dispara o workflow `desktop.yml`, que compila, verifica o pacote e anexa o `Nexo-Setup-<versão>.exe` à release. |

## Novidades da 2.4

A 2.4.0 deixa o Nexo fácil de instalar, configurar, manter e integrar. Um assistente guia o primeiro acesso, o provedor de IA e as chaves passam a ser escolhidos pela tela, com teste de conexão, os agentes chegam a qualquer site com uma linha de código e a qualquer ferramenta que fale com a API da OpenAI, e o backup fica automático. A identidade visual continua a mesma, e o banco da 2.3 é migrado sozinho na primeira execução.

| | O que mudou |
|---|---|
| **Assistente de configuração** | No primeiro acesso, o admin troca a senha padrão (obrigatório), escolhe a inteligência com **Testar conexão**, define o endereço público, liga o backup e vê a lista de próximos passos. Também por `python -m nexo configurar`. |
| **Provedor de IA pela tela** | Ollama (com a lista dos modelos instalados), OpenAI, Groq, OpenRouter, Google Gemini, LM Studio ou qualquer serviço compatível com a OpenAI, além de embeddings e reranking, em **Sistema e conta → Ajustes**, sem editar o `.env` nem reiniciar. |
| **Chaves protegidas** | As chaves dos provedores ficam em `data/segredos.json` (permissão 0600), nunca voltam para a tela e entram no registro de atividades só como "(alterada)". |
| **Troca de embeddings segura** | O Nexo guarda qual modelo gerou os vetores; ao trocar, pela tela ou pelo `.env`, apaga a coleção e reindexa o acervo sozinho, sem misturar vetores incompatíveis. |
| **Widget para sites** | Um botão de conversa com o agente em qualquer site com uma linha `<script>`, sites autorizados, limite por visitante, cor, posição, boas-vindas, fontes, pausa e troca da chave. |
| **API compatível com OpenAI** | `GET /v1/models` e `POST /v1/chat/completions` (com streaming): n8n, Make, Typebot, Flowise, Dify, Open WebUI, LibreChat, LangChain e os SDKs oficiais usam os agentes como modelos. |
| **Backup automático** | A cada 6, 12 ou 24 horas ou toda semana, guardando os mais recentes em `data/backups`, com **Fazer um agora** e download pela tela. |
| **Primeiros passos** | O que falta para o Nexo trabalhar sozinho, com o progresso no topo do menu e o atalho para cada tela. |
| **Instalador mais esperto** | `iniciar.cmd` e `iniciar.sh` conferem o Python 3.11+, reinstalam as dependências quando `requirements.txt` muda e abrem o navegador quando o servidor está pronto. |
| **Porta ocupada** | Se o Nexo já estiver rodando, o script só abre o navegador; se outro programa usar a porta, diz como trocar. |
| **Linha de comando** | `python -m nexo configurar` (assistente no terminal) e `python -m nexo senha <usuario>`. |
| **Interface mais leve** | As telas carregam sob demanda: o arquivo principal da interface caiu de cerca de 500 KB para 270 KB. |

## Novidades da 2.3

A 2.3.0 cuida de quem opera o Nexo e de quem usa todo dia: ajustes pela tela, diagnóstico, manutenção, backup, registro de atividades, linha de comando e Docker, além de conversas fixadas, respostas prontas no WhatsApp, importação por link e uma base de teste pronta. A identidade visual continua a mesma, e o banco da 2.1 ou da 2.2 é migrado sozinho na primeira execução.

| | O que mudou |
|---|---|
| **Ajustes pela tela** | Em **Sistema e conta → Ajustes**, o administrador muda modelo, temperatura, cortes de relevância, trechos, cadastro, duração da sessão, limite de perguntas e retenção sem editar o `.env` nem reiniciar. Os valores ficam em `data/ajustes.json`. |
| **Diagnóstico** | Confere banco, disco, senha padrão, segredo, modelos, banco vetorial, arquivos ausentes, itens com falha ou desatualizados, webhooks e WhatsApp, com o que fazer em cada aviso. Também por `python -m nexo diagnostico`. |
| **Manutenção e backup** | Reindexar falhas, desatualizados ou tudo, limpar arquivos e vetores órfãos, apagar conversas antigas, compactar o banco e baixar um backup `.zip`, restaurável por `python -m nexo restaurar`. |
| **Registro de atividades** | Entradas, tentativas falhas e cada criação, alteração ou exclusão de bases, agentes, documentos, chaves, webhooks, conexões, contas e ajustes, com conta, IP, filtros e CSV. |
| **Base de teste** | Um clique em **Bases de conhecimento** (ou `python -m nexo base-de-teste`) cria uma base com arquivos de exemplo em PDF, Markdown, HTML, CSV, TXT e JSON e o **Agente de teste**, com perguntas sugeridas. |
| **Importar de um link** | Traz uma página ou arquivo publicado para a base e atualiza quando ele mudar. Endereços da rede interna são bloqueados, inclusive por redirecionamento. |
| **Trechos indexados** | Mostra como cada arquivo foi dividido, com busca por palavra e link para a página do PDF. Itens indexados com outra configuração aparecem como **desatualizados**. |
| **Conversas** | Fixar conversas no topo, rascunho guardado por conversa, impressão limpa e, no **não ajudou**, o campo **O que faltou nesta resposta?**. |
| **Agentes** | Perguntas sugeridas que aparecem como atalhos no começo de cada chat e **Duplicar** para criar variações. |
| **WhatsApp** | Respostas prontas da equipe com `{nome}` e `{telefone}`, pelo botão ou digitando `/` na caixa, e o contador de clientes aguardando no menu. |
| **Painel por agente** | Perguntas, taxa de resposta, tempo e avaliações de cada agente, filtro por agente no painel e no CSV, e os comentários das avaliações. |
| **Chaves de API** | Permissão **completa**, **só consulta** ou **só alimentar bases** e validade de 30, 90 ou 365 dias. |
| **Proteção da API** | Limite de perguntas por minuto por conta (HTTP 429 com `Retry-After`) e CORS configurável. |
| **Operação** | Linha de comando `python -m nexo`, logs em texto ou JSON com o id do pedido, métricas para o Prometheus, `Dockerfile` e serviço no `docker-compose.yml`, e CI com `ruff` e build da imagem. |
| **Uso diário** | Atalhos `Alt + N`, `B`, `D` e `W`, a tecla `?` com a lista de atalhos e aviso quando o servidor sai do ar. |

## Novidades da 2.2

A 2.2.0 deixa as respostas mais rápidas de acompanhar, a gestão de contas completa pela tela e o acervo mais fácil de manter. A identidade visual, as cores e as fontes continuam as mesmas, nada no banco relacional muda e quem vem da 2.1 só precisa atualizar e recompilar a interface.

| | O que mudou |
|---|---|
| **Respostas em tempo real** | A resposta aparece enquanto o modelo escreve, nas Conversas e nos Chats com agentes (Server-Sent Events). O botão de parar (ou `Esc`) interrompe sem gravar nada e devolve a pergunta para a caixa de texto. |
| **Refazer resposta** | Cada resposta ganhou o botão **Refazer**: o Nexo busca de novo com o mesmo histórico e troca a resposta no lugar, com fontes novas. |
| **Contas pela tela** | Administradores criam contas (mesmo com o cadastro fechado) e redefinem senhas em **Sistema e conta**. Cada pessoa edita o próprio nome. |
| **Sessões mais seguras** | Trocar ou redefinir a senha encerra as outras sessões abertas, e o botão **Sair dos outros dispositivos** faz o mesmo sem trocar a senha. A nova senha precisa ser diferente da atual. |
| **Novos formatos** | EPUB (livros, capítulo a capítulo na ordem de leitura), PowerPoint (`.pptx`, um trecho por slide), Excel (`.xlsx`, linhas de cada planilha) e OpenDocument (`.odt`). Arquivos compactados grandes demais depois de abertos são recusados. |
| **Ações em lote** | Em **Documentos**, selecione vários itens para reindexar, mover de base ou excluir de uma vez. |
| **Busca nas conversas** | O filtro da lista de conversas procura também no conteúdo das perguntas e respostas. |
| **Exportar o painel** | O **Painel de qualidade** baixa as perguntas do período em CSV, com resposta, avaliação, tempo, modelo e fontes. |
| **Webhooks confiáveis** | Até 3 tentativas em falhas de rede, tempo esgotado, HTTP 429 e 5xx, com o mesmo `X-Nexo-Delivery` para descartar duplicatas e `X-Nexo-Attempt` com o número da tentativa. |
| **Operação** | Toda resposta da API traz `X-Request-ID` (reaproveita o enviado pelo cliente) e `GET /api/health/ready` confere o banco para balanceadores e orquestradores. |
| **Documentação** | Manual e PDF do banco atualizados e gerados por `scripts/docs/gerar_pdfs.py`. |

## Novidades da 2.1

A 2.1.0 transformou o Nexo numa plataforma de agentes, com a identidade visual "caixa única" (a mesma do [Bento](https://github.com/ravelroot/Data-Driven-Admin-Panel)): agentes com instruções próprias, bases de conhecimento com arquivos e textos, vários chats lado a lado, caixa de entrada do WhatsApp (Evolution API, API oficial da Meta ou simulador), tutorial de primeiro acesso e `bot_id` / `base_id` nas integrações.

## O que o Nexo faz

- **Agentes de IA** com instruções, saudação e resposta própria para quando não souber, cada um preso à sua base de conhecimento.
- **Bases de conhecimento** com PDF, DOCX, EPUB, PPTX, XLSX, ODT, TXT, MD, CSV, JSON, HTML e textos digitados, editáveis a qualquer hora, com aba para testar a busca e aba para integrar.
- **Chats com vários agentes** em abas ou lado a lado.
- **Atendimento pelo WhatsApp** com resposta automática do agente, passagem para atendente, assumir e devolver a conversa, sugestão de resposta e simulador.
- **Tutorial de primeiro acesso**, guardado por conta.
- **Envio de arquivos** por arrastar e soltar, com fila de indexação, detecção de duplicados por base, filtro, ordenação, renomear, mover, reindexar e excluir, um a um ou em lote.
- **Respostas com base estrita** nos documentos: o modelo recebe só os trechos recuperados e é instruído a citar cada afirmação com `[n]`.
- **Respostas em tempo real**, com botão para parar e botão para refazer a resposta.
- **Trechos auditáveis**: ao lado da resposta aparecem o documento, a página, a similaridade, a nota do reranker, os termos da pergunta marcados e o botão para abrir o PDF na página certa.
- **Escopo por conversa**: escolha quais documentos cada conversa consulta, ou converse com um agente, que consulta só a base dele.
- **Contexto da conversa**: perguntas como "e o passo seguinte?" são reescritas com o histórico antes da busca.
- **Busca nos trechos** sem LLM, para conferir o que o acervo diz e calibrar perguntas.
- **Painel de qualidade** com as perguntas que ficaram sem resposta, para saber qual PDF falta no acervo, e exportação das perguntas em CSV.
- **Integrações**: chaves de API, pergunta direta por HTTP, respostas em streaming, webhooks com novas tentativas e exportação de conversas.
- **Contas de acesso** com login pré-definido, cadastro próprio e gestão por administradores (criar, promover, redefinir senha e excluir), gravadas em `data/usuarios.json` com senhas em bcrypt. Trocar a senha encerra as outras sessões.
- **Avaliação** de cada resposta (útil / não ajudou) e script de medição de acerto da recuperação.
- **Identidade "caixa única"**, a mesma do [Bento](https://github.com/ravelroot/Data-Driven-Admin-Panel): fundo, menu e cabeçalhos impressos na mesa em `#F5F4F4`, conversa e trechos dividindo paredes finas dentro de uma só caixa branca, resumos na tampa preta, títulos e números em Bricolage Grotesque fina e condensada, textos em Instrument Sans e status como um ponto de cor. Paleta `#FFFFFF`, `#4D4B4B`, `#000000`, `#333232` e `#BAB7B6`.
- **Tema claro ou escuro** em todas as telas (segue o Windows até a primeira troca), layout responsivo para celular e atalhos de teclado. A logo é sempre em preto e branco.

## Como o Nexo evita alucinações

```mermaid
flowchart LR
    P[Pergunta<br/>chat, API ou WhatsApp] --> G{Agente?}
    G -- sim --> E[Escopo = documentos<br/>prontos da base do agente]
    G -- não --> C[Reescrita com o histórico]
    E --> C
    C --> B[Busca vetorial<br/>top_k trechos]
    B --> S{Similaridade<br/>mínima}
    S -- nada relevante --> N[Não encontrei]
    S --> R[Reranking<br/>HuggingFace ou Cohere]
    R --> T{Nota mínima<br/>do reranker}
    T -- nada relevante --> N
    T --> L[LLM com prompt estrito,<br/>instruções do agente<br/>e citações numeradas]
    L --> V[Verificação de fidelidade<br/>opcional]
    V --> A[Resposta + fontes]
    N -.-> W[Webhook<br/>question.unanswered]
    N -.-> H[WhatsApp: aguardando<br/>atendente]
```

1. **Dois cortes de relevância** (`NEXO_MIN_SIMILARITY` e `NEXO_MIN_RERANK_SCORE`). Se nenhum trecho passar, o modelo nem é chamado.
2. **Reranking** com cross-encoder: reordena os candidatos da busca vetorial pela relação real com a pergunta e só os `NEXO_TOP_N` melhores seguem.
3. **Prompt estrito** em português: usar só os trechos, citar `[n]`, responder exatamente "Não encontrei essa informação nos documentos selecionados." quando faltar base. As instruções de cada agente entram no prompt, mas não podem mudar essas regras; a frase de quando não souber é trocada pela do agente.
4. **Verificação de fidelidade** opcional (`NEXO_VERIFY_ANSWERS=true`) com o `FaithfulnessEvaluator` do LlamaIndex.
5. **Temperatura baixa** (0,1 por padrão).
6. **Lacunas visíveis**: toda pergunta sem resposta aparece no Painel de qualidade e pode disparar um webhook; no WhatsApp, o contato passa para a equipe.
7. **Base por agente**: cada agente só enxerga os documentos da própria base, o que evita misturar assuntos.

## Instalar no Windows

1. Baixe o `Nexo-Setup-3.0.0.exe` em [Releases](https://github.com/ravelroot/Retrieval-Augmented-QA-System/releases/latest) e abra. Se o Windows mostrar "O Windows protegeu o computador", clique em **Mais informações → Executar assim mesmo** (o instalador não é assinado digitalmente).
2. Siga o instalador. Ele não pede administrador e termina abrindo o Nexo.
3. Depois, abra pela pesquisa do Windows (digite **Nexo**), pelo menu Iniciar ou por `Win + R` → `nexo`.
4. Entre com `admin` / `Nexo@2026` e escolha uma senha nova.

Para as respostas com o **Llama 3.1**, instale o [Ollama](https://ollama.com/download/windows) e baixe o modelo uma vez:

```powershell
winget install --id Ollama.Ollama -e
ollama pull llama3.1
```

A primeira abertura já deixa a **Base de teste** e o **Agente de teste** prontos: abra **Chats com agentes** e pergunte, por exemplo, "Quanto tempo dura a garantia?". O modelo de embeddings e o reranker são baixados do HuggingFace na primeira indexação e na primeira pergunta e funcionam em CPU. Requisitos: Windows 10 1809 ou mais recente, 64 bits, com o Microsoft Edge WebView2 (já vem no Windows 11 e nos Windows 10 atualizados).

| Pasta | Conteúdo |
|---|---|
| `%LOCALAPPDATA%\Programs\Nexo` | O aplicativo (`Nexo.exe` e bibliotecas) |
| `%LOCALAPPDATA%\Nexo\data` | Banco, contas, ajustes, segredos, arquivos enviados, vetores e backups |
| `%LOCALAPPDATA%\Nexo\modelos` | Modelos baixados do HuggingFace |
| `%LOCALAPPDATA%\Nexo\logs` | `nexo.log`, com os registros do aplicativo |
| `%LOCALAPPDATA%\Nexo\janela.json` | Tema escolhido para a janela, a tela de abertura e a barra de título |
| `%LOCALAPPDATA%\Nexo\.env` | Opcional: variáveis avançadas (modelo em [`.env.example`](.env.example)) |

> Integrações: enquanto o Nexo está aberto, a API, o widget e os webhooks respondem no servidor interno (`http://127.0.0.1:8000` ou a próxima porta livre). Para o WhatsApp ou um widget em site público, deixe esse servidor alcançável (`NEXO_HOST` no `.env` e um túnel ou proxy) e defina `NEXO_PUBLIC_URL`. O painel continua só na janela do aplicativo.

> Vindo da 2.x? Pelo código da versão antiga, gere um backup (`python -m nexo backup --saida nexo.zip`) e, no aplicativo, use **Sistema e conta → Manutenção → Restaurar backup**.

### Gerar o instalador

Publicar uma release no GitHub gera e anexa o instalador sozinho (workflow [`desktop.yml`](.github/workflows/desktop.yml)). Para gerar no próprio computador, com **Python 3.12** e **Node.js 22** instalados:

```powershell
powershell -ExecutionPolicy Bypass -File desktop\build.ps1
```

O script cria `.venv-build`, instala as dependências, compila a interface, empacota o `dist\Nexo\Nexo.exe` com o PyInstaller, roda `Nexo.exe verificar` (módulos, servidor interno, painel fechado fora da janela, login, indexação, resposta e abertura de arquivo) e gera `desktop\saida\Nexo-Setup-3.0.0.exe` com o Inno Setup (instalado pelo `winget` se faltar). Com `-SemInstalador`, para no `Nexo.exe`.

| Arquivo | Papel |
|---|---|
| `nexo/desktop.py` | Janela, servidor interno, instância única, pasta de dados, abertura de arquivos, restauração e verificação do pacote |
| `desktop/nexo.spec` | Empacotamento do PyInstaller (interface, arquivos de exemplo, ícone e versão do `.exe`) |
| `desktop/nexo.iss` | Instalador do Inno Setup (menu Iniciar, pesquisa do Windows, `App Paths`, desinstalador) |
| `desktop/build.ps1` | Build completo no Windows |
| `desktop/nexo.ico` | Ícone do aplicativo e do instalador |

### Rodar pelo código-fonte

Para desenvolver, com Python 3.11+ e Node.js 20.19+:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
python -m nexo
```

`python -m nexo` abre a mesma janela do aplicativo, com os dados em `data/` (ou na pasta de `NEXO_DATA_DIR`) e o `.env` da pasta atual. Para mexer na interface com recarga automática, deixe o Nexo aberto e rode `npm run dev` em `frontend/`.

### Linha de comando

| Comando | Função |
|---|---|
| `python -m nexo` | Abre o aplicativo (janela e servidor interno) |
| `python -m nexo verificar [--saida arquivo.txt]` | Confere o pacote: módulos, servidor interno, painel fechado fora da janela, login, indexação, resposta e abertura de arquivo (no instalado: `Nexo.exe verificar --saida arquivo.txt`) |
| `python -m nexo configurar` | Assistente no terminal: senha do admin e provedor de IA, com teste de conexão |
| `python -m nexo senha <usuario>` | Redefine a senha de uma conta e encerra as sessões dela |
| `python -m nexo diagnostico [--completo]` | Confere banco, modelos, acervo, segurança e integrações |
| `python -m nexo backup [--saida arquivo.zip]` | Grava o backup |
| `python -m nexo restaurar arquivo.zip [--substituir]` | Restaura um backup (Nexo fechado) |
| `python -m nexo reindexar [--desatualizados \| --todos]` | Reindexa no terminal (Nexo fechado) |
| `python -m nexo base-de-teste` | Cria a Base de teste e o Agente de teste |
| `python -m nexo contas` · `versao` | Lista as contas e mostra a versão |

### Escolha um modo

No aplicativo instalado, o `.env` fica em `%LOCALAPPDATA%\Nexo\.env`. Tudo isso também se escolhe pela tela, no assistente de configuração ou em **Sistema e conta → Ajustes**, com um botão para testar a conexão antes de salvar.

| Modo | O que instalar | `.env` |
|---|---|---|
| **Local e gratuito** (padrão) | [Ollama](https://ollama.com) e `ollama pull llama3.1` | já vem configurado |
| **OpenAI** | uma chave de API | `NEXO_LLM_PROVIDER=openai`, `NEXO_LLM_MODEL=gpt-4o-mini`, `OPENAI_API_KEY=...` |
| **Compatível com OpenAI** | uma chave do serviço (Groq, OpenRouter, Gemini) ou o LM Studio aberto | `NEXO_LLM_PROVIDER=compativel`, `NEXO_OPENAI_BASE_URL=https://api.groq.com/openai/v1`, `NEXO_LLM_MODEL=...`, `OPENAI_API_KEY=...` |
| **Reranking Cohere** | uma chave de API | `NEXO_RERANKER=cohere`, `COHERE_API_KEY=...` |
| **Qdrant** | Qdrant local ou em nuvem | `NEXO_VECTOR_STORE=qdrant` e, para servidor, `NEXO_QDRANT_URL=...` |
| **Teste sem modelos** | nada | `NEXO_EMBED_PROVIDER=hash`, `NEXO_LLM_PROVIDER=extrativo`, `NEXO_RERANKER=none` |

No modo padrão, o modelo de embeddings (`intfloat/multilingual-e5-small`) e o reranker (`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`) são baixados do HuggingFace na primeira pergunta e funcionam em CPU.

O modo de teste usa um embedding léxico e devolve as frases mais relevantes dos trechos, sem LLM. Serve para validar a instalação e rodar os testes, não para uso real. As capturas de tela deste README foram feitas nesse modo.

## Login

| Usuário | Senha | Perfil |
|---|---|---|
| `admin` | `Nexo@2026` | Administrador |

Esse é o login pré-definido, criado quando `usuarios.json` não existe na pasta de dados. Ao entrar com ele, o Nexo exige uma senha nova antes de qualquer outra tela (a API responde 403 `PASSWORD_CHANGE_REQUIRED` até a troca) e abre o assistente de configuração. Na primeira entrada de cada conta, o tutorial mostra o caminho: base de conhecimento, agente, chats e WhatsApp. Qualquer pessoa pode criar a própria conta na tela de entrada (desligue com `NEXO_ALLOW_REGISTRATION=false`); com o cadastro fechado, um administrador cria as contas em **Sistema e conta → Contas**. Esqueceu a senha? Um administrador redefine na mesma tela, ou rode `python -m nexo senha <usuario>` pelo código-fonte.

## Telas

| | |
|---|---|
| <img src="docs/images/tela-assistente-ia.png" alt="Assistente de configuração"> | <img src="docs/images/tela-assistente-pronto.png" alt="Primeiros passos"> |
| **Assistente de configuração**: a inteligência escolhida num cartão, com teste de conexão | **Tudo pronto**: a lista de primeiros passos |
| <img src="docs/images/tela-widget-site.png" alt="Widget num site"> | <img src="docs/images/tela-widget.png" alt="Widget para sites"> |
| **Widget** num site, com as fontes | **Widget para sites**: o código para colar, os sites autorizados e o uso |
| <img src="docs/images/tela-openai.png" alt="API compatível com OpenAI"> | <img src="docs/images/tela-widget-celular.png" alt="Widget no celular" width="240"> |
| **API compatível com OpenAI**: Base URL, modelos e exemplos | **Widget no celular** |
| <img src="docs/images/tela-tutorial.png" alt="Tutorial"> | <img src="docs/images/tela-agentes.png" alt="Agentes"> |
| **Tutorial** de primeiro acesso | **Agentes**: cor, base, conversas e situação de cada agente |
| <img src="docs/images/tela-chats.png" alt="Chats com agentes"> | <img src="docs/images/tela-bases.png" alt="Bases de conhecimento"> |
| **Chats com agentes** em abas ou lado a lado | **Bases de conhecimento**: resumo na tampa preta e as abas Arquivos, Textos, Testar e Integrar |
| <img src="docs/images/tela-base-textos.png" alt="Textos da base"> | <img src="docs/images/tela-base-integrar.png" alt="Integrar a base"> |
| **Textos** escritos direto na base | **Integrar**: exemplos prontos com os ids da base e do agente |
| <img src="docs/images/tela-whatsapp.png" alt="WhatsApp"> | <img src="docs/images/tela-whatsapp-conexoes.png" alt="Conexões do WhatsApp"> |
| **WhatsApp**: caixa de entrada com o agente e a equipe | **Conexões**: provedor, agente, webhook e QR code |
| <img src="docs/images/tela-login.png" alt="Entrada"> | <img src="docs/images/tela-documentos.png" alt="Documentos"> |
| **Entrada** | **Documentos**: todo o acervo, com filtro por base, envio para a base escolhida e ações em lote |
| <img src="docs/images/tela-busca.png" alt="Busca nos trechos"> | <img src="docs/images/tela-painel.png" alt="Painel de qualidade"> |
| **Busca nos trechos** com os termos destacados | **Painel de qualidade** com as lacunas do acervo e exportação em CSV |
| <img src="docs/images/tela-integracoes.png" alt="Integrações"> | <img src="docs/images/tela-sistema.png" alt="Sistema e conta"> |
| **Integrações**: widget, API compatível com OpenAI, chaves de API, exemplos e webhooks | **Sistema e conta**: primeiros passos, pipeline de respostas, acervo e contas |
| <img src="docs/images/tela-nao-encontrado.png" alt="Pergunta sem resposta nos documentos"> | <img src="docs/images/tela-comandos.png" alt="Paleta de comandos"> |
| **Sem base nos PDFs**: o Nexo diz que não encontrou e sugere o próximo passo | **Paleta de comandos** (`Ctrl + K`) |
| <img src="docs/images/tela-ajustes.png" alt="Ajustes"> | <img src="docs/images/tela-diagnostico.png" alt="Diagnóstico"> |
| **Ajustes pela tela**, com o provedor de IA e o teste de conexão | **Diagnóstico** |
| <img src="docs/images/tela-manutencao.png" alt="Manutenção"> | <img src="docs/images/tela-atividades.png" alt="Registro de atividades"> |
| **Manutenção** com o backup automático | **Registro de atividades** |
| <img src="docs/images/tela-base-teste.png" alt="Base de teste"> | <img src="docs/images/tela-importar-link.png" alt="Importar de um link"> |
| **Base de teste** | **Importar de um link** |
| <img src="docs/images/tela-trechos.png" alt="Trechos indexados"> | <img src="docs/images/tela-avaliacao.png" alt="Comentário no não ajudou"> |
| **Trechos indexados** | **O que faltou nesta resposta?** |
| <img src="docs/images/tela-respostas-prontas.png" alt="Respostas prontas"> | <img src="docs/images/tela-painel-agentes.png" alt="Painel por agente"> |
| **Respostas prontas no WhatsApp** | **Painel por agente** |
| <img src="docs/images/tela-atalhos.png" alt="Atalhos"> | <img src="docs/images/tela-escuro.png" alt="Tema escuro"> |
| **Atalhos de teclado** | **Tema escuro** |
| <img src="docs/images/tela-celular.png" alt="Celular" width="240"> | |
| **Celular** | |

### Atalhos

| Tecla | Ação |
|---|---|
| `Ctrl + K` (ou `⌘ + K`) | Abre a paleta de comandos |
| `?` | Mostra a lista de atalhos |
| `Alt + N` · `Alt + B` · `Alt + D` · `Alt + W` | Nova conversa, Busca nos trechos, Documentos e WhatsApp |
| `/` | Volta para a caixa de pergunta; no WhatsApp, no começo da caixa, abre as respostas prontas |
| `Enter` | Envia a pergunta e a mensagem do WhatsApp |
| `Shift + Enter` | Quebra a linha na pergunta |
| `Esc` | Interrompe a resposta que está sendo escrita |
| `↑` `↓` `Enter` `Esc` | Navegam, abrem e fecham a paleta |
| `←` `→` `Esc` | Voltam, avançam e fecham o tutorial |

## Integrações

### Widget para sites

Em **Integrações → Widget para sites** (ou pelo ícone de globo no cartão do agente), escolha o agente, os sites autorizados, o título, a cor e o canto da tela. Copie a linha e cole antes de `</body>` no site, no rodapé do WordPress, no Wix ou numa tag do Google Tag Manager:

```html
<script src="https://nexo.suaempresa.com.br/widget.js" data-nexo="nxw_SUA_CHAVE_PUBLICA" async></script>
```

| Item | Como funciona |
|---|---|
| Sites autorizados | Um por linha: `www.loja.com.br`, `https://loja.com.br` ou `*.loja.com.br`. Vazio libera qualquer site. O próprio Nexo sempre pode, para o botão **Testar aqui**. |
| Limite | `NEXO_WIDGET_RATE_LIMIT` perguntas por minuto por visitante (10) e 20 vezes isso para o widget inteiro (429 com `Retry-After`). |
| Conversa | Fica no navegador do visitante; o Nexo conta perguntas e perguntas sem resposta, sem gravar a conversa. |
| Segurança | Shadow DOM, texto sempre tratado como texto, corpo limitado a 32 KB, chave pública própria (`nxw_`) que só pergunta a um agente; **Trocar a chave** invalida o código antigo. |
| Controle pelo site | `window.NexoWidget.open()`, `close()`, `toggle()`, `ask("pergunta")` e `reset()`; `data-open="true"` carrega aberto. |

### API compatível com OpenAI

Qualquer ferramenta que aceita um "Base URL" da OpenAI usa os agentes do Nexo: n8n, Make, Typebot, Flowise, Dify, Open WebUI, LibreChat, LangChain e os SDKs oficiais. Cada agente vira um modelo (`sofia-suporte`), e `nexo` consulta o acervo inteiro. Use uma chave de API com permissão **Só consulta**.

```python
from openai import OpenAI

cliente = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="nxk_SUA_CHAVE")
resposta = cliente.chat.completions.create(
    model="sofia-suporte",
    messages=[{"role": "user", "content": "Como faço a troca do filtro?"}],
)
print(resposta.choices[0].message.content)
```

A última mensagem `user` é a pergunta e as anteriores são o histórico; mensagens `system` são ignoradas, porque quem manda no tom é o agente e as regras de base estrita valem sempre. A resposta traz as fontes no fim do texto (quando o agente cita fontes) e em `nexo.sources`. `stream: true` devolve `chat.completion.chunk` e termina em `data: [DONE]`; os erros seguem o formato `{"error": {...}}` da OpenAI. No n8n: **Credentials → New → OpenAI**, com a chave e o Base URL `https://seu-nexo/v1`.

### Chaves de API

Crie uma chave em **Integrações → Chaves de API**. Ela aparece uma única vez (o servidor guarda só o SHA-256) e age em nome da sua conta, limitada pela permissão escolhida. Envie no cabeçalho `X-API-Key` (ou `Authorization: Bearer nxk_...`).

| Permissão | `scope` | O que libera |
|---|---|---|
| Completa | `full` | Tudo o que a conta pode fazer |
| Só consulta | `ask` | Perguntar, buscar e ler bases e agentes |
| Só alimentar bases | `feed` | Enviar arquivos, textos e links às bases |

Fora da permissão, a resposta é 403 `KEY_SCOPE`; chave vencida recebe 401 `API_KEY_EXPIRED`. Cada conta pode fazer até `NEXO_RATE_LIMIT` perguntas e buscas por minuto (60 por padrão); acima disso, 429 `RATE_LIMITED` com `Retry-After`. Sites que chamam a API pelo navegador precisam estar em `NEXO_CORS_ORIGINS`.

```bash
curl -X POST http://127.0.0.1:8000/api/ask \
  -H "X-API-Key: nxk_SUA_CHAVE" \
  -H "Content-Type: application/json" \
  -d '{"question": "Qual o torque dos parafusos da tampa?"}'
```

```json
{
  "answer": "Aperte os parafusos da tampa traseira em cruz com torque de 45 N·m [1].",
  "answered": true,
  "grounded": null,
  "model": "ollama:llama3.1",
  "latency_ms": 2140,
  "conversation_id": null,
  "sources": [{ "rank": 1, "document_title": "Guia de Manutenção da Bomba Centrífuga BC-40", "page": 5, "similarity": 0.62, "rerank_score": 0.91, "excerpt": "..." }]
}
```

Sem `conversation_id`, a pergunta não fica gravada. Com ele, o Nexo usa o histórico daquela conversa e grava pergunta e resposta. `document_ids` limita o escopo e `bot_id` faz a pergunta a um agente, com a base e as instruções dele.

### Respostas em streaming

`POST /api/conversations/{id}/messages/stream` recebe o mesmo corpo da rota de perguntas e responde em Server-Sent Events: `status` (`searching` e depois `writing`), um `delta` para cada pedaço do texto, e `done` com a pergunta, a resposta gravada e as fontes (o mesmo JSON da rota sem streaming). Se o modelo falhar, chega um `error` com `code` e `message` e nada é gravado.

```bash
curl -N -X POST http://127.0.0.1:8000/api/conversations/ID_DA_CONVERSA/messages/stream \
  -H "X-API-Key: nxk_SUA_CHAVE" -H "Content-Type: application/json" \
  -d '{"content": "Como faço a troca do filtro?"}'
```

```text
event: status
data: {"stage": "searching"}

event: delta
data: {"text": "Desligue a bomba e "}

event: done
data: {"question": {...}, "answer": {...}, "conversation": {...}}
```

### Bases pela API

```bash
curl -X POST http://127.0.0.1:8000/api/bases/ID_DA_BASE/documents \
  -H "X-API-Key: nxk_SUA_CHAVE" -F "files=@tabela-de-precos.csv"

curl -X POST http://127.0.0.1:8000/api/bases/ID_DA_BASE/texts \
  -H "X-API-Key: nxk_SUA_CHAVE" -H "Content-Type: application/json" \
  -d '{"title": "Horário de atendimento", "content": "Segunda a sexta, das 8h às 18h."}'
```

Para trazer uma página ou arquivo publicado e atualizar quando mudar:

```bash
curl -X POST http://127.0.0.1:8000/api/bases/ID_DA_BASE/links \
  -H "X-API-Key: nxk_SUA_CHAVE" -H "Content-Type: application/json" \
  -d '{"url": "https://empresa.com.br/politica-de-trocas"}'

curl -X POST http://127.0.0.1:8000/api/documents/ID_DO_ITEM/refetch -H "X-API-Key: nxk_SUA_CHAVE"
```

A aba **Integrar** de cada base traz esses exemplos (e a pergunta ao agente) em curl, Python e JavaScript, com os ids preenchidos.

### Webhooks

Administradores cadastram webhooks em **Integrações → Webhooks** e escolhem os eventos:

| Evento | Quando |
|---|---|
| `document.ready` | Um PDF terminou de indexar |
| `document.failed` | A indexação de um PDF falhou |
| `question.unanswered` | Uma pergunta não teve base nos documentos (com `source: widget` ou `openai` quando veio de lá) |
| `feedback.negative` | Alguém marcou uma resposta como "não ajudou" |
| `whatsapp.message` | Chegou uma mensagem de cliente no WhatsApp |
| `whatsapp.handoff` | Um contato do WhatsApp passou a aguardar atendente |

Cada entrega é um `POST` em JSON `{"event", "delivery", "created_at", "data"}` com os cabeçalhos `X-Nexo-Event`, `X-Nexo-Delivery`, `X-Nexo-Attempt` e `X-Nexo-Signature: sha256=<hmac>`. Falhas de rede, tempo esgotado, HTTP 429 e 5xx são repetidas até 3 vezes (esperas de 1 e 3 segundos) com o mesmo `delivery`, que serve para descartar duplicatas no destino. Para conferir a assinatura:

```python
import hashlib, hmac

def assinatura_valida(corpo: bytes, cabecalho: str, segredo: str) -> bool:
    esperado = "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecalho)
```

O botão **Testar** envia o evento `ping` uma única vez e mostra a resposta HTTP do destino. A última entrega (código, erro e número de tentativas) fica registrada em cada webhook.

### Exportação

O botão de download no topo de cada conversa gera Markdown (para ler ou colar em documentos) ou JSON (com trechos e notas, para sistemas). Pela API: `GET /api/conversations/{id}/export?format=markdown` ou `format=json`.

O **Painel de qualidade** exporta as perguntas do período em CSV (separado por ponto e vírgula, abre direto no Excel): data, conta, conversa, agente, pergunta, se foi respondida, avaliação, tempo, modelo, fontes e o comentário de quem marcou "não ajudou". Pela API: `GET /api/metrics/export?days=30&bot_id=`. Administradores recebem as perguntas de todas as contas.

### Monitoramento

`GET /api/health/ready` serve para checagens de saúde e `GET /api/health/metrics` entrega pedidos, erros, tempos, fila e acervo no formato do Prometheus (chave completa de administrador). Com `NEXO_LOG_FORMAT=json`, cada pedido vira uma linha JSON com o `X-Request-ID`, a conta e o tempo.

## WhatsApp

Em **WhatsApp › Conexões**, um administrador conecta um número e escolhe o agente que atende:

| Provedor | Passo a passo curto |
|---|---|
| **Evolution API** (seu número, QR code) | Tenha um servidor [Evolution API v2](https://doc.evolution-api.com) com uma instância. Informe endereço, chave e instância, clique em **Mostrar QR code** e leia com o WhatsApp do celular (Aparelhos conectados). Depois clique em **Registrar webhook** (usa `NEXO_PUBLIC_URL`). |
| **API oficial (Meta)** | No app da Meta com o produto WhatsApp, copie o Phone Number ID, um token permanente e o app secret para a conexão. Cole a URL do webhook e o verify token mostrados pelo Nexo no app da Meta e assine o campo `messages`. O Nexo confere a assinatura `X-Hub-Signature-256`. |
| **Simulador** | Nada a configurar: use **Simular mensagem de cliente** na caixa de entrada para testar o agente. |

Na **caixa de entrada**, o agente responde sozinho com a base dele. Quando não encontra a resposta, ou quando o cliente pede "atendente", o contato vai para **Aguardando atendente** e o agente pausa nele. Mensagens digitadas no próprio celular do número (Evolution) aparecem como **Pelo celular**, e as confirmações de entrega da API oficial atualizam cada mensagem. Quem responde pela tela assume a conversa; **Devolver ao agente** religa a resposta automática e **Sugerir resposta** traz um rascunho do agente, com as fontes, para revisar antes de enviar. Pela API oficial, respostas livres só valem até 24 horas depois da última mensagem do cliente. As **respostas prontas** (ícone de raio ou `/` na caixa) inserem textos da equipe, trocando `{nome}` e `{telefone}` pelos dados do contato.

## Configuração

A configuração base fica no `.env` (modelo em [`.env.example`](.env.example)); no aplicativo instalado, em `%LOCALAPPDATA%\Nexo\.env`, e a pasta de dados é `%LOCALAPPDATA%\Nexo\data`. Quase tudo também muda pela tela **Sistema e conta → Ajustes**, sem reiniciar: provedor de IA, modelos, endereços e chaves, busca, trechos, acesso, backup e retenção. Os valores da tela ficam em `data/ajustes.json` e as chaves em `data/segredos.json`, por cima do `.env`. As principais variáveis:

| Variável | Padrão | Função |
|---|---|---|
| `NEXO_LLM_PROVIDER` | `ollama` | `ollama`, `openai`, `compativel` ou `extrativo` |
| `NEXO_LLM_MODEL` | `llama3.1` | Modelo de linguagem |
| `NEXO_OLLAMA_CONTEXT` | automático (8192 a 32768) | Contexto do Ollama em tokens (`num_ctx`). Vazio calcula pelo tamanho e pela quantidade de trechos; valores altos pedem muita memória |
| `NEXO_EMBED_PROVIDER` | `huggingface` | `huggingface`, `openai`, `ollama` ou `hash` |
| `NEXO_EMBED_MODEL` | `intfloat/multilingual-e5-small` | Modelo de embeddings |
| `NEXO_VECTOR_STORE` | `chroma` | `chroma` ou `qdrant` |
| `NEXO_RERANKER` | `huggingface` | `huggingface`, `cohere` ou `none` |
| `NEXO_CHUNK_SIZE` / `NEXO_CHUNK_OVERLAP` | `512` / `64` | Tamanho dos trechos e sobreposição, em tokens |
| `NEXO_TOP_K` / `NEXO_TOP_N` | `12` / `4` | Candidatos da busca e trechos que vão ao modelo |
| `NEXO_MIN_SIMILARITY` | `0.15` | Similaridade mínima de cosseno |
| `NEXO_MIN_RERANK_SCORE` | `0.1` | Nota mínima do reranker |
| `NEXO_VERIFY_ANSWERS` | `false` | Verificação de fidelidade com uma segunda chamada ao LLM |
| `NEXO_WEBHOOK_TIMEOUT` | `5` | Segundos de espera por entrega de webhook |
| `NEXO_OPENAI_BASE_URL` | vazio | Endereço do serviço compatível com a OpenAI (obrigatório com `compativel`) |
| `NEXO_PUBLIC_URL` | vazio | Endereço público do Nexo, usado na URL do webhook do WhatsApp e no código do widget |
| `NEXO_WHATSAPP_HISTORY` | `6` | Mensagens anteriores do contato usadas pelo agente no WhatsApp |
| `NEXO_WHATSAPP_TIMEOUT` | `15` | Segundos de espera por chamada ao provedor do WhatsApp |
| `NEXO_MAX_UPLOAD_MB` | `100` | Tamanho máximo de cada arquivo |
| `NEXO_DATABASE_URL` | SQLite em `data/` | Outro banco relacional |
| `NEXO_SECRET` | gerado em `data/.segredo` | Chave de assinatura das sessões |
| `NEXO_RATE_LIMIT` | `60` | Perguntas e buscas por minuto por conta (0 desliga) |
| `NEXO_RETENTION_DAYS` | `0` | Apaga conversas não fixadas sem atividade há mais dias que isso (0 guarda para sempre) |
| `NEXO_LOG_LEVEL` / `NEXO_LOG_FORMAT` | `INFO` / `texto` | Detalhe e formato dos registros (`texto` ou `json`) |
| `NEXO_CORS_ORIGINS` | vazio | Sites liberados a chamar a API pelo navegador, separados por vírgula |
| `NEXO_ALLOW_PRIVATE_URLS` | `false` | Permite importar links da rede interna |
| `NEXO_LINK_TIMEOUT` | `20` | Segundos de espera ao baixar um link |
| `NEXO_REQUIRE_PASSWORD_CHANGE` | `true` | Exige a troca da senha padrão do admin antes de liberar a sessão |
| `NEXO_BACKUP_HOURS` / `NEXO_BACKUP_KEEP` | `0` / `7` | Backup automático a cada N horas (0 desliga) e quantos guardar em `data/backups` |
| `NEXO_WIDGET_RATE_LIMIT` | `10` | Perguntas por minuto de cada visitante em cada widget |

A tela **Sistema e conta** mostra a configuração ativa e os primeiros passos, e a aba **Ajustes** indica o que foi alterado em relação ao `.env`. Trocar o modelo de embeddings apaga os vetores e reindexa o acervo sozinho: o Nexo guarda em `data/vetores.json` qual modelo gerou os vetores atuais.

## Banco de dados

O Nexo cria tudo sozinho na primeira execução e migra bancos antigos sem passo manual (na 2.4, cria `nx_widget`; na 2.3, acrescentou as colunas que faltavam e criou `nx_quick_reply` e `nx_audit`). Quem for popular ou administrar os dados encontra em [`Banco-de-Dados-Nexo.pdf`](Banco-de-Dados-Nexo.pdf) (e no resumo em [`docs/banco-de-dados.md`](docs/banco-de-dados.md)) o diagrama de relacionamentos, a função de cada tabela, o formato do banco vetorial e do arquivo de usuários, e como trocar o SQLite por PostgreSQL, MySQL ou SQL Server. O DDL está em [`docs/schema-postgresql.sql`](docs/schema-postgresql.sql) e [`docs/schema-sqlite.sql`](docs/schema-sqlite.sql).

```mermaid
erDiagram
    nx_knowledge_base ||--o{ nx_document : contem
    nx_knowledge_base ||--o{ nx_bot : "usada por"
    nx_bot |o--o{ nx_conversation : conversa
    nx_bot |o--o{ nx_whatsapp_channel : atende
    nx_whatsapp_channel ||--o{ nx_whatsapp_contact : clientes
    nx_whatsapp_contact ||--o{ nx_whatsapp_message : mensagens
    nx_document ||--o{ nx_conversation_document : escopo
    nx_conversation ||--o{ nx_conversation_document : consulta
    nx_conversation ||--o{ nx_message : contem
    nx_message ||--o{ nx_message_source : cita
    nx_document |o--o{ nx_message_source : origem
    nx_message ||--o{ nx_feedback : recebe
    nx_bot ||--o{ nx_widget : "publicado em"
    nx_api_key {
        string id PK
        string owner
        string key_hash UK
        string scope
    }
    nx_webhook {
        string id PK
        string url
        string events
    }
    nx_quick_reply {
        string id PK
        string title
        string body
    }
    nx_audit {
        int id PK
        string actor
        string action
    }
    nx_widget {
        string id PK
        string bot_id FK
        string public_key UK
    }
```

`nx_api_key`, `nx_webhook`, `nx_quick_reply` e `nx_audit` ligam-se às contas pelo nome de usuário (as contas ficam em `data/usuarios.json`, fora do banco); `nx_widget` pertence a um agente e some junto com ele. Fora do banco ficam também `data/ajustes.json`, `data/segredos.json`, `data/instalacao.json`, `data/vetores.json` e os backups automáticos em `data/backups/`. Os agentes não têm coleção vetorial própria: a busca filtra pelos documentos da base de cada um, por isso mover itens entre bases não exige reindexar.

## Estrutura

```
nexo/
  config.py          configuração lida do .env
  db.py              tabelas SQLAlchemy
  migrations.py      migração automática (bancos da 2.0 e colunas novas)
  runtime.py         ajustes pela tela (provedores, chaves e pipeline), em data/ajustes.json e data/segredos.json
  onboarding.py      assistente de configuração e primeiros passos
  maintenance.py     diagnóstico, manutenção, retenção, backup automático, troca de embeddings, backup e restauração
  audit.py           registro de atividades
  links.py           importação de links com bloqueio da rede interna
  sample.py          base de teste
  cli.py             linha de comando python -m nexo (abre o aplicativo, configurar, senha, verificar e manutenção)
  desktop.py         aplicativo: janela WebView2, servidor interno, instância única, arquivos, restauração e verificação
  logs.py            registros em texto ou JSON
  knowledge.py       leitura de DOCX, EPUB, PPTX, XLSX, ODT, TXT, MD, CSV, JSON, HTML e textos
  whatsapp.py        provedores, webhook, contatos e respostas do agente no WhatsApp
  users.py           contas em data/usuarios.json
  security.py        tokens JWT e chaves de API
  jobs.py            fila de indexação
  webhooks.py        entrega assinada dos eventos
  rag/
    engine.py        leitura dos PDFs, indexação, busca, reranking, prompt do agente e resposta
    providers.py     LLM (inclusive compatível com OpenAI), embeddings, banco vetorial, reranker e teste de conexão
    hash_embedding.py  embedding léxico para testes
  api/               rotas FastAPI, esquemas e autenticação (agents.py: bases e agentes; whatsapp.py: WhatsApp; system.py: operação;
                     widgets.py: widget para sites; openai_compat.py: rotas /v1 compatíveis com OpenAI)
  static/widget.js   widget para sites, em JavaScript puro e Shadow DOM
frontend/            interface React + TypeScript (Vite)
  src/pages/         Entrada, Assistente, Conversas, Chats, Agents, Bases, WhatsApp, Busca, Documentos, Painel, Integrações, Sistema
  src/components/    menu, Tutorial, paleta de comandos, atalhos, trechos indexados e termos destacados
scripts/             avaliação da recuperação, PDF de exemplo, redefinição de senha
  docs/              gerador do Manual e do PDF do banco de dados
exemplos/            PDF fictício, perguntas de avaliação e base-de-teste/ (arquivos da base de teste)
docs/                manuais em PDF, banco de dados, DDL e imagens
tests/               testes automatizados
desktop/             aplicativo para Windows: nexo.spec (PyInstaller), nexo.iss (Inno Setup), build.ps1, entrada.py e nexo.ico
```

## API

Documentação interativa em **Integrações → /api/docs**, que abre numa janela do Nexo (com o aplicativo aberto, também em `http://127.0.0.1:8000/api/docs`; se a 8000 estiver ocupada, o Nexo usa a próxima livre). Todas as rotas, exceto entrada, cadastro, o webhook público do WhatsApp e as rotas públicas do widget, exigem `Authorization: Bearer <token>` ou uma chave de API.

| Método | Rota | Função |
|---|---|---|
| POST | `/api/auth/login` · `/api/auth/register` | Entrar e criar conta |
| GET / PATCH | `/api/auth/me` | Dados da conta e troca do próprio nome |
| PUT | `/api/auth/password` | Trocar senha (devolve uma sessão nova e encerra as outras) |
| POST | `/api/auth/sessions/revoke` | Sair dos outros dispositivos |
| PUT | `/api/auth/tutorial` | Marcar o tutorial como visto ou para rever |
| GET / POST | `/api/bases` | Listar e criar bases de conhecimento |
| POST | `/api/bases/sample` | Criar a Base de teste e o Agente de teste |
| POST | `/api/bases/{id}/links` | Importar uma página ou arquivo por link |
| GET / PATCH / DELETE | `/api/bases/{id}` | Abrir, renomear e excluir base |
| GET / POST | `/api/bases/{id}/documents` | Listar itens e enviar arquivos para a base |
| POST | `/api/bases/{id}/texts` | Criar um texto na base |
| GET / PUT | `/api/documents/{id}/text` | Ler e editar um texto |
| GET / POST | `/api/bots` | Listar e criar agentes |
| GET / PATCH / DELETE | `/api/bots/{id}` | Abrir, editar (inclusive `suggestions`) e excluir agente |
| POST | `/api/bots/{id}/duplicate` | Duplicar agente |
| GET / POST | `/api/documents` | Listar e enviar PDFs |
| PATCH / DELETE | `/api/documents/{id}` | Renomear, mover de base (`base_id`) e excluir |
| POST | `/api/documents/bulk` | Reindexar, mover ou excluir vários itens (`action`, `ids`, `base_id`) |
| POST | `/api/documents/{id}/reindex` | Reindexar |
| POST | `/api/documents/{id}/refetch` | Baixar de novo do link de origem |
| GET | `/api/documents/{id}/chunks` | Trechos indexados (`offset`, `limit`, `q`) |
| GET | `/api/documents/{id}/file` | Baixar o PDF |
| GET / POST | `/api/conversations` | Listar (filtros `only`, `bot_id` e `q`) e criar conversas (`bot_id` opcional) |
| PATCH | `/api/conversations/{id}` | Renomear, mudar escopo e fixar (`pinned`) |
| POST | `/api/conversations/{id}/messages` | Perguntar |
| POST | `/api/conversations/{id}/messages/stream` | Perguntar com a resposta em streaming (SSE) |
| GET | `/api/conversations/{id}/export` | Exportar em Markdown ou JSON |
| POST | `/api/messages/{id}/feedback` | Avaliar resposta, com `comment` opcional |
| POST | `/api/messages/{id}/regenerate` | Refazer a resposta |
| POST | `/api/ask` | Pergunta direta, para integrações (`bot_id` opcional) |
| POST | `/api/search` | Busca nos trechos, sem LLM (`base_id` opcional) |
| GET | `/api/metrics?days=30&bot_id=` | Painel de qualidade, com números por agente |
| GET | `/api/metrics/export?days=30` | Perguntas do período em CSV |
| GET / POST / DELETE | `/api/keys` · `/api/keys/{id}` | Chaves de API (`scope`, `expires_days`) |
| GET / POST / PATCH / DELETE | `/api/webhooks` · `/api/webhooks/{id}` | Webhooks (administrador) |
| POST | `/api/webhooks/{id}/test` | Entrega de teste |
| GET / POST / PATCH / DELETE | `/api/users` · `/api/users/{usuario}` | Contas: listar, criar, mudar perfil e excluir (administrador) |
| PUT | `/api/users/{usuario}/password` | Redefinir a senha de outra conta (administrador) |
| GET / POST / PATCH / DELETE | `/api/whatsapp/channels` · `/api/whatsapp/channels/{id}` | Conexões do WhatsApp (administrador para alterar) |
| GET | `/api/whatsapp/channels/{id}/status` · `/qrcode` | Situação da conexão e QR code da Evolution |
| POST | `/api/whatsapp/channels/{id}/webhook` · `/simulate` | Registrar webhook e simular mensagem de cliente |
| GET / POST | `/api/whatsapp/webhook/{id}` | Webhook público chamado pelo WhatsApp |
| GET | `/api/whatsapp/summary` · `/api/whatsapp/contacts` | Números da caixa de entrada e contatos |
| GET / PATCH | `/api/whatsapp/contacts/{id}` | Conversa com o cliente; ligar ou pausar o agente |
| POST | `/api/whatsapp/contacts/{id}/messages` · `/suggest` | Responder como a equipe e pedir sugestão ao agente |
| GET / POST / PATCH / DELETE | `/api/whatsapp/quick-replies` · `/{id}` | Respostas prontas |
| GET / PUT | `/api/system/settings` · `POST /reset` | Ajustes pela tela, inclusive provedores e chaves (administrador) |
| POST | `/api/system/providers/test` | Testa o modelo, os embeddings ou o reranking sem salvar (administrador) |
| GET | `/api/system/providers/ollama-models` | Modelos instalados no Ollama (administrador) |
| GET / POST | `/api/system/setup` | Assistente de configuração e primeiros passos (administrador) |
| GET / POST | `/api/system/backups` · `GET /api/system/backups/{nome}` | Backups automáticos: plano, fazer um agora e baixar (administrador) |
| GET / POST / PATCH / DELETE | `/api/widgets` · `/api/widgets/{id}` · `POST /rotate` | Widgets para sites (administrador para alterar) |
| GET / POST | `/api/public/widget/{chave}/config` · `/ask` · `GET /widget.js` | Rotas públicas do widget |
| GET / POST | `/v1/models` · `/v1/chat/completions` | API compatível com OpenAI (chave de API) |
| GET | `/api/system/diagnostics?deep=` | Diagnóstico rápido ou completo (administrador) |
| POST | `/api/system/maintenance` | Ações de manutenção (administrador) |
| GET | `/api/system/backup` | Baixar o backup (administrador) |
| GET | `/api/audit` · `/api/audit/export` | Registro de atividades e CSV (administrador) |
| GET | `/api/health/metrics` | Métricas no formato do Prometheus (administrador) |
| GET | `/api/system/status` | Configuração e números do acervo |
| GET | `/api/health` · `/api/health/ready` | Versão e prontidão (confere o banco; 503 se indisponível) |

## Avaliar a recuperação

Monte um arquivo JSONL com perguntas e a página que deveria ser encontrada (veja [`exemplos/perguntas-exemplo.jsonl`](exemplos/perguntas-exemplo.jsonl)) e rode:

```bash
python scripts/avaliar.py exemplos/perguntas-exemplo.jsonl --detalhes
```

Depois de criar a base de teste, avalie com o conjunto dela: `python scripts/avaliar.py exemplos/base-de-teste/perguntas-de-teste.jsonl`.

O script mostra o acerto e o MRR da busca vetorial pura e com reranking, para calibrar `NEXO_TOP_K`, `NEXO_TOP_N` e os cortes de relevância. A tela **Busca nos trechos** faz a mesma conferência pergunta a pergunta.

## Testes

```bash
pip install -r requirements-ci.txt
python -m pytest
```

```bash
ruff check .
```

Os testes usam o modo sem modelos e cobrem o aplicativo (painel entregue só para a janela, cookie da janela, nomes de arquivo seguros, abertura de documentos e da referência da API, restauração só por administradores, restauração pendente, instância única, primeira abertura já configurada), a troca obrigatória da senha padrão, os provedores e as chaves pela tela (com `data/segredos.json` em 0600), o teste de conexão, a troca de embeddings com reindexação automática, o assistente e os primeiros passos, o backup automático com rotação e download, o widget para sites (sites autorizados, pré-voo, limite por visitante, corpo grande, pausa, troca de chave e exclusão em cascata), a API compatível com OpenAI (modelos, resposta, streaming, erros e permissão), a linha de comando `configurar` e `senha`, a checagem da porta, ajustes pela tela, índice desatualizado, diagnóstico, manutenção, backup e restauração, registro de atividades, permissão e validade das chaves, limite de perguntas, CORS, métricas do Prometheus, conversas fixadas, comentários nas avaliações, perguntas sugeridas, duplicação de agentes, painel por agente, respostas prontas, trechos indexados, importação por link (com bloqueio da rede interna), linha de comando, logs JSON, base de teste, migração de um banco da 2.2, respostas em streaming (com um modelo simulado), refazer resposta, sessões encerradas por troca de senha, criação de contas e redefinição de senha por administradores, leitura de EPUB, PPTX, XLSX e ODT (inclusive arquivos corrompidos e grandes demais), ações em lote, busca nas conversas, exportação CSV do painel, novas tentativas dos webhooks, `X-Request-ID`, prontidão, bases de conhecimento e formatos, textos, mover entre bases, agentes, conversas com agentes, migração de um banco da 2.0, tutorial, WhatsApp (simulador, webhook da Meta com assinatura, Evolution com token, envio, passagem para atendente e sugestão), autenticação, bloqueio por tentativas, cadastro em arquivo, envio e indexação de PDF, respostas com fontes, pergunta fora do conteúdo, escopo, reranking, permissões, exclusão de vetores, busca nos trechos, exportação, painel de qualidade, chaves de API, pergunta direta, webhooks com assinatura e gestão de contas.

## Documentação em PDF

O [`Manual-Nexo.pdf`](Manual-Nexo.pdf) e o [`Banco-de-Dados-Nexo.pdf`](Banco-de-Dados-Nexo.pdf) são gerados a partir do texto em [`scripts/docs/`](scripts/docs/README.md), com as mesmas fontes e cores da interface e as capturas de `docs/images/`:

```bash
pip install playwright pypdf pillow
npm i -g @mermaid-js/mermaid-cli
python scripts/docs/gerar_pdfs.py
```

Os dois PDFs saem na raiz e em `docs/`, com sumário, diagramas em vetor e metadados. Para usar o Chrome instalado no lugar do Chromium do Playwright, defina `NEXO_CHROME` com o caminho do executável.

## Página do projeto

A página de apresentação fica em [`pages/`](pages/index.html) e é publicada no GitHub Pages pelo workflow [`pages.yml`](.github/workflows/pages.yml), junto com as capturas e os dois PDFs. Para ativar, em **Settings → Pages** do repositório escolha **Source: GitHub Actions**.

## Licença

[MIT](LICENSE). Use, copie, altere e distribua à vontade. As fontes [Instrument Sans](https://fonts.google.com/specimen/Instrument+Sans), [Bricolage Grotesque](https://fonts.google.com/specimen/Bricolage+Grotesque) e [IBM Plex Mono](https://www.ibm.com/plex/) da interface vêm do [Fontsource](https://fontsource.org/) e são distribuídas sob a SIL Open Font License 1.1.
