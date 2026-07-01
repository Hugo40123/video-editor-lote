# Resumo para continuar o projeto

**Data do resumo:** 2026-07-01 (atualizado v2.8)

**Projeto:** `VideoEditorLote`

**Pasta principal:**
```
C:\Users\Windows\Documents\VIDEO EDITOR LOTE
```

**Versão atual:** 2.8.0 — Web App (FastAPI + SQLAlchemy + Alembic + Gemini + Scheduler + Produtos + PostgreSQL + Testes)

---

## 🎯 Objetivo geral

Automatizar uma esteira de perfis de afiliados:

1. ✅ **Editar vídeos em lote** — FFmpeg aplica fundo, logo, oculta marca d'água
2. ✅ **Gerar conteúdo de post automaticamente** — Google Gemini transcreve + cria legenda publi
3. ✅ **Scheduler de postagem automática** — Worker em background com retry e lock anti-duplicação
4. ✅ **Buscar produtos e links de afiliado** — Mercado Livre + Shopee + links de afiliado
5. ✅ **Migrar SQLite → PostgreSQL** — SQLAlchemy ORM + Alembic + DATABASE_URL (concluído v2.5)
6. ✅ **Testes automatizados** — 114 testes unitários + integração (concluído v2.8)
7. 🔄 **Storage remoto (R2/Supabase)** — Futuro (v2.6)

---

## 📋 Estado do App (v2.5)

### ✅ O que já foi implementado

| Funcionalidade | Status | Detalhes |
|---|---|---|
| **Upload drag & drop** | ✅ Completo | Max 10 vídeos, 500MB cada, multipart, preview |
| **Edição FFmpeg em lote** | ✅ Completo | 3 templates, delogo, @, logo, posição, duração |
| **Geração legenda (Gemini)** | ✅ Completo | Upload → transcrição → legenda em 1 chamada |
| **Geração legenda (Local)** | ✅ Completo | Rascunho rápido por nome + keywords (fallback) |
| **Scheduler automático** | ✅ Completo | Daemon 30s, retry backoff, lock anti-duplicação |
| **Publisher reutilizável** | ✅ Completo | Compartilhado scheduler + manual |
| **Publicação Instagram** | ✅ Completo | API v25.0, Reels, resumable upload |
| **Worker logs** | ✅ Completo | Tabela + API + interface |
| **Batch history** | ✅ Completo | Tabela + API + interface |
| **Content history** | ✅ Completo | Tabela + API |
| **Configurações (Settings)** | ✅ Completo | DB + JSON, auto-save 30s |
| **Health check** | ✅ Completo | FFmpeg, Gemini, Instagram |
| **Busca Mercado Livre** | ✅ Completo | Scraping HTML + JSON |
| **Busca Shopee** | ✅ Completo | API + fallback Google |
| **Links de afiliado** | ✅ Completo | ML Cliques + Shopee Affiliate |
| **Associação produto ↔ post** | ✅ Completo | Tabela products, seleção, vinculação |
| **Interface web** | ✅ Completo | 5 abas, dark theme, responsiva |
| **API REST** | ✅ Completo | ~40 endpoints, Swagger em /docs |
| **Migrações automáticas DB** | ✅ Completo | Idempotente, status antigos → novos |

### ✅ v2.5 — PostgreSQL Migration

| Funcionalidade | Status | Detalhes |
|---|---|---|
| SQLAlchemy ORM | ✅ Completo | Todos os modelos mapeados |
| DATABASE_URL | ✅ Completo | SQLite (dev) / PostgreSQL (prod) |
| Alembic migrations | ✅ Completo | env.py configurado, migration inicial |
| Tabelas users + accounts | ✅ Completo | Modelos ORM + migration |
| Script migração SQLite→PgSQL | ✅ Completo | `scripts/migrate_to_postgresql.py` |
| Script backup SQLite | ✅ Completo | `scripts/backup_sqlite.py` |
| Compatibilidade reversa | ✅ Completo | Helpers fetch_one/fetch_all mantidos |

### ✅ v2.8 — Testes Automatizados

