import re

from base import RAIZ, VERSAO, Documento
from banco import ER_DIAGRAMA

ESTILO_FLUXO = """
classDef escuro fill:#000000,stroke:#000000,color:#FFFFFF
classDef claro fill:#FFFFFF,stroke:#BAB7B6,color:#000000
classDef cinza fill:#F5F4F4,stroke:#E8E7E6,color:#000000
"""


def contar_testes():
    total = 0
    for arq in (RAIZ / "tests").glob("test_*.py"):
        total += len(re.findall(r"^\s*(?:async\s+)?def test_", arq.read_text(encoding="utf-8"), flags=re.M))
    return total


def no(titulo, detalhe=""):
    d = f"<br/><span style='font-family:Plex Mono;font-size:11px'>{detalhe}</span>" if detalhe else ""
    return f'"<b>{titulo}</b>{d}"'


def visao_geral(d):
    d.capitulo("Visão geral",
               "O Nexo é uma aplicação web em que você cria agentes de IA, cada um com a própria base de "
               "conhecimento, e conversa com eles ou deixa que atendam clientes pelo WhatsApp. As respostas usam "
               "só o que está nos documentos, textos e arquivos da base. Cada resposta mostra os trechos usados, "
               "com documento e página. Quando a informação não está na base, o Nexo diz isso em vez de inventar.")
    d.tela("tela-chat.png", "Conversa com citações numeradas e o painel de trechos usados, com os termos da pergunta "
           "destacados, o link para o PDF na página e o botão Refazer no rodapé de cada resposta.", altura_max_mm=120)

    d.secao("Para que serve")
    d.lista([
        "Consultar manuais de equipamentos, normas, procedimentos internos e livros técnicos sem folhear centenas de páginas.",
        "Criar agentes especializados, como Suporte técnico, Comercial ou RH, cada um respondendo só com a base dele.",
        "Atender clientes pelo WhatsApp com um agente que responde com fonte e passa a conversa para uma pessoa quando não sabe.",
        "Dar a uma equipe um ponto único de consulta, em que cada resposta pode ser conferida no documento original.",
        "Estudar um livro complexo fazendo perguntas e indo direto à página que trata do assunto.",
    ])

    d.secao(f"O que há de novo na {VERSAO}")
    d.p(f"A versão {VERSAO} deixa o uso diário mais rápido e a operação mais segura, sem mudar a estrutura do banco "
        "relacional. A identidade \"caixa única\", a mesma do painel Bento, continua igual, e tudo o que funcionava na "
        "2.1.0 continua funcionando: as conversas, os agentes, as bases, o WhatsApp, a API e as integrações antigas, "
        "inclusive a rota de pergunta sem streaming.")
    d.cartoes([
        ("Respostas ao vivo", "streaming com SSE",
         "A resposta aparece enquanto é escrita, nas conversas e nos chats com agentes. Parar cancela sem gravar nada."),
        ("Refazer", "em cada resposta",
         "Responde de novo a mesma pergunta com o histórico anterior e troca a resposta no lugar, com fontes novas."),
        ("Sessões", "senha e outros dispositivos",
         "Trocar a senha encerra as outras sessões. Sair dos outros dispositivos faz o mesmo sem trocar a senha."),
        ("Contas pelo administrador", "Sistema e conta",
         "Criar contas mesmo com o cadastro fechado e redefinir senhas, o que encerra as sessões e libera o bloqueio."),
        ("Novos formatos", "EPUB, PPTX, XLSX e ODT",
         "Livros capítulo a capítulo, apresentações slide a slide, planilhas aba a aba e documentos do LibreOffice."),
        ("Ações em lote", "tela Documentos",
         "Seleção múltipla para reindexar, excluir ou mover vários itens de uma vez, com o aviso do que foi pulado."),
        ("Webhooks com nova tentativa", "até 3 tentativas",
         "Falhas de rede, tempo esgotado e respostas 5xx ou 429 são repetidas, com X-Nexo-Delivery e X-Nexo-Attempt."),
        ("Exportar CSV", "Painel de qualidade",
         "Baixa as perguntas do período com data, conversa, resposta, avaliação, tempo e fontes."),
        ("Busca nas conversas", "filtro da lista",
         "O filtro de conversas procura também no conteúdo das mensagens, não só no título."),
        ("Perfil", "Sistema e conta",
         "Cada pessoa troca o próprio nome de exibição, sem depender do administrador."),
        ("Operação", "X-Request-ID e /api/health/ready",
         "Cada resposta leva um id de pedido, e a rota de prontidão confere o banco antes de liberar o tráfego."),
        ("Sem migração", "banco existente",
         "Nenhuma tabela muda. O arquivo de contas ganha dois campos sozinho na atualização."),
    ])
    d.p("**Na 2.1.0**, o Nexo virou uma plataforma de agentes: agentes com instruções próprias, bases de conhecimento, "
        "textos digitados direto na base, chats com vários agentes em abas ou lado a lado, atendimento pelo WhatsApp "
        "(Evolution API, API oficial ou simulador), a aba Integrar de cada base, o tutorial de primeiro acesso e a "
        "migração automática dos bancos da 2.0.")

    d.secao("O que o projeto entrega")
    d.p("O Nexo é entregue como estrutura pronta: interfaces, arquitetura, banco de dados e documentação. Quem instala "
        "decide quais arquivos enviar, quais modelos usar, qual número de WhatsApp conectar e onde hospedar. Nenhum "
        "documento real ou dado pessoal vem no repositório; o único PDF incluído é um manual fictício para testes.")
    d.tabela(["Camada", "Tecnologia", "Papel"], [
        ("Interface", "React 19, TypeScript, Vite", "Telas de entrada, tutorial, conversas, chats com agentes, agentes, "
         "bases, WhatsApp, busca, documentos, painel, integrações e sistema"),
        ("API", "Python 3.11+, FastAPI, Uvicorn", "Rotas REST, respostas em streaming (SSE), autenticação por sessão ou "
         "chave de API, envio de arquivos, fila de indexação e webhook do WhatsApp"),
        ("Pipeline de dados", "LlamaIndex, pypdf", "Leitura dos arquivos, divisão em trechos, busca e montagem das respostas"),
        ("Banco vetorial", "ChromaDB (padrão) ou Qdrant", "Embeddings dos trechos e metadados de origem"),
        ("Embeddings", "HuggingFace, OpenAI ou Ollama", "Transformam texto em vetores para a busca semântica"),
        ("Reranking", "Cross-encoder HuggingFace ou Cohere Rerank", "Reordenam os candidatos antes de chegarem ao modelo"),
        ("Modelo de linguagem", "Ollama (local) ou OpenAI", "Redige a resposta a partir dos trechos, seguindo as "
         "instruções do agente"),
        ("Banco relacional", "SQLAlchemy com SQLite (padrão), PostgreSQL, MySQL ou SQL Server", "Bases, documentos, "
         "agentes, conversas, mensagens, fontes, avaliações, chaves, webhooks e WhatsApp"),
        ("Contas", "Arquivo JSON com bcrypt, sessões JWT com versão", "Login pré-definido, cadastro próprio, gestão pelo "
         "administrador, encerramento de sessões e tutorial visto"),
        ("Integrações", "Chaves nxk_, webhooks com HMAC-SHA256", "Perguntas e buscas vindas de outros sistemas e avisos de "
         "eventos, com nova tentativa automática"),
        ("WhatsApp", "Evolution API v2, WhatsApp Cloud API da Meta ou simulador", "Receber mensagens de clientes e "
         "responder pelo agente ou por uma pessoa"),
    ], larguras=["20%", "33%", "47%"])

    d.secao("Funcionalidades")
    d.lista([
        "Bases de conhecimento com PDF, DOCX, ODT, EPUB, PPTX, XLSX, TXT, MD, CSV, JSON e HTML, enviados por arrastar e "
        "soltar, vários de uma vez, com limite de tamanho e bloqueio de duplicados por SHA-256 dentro de cada base.",
        "Textos digitados direto na base, editáveis a qualquer hora; ao salvar, o texto é reindexado.",
        "Mover um item de uma base para outra sem reindexar; excluir apaga o arquivo e todos os vetores dele. Na tela "
        "Documentos, as três ações também valem para vários itens selecionados.",
        "Agentes com instruções próprias, saudação, resposta quando não souber, cor e opção de citar as fontes no WhatsApp.",
        "Chats com vários agentes ao mesmo tempo, em abas ou lado a lado, cada um consultando só a própria base.",
        "Respostas escritas ao vivo, com o botão Parar, e Refazer em cada resposta.",
        "Caixa de entrada do WhatsApp com filtros, resposta automática do agente, passagem para atendente, sugestão de "
        "resposta e simulador.",
        "Indexação em segundo plano com os estados Na fila, Indexando, Pronto e Falhou. A tela se atualiza sozinha.",
        "Conversas salvas por usuário, com título automático, renomeação, exclusão, filtro pelo título e pelo conteúdo "
        "e exportação em Markdown ou JSON.",
        "Citações [n] clicáveis que abrem o trecho usado, com os termos da pergunta destacados, e o PDF na página certa.",
        "Resposta padrão quando nada relevante é encontrado, que cada agente pode trocar pela própria frase.",
        "Busca direta nos trechos, de todo o acervo ou de uma base, sem o modelo de linguagem.",
        "Avaliação de cada resposta e painel de qualidade com as perguntas que ficaram sem resposta e exportação em CSV.",
        "Integrações por chave de API, pergunta direta em `/api/ask` (também para um agente) e webhooks assinados, com "
        "eventos do WhatsApp e nova tentativa automática.",
        "Contas com troca de senha que encerra as outras sessões, Sair dos outros dispositivos, nome editável e, para "
        "administradores, criação de contas e redefinição de senha.",
        "Tutorial no primeiro acesso, paleta de comandos `Ctrl + K`, tema claro, escuro ou automático e layout para celular.",
    ])

    d.secao("Identidade visual")
    d.p(f"A {VERSAO} mantém a identidade \"caixa única\", a mesma do painel Bento (Data-Driven-Admin-Panel), adotada na "
        "1.5.0. Os botões novos (Parar, Refazer, Exportar CSV e as ações em lote) seguem os mesmos materiais.")
    d.tabela(["Elemento", "Como ficou"], [
        ("Mesa", "Fundo, menu lateral e cabeçalhos no mesmo tom #F5F4F4, sem bordas"),
        ("Caixa", "Conversas, listas e painéis dividem paredes finas de 1 px dentro de caixas brancas de cantos arredondados"),
        ("Tampa", "Os resumos (acervo, base escolhida, caixa de entrada do WhatsApp, números do painel) e a lateral da "
         "tela de entrada ficam no bloco preto"),
        ("Tipografia", "Títulos e números em Bricolage Grotesque fina e condensada, textos em Instrument Sans, código em "
         "IBM Plex Mono"),
        ("Agentes", "Cada agente tem uma cor de destaque, usada só no selo com a inicial; o resto da tela continua em "
         "preto e branco"),
        ("Status", "Um ponto de cor e o texto neutro: verde para Pronto, azul para Indexando, cinza para Na fila, "
         "vermelho para Falhou"),
        ("Temas", "Claro, escuro ou automático; o escuro usa os mesmos materiais em tons escuros"),
        ("Paleta", "#FFFFFF, #4D4B4B, #000000, #333232 e #BAB7B6; a logo é sempre em preto e branco"),
    ], larguras=["20%", "80%"])


