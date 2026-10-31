# Arquitetura de dados do Nexo

O Nexo guarda informações em **três lugares**, cada um com um papel:

| Camada | Onde fica (padrão) | O que guarda |
|---|---|---|
| Banco relacional | `data/nexo.db` (SQLite) ou o banco de `NEXO_DATABASE_URL` | Bases de conhecimento, documentos e textos, agentes, conversas, mensagens, fontes citadas, avaliações, chaves de API, webhooks e WhatsApp (conexões, contatos e mensagens) |
| Banco vetorial | `data/chroma/` (ChromaDB) ou Qdrant | Trechos dos arquivos com os embeddings e os metadados de origem |
| Arquivos | `data/usuarios.json` e `data/uploads/` | Contas de acesso (com o tutorial visto) e os arquivos originais (`<id>.<extensão>`) |

As tabelas são criadas automaticamente na primeira execução, e bancos da 2.0 são migrados sozinhos para a 2.1 por `nexo/migrations.py` (veja [Migração automática](#migração-automática)). Os arquivos `schema-postgresql.sql` e `schema-sqlite.sql` desta pasta trazem o DDL equivalente para quem prefere criar o banco manualmente.

## Diagrama de relacionamentos

```mermaid
erDiagram
    nx_knowledge_base ||--o{ nx_document : "contém"
    nx_knowledge_base ||--o{ nx_bot : "usada por"
    nx_bot |o--o{ nx_conversation : "conversa"
    nx_bot |o--o{ nx_whatsapp_channel : "atende"
    nx_whatsapp_channel ||--o{ nx_whatsapp_contact : "clientes"
    nx_whatsapp_contact ||--o{ nx_whatsapp_message : "mensagens"
    nx_document ||--o{ nx_conversation_document : "escopo"
    nx_conversation ||--o{ nx_conversation_document : "consulta"
    nx_conversation ||--o{ nx_message : "contém"
    nx_message ||--o{ nx_message_source : "cita"
    nx_document |o--o{ nx_message_source : "origem"
    nx_message ||--o{ nx_feedback : "recebe"

    nx_knowledge_base {
        varchar32 id PK
        varchar120 name
        text description
        varchar16 color
        boolean is_default
        varchar32 created_by
        timestamp created_at
        timestamp updated_at
    }
    nx_bot {
        varchar32 id PK
        varchar80 name
        varchar300 description
        varchar32 base_id FK
        text instructions
        varchar500 greeting
        varchar500 fallback
        varchar16 color
        boolean cite_sources
        varchar32 created_by
    }
    nx_whatsapp_channel {
        varchar32 id PK
        varchar80 name
        varchar16 provider
        varchar32 bot_id FK
        boolean auto_reply
        boolean active
        varchar64 verify_token
        varchar64 webhook_token
    }
    nx_whatsapp_contact {
        varchar32 id PK
        varchar32 channel_id FK
        varchar32 phone UK
        varchar120 name
        boolean bot_enabled
        boolean needs_human
        int unread
        timestamp last_message_at
    }
    nx_whatsapp_message {
        varchar32 id PK
        varchar32 contact_id FK
        varchar3 direction
        varchar40 author
        text body
        varchar12 status
        varchar128 external_id
        boolean answered
        text sources_json
    }
    nx_document {
        varchar32 id PK
        varchar32 base_id FK
        varchar10 kind
        varchar10 extension
        text content
        varchar200 title
        varchar255 filename
        varchar64 sha256 UK
        int size_bytes
        int pages
        int chunks
        varchar20 status
        text error
        varchar32 uploaded_by
        timestamp created_at
        timestamp indexed_at
    }
    nx_conversation {
        varchar32 id PK
        varchar32 owner
        varchar32 bot_id FK
        varchar160 title
        timestamp created_at
        timestamp updated_at
    }
    nx_conversation_document {
        varchar32 conversation_id PK, FK
        varchar32 document_id PK, FK
    }
    nx_message {
        varchar32 id PK
        varchar32 conversation_id FK
        varchar10 role
        text content
        boolean answered
        boolean grounded
        varchar120 model
        int latency_ms
        timestamp created_at
    }
    nx_message_source {
        int id PK
        varchar32 message_id FK
        varchar32 document_id FK
        varchar200 document_title
        varchar80 chunk_id
        int page
        int rank
        float similarity
        float rerank_score
        text excerpt
    }
    nx_feedback {
        int id PK
        varchar32 message_id FK
        varchar32 owner
        int rating
        text comment
        timestamp created_at
    }
    nx_api_key {
        varchar32 id PK
        varchar32 owner
        varchar80 name
        varchar16 prefix
        varchar64 key_hash UK
        timestamp created_at
        timestamp last_used_at
    }
    nx_webhook {
        varchar32 id PK
        varchar500 url
        varchar300 events
        varchar80 secret
        boolean active
        varchar32 created_by
        timestamp created_at
        int last_status
        text last_error
        timestamp last_delivery_at
    }
```

`nx_api_key` e `nx_webhook` não têm chaves estrangeiras: `owner` e `created_by` apontam para contas do `usuarios.json`.

## Tabelas

### nx_knowledge_base
Uma linha por base de conhecimento (o "RAG" de cada agente). A base padrão, "Acervo geral" (`is_default`), é criada sozinha, recebe os documentos antigos e os envios sem base e não pode ser excluída.

| Coluna | Tipo | Regra |
|---|---|---|
| id | varchar(32) | Chave primária, UUID em hexadecimal |
| name | varchar(120) | Nome da base |
| description | text | Descrição curta, opcional |
| color | varchar(16) | Cor de destaque na interface |
| is_default | boolean | Verdadeiro só na base padrão |
| created_by | varchar(32) | Quem criou; ele e os administradores editam e excluem |
| created_at / updated_at | timestamp | Criação e última alteração, em UTC |

Uma base usada por algum agente não pode ser excluída (409 `BASE_IN_USE`). Excluir uma base apaga os itens dela, com os vetores e os arquivos.

### nx_document
Um registro por arquivo enviado ou texto criado numa base.

| Coluna | Tipo | Regra |
|---|---|---|
| id | varchar(32) | Chave primária, UUID em hexadecimal. O arquivo fica em `data/uploads/<id>.<extensão>` |
| base_id | varchar(32) | FK para `nx_knowledge_base`, `ON DELETE CASCADE`. Trocar o valor move o item de base sem reindexar |
| kind | varchar(10) | `pdf`, `file` (DOCX, TXT, MD, CSV, JSON, HTML) ou `note` (texto digitado na base) |
| extension | varchar(10) | `pdf`, `docx`, `txt`, `md`, `csv`, `json`, `html` ou `note` |
| content | text | O texto, quando `kind = note` |
| title | varchar(200) | Título dos metadados do PDF, o nome do arquivo ou o título do texto |
| filename | varchar(255) | Nome original, saneado |
| sha256 | varchar(64) | Único junto com `base_id` (`uk_document_base_sha256`). Impede o mesmo conteúdo duas vezes na mesma base |
| size_bytes | integer | Tamanho do arquivo |
| pages | integer | Páginas do PDF ou partes do texto nos demais formatos |
| chunks | integer | Trechos gravados no banco vetorial |
| status | varchar(20) | `PENDING`, `PROCESSING`, `READY` ou `FAILED` |
| error | text | Motivo da falha, quando houver |
| uploaded_by | varchar(32) | Usuário que enviou (ver `usuarios.json`) |
| created_at / indexed_at | timestamp | Envio e fim da indexação, em UTC |
| updated_at | timestamp | Última edição de um texto |

### nx_bot
Um agente: nome, instruções e a base de conhecimento de onde tira as respostas.

| Coluna | Tipo | Regra |
|---|---|---|
| id | varchar(32) | Chave primária, UUID em hexadecimal |
| name / description | varchar(80) / varchar(300) | Nome e descrição do agente |
| base_id | varchar(32) | FK para `nx_knowledge_base`, sem cascata |
| instructions | text | Tom e regras somadas ao prompt estrito do Nexo |
| greeting | varchar(500) | Saudação; responde a cumprimentos como "oi" |
| fallback | varchar(500) | Frase usada quando a base não tem a resposta |
| color | varchar(16) | Cor do selo do agente |
| cite_sources | boolean | Acrescenta "Fontes:" nas respostas enviadas pelo WhatsApp |
| created_by / created_at / updated_at | varchar(32) / timestamp | Quem criou, criação e última alteração |

O agente não tem coleção vetorial própria: a busca filtra pelos documentos prontos da base dele.

### nx_conversation
Uma conversa pertence a um único usuário (`owner`). Ninguém mais consegue abri-la. `bot_id` (FK para `nx_bot`, `ON DELETE CASCADE`) liga a conversa a um agente; nas conversas gerais fica nulo.

### nx_conversation_document
Escopo da conversa. Sem linhas, a conversa consulta todos os documentos prontos. Com linhas, a busca vetorial é filtrada pelos documentos listados. Excluir um documento remove-o do escopo (`ON DELETE CASCADE`).

### nx_message
Perguntas (`role = user`) e respostas (`role = assistant`). Nas respostas:
- `answered = false` quando nada relevante foi encontrado e o Nexo respondeu que não achou a informação;
- `grounded` traz o resultado da verificação de fidelidade (`NEXO_VERIFY_ANSWERS=true`), ou fica nulo;
- `model` e `latency_ms` registram quem respondeu e em quanto tempo.

### nx_message_source
Os trechos efetivamente enviados ao modelo, na ordem das citações `[1]`, `[2]`... `similarity` é a similaridade de cosseno da busca vetorial e `rerank_score` é a nota do reranker. `document_id` vira nulo se o documento for excluído, mas o título e o trecho continuam guardados para manter o histórico legível.

### nx_feedback
Avaliação de cada resposta: `rating` 1 (útil) ou -1 (não ajudou). Um usuário tem no máximo uma avaliação por resposta (`uk_feedback_message_owner`).

### nx_api_key
Chaves de API para integrações (planilhas, scripts, outros sistemas). Cada chave age com as permissões do dono.

| Coluna | Tipo | Regra |
|---|---|---|
| id | varchar(32) | Chave primária, UUID em hexadecimal |
| owner | varchar(32) | Dono da chave (ver `usuarios.json`). Se a conta deixar de existir, a chave para de valer |
| name | varchar(80) | Nome dado pelo usuário, como "Planilha de leads" |
| prefix | varchar(16) | Primeiros 12 caracteres da chave (`nxk_...`), para reconhecê-la na lista |
| key_hash | varchar(64) | Único. SHA-256 da chave. A chave completa aparece uma única vez, na criação, e não é guardada |
| created_at / last_used_at | timestamp | Criação e último uso, em UTC |

A chave vai no cabeçalho `X-API-Key` ou em `Authorization: Bearer nxk_...`. Excluir a linha revoga o acesso na hora.

### nx_webhook
Avisos enviados por POST a outros sistemas quando algo acontece no Nexo. Só administradores cadastram webhooks.

| Coluna | Tipo | Regra |
|---|---|---|
| id | varchar(32) | Chave primária, UUID em hexadecimal |
| url | varchar(500) | Endereço `http://` ou `https://` que recebe os avisos |
| events | varchar(300) | Eventos assinados, separados por vírgula: `document.ready`, `document.failed`, `question.unanswered`, `feedback.negative` |
| secret | varchar(80) | Segredo da assinatura `X-Nexo-Signature: sha256=<HMAC-SHA256 do corpo>`. Fica em texto, porque é preciso para assinar |
| active | boolean | Webhook desativado não recebe avisos |
| created_by | varchar(32) | Administrador que cadastrou |
| created_at | timestamp | Cadastro, em UTC |
| last_status | integer | Código HTTP da última entrega, ou nulo se o destino não respondeu |
| last_error | text | Motivo da última falha, quando houver |
| last_delivery_at | timestamp | Última tentativa de entrega, em UTC |

Cada entrega tem tempo limite de `NEXO_WEBHOOK_TIMEOUT` segundos (padrão 5) e não é repetida em caso de falha. Na 2.1 entram os eventos `whatsapp.message` e `whatsapp.handoff`.

### nx_whatsapp_channel
Um número de WhatsApp conectado. Só administradores criam e alteram. Os segredos nunca voltam inteiros pela API.

| Coluna | Tipo | Regra |
|---|---|---|
| id | varchar(32) | Chave primária; faz parte da URL do webhook `/api/whatsapp/webhook/{id}` |
| name | varchar(80) | Nome da conexão |
| provider | varchar(16) | `evolution` (QR code do próprio número), `cloud` (API oficial da Meta) ou `simulador` |
| bot_id | varchar(32) | FK para `nx_bot`, `ON DELETE SET NULL`. Agente que responde |
| auto_reply / active | boolean | Resposta automática ligada; conexão ativa |
| phone | varchar(32) | Número exibido |
| verify_token | varchar(64) | Token da confirmação do webhook da Meta |
| webhook_token | varchar(64) | Token na URL do webhook da Evolution (`?token=`) |
| api_version / phone_number_id / access_token / app_secret | varchar / text | API oficial: versão da Graph API, id do número, token e segredo do app (assinatura `X-Hub-Signature-256`) |
| base_url / api_key / instance | varchar | Evolution API: servidor, chave e instância |
| created_by / created_at | varchar(32) / timestamp | Quem criou e quando |
| last_event_at / last_error | timestamp / text | Último evento recebido e último erro de envio |

### nx_whatsapp_contact
Um cliente que escreveu para um número. Único por (`channel_id`, `phone`).

| Coluna | Tipo | Regra |
|---|---|---|
| id | varchar(32) | Chave primária |
| channel_id | varchar(32) | FK para `nx_whatsapp_channel`, `ON DELETE CASCADE` |
| phone / name | varchar(32) / varchar(120) | Número do cliente e nome do perfil |
| bot_enabled | boolean | Agente respondendo neste contato; falso quando a equipe assume |
| needs_human | boolean | Aguardando atendente (o agente não sabia ou o cliente pediu uma pessoa) |
| unread | integer | Mensagens do cliente ainda não abertas na tela |
| last_message_at / created_at | timestamp | Ordena a caixa de entrada; primeiro contato |

### nx_whatsapp_message
Cada mensagem recebida ou enviada.

| Coluna | Tipo | Regra |
|---|---|---|
| id | varchar(32) | Chave primária |
| contact_id | varchar(32) | FK para `nx_whatsapp_contact`, `ON DELETE CASCADE`; índice com `created_at` |
| direction | varchar(3) | `in` (cliente) ou `out` (agente ou equipe) |
| author | varchar(40) | `cliente`, `agente` ou o usuário que respondeu |
| body | text | Texto da mensagem |
| status | varchar(12) | `received`, `pending`, `sent`, `delivered`, `read` ou `failed` |
| external_id | varchar(128) | Id da mensagem no provedor, para atualizar a situação da entrega |
| error | text | Erro devolvido pelo provedor |
| answered | boolean | Nas respostas do agente, falso quando a base não tinha a resposta |
| sources_json | text | Fontes da resposta do agente, em JSON |

## Banco vetorial

Coleção padrão: `nexo_trechos` (`NEXO_COLLECTION`), com distância de cosseno.

| Campo | Conteúdo |
|---|---|
| id | UUID v5 calculado a partir do documento e da posição do trecho |
| embedding | Vetor do modelo configurado em `NEXO_EMBED_MODEL` |
| document | Texto do trecho (até `NEXO_CHUNK_SIZE` tokens, com `NEXO_CHUNK_OVERLAP` de sobreposição) |
| metadata.source_id | `nx_document.id` do item de origem; filtra o escopo das conversas e a base de cada agente |
| metadata.title | Título do documento |
| metadata.filename | Nome do arquivo |
| metadata.page | Página do PDF (ou parte, nos demais formatos), começando em 1 |
| metadata.chunk_index | Posição do trecho dentro do documento |

O título entra no texto usado para gerar o embedding, o que ajuda perguntas como "no manual da bomba, ...". Trocar o modelo de embeddings exige reindexar todos os documentos, porque vetores de modelos diferentes não são comparáveis. Use uma coleção nova (`NEXO_COLLECTION`) ou o botão de reindexar de cada documento.

## Arquivo de usuários

`data/usuarios.json`:

```json
{
  "versao": 1,
  "usuarios": [
    {
      "username": "admin",
      "name": "Administrador",
      "role": "admin",
      "password_hash": "$2b$12$...",
      "created_at": "2026-01-01T12:00:00+00:00",
      "last_login_at": null,
      "tutorial_done_at": "2026-10-30T14:02:11+00:00"
    }
  ]
}
```

- Senhas são guardadas só como hash bcrypt.
- `role` é `admin` (pode excluir qualquer documento, gerencia contas e webhooks) ou `user`.
- Excluir uma conta apaga também as chaves de API e as conversas dela.
- O arquivo é regravado de forma atômica a cada alteração.
- `tutorial_done_at` marca quando a conta concluiu ou pulou o tutorial; nulo (ou ausente, em arquivos antigos) mostra o tutorial na próxima entrada.
- Se o arquivo não existir, o Nexo cria o login pré-definido `admin` / `Nexo@2026`.

## Usando outro banco relacional

Defina `NEXO_DATABASE_URL` no `.env` e instale o driver:

| Banco | Driver | Exemplo de URL |
|---|---|---|
| PostgreSQL | `pip install "psycopg[binary]"` | `postgresql+psycopg://nexo:senha@localhost:5432/nexo` |
| MySQL / MariaDB | `pip install pymysql` | `mysql+pymysql://nexo:senha@localhost:3306/nexo` |
| SQL Server | `pip install pyodbc` | `mssql+pyodbc://nexo:senha@servidor/nexo?driver=ODBC+Driver+18+for+SQL+Server` |

O `docker-compose.yml` tem um serviço PostgreSQL de exemplo (`docker compose --profile postgres up -d`).

## Migração automática

Ao subir a 2.1 sobre um banco da 2.0, `nexo/migrations.py`:

1. cria as tabelas novas (`nx_knowledge_base`, `nx_bot`, `nx_whatsapp_channel`, `nx_whatsapp_contact`, `nx_whatsapp_message`);
2. cria a base "Acervo geral" e liga a ela todos os documentos existentes;
3. acrescenta `base_id`, `kind`, `extension`, `content` e `updated_at` em `nx_document` e troca o único de `sha256` pelo único por base;
4. acrescenta `bot_id` em `nx_conversation` e cria os índices que faltarem.

No SQLite, `nx_document` é reconstruída seguindo os 12 passos oficiais (o SQLite não remove uma restrição única com `ALTER TABLE`); nos outros bancos, a migração usa `ALTER TABLE`. Nenhum vetor precisa ser recalculado. Faça um backup da pasta `data` antes de atualizar.