| Funcionalidade | Status | Detalhes |
|---|---|---|
| content_generator | ✅ Completo | 8 testes: geração local, edge cases |
| retry | ✅ Completo | 10 testes: backoff, reset, contagem |
| video_processor | ✅ Completo | 18 testes: templates, filtros, comandos FFmpeg |
| instagram_api | ✅ Completo | 12 testes: client, API, publish flow |
| publisher | ✅ Completo | 6 testes: credenciais, upload, erros |
| product_search | ✅ Completo | 7 testes: modelos, URL afiliado, busca |
| scheduler | ✅ Completo | 10 testes: tick, due check, lock, retry |
| repository (integration) | ✅ Completo | 20 testes: CRUD isolado (suppress_db fixture) |
| Cobertura config | ✅ Completo | pyproject.toml com pytest + coverage |
| Isolamento | ✅ Completo | suppress_db fixture com in-memory SQLite |

**Total:** 114 testes, 0 falhas

### ❌ Não implementado

| Funcionalidade | Prioridade | Planejado |
|---|---|---|
| Storage remoto (R2/Supabase) | Média | v2.6 |
| Autenticação (JWT) | Média | v2.7 |
| Observabilidade | Baixa | — |
| Rate limiting | Baixa | — |
| Log rotation automática | Baixa | — |

### ⚠️ Pendências menores

- `file_dialog_helper.py` — não usado (legacy desktop), pode ser removido
- Barra de progresso de upload por arquivo
- Mais categorias no gerador local

---

## 📁 Estrutura do projeto

```
video_editor_lote/
│
├── main.py                     # Inicia servidor web (FastAPI + uvicorn)
├── requirements.txt            # Dependências
├── README.md                   # Documentação atualizada
├── RESUMO_PARA_CONTINUAR.md    # ⬅️ ESTE ARQUIVO
│
├── uploads/                    # Uploads de vídeos e imagens
├── saida/                      # Vídeos processados
├── assets/                     # fundo_padrao.jpg, logo_padrao.png
├── config/                     # app.db, settings.json
│
├── app/                        # 🔧 Core da aplicação
│   ├── __init__.py
│   ├── models.py               # 🆕 v2.5 — SQLAlchemy ORM models
│   ├── database.py             # 🆕 v2.5 — SQLAlchemy engine/session + helpers
│   ├── repository.py           # 🆕 v2.5 — ORM CRUD (posts, settings, logs, products, users, accounts)
│   ├── utils.py                # FFmpeg, paths, config
│   ├── video_processor.py      # FFmpeg pipeline (3 templates)
│   ├── gemini_content.py       # Google Gemini API
│   ├── free_ai_content.py      # Gemini + fallback local
│   ├── content_generator.py    # Rascunho local
│   ├── instagram_api.py        # Instagram Graph API client
│   ├── product_search.py       # Busca ML + Shopee
│   ├── file_dialog_helper.py   # ⬇️ Legacy (não usado)
│   └── workers/
│       ├── __init__.py
│       ├── scheduler.py        # Daemon de publicação
│       ├── publisher.py        # Lógica reutilizável
│       └── retry.py            # Backoff e reset
│
├── scripts/                    # 🆕 v2.5 — Scripts utilitários
│   ├── migrate_to_postgresql.py # Migração SQLite → PostgreSQL
│   └── backup_sqlite.py        # Backup do banco SQLite
│
├── alembic/                    # 🆕 v2.5 — Migrations
│   ├── env.py                  # Configuração Alembic
│   ├── script.py.mako          # Template de migration
│   └── versions/
│       └── a5b31616b948_initial_schema_v2_5.py  # Migration inicial
│
├── alembic.ini                 # 🆕 v2.5 — Config Alembic
├── ROADMAP.md                  # 🆕 v2.5 — Roadmap do projeto
│
├── web/                        # Interface web
│   ├── __init__.py
│   ├── server.py               # FastAPI, lifespan, health check
│   └── routes/
│       ├── __init__.py
│       ├── editor.py           # Upload, edição, preview
│       ├── content.py          # Conteúdo (Gemini + local)
│       ├── posts.py            # Fila, scheduler, logs
│       ├── products.py         # Busca de produtos
│       └── settings.py         # Configurações
│
├── templates/
│   └── index.html              # Interface completa
│
└── static/
    ├── css/app.css             # Tema dark
    └── js/app.js               # Lógica frontend
```

---

## 🔄 Pipeline completo

