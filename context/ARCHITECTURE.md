# ARCHITECTURE.md — Arquitetura do Sistema

## Visao de Alto Nivel (v2.9)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (SPA)                           │
│    templates/index.html + static/js/app.js (cache-busted)       │
│    5 abas: Edicao | Conteudo | Posts | Produtos | Config        │
│    Canvas preview: frame + fundo + delogo + logo + @            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP + SSE
┌──────────────────────────▼──────────────────────────────────────┐
│                     Web Layer (FastAPI)                          │
│  web/server.py  ->  routes/ (editor, content, posts, products,  │
│                     settings)                                   │
│  Static mounts: /static (CSS/JS), /assets (fundo, logo)        │
│  File serving: /uploads/*, /output/*                            │
└──────┬───────────────────┬──────────────────┬───────────────────┘
       │                   │                  │
┌──────▼──────┐  ┌─────────▼────────┐  ┌─────▼──────────────────┐
│  Processamento│  │  Conteudo/IA     │  │  Agendamento/Publicacao │
│  FFmpeg       │  │  Groq ou Gemini  │  │  Scheduler -> Publisher │
│  video_proc.  │  │  groq_content    │  │  workers/               │
│  3 templates  │  │  gemini_content  │  │  scheduler -> instagram  │
└──────┬──────┘  └────────┬─────────┘  └─────┬───────────────────┘
       │                  │                   │
┌──────▼──────────────────▼───────────────────▼───────────────────┐
│                    Repository Layer (app/repository.py)         │
│                    ~800 linhas de CRUD ORM                       │
│                    cleanup_orphan_posts()                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    Database Layer                                │
│  app/database.py  ->  SQLAlchemy Engine                          │
│  SQLite (dev, config/app.db)  |  PostgreSQL (prod, DATABASE_URL)│
│  8 tabelas: User, Account, Post, ContentHistory, Product,       │
│             Setting, WorkerLog, BatchHistory                     │
└─────────────────────────────────────────────────────────────────┘
```

## Camadas Arquiteturais

### 1. Frontend (Apresentacao)

**Arquivos:** templates/index.html + static/js/app.js + static/css/app.css

- SPA vanilla com navegacao por sidebar
- Canvas de previsao (142x252px) com frame, fundo, delogo, logo, @
- Comunicacao via fetch() para APIs REST
- Progresso em tempo real via Server-Sent Events (SSE)
- Auto-save de configuracoes a cada 30 segundos
- Cache busting com ?v=N no src de JS/CSS
- Provider de IA selecionavel (Groq ou Gemini)

### 2. Web Layer (Rotas HTTP)

**Arquivos:** web/server.py + web/routes/*.py

- FastAPI com lifespan context manager
- Rotas organizadas por dominio (5 modulos)
- ThreadPoolExecutor para processamento bloqueante
- SSE para progresso em tempo real
- Upload: max 10 arquivos, 500MB cada
- Static files: /static (CSS/JS), /assets (imagens)
- File serving: /uploads/*, /output/*

### 3. Business Logic (Core)

| Modulo | Responsabilidade |
|--------|-----------------|
| video_processor.py | Pipeline FFmpeg, templates, filtros |
| groq_content.py | Groq Whisper + Llama ( transcricao + legenda) |
| gemini_content.py | Gemini API (frame-based, sem transcricao) |
| free_ai_content.py | Orquestrador AI (Groq/Gemini -> fallback local) |
| content_generator.py | Geracao local de captions |
| instagram_api.py | Graph API v25.0 client |
| product_search.py | Scraping ML + Shopee |
| utils.py | Paths, FFmpeg/ffprobe detect, settings I/O |

### 4. Workers (Background)

```
Scheduler (daemon thread, 30s tick)
    │
    ├── Carrega todos os posts
    ├── Filtra posts devidos (AGENDADO + passado, ERRO + retry)
    ├── Adquire worker lock (600s timeout)
    └── Chama Publisher para cada post
            │
            ├── Valida credenciais Instagram
            ├── Le arquivo de video
            ├── Cria InstagramClient
            ├── publish_local_video()
            └── Atualiza status (PUBLICADO / ERRO)
```

### 5. Data Layer

- **Repository pattern** com funcoes puras (nao classes)
- **cleanup_orphan_posts()** remove posts com arquivos deletados
- **Dual-write** para settings (DB + JSON)
- **Alembic** para migrations

## Fluxos de Dados

### Processamento de Video
```
Upload -> UUID rename -> Session dir -> FFmpeg subprocess -> Output dir
         (ThreadPoolExecutor)                    |
                                                 v
                              Auto-add to post queue via POST /api/posts
                                                 |
                                                 v
                              Auto-switch to Content tab after 1.5s
```

### Conteudo com IA (Groq)
```
Video -> FFmpeg extract audio (.mp3) -> Check duration
    |
    ├── Has audio (>1s) -> Groq Whisper transcribe -> Groq Llama generate caption
    │                                                              |
    │                                                              v
    │                                              Return (draft, has_audio=true, transcript)
    │
    └── No audio -> Fallback local generator
                                                 |
                                                 v
                                    Frontend shows "Sem audio. Revise manualmente."
```

### Publicacao Instagram
```
Scheduler tick -> Find due posts -> Lock worker -> Publisher
    -> Read credentials from DB -> Validate video exists
    -> InstagramClient.create_container() -> Upload binary
    -> Poll status -> media_publish() -> Update DB status
```

## Confiabilidade

- **Retry:** Backoff exponencial para falhas de publicacao
- **Worker Lock:** Previne processamento duplicado (600s timeout)
- **Stuck Reset:** Posts em PROCESSANDO por muito tempo sao resetados
- **Orphan Cleanup:** Posts com arquivos deletados sao removidos da fila
- **Dual-Write:** Settings sobrevivem a falhas de um dos stores
- **Cache Busting:** JS/CSS atualizados sem problema de cache do navegador