def instalacao(d):
    d.capitulo("Instalação",
               "Este capítulo leva do download à primeira pergunta respondida. O caminho mais curto é o script de "
               "inicialização; os passos manuais vêm logo depois.")
    d.secao("Pré-requisitos")
    d.tabela(["Item", "Versão", "Para quê"], [
        ("Python", "3.11 ou mais recente", "Servidor, indexação e respostas"),
        ("Node.js", "20.19 ou mais recente", "Compilar a interface (uma vez)"),
        ("Ollama", "Atual", "Modelo de linguagem local e gratuito (modo padrão)"),
        ("Espaço em disco", "Cerca de 3 GB", "Dependências do Python, modelos de embeddings e reranking"),
        ("Memória", "8 GB ou mais", "Rodar o llama3.1 local com folga"),
        ("WhatsApp (opcional)", "Evolution API v2 ou conta Meta", "Atender clientes pelo WhatsApp (capítulo 6)"),
    ], larguras=["23%", "26%", "51%"])
    d.nota("Sem Ollama ou sem GPU?", "Use a OpenAI como modelo de linguagem (seção 3.1) ou o modo de teste sem modelos "
           "para validar a instalação. Os modelos de embeddings e reranking padrão rodam bem em CPU.")

    d.secao("Caminho rápido")
    d.passos([
        "Baixe o repositório (botão **Code › Download ZIP** no GitHub ou `git clone`) e extraia em uma pasta.",
        "Instale o Ollama em ollama.com e, num terminal, rode `ollama pull llama3.1`.",
        "No Windows, dê dois cliques em `iniciar.cmd`. No Linux ou macOS, rode `./iniciar.sh`.",
        "Espere a instalação terminar. Na primeira vez ela leva alguns minutos.",
        "Abra `http://127.0.0.1:8000` no navegador e entre com `admin` / `Nexo@2026`. O tutorial aparece na primeira entrada.",
        "Em **Bases de conhecimento**, envie um arquivo; em **Agentes**, crie um agente com essa base; em **Chats com "
        "agentes**, faça a primeira pergunta.",
    ])
    d.p("O script cria o ambiente virtual `.venv`, instala `requirements.txt`, copia `.env.example` para `.env`, compila a "
        "interface em `frontend/dist` e sobe o servidor. Nas próximas vezes ele só sobe o servidor; quando a versão "
        "muda, recompila a interface.")

    d.secao("Passo a passo manual")
    d.codigo("""
python -m venv .venv
.venv\\Scripts\\activate          # Windows
source .venv/bin/activate        # Linux / macOS
pip install -r requirements.txt
copy .env.example .env           # Windows; no Linux/macOS use cp
cd frontend
npm install
npm run build
cd ..
python -m nexo
""")
    d.p("Para desenvolver a interface com recarga automática, rode `python -m nexo` em um terminal e `npm run dev` dentro "
        "de `frontend` em outro. A interface abre em `http://localhost:5173` e repassa as chamadas `/api` para a porta 8000.")

    d.secao("Primeiro acesso")
    d.p("O login pré-definido é criado quando não há nenhum administrador, como na primeira execução. O aviso some da "
        "tela de entrada (seção 4.1) assim que a senha do admin é trocada. Troque-a em Sistema e conta no primeiro acesso.")
    d.tabela(["Usuário", "Senha", "Perfil", "Pode"], [
        ("`admin`", "`Nexo@2026`", "Administrador", "Tudo: excluir conteúdo de outras pessoas, ver o painel de todos, "
         "criar e gerenciar contas, redefinir senhas, webhooks e conexões do WhatsApp"),
        ("contas novas", "definida no cadastro ou pelo administrador", "Usuário", "Criar bases e agentes, enviar arquivos, "
         "conversar, atender no WhatsApp, buscar, ver o próprio painel e criar as próprias chaves"),
    ], larguras=["16%", "19%", "15%", "50%"])

    d.secao("Atualizando a partir da 1.5")
    d.passos([
        "Pare o servidor e faça uma cópia da pasta `data` (seção 10.5).",
        f"Substitua os arquivos do projeto pelos da {VERSAO}, mantendo `data` e o seu `.env`.",
        "Rode `pip install -r requirements.txt` e, em `frontend`, `npm install` e `npm run build`.",
        "Se quiser, acrescente `NEXO_WEBHOOK_TIMEOUT=5` ao `.env`. Sem a linha, vale o padrão de 5 segundos.",
        "Suba o servidor. As tabelas `nx_api_key` e `nx_webhook` da 2.0 e as tabelas da 2.1 são criadas sozinhas na "
        "primeira conexão; as tabelas existentes são migradas pela migração automática e os documentos vão para a "
        "base \"Acervo geral\".",
    ])

    d.secao("Atualizando a partir da 2.0")
    d.passos([
        "Pare o servidor e faça uma cópia da pasta `data` (seção 10.5).",
        f"Substitua os arquivos do projeto pelos da {VERSAO}, mantendo `data` e o seu `.env`.",
        "Rode `pip install -r requirements.txt` e, em `frontend`, `npm install` e `npm run build` (o script de "
        "inicialização faz isso sozinho).",
        "Se for usar o WhatsApp, acrescente `NEXO_PUBLIC_URL` ao `.env` (seção 3.2).",
        "Suba o servidor. A migração automática cria as tabelas novas, acrescenta as colunas novas e coloca os "
        "documentos antigos na base \"Acervo geral\". Conversas antigas continuam consultando todos os documentos.",
    ])

    d.secao("Atualizando a partir da 2.1", novo=True)
    d.p(f"A {VERSAO} não muda nenhuma tabela, então não há migração a fazer.")
    d.passos([
        "Pare o servidor. A cópia da pasta `data` (seção 10.5) continua recomendada antes de qualquer atualização.",
        "Traga os arquivos novos com `git pull` (ou substitua pelos da versão nova), mantendo `data` e o seu `.env`.",
        "Rode `pip install -r requirements.txt`.",
        "Em `frontend`, rode `npm ci && npm run build`.",
        "Suba o servidor. Nada mais precisa ser feito.",
    ])
    d.p("As sessões abertas antes da atualização continuam válidas. O arquivo `data/usuarios.json` ganha os campos "
        "`session_version` e `password_changed_at` automaticamente; não é preciso editá-lo. O `.env` também não muda.")


def configuracao(d):
    d.capitulo("Configuração",
               "Toda a configuração fica no arquivo .env na raiz do projeto. Altere, salve e reinicie o servidor. A "
               "tela Sistema e conta mostra o que está valendo. As conexões do WhatsApp são feitas pela tela, não pelo .env.")
    d.secao("Modos prontos")
    d.tabela(["Modo", "Linhas no .env", "Quando usar"], [
        ("Local e gratuito (padrão)", "`NEXO_LLM_PROVIDER=ollama` `NEXO_LLM_MODEL=llama3.1` "
         "`NEXO_EMBED_PROVIDER=huggingface` `NEXO_RERANKER=huggingface`", "Documentos sigilosos que não podem sair da máquina"),
        ("OpenAI", "`NEXO_LLM_PROVIDER=openai` `NEXO_LLM_MODEL=gpt-4o-mini` `OPENAI_API_KEY=sua-chave`",
         "Respostas mais elaboradas sem precisar de GPU"),
        ("Embeddings da OpenAI", "`NEXO_EMBED_PROVIDER=openai` `NEXO_EMBED_MODEL=text-embedding-3-small` "
         "`NEXO_EMBED_QUERY_PREFIX=` `NEXO_EMBED_TEXT_PREFIX=`", "Acervos grandes, sem baixar modelos locais"),
        ("Reranking Cohere", "`NEXO_RERANKER=cohere` `COHERE_API_KEY=sua-chave`", "Melhor ordenação em vários idiomas sem "
         "custo de CPU"),
        ("Qdrant", "`NEXO_VECTOR_STORE=qdrant` `NEXO_QDRANT_URL=http://localhost:6333`", "Acervos com muitos milhares de "
         "trechos ou servidor dedicado"),
        ("Teste sem modelos", "`NEXO_EMBED_PROVIDER=hash` `NEXO_LLM_PROVIDER=extrativo` `NEXO_RERANKER=none` "
         "`NEXO_MIN_SIMILARITY=0.1`", "Validar a instalação e rodar os testes automatizados"),
    ], larguras=["20%", "50%", "30%"])
    d.nota("Trocou o modelo de embeddings?", "Vetores de modelos diferentes não são comparáveis. Depois de mudar "
           "`NEXO_EMBED_PROVIDER` ou `NEXO_EMBED_MODEL`, use uma coleção nova (`NEXO_COLLECTION`) ou reindexe todos os "
           "documentos (na tela Documentos, selecione todos e use Reindexar).")

    d.secao("Todas as variáveis")
    d.tabela(["Variável", "Padrão", "Descrição"], [
        "Servidor e contas",
        ("`NEXO_HOST` / `NEXO_PORT`", "127.0.0.1 / 8000", "Endereço do servidor. Use 0.0.0.0 para aceitar acessos da rede"),
        ("`NEXO_DATA_DIR`", "data", "Pasta do banco SQLite, arquivos enviados, vetores locais e usuários"),
        ("`NEXO_SECRET`", "gerado", "Chave das sessões. Vazia: o Nexo cria data/.segredo"),
        ("`NEXO_TOKEN_HOURS`", "8", "Duração da sessão em horas (1 a 168)"),
        ("`NEXO_ALLOW_REGISTRATION`", "true", "Permite criar contas na tela de entrada. Desligado, só o administrador "
         "cria contas"),
        ("`NEXO_MAX_UPLOAD_MB`", "100", "Tamanho máximo de cada arquivo (1 a 2048)"),
        ("`NEXO_DATABASE_URL`", "vazio", "URL SQLAlchemy de outro banco relacional. Vazio: data/nexo.db"),
        ("`NEXO_WEBHOOK_TIMEOUT`", "5", "Tempo máximo de cada tentativa de entrega de webhook, em segundos (até 120)"),
        "WhatsApp",
        ("`NEXO_PUBLIC_URL`", "vazio", "Endereço público do Nexo (https://…) usado para montar a URL do webhook do WhatsApp"),
        ("`NEXO_WHATSAPP_HISTORY`", "6", "Mensagens anteriores do contato usadas pelo agente para entender a pergunta"),
        ("`NEXO_WHATSAPP_TIMEOUT`", "15", "Tempo máximo de cada chamada ao provedor do WhatsApp, em segundos"),
        "Modelo de linguagem",
        ("`NEXO_LLM_PROVIDER`", "ollama", "ollama, openai ou extrativo"),
        ("`NEXO_LLM_MODEL`", "llama3.1", "Nome do modelo no provedor escolhido"),
        ("`NEXO_LLM_TEMPERATURE`", "0.1", "Criatividade do modelo (0 a 1). Mantenha baixa"),
        ("`NEXO_LLM_TIMEOUT`", "120", "Tempo máximo de resposta do modelo, em segundos"),
        ("`NEXO_OLLAMA_URL`", "http://localhost:11434", "Endereço do Ollama"),
        ("`OPENAI_API_KEY`", "vazio", "Chave da OpenAI (também aceita NEXO_OPENAI_API_KEY)"),
        ("`NEXO_OPENAI_BASE_URL`", "vazio", "Endpoint compatível com a OpenAI (Azure, LM Studio, vLLM)"),
        "Embeddings e banco vetorial",
        ("`NEXO_EMBED_PROVIDER`", "huggingface", "huggingface, openai, ollama ou hash"),
        ("`NEXO_EMBED_MODEL`", "intfloat/multilingual-e5-small", "Modelo de embeddings"),
        ("`NEXO_EMBED_QUERY_PREFIX` / `_TEXT_PREFIX`", "\"query: \" / \"passage: \"", "Prefixos exigidos pela família "
         "E5. Deixe vazio em outros modelos"),
        ("`NEXO_VECTOR_STORE`", "chroma", "chroma ou qdrant"),
        ("`NEXO_COLLECTION`", "nexo_trechos", "Nome da coleção vetorial"),
        ("`NEXO_CHROMA_HOST` / `_PORT`", "vazio / 8001", "Servidor ChromaDB. Vazio: arquivos em data/chroma"),
        ("`NEXO_QDRANT_URL` / `_API_KEY`", "vazio", "Servidor Qdrant. Vazio: arquivos em data/qdrant"),
        "Reranking e recuperação",
        ("`NEXO_RERANKER`", "huggingface", "huggingface, cohere ou none"),
        ("`NEXO_RERANK_MODEL`", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "Cross-encoder multilíngue do HuggingFace"),
        ("`NEXO_COHERE_MODEL` / `COHERE_API_KEY`", "rerank-v3.5 / vazio", "Reranking da Cohere"),
        ("`NEXO_CHUNK_SIZE` / `_OVERLAP`", "512 / 64", "Tamanho dos trechos e sobreposição, em tokens"),
        ("`NEXO_TOP_K`", "12", "Candidatos trazidos pela busca vetorial"),
        ("`NEXO_TOP_N`", "4", "Trechos enviados ao modelo depois do reranking"),
        ("`NEXO_MIN_SIMILARITY`", "0.15", "Corte 1: similaridade de cosseno mínima para um trecho ser considerado"),
        ("`NEXO_MIN_RERANK_SCORE`", "0.1", "Corte 2: nota mínima do reranker (0 a 1)"),
        ("`NEXO_HISTORY_TURNS`", "3", "Trocas anteriores usadas para reescrever a pergunta (0 a 10)"),
        ("`NEXO_VERIFY_ANSWERS`", "false", "Liga a verificação de fidelidade, uma segunda chamada ao modelo"),
    ], larguras=["37%", "24%", "39%"])

    d.secao("Calibrando a precisão")
    d.lista([
        "**Respostas dizendo que não encontrou, mas a informação existe:** baixe `NEXO_MIN_SIMILARITY` (por exemplo 0.1) e "
        "`NEXO_MIN_RERANK_SCORE` (0.05), ou aumente `NEXO_TOP_K`.",
        "**Respostas misturando assuntos:** suba `NEXO_MIN_RERANK_SCORE` (0.3) e reduza `NEXO_TOP_N` para 3. Separar os "
        "assuntos em bases e agentes diferentes também ajuda.",
        "**Tabelas e listas longas cortadas:** aumente `NEXO_CHUNK_SIZE` para 768 ou 1024 e reindexe.",
    ])
    d.nota("Antes de mexer:", "use a aba Testar da base (seção 4.6) ou a Busca nos trechos para ver as notas reais dos "
           "trechos, e o Painel de qualidade para acompanhar a taxa de resposta depois do ajuste. Para medir em vez de "
           "adivinhar, use `scripts/avaliar.py` (seção 10.2).")

    d.secao("Serviços externos com Docker")
    d.p("O `docker-compose.yml` traz serviços opcionais, cada um em um perfil:")
    d.codigo("""
docker compose --profile chroma up -d      # ChromaDB em http://localhost:8001
docker compose --profile qdrant up -d      # Qdrant em http://localhost:6333
docker compose --profile ollama up -d      # Ollama em http://localhost:11434
docker compose --profile postgres up -d    # PostgreSQL em localhost:5432
""")
    d.p("Depois aponte o `.env` para eles, por exemplo `NEXO_CHROMA_HOST=localhost` ou "
        "`NEXO_DATABASE_URL=postgresql+psycopg://nexo:troque-esta-senha@localhost:5432/nexo` (instale "
        "`pip install \"psycopg[binary]\"`). Troque a senha do PostgreSQL no arquivo antes de usar. A Evolution API, usada "
        "para conectar o próprio número de WhatsApp, tem imagem Docker oficial; siga a documentação do projeto para subi-la.")

    d.secao("Acesso pela rede")
    d.p("Para outras máquinas acessarem, use `NEXO_HOST=0.0.0.0`, libere a porta no firewall e defina `NEXO_SECRET` com "
        "um valor longo e aleatório. Em produção, coloque o Nexo atrás de um proxy com HTTPS (Nginx, Caddy ou IIS) e "
        "desligue o cadastro aberto se o acesso deve ser restrito; o administrador continua criando contas pela tela.")
    d.p("Com integrações e WhatsApp, o HTTPS deixa de ser opcional: chaves de API viajam em cada pedido, e a API oficial "
        "da Meta só entrega webhooks em endereços HTTPS públicos. Defina `NEXO_PUBLIC_URL` com esse endereço. Para "
        "webhooks de saída, o servidor do Nexo precisa conseguir abrir conexões até as URLs cadastradas.")
    d.p("Respostas em streaming chegam por Server-Sent Events. No Nginx, desligue o buffer da rota de streaming "
        "(`proxy_buffering off`) para que o texto apareça enquanto é escrito. Para checagens de saúde do balanceador, "
        "use `GET /api/health/ready`, que devolve 503 quando o banco não responde.")