```
PASSO 1 ──── UPLOAD + EDIÇÃO ──────────────────────────────
  • Arrasta vídeos (max 10)
  • Fundo/logo opcionais
  • Configura template, máscara, @, posição
  • "Gerar vídeos" → FFmpeg → /saida/
  • Download em /output/{filename}

PASSO 2 ──── GERAÇÃO DE CONTEÚDO ──────────────────────────
  • Aba "Conteúdo" → fila de vídeos
  • "Gerar com Gemini" → transcrição + legenda
  • Revisa → "Aprovar"

PASSO 3 ──── BUSCAR PRODUTO ───────────────────────────────
  • Aba "Produtos" → busca ML/Shopee
  • Seleciona produto
  • Gera link de afiliado
  • Vincula ao post

PASSO 4 ──── AGENDAR E PUBLICAR ───────────────────────────
  • Aba "Postagens" → fila com status
  • Define data/hora → AGENDADO
  • Scheduler automático publica no horário
  • Ou "Publicar agora" manual
  • Retry automático em caso de erro (máx 3)
```

---

## ⚙️ Configuração da IA

### Google Gemini
- **API Key:** https://aistudio.google.com/apikey
- **Modelo recomendado:** `gemini-2.0-flash`
- **Tier gratuito:** 1.500 requisições/dia
- **Configurar na aba Configurações > Google Gemini**

### Fluxo
1. Seleciona vídeo na fila da aba Conteúdo
2. "🤖 Gerar com Gemini" → servidor envia para API
3. Gemini transcreve áudio + analisa frames + gera legenda publi
4. Fallback: "📝 Rascunho rápido" se Gemini falhar

---

## 🛠️ Como rodar

```bash
cd "C:\Users\Windows\Documents\VIDEO EDITOR LOTE"
pip install -r requirements.txt
python main.py
# → http://localhost:5000
# → Swagger: http://localhost:5000/docs
```

### Endpoints da API

```
# Sistema
GET  /api/health                      → Health check (+ FFmpeg/Gemini/IG status)
GET  /api/config/paths                → Caminhos do sistema

# Upload e Edição
GET  /api/editor/templates            → Lista templates
GET  /api/editor/ffmpeg-check         → Verifica FFmpeg
GET  /api/editor/upload-limits        → Limites (max 10, 500MB)
POST /api/editor/upload               → Upload vídeos (multipart)
POST /api/editor/upload-image         → Upload imagem (fundo/logo)
POST /api/editor/thumbnail            → Thumbnail
POST /api/editor/process              → Inicia processamento
GET  /api/editor/stream/{id}          → SSE progresso
GET  /api/editor/default-paths        → Caminhos padrão

# Arquivos
GET  /uploads/{session}/{file}        → Servir uploads
GET  /output/{filename}               → Download vídeos processados

# Conteúdo
POST /api/content/generate-local      → Rascunho rápido
POST /api/content/generate-ai         → Gera com Gemini
POST /api/content/test-gemini         → Testa conexão Gemini
POST /api/content/draft               → Rascunho rápido por nome

# Postagens
GET  /api/posts                       → Lista fila
POST /api/posts                       → Adiciona à fila
PUT  /api/posts/{id}                  → Atualiza item
DELETE /api/posts/{id}                → Remove
POST /api/posts/{id}/publish          → Publicar agora
GET  /api/posts/output/videos         → Lista saída
GET  /api/posts/stats/summary         → Status da fila

# Scheduler
GET  /api/posts/scheduler/status      → Scheduler rodando?
POST /api/posts/scheduler/start       → Iniciar scheduler
POST /api/posts/scheduler/stop        → Parar scheduler

# Logs e Histórico
GET  /api/posts/logs                  → Logs do worker
POST /api/posts/logs/clean            → Limpar logs antigos
GET  /api/posts/batch-history         → Histórico de lotes
POST /api/posts/batch-history         → Registrar lote
GET  /api/posts/content-history       → Histórico de conteúdo
POST /api/posts/maintenance/reset-stuck → Resetar posts travados

# 🆕 Produtos (v2.4)
POST /api/products/search             → Busca ML + Shopee
GET  /api/products/search/{source}    → Busca fonte específica
POST /api/products/associate          → Associar produto ao post
GET  /api/products                    → Listar produtos
POST /api/products/affiliate-link     → Gerar link de afiliado
DELETE /api/products/{id}             → Remover produto

# Configurações
GET  /api/settings                    → Lê configurações
PUT  /api/settings                    → Salva configurações
```

