# Arquitetura de dados do Nexo

O Nexo guarda informações em **três lugares**, cada um com um papel:

| Camada | Onde fica (padrão) | O que guarda |
|---|---|---|
| Banco relacional | `data/nexo.db` (SQLite) ou o banco de `NEXO_DATABASE_URL` | Documentos, conversas, mensagens, fontes citadas e avaliações |
| Banco vetorial | `data/chroma/` (ChromaDB) ou Qdrant | Trechos dos PDFs com os embeddings e os metadados de origem |
| Arquivos | `data/usuarios.json` e `data/uploads/` | Contas de acesso e os PDFs originais |

As tabelas são criadas automaticamente na primeira execução. Os arquivos `schema-postgresql.sql` e `schema-sqlite.sql` desta pasta trazem o DDL equivalente para quem prefere criar o banco manualmente.

## Diagrama de relacionamentos

```mermaid
erDiagram
    nx_document ||--o{ nx_conversation_document : "escopo"
    nx_conversation ||--o{ nx_conversation_document : "consulta"
    nx_conversation ||--o{ nx_message : "contém"
    nx_message ||--o{ nx_message_source : "cita"
    nx_document |o--o{ nx_message_source : "origem"
    nx_message ||--o{ nx_feedback : "recebe"

    nx_document {
        varchar32 id PK
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
```

## Tabelas

### nx_document
Um registro por PDF enviado.

| Coluna | Tipo | Regra |
|---|---|---|
| id | varchar(32) | Chave primária, UUID em hexadecimal. O PDF fica em `data/uploads/<id>.pdf` |
| title | varchar(200) | Título dos metadados do PDF ou o nome do arquivo |
| filename | varchar(255) | Nome original, saneado |
| sha256 | varchar(64) | Único. Impede o envio do mesmo arquivo duas vezes |
| size_bytes | integer | Tamanho do arquivo |
| pages | integer | Total de páginas do PDF |
| chunks | integer | Trechos gravados no banco vetorial |
| status | varchar(20) | `PENDING`, `PROCESSING`, `READY` ou `FAILED` |
| error | text | Motivo da falha, quando houver |
| uploaded_by | varchar(32) | Usuário que enviou (ver `usuarios.json`) |
| created_at / indexed_at | timestamp | Envio e fim da indexação, em UTC |

### nx_conversation
Uma conversa pertence a um único usuário (`owner`). Ninguém mais consegue abri-la.

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

## Banco vetorial

Coleção padrão: `nexo_trechos` (`NEXO_COLLECTION`), com distância de cosseno.

| Campo | Conteúdo |
|---|---|
| id | UUID v5 calculado a partir do documento e da posição do trecho |
| embedding | Vetor do modelo configurado em `NEXO_EMBED_MODEL` |
| document | Texto do trecho (até `NEXO_CHUNK_SIZE` tokens, com `NEXO_CHUNK_OVERLAP` de sobreposição) |
| metadata.source_id | `nx_document.id` do PDF de origem |
| metadata.title | Título do documento |
| metadata.filename | Nome do arquivo |
| metadata.page | Página do PDF, começando em 1 |
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
      "last_login_at": null
    }
  ]
}
```

- Senhas são guardadas só como hash bcrypt.
- `role` é `admin` (pode excluir qualquer documento e vê o total de contas) ou `user`.
- O arquivo é regravado de forma atômica a cada alteração.
- Se o arquivo não existir, o Nexo cria o login pré-definido `admin` / `Nexo@2026`.

## Usando outro banco relacional

Defina `NEXO_DATABASE_URL` no `.env` e instale o driver:

| Banco | Driver | Exemplo de URL |
|---|---|---|
| PostgreSQL | `pip install "psycopg[binary]"` | `postgresql+psycopg://nexo:senha@localhost:5432/nexo` |
| MySQL / MariaDB | `pip install pymysql` | `mysql+pymysql://nexo:senha@localhost:3306/nexo` |
| SQL Server | `pip install pyodbc` | `mssql+pyodbc://nexo:senha@servidor/nexo?driver=ODBC+Driver+18+for+SQL+Server` |

O `docker-compose.yml` tem um serviço PostgreSQL de exemplo (`docker compose --profile postgres up -d`).