def usando(d):
    d.capitulo("Usando o Nexo",
               "As telas seguem o caminho natural de uso: entrar, montar as bases, criar os agentes, conversar, atender "
               "no WhatsApp, conferir a qualidade e integrar. O menu lateral agrupa as telas em Consulta, Agentes, "
               "Atendimento, Gestão e Conta.")
    d.tabela(["Grupo", "Telas", "Para quê"], [
        ("Consulta", "Conversas, Busca nos trechos, Documentos", "Perguntar a todo o acervo, procurar trechos e ver todos os arquivos"),
        ("Agentes", "Chats com agentes, Agentes, Bases de conhecimento", "Conversar com vários agentes, criá-los e cuidar "
         "dos dados de cada um"),
        ("Atendimento", "WhatsApp", "Caixa de entrada com os clientes e as conexões dos números"),
        ("Gestão", "Painel de qualidade, Integrações", "Acompanhar as respostas e ligar outros sistemas"),
        ("Conta", "Sistema e conta", "Pipeline, acervo, perfil, senha, sessões, tutorial e, para administradores, as contas"),
    ], larguras=["16%", "36%", "48%"])
    d.p("No topo do menu, o botão **Ir para…** (`Ctrl + K`) abre a paleta de comandos. No rodapé ficam o usuário "
        "conectado, o botão de tema e **Sair**.")

    d.secao("Entrada", quebra=True)
    d.tela("tela-login.png", "Entrada, com as abas Entrar e Criar conta e o aviso do login pré-definido enquanto a senha "
           "do admin não for trocada.", altura_max_mm=125)
    d.lista([
        "**Entrar** pede usuário e senha. Cinco erros seguidos bloqueiam o usuário por 5 minutos; o administrador pode "
        "liberar antes redefinindo a senha.",
        "**Criar conta** aparece quando `NEXO_ALLOW_REGISTRATION=true`. O nome de usuário tem de 3 a 32 caracteres "
        "minúsculos; a senha, de 8 a 72 caracteres, com letras e números, sem conter o nome de usuário. Com o cadastro "
        "fechado, as contas são criadas pelo administrador em Sistema e conta.",
        "A sessão dura `NEXO_TOKEN_HOURS` horas e fica só na aba aberta.",
        "Uma sessão encerrada por troca de senha, por **Sair dos outros dispositivos** ou por redefinição feita pelo "
        "administrador volta para a entrada com o aviso de sessão encerrada.",
    ])

    d.secao("Tutorial de primeiro acesso", quebra=True)
    d.tela("tela-tutorial.png", "Tutorial de primeiro acesso: cada passo mostra uma ilustração da tela, o que fazer e o "
           "atalho para começar.", altura_max_mm=120)
    d.p("Na primeira vez que uma conta entra, o Nexo abre um tutorial curto por cima da tela. Ele explica, em poucos "
        "passos, o caminho completo: o que o Nexo faz, como montar uma base de conhecimento, como criar um agente, como "
        "conversar com vários agentes ao mesmo tempo e como ligar o WhatsApp. O último passo traz atalhos para criar a "
        "primeira base, o primeiro agente e conectar o WhatsApp.")
    d.lista([
        "Avance com **Próximo** ou com a seta para a direita; volte com **Voltar** ou a seta para a esquerda. Os pontos no "
        "rodapé mostram em que passo você está e levam direto a qualquer um.",
        "**Pular** fecha o tutorial. Fechando ou concluindo, o Nexo marca o tutorial como visto na sua conta (campo "
        "`tutorial_done_at`), então ele não volta a aparecer, nem em outro computador.",
        "Para rever, use **Ver tutorial** na paleta de comandos ou em Sistema e conta.",
    ])

    d.secao("Conversas", quebra=True)
    d.tela("tela-chat.png", "Duas perguntas na mesma conversa, com os trechos da primeira resposta abertos, os termos "
           "da pergunta destacados e Refazer no rodapé de cada resposta.", altura_max_mm=118)
    d.lista([
        "**Nova** abre uma conversa vazia que consulta todo o acervo, de todas as bases. O campo **Filtrar conversas** "
        "encontra conversas pelo título e pelo conteúdo das perguntas e respostas. As conversas com agentes ficam na tela "
        "Chats com agentes.",
        "O título vem da primeira pergunta. No topo da conversa, o ícone de renomear edita o título e o ícone de exportar "
        "abre o menu Markdown / JSON (seção 5.7).",
        "`Enter` envia, `Shift + Enter` quebra a linha.",
        "A resposta aparece enquanto é escrita: primeiro a etapa de busca nos documentos, depois o texto chegando aos "
        "poucos. **Parar** cancela a resposta; nada é gravado e a pergunta volta para a caixa de texto.",
        "Os números [n] no texto indicam de qual trecho veio cada informação. Clique para destacá-lo no painel Trechos usados.",
        "Abaixo de cada resposta ficam **Ver N trechos**, **Refazer**, o ícone de copiar a resposta com as fontes e a "
        "avaliação útil / não ajudou.",
        "**Refazer** responde de novo a mesma pergunta, com o histórico anterior a ela, e troca a resposta no lugar: as "
        "fontes são renovadas e a avaliação anterior é apagada.",
        "Cada trecho mostra a página (ou a parte, em arquivos que não são PDF), a similaridade, a nota do reranker e o "
        "link para abrir o arquivo.",
        "Perguntas seguintes podem usar \"isso\" ou \"e depois?\": o Nexo reescreve a pergunta com o histórico antes de buscar.",
    ])
    d.sub("Escolhendo os documentos consultados")
    d.p("A linha **Consultando** mostra o escopo atual. Clique em **Escolher documentos** e marque os documentos que a "
        "conversa deve usar. Sem nenhum marcado, todos os documentos prontos são consultados, inclusive os que forem "
        "enviados depois.")
    d.sub("Quando a resposta não está nos documentos")
    d.tela("tela-nao-encontrado.png", "Pergunta fora do conteúdo dos documentos: o Nexo responde que não encontrou e "
           "sugere como reformular.", altura_max_mm=105)
    d.p("Se nenhum trecho passar pelos cortes de relevância, o modelo nem é chamado e a resposta aparece num quadro "
        "marcado, com três saídas: **Ver trechos parecidos**, **Consultar todos os documentos** (quando há escopo) e "
        "**Enviar outro arquivo**. A pergunta entra nas lacunas do painel de qualidade e, se houver webhook inscrito, "
        "dispara `question.unanswered`.")

    d.secao("Chats com agentes", quebra=True)
    d.tela("tela-chats.png", "Chats com agentes lado a lado: cada coluna conversa com um agente diferente, que responde "
           "só com a própria base.", altura_max_mm=118)
    d.p("É aqui que você conversa com os agentes. A tela tem a lista de agentes e das conversas recentes à esquerda e, à "
        "direita, as conversas abertas em abas.")
    d.passos([
        "Clique num agente da lista (ou em **Conversar** na tela Agentes). Uma conversa nova abre numa aba, com a "
        "saudação do agente.",
        "Escreva a pergunta e tecle `Enter`. O agente responde com base só na base de conhecimento dele, com as citações "
        "[n], e o texto aparece enquanto é escrito. **Parar** cancela sem gravar.",
        "Abra outros agentes: cada um ganha uma aba. Clique numa aba para trazê-la à frente; o × fecha a aba sem apagar "
        "a conversa.",
        "Clique em **Lado a lado** para ver até três conversas abertas ao mesmo tempo, uma por coluna. Clique em "
        "**Em abas** para voltar.",
        "Em cada resposta, **Ver trechos** abre os trechos usados logo abaixo dela, com documento e página, e **Refazer** "
        "pede ao agente uma nova resposta para a mesma pergunta.",
    ])
    d.p("As abas abertas ficam guardadas no navegador. Conversas antigas de cada agente aparecem abaixo dele na lista e "
        "reabrem numa aba. Um agente cuja base ainda não tem conteúdo pronto avisa isso no lugar da caixa de pergunta.")

    d.secao("Agentes", quebra=True)
    d.tela("tela-agentes.png", "Agentes: cada cartão mostra a cor, a base de conhecimento, as conversas e se o agente "
           "está pronto para responder.", altura_max_mm=110)
    d.p("Um agente é um assistente com nome, personalidade e uma base de conhecimento própria. Ele segue as regras "
        "estritas do Nexo (responder só com a base e citar as fontes) e, dentro delas, as instruções que você escrever.")
    d.tabela(["Campo", "Para quê"], [
        ("Nome e descrição", "Como o agente aparece nas listas, nos chats e no WhatsApp"),
        ("Base de conhecimento", "A única fonte das respostas. Escolha uma base existente; várias pessoas podem usar o mesmo agente"),
        ("Instruções", "Tom e regras, por exemplo \"Responda de forma curta e cordial; trate o cliente por você\". Não "
         "podem liberar o agente para inventar"),
        ("Saudação", "Mensagem de boas-vindas. Aparece ao abrir um chat e responde a cumprimentos como \"oi\" e \"bom dia\""),
        ("Quando não souber", "Frase usada no lugar da resposta padrão, por exemplo \"Vou chamar alguém da equipe\""),
        ("Cor", "Destaque do selo com a inicial do agente"),
        ("Citar fontes no WhatsApp", "Acrescenta \"Fontes:\" com documento e página no fim das respostas enviadas aos clientes"),
    ], larguras=["27%", "73%"])
    d.tela("tela-agente-editar.png", "Painel de criação do agente: nome, base de conhecimento, instruções, saudação, "
           "frase para quando não souber e cor.", altura_max_mm=110)
    d.passos([
        "Abra **Agentes** e clique em **Criar agente**.",
        "Dê um nome, escolha a base (ou crie uma em Bases de conhecimento antes) e escreva as instruções, a saudação e a "
        "frase para quando não souber.",
        "Salve. O cartão mostra **Pronto** quando a base tem conteúdo indexado. Use **Conversar** para testar e "
        "**Editar** para ajustar.",
    ])
    d.p("Excluir um agente apaga as conversas feitas com ele e desliga a resposta automática dos números de WhatsApp que "
        "ele atendia. Só quem criou o agente ou um administrador pode editá-lo ou excluí-lo.")

    d.secao("Bases de conhecimento", quebra=True)
    d.tela("tela-bases.png", "Base de conhecimento aberta: o resumo na tampa preta, as abas Arquivos, Textos, Testar e "
           "Integrar e a lista de arquivos.", altura_max_mm=112)
    d.p("A base de conhecimento é o \"RAG\" de cada agente: o conjunto de documentos, dados e arquivos de onde ele tira as "
        "respostas. A tela mostra todas as bases à esquerda e, à direita, a base escolhida, com o resumo na tampa preta "
        "(itens, prontos, trechos, páginas e agentes que usam a base) e quatro abas.")
    d.tabela(["Aba", "O que dá para fazer"], [
        ("Arquivos", "Arrastar ou escolher arquivos PDF, DOCX, ODT, EPUB, PPTX, XLSX, TXT, MD, CSV, JSON e HTML; filtrar; "
         "abrir, renomear, reindexar, mover para outra base e excluir"),
        ("Textos", "Escrever ou colar uma informação direto na base, com título; editar e excluir a qualquer hora"),
        ("Testar", "Fazer uma busca só nesta base e ver os trechos que um agente receberia, com as notas"),
        ("Integrar", "Exemplos prontos (curl, Python e JavaScript) para enviar arquivos, criar textos e perguntar ao agente "
         "desta base por outros sistemas, com os ids já preenchidos"),
    ], larguras=["18%", "82%"])
    d.sub("Como cada formato é lido")
    d.tabela(["Formato", "Como vira texto", "Citação"], [
        ("PDF", "Texto de cada página com pypdf (PDF digitalizado precisa de OCR antes)", "página N"),
        ("DOCX", "Parágrafos e tabelas do documento do Word", "parte N"),
        ("ODT [[novo]]", "Parágrafos e tabelas do documento do LibreOffice / OpenDocument", "parte N"),
        ("EPUB [[novo]]", "O livro capítulo a capítulo, na ordem de leitura", "parte N"),
        ("PPTX [[novo]]", "O texto de cada slide, um slide por parte", "parte N"),
        ("XLSX [[novo]]", "As linhas de cada aba, como no CSV, com o nome da aba antes", "parte N"),
        ("TXT e MD", "O texto como está, dividido em partes por parágrafos", "parte N"),
        ("CSV", "Cada linha vira \"coluna: valor\", com o cabeçalho repetido a cada bloco de linhas", "parte N"),
        ("JSON", "Cada valor vira \"caminho: valor\", para que chaves e valores entrem na busca", "parte N"),
        ("HTML", "O texto visível da página, sem scripts e estilos", "parte N"),
        ("Texto da aba Textos", "O texto digitado", "parte N"),
    ], larguras=["19%", "66%", "15%"])
    d.nota("Arquivos compactados.", "DOCX, ODT, EPUB, PPTX e XLSX são pacotes zip por dentro. O envio é recusado se "
           "algum item do pacote passar de 50 MB descompactado, o que protege o servidor de arquivos feitos para "
           "estourar a memória.")
    d.tela("tela-base-textos.png", "Aba Textos: informações escritas direto na base, editáveis a qualquer hora.",
           altura_max_mm=100)
    d.lista([
        "**Acrescentar informação a qualquer hora:** envie arquivos ou crie textos; cada item entra na fila e, ao ficar "
        "Pronto, já é usado pelos agentes da base.",
        "**Retirar informação:** exclua o item. Os vetores dele saem do banco vetorial na hora e os agentes param de usá-lo.",
        "**Mover entre bases:** o ícone de mover troca a base de um item sem reindexar, porque a busca filtra pelos "
        "documentos de cada base.",
        "**Acervo geral:** a base padrão existe sempre, recebe os documentos antigos e os envios feitos pela tela "
        "Documentos sem base escolhida. Pode ser renomeada, mas não excluída.",
        "Uma base usada por algum agente não pode ser excluída; troque a base do agente antes.",
    ])
    d.tela("tela-base-testar.png", "Aba Testar: busca só na base, com os trechos e as notas que o agente receberia.",
           altura_max_mm=100)
    d.tela("tela-base-integrar.png", "Aba Integrar: exemplos prontos com o id da base e do agente para levar dados e "
           "perguntas de outros sistemas.", altura_max_mm=100)

    d.secao("WhatsApp", quebra=True)
    d.tela("tela-whatsapp.png", "Caixa de entrada do WhatsApp: contatos com filtros, a conversa com o cliente, o agente "
           "respondendo e a sugestão de resposta.", altura_max_mm=112)
    d.p("A caixa de entrada reúne as conversas com os clientes de todos os números conectados. Em cima, a tampa preta "
        "resume contatos, não lidas, aguardando atendente e respostas do agente hoje.")
    d.lista([
        "**Contatos:** busca por nome ou número e filtros Todos, Não lidas, Aguardando atendente, Com o agente e Com a "
        "equipe. A lista se atualiza sozinha a cada poucos segundos.",
        "**Conversa:** mensagens do cliente à esquerda, do agente e da equipe à direita, com o autor, o horário e a "
        "situação da entrega (enviada, entregue, lida ou falhou). Mensagens digitadas no próprio celular do número "
        "(Evolution) aparecem como **Pelo celular**.",
        "**Assumir:** escrever e enviar uma mensagem pela tela coloca a equipe no controle daquele contato e pausa o agente nele.",
        "**Devolver ao agente:** religa a resposta automática naquele contato e tira a marca de aguardando atendente.",
        "**Sugerir resposta:** o agente redige uma resposta para a última mensagem do cliente, com as fontes, e coloca no "
        "campo de texto sem enviar. Revise e envie.",
        "**Aguardando atendente:** quando o agente não encontra a resposta na base, ou quando o cliente pede \"atendente\" "
        "ou \"humano\", o contato ganha essa marca, o agente pausa nele e sai o evento `whatsapp.handoff`.",
    ])
    d.tela("tela-whatsapp-conexoes.png", "Aba Conexões: provedor, agente que atende, resposta automática, URL do webhook "
           "e o QR code da Evolution API.", altura_max_mm=112)
    d.p("A aba **Conexões** lista os números conectados e, para administradores, permite criar, editar, pausar e excluir "
        "conexões. O passo a passo de cada provedor está no capítulo 6. Com o provedor Simulador, a própria tela tem o "
        "quadro **Simular mensagem de cliente** para testar o agente sem um número real.")

    d.secao("Busca nos trechos", quebra=True)
    d.tela("tela-busca.png", "Busca nos trechos: resultados em ordem de relevância, com documento, página, similaridade, "
           "nota do reranker e o trecho.", altura_max_mm=115)
    d.p("A busca mostra o que o acervo tem sobre um assunto sem chamar o modelo de linguagem. É rápida, não gasta tokens "
        "e serve para conferir se um assunto está nos documentos antes de perguntar, ou para calibrar os cortes de "
        "relevância. Para buscar dentro de uma base só, use a aba Testar da base.")
    d.passos([
        "Abra **Busca nos trechos** no menu lateral.",
        "Escreva o que procura (até 500 caracteres) e, se quiser, limite a busca a alguns documentos em **Documento**.",
        "Deixe **Reordenar com o reranker** ligado para a ordem mais precisa, ou desligue para ver a ordem da busca vetorial pura.",
        "Escolha em **Resultados** quantos quer ver (1 a 20; o padrão é 8) e clique em **Buscar** ou tecle `Enter`.",
        "Clique num resultado para abrir o arquivo no trecho, ou em **Perguntar sobre isso** para levar o assunto a uma conversa.",
    ])

    d.secao("Documentos", quebra=True)
    d.tela("tela-documentos.png", "Documentos: o resumo do acervo na tampa preta, a área de envio com os formatos aceitos e a "
           "barra de ações em lote com dois itens selecionados.", altura_max_mm=115)
    d.p("A tela Documentos mostra todos os itens de todas as bases numa lista só, com o filtro **Base** para ver uma base "
        "de cada vez. Escolha em **Enviar para** a base onde os arquivos enviados aqui vão entrar; sem escolha, vão para "
        "a base \"Acervo geral\". Cada item entra como Na fila, passa a Indexando e termina em Pronto; se aparecer "
        "Falhou, o motivo fica abaixo do título. Os ícones à direita abrem o arquivo, perguntam a este documento, "
        "renomeiam (reindexa), reindexam e excluem. A barra acima da lista filtra por título, situação e ordem.")
    d.sub("Ações em lote [[novo]]")
    d.passos([
        "Marque a caixa de seleção dos itens desejados, ou a caixa do cabeçalho para marcar todos os itens filtrados.",
        "Na barra que aparece, escolha **Reindexar**, **Mover para** (com a base de destino) ou **Excluir**. A exclusão "
        "pede confirmação.",
        "O Nexo aplica a ação só aos itens que você pode alterar (os que você enviou, os das suas bases ou todos, para "
        "administradores) e avisa quantos foram pulados.",
    ])

    d.secao("Painel de qualidade", quebra=True)
    d.tela("tela-painel.png", "Painel de qualidade com os números do período na tampa preta, o botão Exportar CSV, as "
           "perguntas por dia e as lacunas do acervo.", altura_max_mm=115)
    d.p("O painel responde a duas perguntas: o Nexo está respondendo bem? E o que falta no acervo? O administrador vê os "
        "números de todas as conversas, inclusive as com agentes; os demais usuários veem só os das próprias conversas. "
        "Escolha o período em 7, 30 ou 90 dias.")
    d.tabela(["Indicador", "Como ler"], [
        "Na tampa preta",
        ("Perguntas", "Total de perguntas feitas no período"),
        ("Taxa de resposta", "Respondidas ÷ perguntas. Caindo, o acervo não cobre o que as pessoas procuram ou os cortes estão altos"),
        ("Tempo médio e p95", "Tempo de resposta típico e o dos 5% mais lentos"),
        ("Avaliações", "Respostas marcadas como úteis e como \"não ajudou\""),
        "Abaixo da tampa",
        ("Perguntas por dia", "Perguntas e perguntas sem resposta de cada dia"),
        ("Documentos mais citados", "Os seis documentos que mais embasaram respostas"),
        ("Lacunas do acervo", "As 10 perguntas sem resposta mais recentes, com Buscar e Abrir"),
        ("Respostas avaliadas como \"não ajudou\"", "As 10 respostas mais recentes marcadas como \"não ajudou\", com a pergunta"),
    ], larguras=["32%", "68%"])
    d.sub("Exportar CSV [[novo]]")
    d.p("O botão **Exportar CSV** baixa as perguntas do período escolhido, uma por linha, pela rota "
        "`GET /api/metrics/export?days=N`. O escopo é o mesmo do painel: tudo para o administrador, só as próprias "
        "conversas para os demais.")
    d.tabela(["Coluna", "Conteúdo"], [
        ("data", "Quando a pergunta foi respondida"),
        ("conversa", "Título da conversa"),
        ("pergunta", "Texto da pergunta"),
        ("respondida", "Se a resposta veio dos documentos ou foi a resposta padrão"),
        ("avaliação", "Útil, não ajudou ou vazio"),
        ("latência", "Tempo de resposta, em milissegundos"),
        ("fontes", "Documentos e páginas citados"),
    ], larguras=["22%", "78%"], cls="compacta")
    d.nota("Rotina sugerida.", "Uma vez por semana, leia as lacunas e os contatos que ficaram aguardando atendente no "
           "WhatsApp. Se o assunto é legítimo e não está na base, crie um texto ou envie o arquivo que falta na base do agente.")

    d.secao("Integrações", quebra=True)
    d.tela("tela-integracoes.png", "Integrações: chaves de API do usuário, a pergunta direta com exemplos em curl, "
           "Python e JavaScript e, para administradores, os webhooks.", altura_max_mm=112)
    d.sub("Criar uma chave de API")
    d.passos([
        "Abra **Integrações** e, em **Chaves de API**, escreva um nome que diga onde a chave será usada.",
        "Clique em **Criar chave** e copie a chave exibida. Ela começa com `nxk_` e aparece uma única vez.",
        "Guarde a chave no cofre de segredos do sistema que vai usá-la e teste com um dos exemplos de **Pergunta direta**.",
    ])
    d.sub("Cadastrar um webhook (administrador)")
    d.passos([
        "Na seção **Webhooks**, informe a URL `http` ou `https` que vai receber os avisos.",
        "Em **Avisar quando**, marque ao menos um evento, inclusive Mensagem recebida no WhatsApp e Cliente aguardando "
        "atendente, e clique em **Adicionar webhook**.",
        "Copie o segredo de assinatura exibido (ele aparece uma única vez) e clique em **Testar**.",
    ])
    d.p("Cada webhook mostra o resultado da última entrega. Falhas passageiras são repetidas sozinhas, até três "
        "tentativas por evento (seção 5.5).")

    d.secao("Sistema e conta", quebra=True)
    d.tela("tela-sistema.png", "Sistema e conta: o pipeline de respostas com os provedores em uso, o acervo na tampa "
           "preta, a conta com a troca de senha e Sair dos outros dispositivos e, para administradores, o painel Contas "
           "com Nova conta e Redefinir senha.", altura_max_mm=196)
    d.p("O pipeline de respostas aparece na ordem em que a pergunta passa por ele, com os parâmetros de busca. A tampa "
        "preta resume o acervo.")
    d.sub("Sua conta")
    d.lista([
        "**Nome** [[novo]]: cada pessoa troca o próprio nome de exibição (`PATCH /api/auth/me`). O nome de usuário não muda.",
        "**Trocar senha:** pede a senha atual e a nova, que precisa ser diferente da atual. Ao trocar, todas as outras "
        "sessões da conta são encerradas; esta aba continua conectada com uma sessão nova.",
        "**Sair dos outros dispositivos** [[novo]]: encerra as sessões abertas em outros navegadores e computadores sem "
        "trocar a senha. Útil depois de usar um computador compartilhado.",
        "**Senha trocada em** mostra a data da última troca ou redefinição da senha.",
        "**Ver tutorial** abre de novo o tutorial de primeiro acesso.",
    ])
    d.sub("Contas (administrador)")
    d.lista([
        "**Nova conta** [[novo]]: nome, usuário, senha e perfil. Funciona mesmo com o cadastro aberto desligado.",
        "**Redefinir senha** [[novo]]: define uma senha nova para a conta, encerra todas as sessões dela e libera o "
        "bloqueio por senhas erradas.",
        "Promover, rebaixar e excluir contas. Ninguém rebaixa nem exclui a própria conta, e o último administrador não "
        "pode ser rebaixado.",
    ])

    d.secao("Paleta de comandos e atalhos", quebra=True)
    d.tela("tela-comandos.png", "Paleta de comandos aberta com Ctrl + K.", altura_max_mm=105)
    d.p("Clique em **Ir para…** ou tecle `Ctrl + K` em qualquer tela, escreva parte do nome do que procura e tecle "
        "`Enter`. A paleta leva a qualquer tela, abre conversas e executa ações como nova conversa, criar agente, criar "
        "base, abrir o WhatsApp, trocar o tema e ver o tutorial.")
    d.tabela(["Atalho", "O que faz"], [
        ("`Ctrl + K`", "Abre a paleta de comandos"),
        ("Setas e `Enter`", "Escolhem e executam um comando da paleta; no tutorial, as setas avançam e voltam"),
        ("`Esc`", "Fecha a paleta ou o tutorial e interrompe a resposta que está sendo escrita"),
        ("`Enter`", "Envia a pergunta, a mensagem do WhatsApp e a busca"),
        ("`Shift + Enter`", "Quebra a linha"),
    ], larguras=["25%", "75%"])

    d.secao("Tema e celular", quebra=True)
    d.tela("tela-escuro.png", "Tema escuro: os mesmos materiais da caixa única em tons escuros.", altura_max_mm=110)
    d.lado(["O botão de tema no rodapé do menu alterna **Tema claro**, **Tema escuro** e **Tema automático**. No celular, "
            "o menu recolhe para o botão no topo, as listas abrem por botões e as colunas viram uma só. Na tela Chats com "
            "agentes, o modo lado a lado vira abas; na caixa do WhatsApp, a lista de contatos e a conversa se alternam.",
            "As respostas ao vivo e os botões Parar e Refazer funcionam igual no celular."],
           "tela-celular.png", "Conversa no celular, com o menu recolhido.", largura_mm=46, altura_max_mm=100)