---

## 📊 Roadmap

### ✅ Concluído (v2.0 → v2.5)

**Upload e Edição:**
- [x] Upload drag & drop (max 10, 500MB)
- [x] Três templates de layout vertical
- [x] Máscara delogo para ocultar marca d'água
- [x] Sobreposição de @ translúcido
- [x] Logo personalizada no canto inferior
- [x] Ajuste de tamanho, largura e posição
- [x] Preview canvas em tempo real
- [x] Download de vídeos processados

**Conteúdo e IA:**
- [x] Google Gemini como única IA (transcrição + legenda)
- [x] Fallback local (rascunho rápido)
- [x] Editor de legenda completo
- [x] Aprovação de conteúdo
- [x] Histórico de conteúdo gerado

**Scheduler e Publicação:**
- [x] Scheduler automático (daemon 30s)
- [x] Retry com backoff exponencial (máx 3)
- [x] Lock anti-duplicação (worker_lock)
- [x] Status: PENDENTE → AGENDADO → PROCESSANDO → PUBLICADO / ERRO
- [x] Publisher reutilizável (scheduler + manual)
- [x] Publicação Instagram (Graph API v25.0)

**Logs e Histórico:**
- [x] Worker logs (tabela + API + interface)
- [x] Batch history (tabela + API + interface)
- [x] Content history (tabela + API)
- [x] Limpeza de logs antigos

**Produtos (v2.4):**
- [x] Busca Mercado Livre (scraping HTML + JSON)
- [x] Busca Shopee (API + Google fallback)
- [x] Geração de link de afiliado (ML Cliques + Shopee Affiliate)
- [x] Associação produto ↔ post
- [x] Tabela products no banco

**Sistema:**
- [x] Health check (FFmpeg, Gemini, Instagram)
- [x] Configurações salvas automaticamente (30s)
- [x] Dark theme responsivo
- [x] ~40 endpoints REST documentados

### ✅ PostgreSQL (v2.5)
- [x] SQLAlchemy ORM para todos os modelos (8 tabelas)
- [x] DATABASE_URL funcional: SQLite (dev) / PostgreSQL (prod)
- [x] Alembic configurado com migrations
- [x] Tabelas `users` + `accounts` (preparação para auth)
- [x] Índices de performance (status, worker_logs)
- [x] Script de migração de dados SQLite → PostgreSQL
- [x] Script de backup do banco SQLite
- [x] Compatibilidade reversa mantida (helpers fetch_one/fetch_all)

### 🔄 v2.6 — Storage Remoto
- StorageProvider pattern (Local, R2, Supabase)
- Upload → Storage → URL pública
- Salvar original_url, processed_url, thumbnail_url

### 🔄 v2.7 — Autenticação
- Login com JWT
- Papéis: admin, operator
- Auditoria de ações
- Rotas protegidas

### 🔄 v2.8 — Testes
- tests/unit/ + tests/integration/
- Cobertura: video_processor, publisher, scheduler, instagram_api, product_search
- Meta: 80% módulos críticos

### 📝 Backlog
- Observabilidade (CPU, RAM, fila, métricas)
- Rate limiting + CORS + validação de upload
- Exportar logs CSV
- Duplicar post / lote
- Clonar configuração entre perfis
- Filtros de histórico (data, status, fonte)
- Progresso upload via WebSocket
- Paginação na API
- Remover `file_dialog_helper.py` (legacy)
- Mais categorias no gerador local

---

## 🐛 Dívida técnica conhecida

- **Sem testes automatizados** — Toda validação é manual
- **Sem rate limiting** — Upload e processamento sem proteção
- **Sem autenticação** — App aberto para qualquer um na rede
- **SQLite em WAL mode** — Funciona para dev, mas precisa de PostgreSQL em produção
- **Scheduler single-thread** — Publica 1 post por tick
- **Logs sem rotação** — worker_logs cresce indefinidamente (limpeza manual via API)

---

## 🔒 Observações de segurança

- Não expor `instagram_access_token` ou `gemini_api_key`
- Token e chave salvos localmente no SQLite
- Tier gratuito do Gemini pode usar dados para treinamento
- Uploads com proteção contra path traversal
- Scheduler roda como daemon thread (sem acesso externo direto)
- Health check não expõe credenciais