def integracoes(d):
    d.capitulo("Integrações",
               "Outros sistemas podem perguntar ao Nexo e aos agentes, alimentar as bases, buscar nos trechos e receber "
               "avisos. Este capítulo mostra como autenticar com uma chave de API, como usar a pergunta direta, como "
               "receber respostas em streaming e como receber e conferir webhooks.")
    d.secao("Autenticação por chave de API")
    d.p("Toda rota que aceita a sessão da interface também aceita uma chave de API. Envie a chave num destes cabeçalhos:")
    d.codigo("""
X-API-Key: nxk_Q2x5...                   # recomendado
Authorization: Bearer nxk_Q2x5...        # alternativa, para clientes que só enviam Bearer
""")
    d.lista([
        "A chave age em nome de quem a criou, com as mesmas permissões.",
        "Formato: `nxk_` seguido de 43 caracteres. O prefixo (12 primeiros caracteres) identifica a chave nas telas sem expô-la.",
        "O Nexo guarda só o hash SHA-256 da chave. Se ela se perder, revogue e crie outra.",
        "Chave inválida ou revogada recebe 401 `INVALID_API_KEY`. Encerrar as sessões da conta não afeta as chaves de API.",
    ])

    d.secao("Pergunta direta: /api/ask")
    d.p("Uma chamada, uma resposta com fontes. Sem `conversation_id`, nada é gravado. Com ele, o Nexo usa o histórico e "
        "grava a troca. Com `bot_id`, a pergunta vai para um agente: valem a base, as instruções, a saudação e a frase "
        "de quando não souber dele.")
    d.tabela(["Campo do corpo", "Tipo", "Regra"], [
        ("`question`", "texto", "Obrigatório, 1 a 4000 caracteres"),
        ("`bot_id`", "id ou null", "Opcional. Responde como o agente, só com a base dele"),
        ("`document_ids`", "lista de ids", "Opcional. Vazio consulta todos os documentos prontos (ou a base do agente)"),
        ("`conversation_id`", "id ou null", "Opcional. Conversa do próprio usuário cujo histórico será usado e onde a "
         "troca será gravada"),
    ], larguras=["24%", "18%", "58%"])
    d.codigo("""
curl -X POST http://127.0.0.1:8000/api/ask \\
  -H "X-API-Key: $NEXO_CHAVE" \\
  -H "Content-Type: application/json" \\
  -d '{"question": "Qual a temperatura de operação?", "bot_id": "ID_DO_AGENTE"}'
""", rotulo="curl")
    d.codigo("""
{
  "answer": "A faixa de operação vai de 5 °C a 40 °C [1].",
  "answered": true,
  "grounded": null,
  "model": "llama3.1",
  "latency_ms": 2140,
  "conversation_id": null,
  "sources": [
    { "rank": 1, "document_id": "3f2a…", "document_title": "Manual de exemplo",
      "page": 5, "similarity": 0.71, "rerank_score": 0.93, "kind": "pdf",
      "excerpt": "Temperatura de operação: 5 °C a 40 °C…" }
  ]
}
""", rotulo="Resposta")
    d.codigo("""
import os
import requests

resp = requests.post(
    "http://127.0.0.1:8000/api/ask",
    headers={"X-API-Key": os.environ["NEXO_CHAVE"]},
    json={"question": "Como restaurar as configurações de fábrica?"},
    timeout=180,
)
resp.raise_for_status()
dados = resp.json()
print(dados["answer"])
for f in dados["sources"]:
    print(f"[{f['rank']}] {f['document_title']}, página {f['page']}")
""", rotulo="Python")
    d.codigo("""
const resp = await fetch("http://127.0.0.1:8000/api/ask", {
  method: "POST",
  headers: { "X-API-Key": process.env.NEXO_CHAVE, "Content-Type": "application/json" },
  body: JSON.stringify({ question: "Como restaurar as configurações de fábrica?" }),
});
if (!resp.ok) throw new Error((await resp.json()).message);
const dados = await resp.json();
console.log(dados.answer);
""", rotulo="JavaScript (Node.js 18+ ou navegador)")

    d.secao("Alimentando uma base pela API")
    d.p("Qualquer sistema pode acrescentar ou retirar informação de uma base. Os mesmos exemplos aparecem prontos, com os "
        "ids preenchidos, na aba Integrar da base. Os formatos aceitos são os da seção 4.6.")
    d.codigo("""
curl -X POST http://127.0.0.1:8000/api/bases/ID_DA_BASE/documents \\
  -H "X-API-Key: $NEXO_CHAVE" \\
  -F "files=@tabela-de-precos.xlsx" -F "files=@politica-de-trocas.docx"

curl -X POST http://127.0.0.1:8000/api/bases/ID_DA_BASE/texts \\
  -H "X-API-Key: $NEXO_CHAVE" -H "Content-Type: application/json" \\
  -d '{"title": "Horário de atendimento", "content": "Segunda a sexta, das 8h às 18h."}'

curl -X DELETE http://127.0.0.1:8000/api/documents/ID_DO_ITEM -H "X-API-Key: $NEXO_CHAVE"

curl -X POST http://127.0.0.1:8000/api/documents/bulk \\
  -H "X-API-Key: $NEXO_CHAVE" -H "Content-Type: application/json" \\
  -d '{"action": "move", "ids": ["ID_1", "ID_2"], "base_id": "ID_DA_BASE"}'
""")
    d.p("Em `/api/documents/bulk`, `action` é `reindex`, `delete` ou `move` (este com `base_id`). A ação vale só para os "
        "itens que a chave pode alterar; a resposta informa os itens aplicados e os pulados.")

    d.secao("Busca pela API")
    d.codigo("""
curl -X POST http://127.0.0.1:8000/api/search \\
  -H "X-API-Key: $NEXO_CHAVE" -H "Content-Type: application/json" \\
  -d '{"query": "torque dos parafusos", "limit": 5, "rerank": true, "base_id": "ID_DA_BASE"}'
""")
    d.p("A resposta traz `query`, `took_ms` e `results`, cada um com `rank`, `document_id`, `document_title`, `page`, "
        "`similarity`, `rerank_score`, `kind` e `excerpt`. Sem documento pronto, devolve 409 `NO_DOCUMENTS`.")

    d.secao("Webhooks")
    d.p("Webhooks avisam outro sistema quando algo acontece no Nexo. Só administradores cadastram webhooks.")
    d.diagrama(f"""
flowchart LR
  A1[{no("Fila de indexação", "document.ready · document.failed")}] --> B1
  A2[{no("Pergunta sem resposta", "question.unanswered")}] --> B1
  A3[{no("Avaliação “não ajudou”", "feedback.negative")}] --> B1
  A4[{no("WhatsApp", "whatsapp.message · whatsapp.handoff")}] --> B1
  subgraph W["nexo/webhooks.py"]
    direction TB
    B1[{no("1 · Seleciona os ativos inscritos")}] --> B2[{no("2 · Monta {event, created_at, data}")}]
    B2 --> B3[{no("3 · Assina com HMAC-SHA256", "segredo do webhook")}]
    B3 --> B4[{no("4 · POST em segundo plano", "até 3 tentativas · 1 s e 3 s")}]
  end
  B4 --> C1[{no("Sistema externo", "confere X-Nexo-Signature e X-Nexo-Delivery")}]
  B4 --> C2[{no("Grava nx_webhook", "last_status · last_error · last_delivery_at")}]
  class B1,B2,B3,B4 escuro
  class A1,A2,A3,A4,C1,C2 claro
{ESTILO_FLUXO}
style W fill:#F5F4F4,stroke:#E8E7E6
""", "De onde vêm os eventos, o que o módulo de webhooks faz e onde o resultado de cada entrega é gravado.",
               altura_max_mm=100)
    d.tabela(["Evento", "Quando", "Dados em data"], [
        ("`document.ready`", "Um item termina de indexar", "id, title, pages, chunks"),
        ("`document.failed`", "A indexação de um item falha", "id, title, error"),
        ("`question.unanswered`", "Uma pergunta fica sem resposta, no chat ou em /api/ask", "question, conversation_id, username"),
        ("`feedback.negative`", "Uma avaliação passa a ser \"não ajudou\"", "message_id, question, answer, username"),
        ("`whatsapp.message`", "Chega uma mensagem de cliente no WhatsApp", "channel_id, contact_id, phone, name, text"),
        ("`whatsapp.handoff`", "Um contato passa a aguardar atendente", "channel_id, contact_id, phone, name, reason, text"),
        ("`ping`", "Botão Testar", "Entrega de teste, síncrona"),
    ], larguras=["27%", "38%", "35%"])
    d.codigo(f"""
POST /recebe-nexo HTTP/1.1
Content-Type: application/json
User-Agent: Nexo/{VERSAO}
X-Nexo-Event: whatsapp.handoff
X-Nexo-Delivery: 7b0e4c2a9f1d4e8b8c3a5d6e7f809a1b
X-Nexo-Attempt: 1
X-Nexo-Signature: sha256=5d2b0c9e...

{{"event": "whatsapp.handoff",
 "created_at": "2026-11-12T14:32:08+00:00",
 "data": {{"channel_id": "9c1e…", "contact_id": "41ab…", "phone": "5521999990000",
          "name": "Cliente", "reason": "not_found", "text": "Vocês abrem no feriado?"}}}}
""", rotulo="Formato da entrega")
    d.p("O receptor deve recalcular o HMAC sobre o corpo bruto, exatamente como chegou, e comparar em tempo constante.")
    d.codigo("""
import hashlib
import hmac


def assinatura_valida(corpo: bytes, cabecalho: str, segredo: str) -> bool:
    esperado = "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecalho or "")
""", rotulo="Python")
    d.sub("Novas tentativas [[novo]]")
    d.tabela(["Resultado da tentativa", "O que o Nexo faz"], [
        ("Resposta 2xx", "Entrega concluída; grava o status"),
        ("Erro de rede, tempo esgotado, 5xx ou 429", "Tenta de novo: a segunda tentativa sai 1 s depois, a terceira 3 s "
         "depois da segunda"),
        ("Outros 3xx e 4xx", "Não tenta de novo; o receptor recusou a entrega"),
        ("Terceira tentativa sem sucesso", "Desiste; o último status e o erro ficam no webhook"),
    ], larguras=["38%", "62%"])
    d.p("`X-Nexo-Delivery` é único por evento e se repete igual em todas as tentativas; `X-Nexo-Attempt` conta 1, 2 e 3. "
        "Use o primeiro para descartar repetições: o mesmo evento pode chegar duas vezes se o receptor gravou mas "
        "demorou a responder. O resultado da última tentativa aparece na tela Integrações.")
    d.tabela(["Método", "Rota", "O que faz"], [
        ("RAW:<span class=\"metodo\">GET</span>", "`/api/webhooks`", "Lista os webhooks com eventos, situação e resultado da última entrega"),
        ("RAW:<span class=\"metodo\">POST</span>", "`/api/webhooks`", "Cria. Corpo {\"url\", \"events\", \"secret\"}; sem secret, um é gerado"),
        ("RAW:<span class=\"metodo\">PATCH</span>", "`/api/webhooks/{id}`", "Pausa ou reativa: {\"active\": false}"),
        ("RAW:<span class=\"metodo\">DELETE</span>", "`/api/webhooks/{id}`", "Exclui"),
        ("RAW:<span class=\"metodo\">POST</span>", "`/api/webhooks/{id}/test`", "Entrega ping na hora e devolve {\"status\", \"error\"}"),
    ], larguras=["13%", "33%", "54%"])

    d.secao("Boas práticas")
    d.lista([
        "Uma chave por sistema integrado, com nome claro. Revogar uma não derruba as outras.",
        "Responda ao webhook rápido e faça o trabalho pesado depois, numa fila do seu lado. Uma resposta lenta vira "
        "tempo esgotado e uma nova tentativa.",
        "Guarde os `X-Nexo-Delivery` já processados para ignorar repetições.",
        "Use HTTPS e confira a assinatura sempre, mesmo em rede interna.",
        "Use `question.unanswered` e `whatsapp.handoff` para abrir tarefas de curadoria das bases e avisar a equipe de atendimento.",
        "Registre o `X-Request-ID` de cada resposta do Nexo nos seus logs; ele localiza o pedido nos logs do servidor.",
    ])

    d.secao("Exportação de conversas")
    d.p("O ícone de exportar no topo da conversa e a rota `GET /api/conversations/{id}/export` baixam a conversa inteira "
        "em `markdown` (padrão) ou `json`, com as fontes de cada resposta. Vale também para as conversas com agentes. "
        "Para as perguntas de um período em planilha, use o CSV do painel (seção 4.10).")

    d.secao("Respostas em streaming", novo=True)
    d.p("`POST /api/conversations/{id}/messages/stream` recebe o mesmo corpo de `POST /api/conversations/{id}/messages` e "
        "devolve `text/event-stream` (Server-Sent Events). A rota JSON antiga continua igual.")
    d.tabela(["Evento", "Dados", "Quando"], [
        ("`status`", "{\"stage\": \"searching\"} ou {\"stage\": \"writing\"}", "Antes da busca e quando o modelo começa a escrever"),
        ("`delta`", "{\"text\": \"…\"}", "Cada pedaço do texto da resposta, na ordem"),
        ("`done`", "{\"question\", \"answer\", \"conversation\"}", "Fim: o mesmo JSON da rota sem streaming. Só aqui a "
         "troca está gravada"),
        ("`error`", "{\"code\", \"message\"}", "Falha no meio do caminho; nada é gravado"),
    ], larguras=["14%", "40%", "46%"])
    d.codigo("""
curl -N -X POST http://127.0.0.1:8000/api/conversations/ID_DA_CONVERSA/messages/stream \\
  -H "X-API-Key: $NEXO_CHAVE" -H "Content-Type: application/json" \\
  -d '{"question": "Qual a temperatura de operação?"}'

event: status
data: {"stage": "searching"}

event: status
data: {"stage": "writing"}

event: delta
data: {"text": "A faixa de operação vai de 5 °C"}

event: delta
data: {"text": " a 40 °C [1]."}

event: done
data: {"question": {...}, "answer": {...}, "conversation": {...}}
""", rotulo="curl")
    d.p("Fechar a conexão antes do `done` cancela a resposta, como o botão Parar: nada é gravado. Para gerar de novo uma "
        "resposta já gravada, use `POST /api/messages/{id}/regenerate` com o id da resposta.")


def whatsapp(d):
    d.capitulo("WhatsApp",
               "Conecte um número, escolha o agente que atende e acompanhe os clientes pela caixa de entrada. O Nexo fala "
               "com o WhatsApp por três provedores: a Evolution API, com o seu próprio número pelo QR code; a API "
               "oficial da Meta; e um simulador para testar sem número.")
    d.secao("Escolhendo o provedor")
    d.tabela(["Provedor", "Como conecta", "Quando usar"], [
        ("Evolution API", "Servidor Evolution API v2 (seu ou contratado) e leitura de um QR code com o celular do número",
         "Usar o seu próprio WhatsApp ou WhatsApp Business já existente, sem aprovação da Meta"),
        ("API oficial (Meta)", "WhatsApp Cloud API: Phone Number ID, token de acesso, app secret e webhook HTTPS",
         "Operação oficial, com número verificado e regras da Meta"),
        ("Simulador", "Nada: as mensagens de cliente são simuladas pela tela", "Testar o agente, a passagem para atendente "
         "e a caixa de entrada antes de ligar um número real"),
    ], larguras=["20%", "42%", "38%"])

    d.secao("Conectando com a Evolution API (QR code)")
    d.passos([
        "Tenha um servidor Evolution API v2 no ar e crie nele uma instância (por exemplo `atendimento`). Anote o endereço "
        "do servidor e a chave de API.",
        "No Nexo, abra **WhatsApp › Conexões** e clique em **Nova conexão**. Escolha **Evolution API**, dê um nome, informe "
        "**Endereço do servidor**, **Chave da API** e **Instância**, escolha o agente e salve.",
        "Clique em **Mostrar QR code**. No celular, abra o WhatsApp › **Aparelhos conectados** › **Conectar um aparelho** e "
        "leia o código. A situação muda para **Conectado**.",
        "Informe o endereço público do Nexo (ou defina `NEXO_PUBLIC_URL`) e clique em **Registrar webhook**. O Nexo chama "
        "`POST /webhook/set/{instância}` com o evento `MESSAGES_UPSERT` e a URL `…/api/whatsapp/webhook/{id}?token=…`.",
        "Mande uma mensagem de outro celular para o número. Ela aparece na caixa de entrada e o agente responde.",
    ])
    d.nota("Envio e QR code.", "O Nexo envia texto com `POST {servidor}/message/sendText/{instância}` (cabeçalho "
           "`apikey`), busca o QR em `GET /instance/connect/{instância}` e a situação em "
           "`GET /instance/connectionState/{instância}`. Mensagens de grupos são ignoradas.")

    d.secao("Conectando com a API oficial da Meta")
    d.passos([
        "No painel de desenvolvedores da Meta, crie um app do tipo Business com o produto WhatsApp e anote o **Phone "
        "Number ID** do número, um **token de acesso** permanente (usuário do sistema) e o **app secret**.",
        "No Nexo, crie a conexão com o provedor **API oficial (Meta)**, preencha esses campos, a versão da API (padrão "
        "`v24.0`), escolha o agente e salve. O Nexo gera um **verify token**.",
        "Copie a URL do webhook mostrada na conexão (`https://seu-endereco/api/whatsapp/webhook/{id}`) e o verify token. "
        "No app da Meta, em **WhatsApp › Configuração › Webhook**, cole os dois e assine o campo **messages**.",
        "A Meta confirma com um GET (`hub.mode`, `hub.verify_token`, `hub.challenge`); o Nexo responde o desafio quando "
        "o token confere.",
        "Mande uma mensagem para o número de teste. O Nexo confere a assinatura `X-Hub-Signature-256` com o app secret e "
        "processa a mensagem.",
    ])
    d.nota("Janela de 24 horas.", "Pela API oficial, respostas livres só podem ser enviadas até 24 horas depois da última "
           "mensagem do cliente. Fora dessa janela, a Meta só aceita modelos aprovados, que o Nexo não envia; a mensagem "
           "fica marcada como falhou com o erro devolvido.")

    d.secao("Testando com o simulador")
    d.passos([
        "Crie uma conexão com o provedor **Simulador** e escolha o agente.",
        "Na caixa de entrada, use **Simular mensagem de cliente**: informe um número, um nome e o texto, e envie.",
        "O contato aparece como se tivesse escrito pelo WhatsApp, e o agente responde. Teste perguntas fora da base e a "
        "palavra \"atendente\" para ver a passagem para a equipe.",
    ])

    d.secao("Como o atendimento funciona")
    d.diagrama(f"""
flowchart TB
  A[{no("Mensagem do cliente", "webhook do provedor ou simulador")}] --> B[{no("Contato criado ou atualizado", "não lidas + 1 · evento whatsapp.message")}]
  B --> C{{"<b>Agente ligado no canal e no contato?</b>"}}
  C -- não --> E1[{no("Fica para a equipe")}]
  C -- sim --> D[{no("Agente responde com a base dele", "últimas NEXO_WHATSAPP_HISTORY mensagens · saudação · Fontes no fim")}]
  D --> F{{"<b>Não encontrou ou pediu atendente?</b>"}}
  F -- sim --> G[{no("Aguardando atendente", "agente pausa no contato · whatsapp.handoff")}]
  F -- não --> H[{no("Envio pelo provedor", "situação: enviada, entregue, lida ou falhou")}]
  G --> H
  class A,B,D,H claro
  class C,F escuro
  class E1,G cinza
{ESTILO_FLUXO}
""", "Caminho de uma mensagem de cliente até a resposta. A equipe pode assumir em qualquer ponto.", altura_max_mm=120)
    d.tabela(["Situação", "O que acontece"], [
        ("Cumprimento (\"oi\", \"bom dia\")", "O agente responde com a saudação dele"),
        ("Pergunta coberta pela base", "Resposta com citações [n] e, se ligado no agente, \"Fontes:\" com documento e página"),
        ("Pergunta fora da base", "Envia a frase \"quando não souber\" do agente, marca aguardando atendente e pausa o "
         "agente no contato"),
        ("Cliente pede atendente ou humano", "Responde \"Certo! Vou chamar uma pessoa da equipe...\", marca aguardando "
         "atendente e pausa o agente"),
        ("Mensagem enviada pelo celular do número", "Com a Evolution API, entra na conversa como Pelo celular, sem acionar o agente"),
        ("Confirmação de entrega (API oficial)", "As situações sent, delivered, read e failed atualizam a mensagem na tela"),
        ("Pessoa responde pela tela", "Envia como a equipe e pausa o agente naquele contato"),
        ("Devolver ao agente", "Religa a resposta automática no contato"),
        ("Mensagem que não é texto", "Fica registrada como mídia; o agente não responde"),
    ], larguras=["33%", "67%"])

    d.secao("Segurança")
    d.lista([
        "Tokens, app secret e chaves da Evolution ficam no banco e nunca voltam inteiros pela API: a tela mostra só os "
        "quatro últimos caracteres. Deixar o campo vazio ao editar mantém o valor.",
        "Webhook da Meta: verify token na confirmação e assinatura `X-Hub-Signature-256` (HMAC-SHA256 do corpo bruto com "
        "o app secret) em cada entrega; assinatura errada recebe 401.",
        "Webhook da Evolution: a URL leva um token aleatório (`?token=…`) que o Nexo confere a cada entrega.",
        "Só administradores criam e alteram conexões. Todos os usuários conectados podem atender na caixa de entrada.",
    ])

    d.secao("Solução de problemas")
    d.tabela(["Sintoma", "Causa provável", "O que fazer"], [
        ("QR code não aparece", "Endereço, chave ou instância da Evolution errados", "Confira os campos e se o servidor "
         "responde; veja a mensagem da situação"),
        ("Mensagens não chegam", "Webhook não registrado ou endereço não público", "Defina `NEXO_PUBLIC_URL` com HTTPS e "
         "clique em Registrar webhook (Evolution) ou confira o webhook no app da Meta"),
        ("Meta recusa a verificação", "Verify token diferente", "Copie o verify token exibido na conexão"),
        ("Entrega recebe 401", "App secret errado na conexão", "Copie de novo o app secret do app da Meta"),
        ("Mensagem marcada como falhou", "Token vencido ou fora da janela de 24 h", "Gere um token permanente; fora da "
         "janela, só modelos aprovados"),
        ("Agente não responde", "Sem agente no canal, resposta automática desligada ou contato com a equipe", "Escolha o "
         "agente, ligue a resposta automática e use Devolver ao agente"),
    ], larguras=["24%", "34%", "42%"])


def arquitetura(d):
    d.capitulo("Arquitetura",
               "O Nexo é um único processo Python que serve a API e a interface compilada. Os componentes pesados "
               "(modelos e banco vetorial) e o provedor de WhatsApp são plugáveis por configuração.")
    d.diagrama(f"""
flowchart LR
  N[{no("Navegador", "React 19 + TypeScript + Vite")}] --> API
  X[{no("Sistemas externos", "X-API-Key: nxk_… · recebem webhooks")}] --> API
  Z[{no("WhatsApp", "Evolution API ou Cloud API da Meta")}] --> API
  API[{no("API FastAPI · nexo/api", "REST e SSE em /api · JWT com versão ou chave de API · X-Request-ID · webhook do WhatsApp")}]
  API --> U[{no("Contas", "nexo/users.py")}]
  API --> R[{no("Motor RAG", "nexo/rag/engine.py")}]
  API --> K[{no("Leitura de arquivos", "nexo/knowledge.py")}]
  API --> WA[{no("WhatsApp", "nexo/whatsapp.py")}]
  API --> J[{no("Fila de indexação", "nexo/jobs.py")}]
  API --> WH[{no("Webhooks", "nexo/webhooks.py")}]
  API --> MG[{no("Migração", "nexo/migrations.py")}]
  R --> E[{no("Embeddings", "HuggingFace, OpenAI ou Ollama")}]
  R --> RR[{no("Reranker", "HuggingFace ou Cohere")}]
  R --> L[{no("Modelo de linguagem", "Ollama ou OpenAI")}]
  R --> V[{no("Banco vetorial", "ChromaDB ou Qdrant")}]
  MG --> DB[{no("Banco relacional", "SQLite, PostgreSQL, MySQL, SQL Server")}]
  class API escuro
  class N,X,Z,U,R,K,WA,J,WH,MG claro
  class E,RR,L,V,DB cinza
{ESTILO_FLUXO}
""", f"Componentes do Nexo {VERSAO[:3]}. O WhatsApp entra pelo webhook público e sai pelo provedor configurado em "
     "cada conexão.", altura_max_mm=125)

    d.secao("Módulos do código")
    d.tabela(["Arquivo", "Responsabilidade"], [
        ("`nexo/config.py`", "Lê o .env com pydantic-settings e define os caminhos em data/"),
        ("`nexo/db.py`", "Modelos SQLAlchemy das tabelas, criação automática e sessões"),
        ("`nexo/migrations.py`", "Migração automática de bancos da 2.0: colunas novas, base padrão e única de sha256 por base"),
        ("`nexo/knowledge.py`", "Leitura de DOCX, ODT, EPUB, PPTX, XLSX, TXT, MD, CSV, JSON, HTML e textos em partes para "
         "indexar, com o limite de 50 MB por item dos pacotes zip"),
        ("`nexo/whatsapp.py`", "Provedores Evolution, Cloud e simulador, webhook, contatos, resposta do agente e passagem "
         "para atendente"),
        ("`nexo/users.py`", "Contas em JSON: cadastro, criação pelo administrador, autenticação, bloqueio, troca e "
         "redefinição de senha, versão da sessão, perfil, exclusão e tutorial visto"),
        ("`nexo/security.py`", "Tokens JWT (HS256) com a versão da sessão e chaves de API"),
        ("`nexo/api/deps.py`", "Identifica o usuário pelo token ou pela chave de API, confere a versão da sessão e o perfil"),
        ("`nexo/jobs.py`", "Fila de indexação em uma thread, retomada de pendências e eventos document.*"),
        ("`nexo/webhooks.py`", "Seleciona os webhooks do evento, assina com HMAC e entrega em segundo plano, com até 3 tentativas"),
        ("`nexo/rag/engine.py`", "Divisão em trechos, indexação, busca, reranking, prompt do agente e resposta, inteira "
         "ou em pedaços para o streaming"),
        ("`nexo/rag/providers.py`", "Fábrica de LLM, embeddings, banco vetorial e reranker"),
        ("`nexo/api/routes.py`", "Rotas REST de autenticação, sessões, documentos e ações em lote, conversas, streaming, "
         "Refazer, busca, métricas e CSV, chaves, webhooks, contas e sistema"),
        ("`nexo/api/agents.py`", "Rotas de bases de conhecimento, textos, formatos e agentes"),
        ("`nexo/api/whatsapp.py`", "Rotas das conexões, do webhook público, dos contatos e das mensagens do WhatsApp"),
        ("`frontend/src`", "Interface React: páginas (Agents, Chats, Bases, WhatsApp e as da 2.0), componentes (Tutorial, "
         "paleta, trechos), cliente da API com leitura do streaming e temas"),
    ], larguras=["27%", "73%"])

    d.secao("Indexação de um item")
    d.lista([
        "O envio confere a extensão, o tamanho, o cabeçalho `%PDF` dos PDFs, o tamanho descompactado de cada item dos "
        "pacotes zip e o SHA-256 dentro da base; grava o arquivo em `data/uploads/<id>.<extensão>` e a linha em "
        "`nx_document` como PENDING.",
        "A fila lê o texto (pypdf para PDF, `nexo/knowledge.py` para os demais formatos e para os textos) em páginas ou partes.",
        "O SentenceSplitter do LlamaIndex divide em trechos de `NEXO_CHUNK_SIZE` tokens com sobreposição. Cada trecho "
        "guarda `source_id`, `title`, `filename`, `page` e `chunk_index`.",
        "Reindexar apaga os vetores antigos antes de gravar os novos. Ao terminar, a fila dispara `document.ready` ou "
        "`document.failed`.",
    ])

    d.secao("Respondendo uma pergunta", quebra=True)
    d.diagrama(f"""
flowchart TB
  P[{no("Pergunta", "conversa geral, /api/ask, agente ou Refazer")}] --> H[{no("Reescrita com o histórico", "NEXO_HISTORY_TURNS")}]
  H --> B[{no("Busca vetorial no escopo da conversa", "NEXO_TOP_K candidatos · status searching")}]
  B --> C1[{no("Corte 1 · similaridade mínima", "NEXO_MIN_SIMILARITY · nenhum trecho passa: resposta padrão")}]
  C1 --> R[{no("Reranking com cross-encoder", "HuggingFace ou Cohere")}]
  R --> C2[{no("Corte 2 · nota mínima do reranker", "NEXO_MIN_RERANK_SCORE · nenhum trecho passa: resposta padrão")}]
  C2 --> L[{no("LLM com prompt estrito e citações [n]", "NEXO_TOP_N trechos · status writing · eventos delta")}]
  L --> V[{no("Verificação de fidelidade (opcional)", "NEXO_VERIFY_ANSWERS")}]
  V --> F[{no("Resposta + fontes com página", "gravada no fim · evento done")}]
  class C1,C2 escuro
  class P,H,B,R,L,V,F claro
{ESTILO_FLUXO}
""", "Os dois cortes de relevância, em destaque, decidem se o modelo de linguagem é chamado. A busca nos trechos para "
     "no reranking e devolve os candidatos sem passar pelo modelo.", altura_max_mm=150)
    d.p("Quando nenhum trecho passa pelos cortes, o modelo de linguagem não é chamado: a resposta padrão \"Não encontrei "
        "essa informação nos documentos selecionados.\" é gravada com `answered = false`, os webhooks ativos recebem "
        "`question.unanswered` e a pergunta entra nas lacunas do painel. Numa conversa geral, o escopo é a lista de "
        "documentos escolhida (ou todo o acervo pronto); numa conversa com agente, é a base dele, como mostra a seção seguinte.")
    d.p("**Streaming.** Na rota `/messages/stream`, o mesmo caminho avisa `status` `searching` antes da busca e `writing` "
        "quando o modelo começa, manda o texto em eventos `delta` e só grava a troca no fim, no evento `done`. Se a "
        "conexão cair ou o usuário clicar em Parar, nada é gravado.")
    d.p("**Refazer.** `POST /api/messages/{id}/regenerate` roda o pipeline de novo com a pergunta original e só o "
        "histórico anterior a ela, e substitui a resposta no mesmo lugar da conversa: o texto, as fontes em "
        "`nx_message_source` e a avaliação anterior, que é apagada.")

    d.secao("Como o agente responde")
    d.diagrama(f"""
flowchart TB
  P[{no("Pergunta ao agente", "chat, /api/ask com bot_id ou WhatsApp")}] --> C{{"<b>Cumprimento?</b>"}}
  C -- sim --> S[{no("Devolve a saudação do agente")}]
  C -- não --> E[{no("Escopo = documentos prontos da base do agente", "filtro source_id IN (…) no banco vetorial")}]
  E --> B[{no("Reescrita, busca, corte 1, reranking e corte 2", "NEXO_TOP_K · NEXO_MIN_SIMILARITY · NEXO_MIN_RERANK_SCORE")}]
  B --> PR[{no("Prompt: regras estritas + instruções do agente + trechos numerados", "nome e tom vêm das instruções; as regras prevalecem")}]
  B -. sem trechos ou sem base .-> N[{no("Frase “quando não souber” do agente", "answered = false")}]
  class C escuro
  class P,E,B,PR claro
  class S,N cinza
{ESTILO_FLUXO}
""", "O agente usa o mesmo pipeline das conversas, limitado aos documentos da base dele.", altura_max_mm=120)
    d.p("A base não é uma coleção vetorial separada: todos os trechos ficam na mesma coleção, e a busca do agente filtra "
        "pelos ids dos documentos prontos da base dele. Por isso mover um item entre bases não exige reindexar, e uma "
        "base sem conteúdo pronto nunca cai na busca de todo o acervo: o Nexo avisa que a base ainda não tem conteúdo.")

    d.secao("Como as alucinações são reduzidas")
    d.tabela(["Mecanismo", "Efeito"], [
        ("Cortes de similaridade e de reranking", "Trechos fracos são descartados. Sem trechos, o LLM não é chamado"),
        ("Reranking com cross-encoder", "Reordena os candidatos por relevância real"),
        ("Prompt estrito", "Proíbe conhecimento próprio e exige citação [n]; as instruções do agente não podem mudar essas regras"),
        ("Base por agente", "Cada agente só enxerga os documentos da própria base, o que evita misturar assuntos"),
        ("Temperatura 0,1", "Respostas estáveis e próximas do texto"),
        ("Verificação de fidelidade", "Opcional: confere se a resposta é sustentada pelos trechos"),
        ("Passagem para atendente", "No WhatsApp, o que o agente não sabe vai para uma pessoa em vez de virar palpite"),
        ("Painel de qualidade", "Mostra lacunas e respostas mal avaliadas para corrigir as bases"),
    ], larguras=["34%", "66%"])

    d.secao("Segurança")
    d.lista([
        "Senhas só como hash bcrypt; cinco erros seguidos bloqueiam o usuário por 5 minutos. A senha nova precisa ser "
        "diferente da atual (`SAME_PASSWORD`).",
        "Sessões com JWT assinado por `NEXO_SECRET`; a interface guarda o token só na aba aberta (`sessionStorage`).",
        "Cada token leva a versão da sessão da conta (`session_version`). Trocar a senha, Sair dos outros dispositivos e "
        "a redefinição pelo administrador sobem a versão, e os tokens antigos passam a receber 401 `SESSION_REVOKED`.",
        "Chaves de API só como hash SHA-256, exibidas uma vez e revogáveis.",
        "Webhooks assinados com HMAC-SHA256; cadastro restrito a administradores.",
        "Conexões do WhatsApp criadas só por administradores; segredos mascarados; webhook da Meta com assinatura e o da "
        "Evolution com token.",
        "Conversas visíveis apenas para o dono. Bases e agentes só são alterados por quem criou ou por um administrador; "
        "um item pode ser excluído por quem enviou, pelo dono da base ou por um administrador. As ações em lote seguem "
        "as mesmas regras, item a item.",
        "Envios validados pela extensão, pelo tamanho, pelo cabeçalho dos PDFs, pelo SHA-256 e, nos pacotes zip, pelo "
        "limite de 50 MB descompactados por item; nomes saneados e arquivos gravados com o id interno.",
        "Cabeçalhos `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` e `Permissions-Policy` em todas as "
        "respostas; a API não é guardada em cache.",
        "Cada resposta leva `X-Request-ID`. Um id válido vindo do cliente ou do proxy é reaproveitado; sem ele, o Nexo gera um.",
    ])


def banco_de_dados(d):
    d.capitulo("Banco de dados",
               "Resumo da estrutura dos dados. As tabelas são criadas e migradas automaticamente; a versão detalhada, "
               "com índices, restrições, decisões e consultas, está em Banco-de-Dados-Nexo.pdf.")
    d.secao("Onde cada dado fica")
    d.tabela(["Camada", "Local padrão", "Conteúdo"], [
        ("Banco relacional", "`data/nexo.db`", "Bases, documentos, agentes, conversas, mensagens, fontes, avaliações, "
         "chaves, webhooks e WhatsApp"),
        ("Banco vetorial", "`data/chroma/` ou `data/qdrant/`", "Trechos, embeddings e metadados de origem"),
        ("Arquivos", "`data/uploads/<id>.<extensão>`", "Arquivos originais enviados às bases"),
        ("Contas", "`data/usuarios.json`", "Usuários, perfis, hashes de senha, versão da sessão e tutorial visto"),
        ("Segredo", "`data/.segredo`", "Chave das sessões quando NEXO_SECRET está vazio"),
    ], larguras=["20%", "32%", "48%"])

    d.secao("Diagrama de relacionamentos", quebra=True)
    d.diagrama(ER_DIAGRAMA, "As treze tabelas do Nexo. A 2.2 não muda nenhuma delas; `nx_api_key` e `nx_webhook` se "
               "ligam às contas pelo nome de usuário, sem chave estrangeira.", altura_max_mm=205)

    d.secao("Tabelas")
    d.tabela(["Tabela", "Uma linha por", "Ligações"], [
        ("`nx_knowledge_base`", "Base de conhecimento", "Pai de nx_document (CASCADE) e de nx_bot"),
        ("`nx_document`", "Arquivo ou texto de uma base", "base_id para nx_knowledge_base; único (base_id, sha256)"),
        ("`nx_bot`", "Agente", "base_id para nx_knowledge_base; pai das conversas do agente (CASCADE)"),
        ("`nx_conversation`", "Conversa", "bot_id para nx_bot (CASCADE), nulo nas conversas gerais"),
        ("`nx_conversation_document`", "Documento no escopo de uma conversa", "CASCADE dos dois lados"),
        ("`nx_message` / `nx_message_source` / `nx_feedback`", "Mensagem, trecho citado, avaliação", "Refazer troca a "
         "resposta, as fontes e apaga as avaliações dela"),
        ("`nx_api_key` / `nx_webhook`", "Chave de API, webhook", "Pelo nome de usuário, sem chave estrangeira"),
        ("`nx_whatsapp_channel`", "Número conectado", "bot_id para nx_bot (SET NULL)"),
        ("`nx_whatsapp_contact`", "Cliente de um número", "channel_id (CASCADE); único (channel_id, phone)"),
        ("`nx_whatsapp_message`", "Mensagem recebida ou enviada", "contact_id (CASCADE)"),
    ], larguras=["38%", "26%", "36%"])

    d.secao("Coleção vetorial")
    d.tabela(["Campo", "Conteúdo"], [
        ("`id`", "UUID v5 calculado de documento + posição do trecho"),
        ("`embedding`", "Vetor do modelo de NEXO_EMBED_MODEL, distância de cosseno"),
        ("`document`", "Texto do trecho"),
        ("`metadata.source_id`", "nx_document.id de origem; usado nos filtros de escopo, no filtro da base de cada agente e na exclusão"),
        ("`metadata.title` / `filename` / `page` / `chunk_index`", "Título, nome do arquivo, página ou parte (a partir de 1) "
         "e posição do trecho"),
    ], larguras=["36%", "64%"])

    d.secao("Arquivo de usuários")
    d.codigo("""
{
  "versao": 1,
  "usuarios": [
    { "username": "admin", "name": "Administrador", "role": "admin",
      "password_hash": "$2b$12$...", "created_at": "2026-01-01T12:00:00+00:00",
      "last_login_at": null, "tutorial_done_at": null,
      "session_version": 0, "password_changed_at": null }
  ]
}
""")
    d.p("O arquivo é regravado de forma atômica. Nomes de usuário têm de 3 a 32 caracteres minúsculos (letras, números, "
        "ponto, hífen e sublinhado). O administrador cria contas, redefine senhas, muda perfis e exclui contas pela tela "
        "Sistema e conta; o login pré-definido só é recriado se não houver nenhum administrador. `tutorial_done_at` "
        "guarda quando a conta viu o tutorial. `session_version` [[novo]] sobe a cada troca ou redefinição de senha e a "
        "cada Sair dos outros dispositivos, e `password_changed_at` [[novo]] guarda a última troca de senha. Para "
        "redefinir uma senha esquecida sem a tela, rode `python scripts/redefinir_senha.py nome-do-usuario` no servidor.")

    d.secao("Migração automática")
    d.p("Ao subir sobre um banco da 2.0, `nexo/migrations.py` cria as tabelas novas, acrescenta as colunas novas, cria a "
        "base \"Acervo geral\" e liga a ela todos os documentos existentes. No SQLite, a tabela `nx_document` é "
        "reconstruída seguindo os 12 passos oficiais (para trocar o único de sha256 pelo único por base); nos outros "
        "bancos, `ALTER TABLE`. Nenhum vetor precisa ser recalculado.")
    d.p(f"A {VERSAO} não muda nenhuma tabela: um banco da 2.1 sobe sem nenhuma alteração de esquema. Só o arquivo de "
        "contas ganha os dois campos novos, preenchidos sozinhos.")

    d.secao("Outro banco relacional")
    d.tabela(["Banco", "Driver", "NEXO_DATABASE_URL"], [
        ("PostgreSQL", "`pip install \"psycopg[binary]\"`", "`postgresql+psycopg://usuario:senha@host:5432/nexo`"),
        ("MySQL / MariaDB", "`pip install pymysql`", "`mysql+pymysql://usuario:senha@host:3306/nexo`"),
        ("SQL Server", "`pip install pyodbc`", "`mssql+pyodbc://usuario:senha@host/nexo?driver=ODBC+Driver+18+for+SQL+Server`"),
    ], larguras=["19%", "31%", "50%"])
    d.p("O DDL de referência está em `docs/schema-postgresql.sql` e `docs/schema-sqlite.sql`, e o resumo em "
        "`docs/banco-de-dados.md`.")


def api(d):
    d.capitulo("API",
               "A interface usa a mesma API REST que fica disponível para integrações. A documentação interativa "
               "(OpenAPI) abre em http://127.0.0.1:8000/api/docs.")
    d.secao("Autenticação")
    d.p("Fora `/api/health`, `/api/health/ready`, `/api/auth/options`, `/api/auth/login`, `/api/auth/register` e o "
        "webhook público `/api/whatsapp/webhook/{id}`, todas as rotas exigem `Authorization: Bearer <token JWT>` ou uma "
        "chave de API. As rotas marcadas como admin devolvem 403 `FORBIDDEN` para os demais. Todas as respostas trazem "
        "`X-Request-ID`.")

    def m(x):
        return f'RAW:<span class="metodo">{x}</span>'

    d.secao("Rotas")
    d.tabela(["Método", "Rota", "Descrição"], [
        "Sessão e conta",
        (m("GET"), "`/api/health`", "Situação do servidor e versão"),
        (m("GET"), "`/api/health/ready` [[novo]]", "Prontidão: confere o banco; 503 quando ele não responde"),
        (m("GET"), "`/api/auth/options`", "Cadastro aberto e se o login pré-definido ainda está ativo"),
        (m("POST"), "`/api/auth/login` · `/api/auth/register`", "Entrar e criar conta"),
        (m("GET / PATCH"), "`/api/auth/me`", "Usuário da sessão, com tutorial_done_at; PATCH {\"name\"} troca o próprio nome [[novo]]"),
        (m("PUT"), "`/api/auth/password`", "Trocar a própria senha. Encerra as outras sessões e devolve uma sessão nova (200)"),
        (m("POST"), "`/api/auth/sessions/revoke` [[novo]]", "Sair dos outros dispositivos; devolve uma sessão nova para este"),
        (m("PUT"), "`/api/auth/tutorial`", "Marcar o tutorial como visto ({\"done\": true}) ou para rever (false)"),
        (m("GET"), "`/api/system/status`", "Configuração ativa e números do acervo"),
        "Bases de conhecimento",
        (m("GET / POST"), "`/api/bases`", "Listar com os números de cada base, ou criar"),
        (m("GET / PATCH / DELETE"), "`/api/bases/{id}`", "Abrir, renomear ou excluir (409 se usada por agente ou se for a padrão)"),
        (m("GET / POST"), "`/api/bases/{id}/documents`", "Listar itens ou enviar arquivos (multipart, campo files)"),
        (m("POST"), "`/api/bases/{id}/texts`", "Criar um texto {\"title\", \"content\"}"),
        (m("GET"), "`/api/formats`", "Extensões aceitas e tamanho máximo"),
        "Documentos",
        (m("GET / POST"), "`/api/documents`", "Listar todos ou enviar (campo base_id opcional)"),
        (m("POST"), "`/api/documents/bulk` [[novo]]", "Ações em lote {\"action\": \"reindex\" | \"delete\" | \"move\", \"ids\", "
         "\"base_id\"?}; informa os itens pulados"),
        (m("GET / PATCH"), "`/api/documents/{id}`", "Detalhes; renomear (reindexa) ou mover de base (base_id, sem reindexar)"),
        (m("GET / PUT"), "`/api/documents/{id}/text`", "Ler ou editar um texto (reindexa)"),
        (m("GET"), "`/api/documents/{id}/file`", "Baixar o arquivo original"),
        (m("POST"), "`/api/documents/{id}/reindex`", "Reindexar"),
        (m("DELETE"), "`/api/documents/{id}`", "Excluir arquivo, vetores e escopos"),
        "Agentes, conversas e busca",
        (m("GET / POST"), "`/api/bots`", "Listar ou criar agentes"),
        (m("GET / PATCH / DELETE"), "`/api/bots/{id}`", "Abrir, editar ou excluir (apaga as conversas do agente)"),
        (m("GET / POST"), "`/api/conversations`", "Listar (filtros only=general|bots, bot_id e q, que procura no título e "
         "nas mensagens) ou criar (bot_id opcional)"),
        (m("GET / PATCH / DELETE"), "`/api/conversations/{id}`", "Abrir, renomear ou mudar escopo, excluir"),
        (m("GET"), "`/api/conversations/{id}/export`", "Exportar em markdown ou json"),
        (m("POST"), "`/api/conversations/{id}/messages`", "Perguntar (resposta JSON)"),
        (m("POST"), "`/api/conversations/{id}/messages/stream` [[novo]]", "Perguntar com resposta em Server-Sent Events: "
         "status, delta, done e error"),
        (m("POST"), "`/api/messages/{id}/regenerate` [[novo]]", "Refazer a resposta no lugar; renova as fontes e apaga a avaliação"),
        (m("POST"), "`/api/messages/{id}/feedback`", "Avaliar resposta"),
        (m("POST"), "`/api/ask`", "Pergunta direta, com bot_id opcional"),
        (m("POST"), "`/api/search`", "Busca nos trechos, com base_id opcional"),
        (m("GET"), "`/api/metrics?days=30`", "Painel de qualidade"),
        (m("GET"), "`/api/metrics/export?days=N` [[novo]]", "CSV com data, conversa, pergunta, respondida, avaliação, latência e fontes"),
        "WhatsApp",
        (m("GET / POST"), "`/api/whatsapp/channels`", "Listar conexões ou criar (admin)"),
        (m("PATCH / DELETE"), "`/api/whatsapp/channels/{id}`", "Editar, pausar ou excluir (admin)"),
        (m("GET"), "`/api/whatsapp/channels/{id}/status`", "Situação da conexão: open, connecting, close ou unknown"),
        (m("GET"), "`/api/whatsapp/channels/{id}/qrcode`", "QR code e código de pareamento (Evolution)"),
        (m("POST"), "`/api/whatsapp/channels/{id}/webhook`", "Registrar o webhook na Evolution ou obter a URL para a Meta"),
        (m("POST"), "`/api/whatsapp/channels/{id}/simulate`", "Simular mensagem de cliente (simulador)"),
        (m("GET / POST"), "`/api/whatsapp/webhook/{id}`", "Webhook público chamado pelo WhatsApp"),
        (m("GET"), "`/api/whatsapp/summary`", "Números da caixa de entrada"),
        (m("GET"), "`/api/whatsapp/contacts`", "Contatos, com channel_id, filter e q"),
        (m("GET / PATCH"), "`/api/whatsapp/contacts/{id}`", "Conversa (marca como lida); ligar ou pausar o agente, nome"),
        (m("POST"), "`/api/whatsapp/contacts/{id}/messages`", "Responder como a equipe"),
        (m("POST"), "`/api/whatsapp/contacts/{id}/suggest`", "Sugestão de resposta do agente, sem enviar"),
        "Integrações e contas",
        (m("GET / POST / DELETE"), "`/api/keys` · `/api/keys/{id}`", "Chaves de API do usuário"),
        (m("GET / POST / PATCH / DELETE"), "`/api/webhooks` · `/api/webhooks/{id}`", "Webhooks (admin)"),
        (m("POST"), "`/api/webhooks/{id}/test`", "Entregar ping (admin)"),
        (m("GET / POST"), "`/api/users`", "Listar contas ou criar uma {name, username, password, role} (admin), mesmo com "
         "o cadastro fechado"),
        (m("PUT"), "`/api/users/{usuario}/password` [[novo]]", "Redefinir a senha {password}; encerra as sessões e libera o bloqueio (admin)"),
        (m("PATCH / DELETE"), "`/api/users/{usuario}`", "Mudar perfil ou excluir conta (admin)"),
    ], larguras=["17%", "42%", "41%"], cls="compacta")

    d.secao("Exemplo com curl")
    d.codigo("""
curl -X POST http://127.0.0.1:8000/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"username": "admin", "password": "Nexo@2026"}'

curl -X POST http://127.0.0.1:8000/api/bases \\
  -H "Authorization: Bearer SEU_TOKEN" -H "Content-Type: application/json" \\
  -d '{"name": "Suporte técnico"}'

curl -X POST http://127.0.0.1:8000/api/bots \\
  -H "Authorization: Bearer SEU_TOKEN" -H "Content-Type: application/json" \\
  -d '{"name": "Técnico", "base_id": "ID_DA_BASE", "greeting": "Olá! Como posso ajudar?"}'

curl -X POST http://127.0.0.1:8000/api/conversations \\
  -H "Authorization: Bearer SEU_TOKEN" -H "Content-Type: application/json" \\
  -d '{"bot_id": "ID_DO_AGENTE"}'

curl -X POST http://127.0.0.1:8000/api/users \\
  -H "Authorization: Bearer SEU_TOKEN" -H "Content-Type: application/json" \\
  -d '{"name": "Ana Souza", "username": "ana", "password": "Troque-1234", "role": "user"}'

curl -X POST http://127.0.0.1:8000/api/auth/sessions/revoke -H "Authorization: Bearer SEU_TOKEN"
""")

    d.secao("Erros")
    d.p("Todo erro volta como JSON com `code`, `message` e, quando for de campo, `fields`.")
    d.tabela(["HTTP", "code", "Quando"], [
        ("400", "`EMPTY` / `NO_FILES` / `UNKNOWN_DOCUMENT`", "Pergunta vazia, envio sem arquivos ou escopo com documento que não existe"),
        ("400", "`SELF` / `LAST_ADMIN`", "Rebaixar ou excluir a própria conta, ou o último administrador"),
        ("400", "`SAME_PASSWORD` [[novo]]", "Senha nova igual à atual"),
        ("400", "`INVALID_URL` / `INVALID_EVENTS`", "Webhook com URL inválida ou eventos desconhecidos"),
        ("400", "`NOT_A_NOTE` / `INVALID_PROVIDER`", "Editar como texto um item que é arquivo; provedor de WhatsApp desconhecido"),
        ("401", "`UNAUTHENTICATED` / `SESSION_EXPIRED` / `INVALID_API_KEY`", "Sem credencial, token vencido ou chave inválida"),
        ("401", "`SESSION_REVOKED` [[novo]]", "Sessão encerrada por troca ou redefinição de senha ou por Sair dos outros dispositivos"),
        ("401", "`INVALID_SIGNATURE`", "Webhook do WhatsApp com assinatura ou token errado"),
        ("403", "`FORBIDDEN` / `REGISTRATION_DISABLED`", "Rota de administrador, ação sobre conteúdo de outra pessoa ou cadastro fechado"),
        ("404", "`NOT_FOUND` / `FILE_MISSING`", "Registro inexistente ou de outro usuário; arquivo original ausente"),
        ("409", "`DUPLICATE` / `NO_DOCUMENTS` / `BASE_EMPTY`", "Arquivo repetido na base, pergunta sem documentos prontos ou "
         "agente com base vazia"),
        ("409", "`BASE_IN_USE` / `DEFAULT_BASE`", "Excluir base usada por agente ou a base padrão"),
        ("413 / 415", "`FILE_TOO_LARGE` / `NOT_A_PDF` / `UNSUPPORTED`", "Arquivo grande demais (inclusive item de pacote zip "
         "acima de 50 MB), PDF inválido ou formato não aceito"),
        ("422", "`VALIDATION`", "Corpo fora do formato, com os campos em fields"),
        ("429", "`LOCKED`", "Cinco senhas erradas seguidas"),
        ("502 / 503", "`LLM_FAILURE` / `PROVIDER` / `WHATSAPP`", "Modelo fora do ar, provedor ausente ou WhatsApp recusou o pedido"),
    ], larguras=["11%", "41%", "48%"])
    d.p("Na rota de streaming, um erro depois do início da resposta chega como evento `error` com os mesmos `code` e "
        "`message`, porque o status HTTP 200 já foi enviado.")


def qualidade(d):
    d.capitulo("Qualidade e manutenção",
               "Testes automatizados, medição da busca, integração contínua, backup e solução de problemas.")
    d.secao("Testes automatizados")
    d.codigo("""
pip install -r requirements-ci.txt
python -m pytest
""")
    n = contar_testes()
    d.p(f"São {n} testes. Eles rodam sem internet nem modelos (embedding hash, modo extrativo, reranker desligado) e "
        "cobrem: login, bloqueio, cadastro, senhas, envio e indexação, resposta com fonte e página, pergunta fora do "
        "conteúdo, isolamento entre usuários, avaliação, arquivos inválidos e duplicados, permissões, remoção dos vetores, "
        "escopo, reranking, scripts, busca, exportação, métricas, chaves, pergunta direta, webhooks e contas; as bases, "
        "os textos, mover entre bases, agentes, conversas com agentes, a migração de um banco da 2.0, o tutorial e o "
        "WhatsApp (simulador, webhook da Meta com assinatura, Evolution com token, envio, passagem para atendente e sugestão).")
    d.p(f"Na {VERSAO[:3]} entram `tests/test_streaming.py` (eventos status, delta, done e error, cancelamento sem gravar e "
        "Refazer) e `tests/test_formatos.py` (EPUB, PPTX, XLSX, ODT e o limite dos pacotes zip), além de casos novos para "
        "as sessões com versão, a criação de contas e a redefinição de senha pelo administrador, as ações em lote, o CSV "
        "do painel, as novas tentativas dos webhooks, o `X-Request-ID` e a rota de prontidão.")

    d.secao("Medindo a recuperação")
    d.codigo("""
{"pergunta": "Como restaurar as configurações de fábrica?", "documento": "manual-exemplo.pdf", "pagina": 2}
{"pergunta": "Qual a temperatura de operação?", "documento": "manual-exemplo.pdf", "pagina": 5}
""")
    d.codigo("python scripts/avaliar.py exemplos/perguntas-exemplo.jsonl --detalhes")
    d.p("O script mostra, para a busca vetorial pura e com reranking, o acerto e o MRR. Repita depois de cada ajuste de parâmetros.")

    d.secao("Integração contínua")
    d.p("O workflow `.github/workflows/ci.yml` roda os testes do Python e o build da interface a cada push e pull request.")

    d.secao("Commit automático diário")
    d.p("O workflow `.github/workflows/diario.yml` acrescenta a data e a hora em `.github/atividade.txt` e faz um commit "
        "todos os dias às 11h37 de Brasília. Para ativar, crie os segredos `GIT_NAME` e `GIT_EMAIL` em **Settings › Secrets "
        "and variables › Actions** e marque **Read and write permissions** em **Settings › Actions › General**.")

    d.secao("Backup")
    d.p("Pare o servidor e copie a pasta `data` inteira: banco SQLite (com bases, agentes, chaves, webhooks, conexões e "
        "conversas do WhatsApp), vetores locais, arquivos, usuários e segredo. Com bancos externos, faça também o backup "
        "deles no mesmo momento.")
    d.nota("O backup contém segredos.", "Os segredos dos webhooks, os tokens do WhatsApp e `data/.segredo` estão nele. "
           "Guarde as cópias com o mesmo cuidado de uma senha.", alerta=True)

    d.secao("Atualizando dependências")
    d.codigo("""
pip install --upgrade -r requirements.txt
cd frontend && npm update && npm run build
""")

    d.secao("Solução de problemas")
    d.tabela(["Sintoma", "Causa provável", "O que fazer"], [
        ("\"O modelo não respondeu\"", "Ollama desligado ou modelo não baixado", "Abra o Ollama e rode `ollama pull llama3.1`"),
        ("\"Instale o pacote ...\"", "Provedor sem a biblioteca", "pip install do pacote indicado"),
        ("Item em Falhou: sem texto", "PDF digitalizado ou arquivo vazio", "Aplique OCR (OCRmyPDF) ou envie o texto pela aba Textos"),
        ("Formato não aceito (415)", "Extensão fora da lista", "Converta para PDF, DOCX, ODT, EPUB, PPTX, XLSX, TXT, MD, CSV, JSON ou HTML"),
        ("EPUB, PPTX, XLSX ou ODT recusado (413)", "Algum item do pacote passa de 50 MB descompactado", "Divida o arquivo ou "
         "reduza as imagens embutidas"),
        ("Agente diz que a base não tem conteúdo", "Base vazia ou itens ainda indexando", "Envie arquivos ou textos e aguarde Pronto"),
        ("Respostas sempre \"Não encontrei\"", "Cortes de relevância altos", "Veja as notas na aba Testar e baixe os cortes"),
        ("Resposta aparece só no fim, de uma vez", "Proxy guardando a resposta em buffer", "Desligue o buffer da rota de "
         "streaming (seção 3.5)"),
        ("Sessão encerrada de repente", "Senha trocada ou redefinida, ou Sair dos outros dispositivos (401 SESSION_REVOKED)",
         "Entre de novo com a senha atual"),
        ("Não consigo excluir uma base", "Algum agente usa a base, ou é a padrão", "Troque a base do agente antes"),
        ("Integração recebe 401", "Chave revogada ou errada", "Crie uma chave nova e confira o cabeçalho X-API-Key"),
        ("Receptor recusa a assinatura", "HMAC sobre o JSON reformatado", "Calcule sobre o corpo bruto e confira o segredo"),
        ("Receptor recebe o mesmo evento duas vezes", "Nova tentativa depois de uma resposta lenta", "Ignore repetições "
         "pelo X-Nexo-Delivery"),
        ("WhatsApp não recebe mensagens", "Webhook não registrado", "Veja a seção 6.7"),
        ("Tutorial não aparece mais", "Já foi visto pela conta", "Use Ver tutorial na paleta ou em Sistema e conta"),
        ("Tela em branco em /", "Interface não compilada", "cd frontend, npm ci e npm run build"),
        ("Esqueci a senha do admin", "Senha trocada e perdida", "Outro administrador usa Redefinir senha; sem nenhum, rode "
         "`python scripts/redefinir_senha.py admin`"),
    ], larguras=["30%", "33%", "37%"])


def montar(temp):
    d = Documento("Manual técnico", temp)
    d.capa("Manual técnico",
           "Agentes de IA com bases de conhecimento próprias, chats com vários agentes e atendimento pelo WhatsApp, com "
           "respostas baseadas somente nos documentos enviados. Instalação, configuração, cada tela, integrações, "
           "arquitetura, banco de dados, API e manutenção, passo a passo.")
    d.lugar_do_sumario()
    visao_geral(d)
    instalacao(d)
    configuracao(d)
    usando(d)
    integracoes(d)
    whatsapp(d)
    arquitetura(d)
    banco_de_dados(d)
    api(d)
    qualidade(d)
    return d
