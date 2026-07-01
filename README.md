# VideoEditorLote v2.5.0

**Editor de Vídeos em Lote** — Ferramenta de operação para afiliados.

Pipeline completo: upload → edição FFmpeg → legenda com IA → agendamento → publicação Instagram.

---

## 🐘 v2.5 — PostgreSQL

O banco de dados agora suporta **SQLite (desenvolvimento)** e **PostgreSQL (produção)** via `DATABASE_URL`.

- **Dev:** `DATABASE_URL` vazia/não configurada → SQLite local (`config/app.db`)
- **Prod:** `DATABASE_URL=postgresql://user:pass@host:5432/dbname` → PostgreSQL

```bash
# Windows (CMD)
set DATABASE_URL=postgresql://user:pass@localhost:5432/videoeditor
python main.py

# Windows (PowerShell)
$env:DATABASE_URL="postgresql://user:pass@localhost:5432/videoeditor"
python main.py
```

### Migração de dados SQLite → PostgreSQL

```bash
# 1. Configure a conexão PostgreSQL
set DATABASE_URL=postgresql://user:pass@host:5432/dbname

# 2. Execute a migração
python scripts/migrate_to_postgresql.py
```

### Backup

```bash
python scripts/backup_sqlite.py              # Backup padrão
python scripts/backup_sqlite.py --output .    # Pasta específica
python scripts/backup_sqlite.py --list        # Listar backups
```

---

## ⚡ Funcionalidades

### ✅ Upload
- Arraste vídeos (max 10, 500MB cada) para upload multipart
- Upload opcional de fundo e logo (fallback para assets padrão)
- Preview canvas em tempo real com ajustes de posição

### ✅ Edição FFmpeg em lote
- 3 templates de layout vertical (1080x1920)
- Máscara delogo para ocultar marca d'água central
- Sobreposição de @ translúcido com ajuste de posição/tamanho
- Logo no canto inferior direito
- Ajuste de tamanho, largura, posição horizontal e vertical
- Corte por duração máxima
- Download dos vídeos processados (`/output/{filename}`)

### ✅ Geração de conteúdo com IA
- **Google Gemini** — transcreve o áudio e gera legenda estilo publi em 1 chamada
- **Fallback local** — rascunho rápido baseado no nome do arquivo
- Editor de legenda completo: título, CTA, hashtags, product query, link afiliado
- Fluxo: gerar → revisar → aprovar

### ✅ Agendamento automático (Scheduler)
- Worker daemon em background verificando a cada 30s
- Publica posts no horário agendado
- Retry com backoff exponencial (5min → 10min → 20min, máx 3)
- Lock anti-duplicação (worker_lock com timeout 10min)
- Botões ▶ Iniciar / ⏹ Parar na interface
- Reset de posts travados em PROCESSANDO

### ✅ Publicação no Instagram
- API Graph v25.0 com upload resumable
- Suporte a REELS com share_to_feed
- Polling de status do container
- Publicação manual e automática (compartilha o mesmo publisher)

### ✅ Busca de Produtos (v2.4)
- **Mercado Livre** — scraping HTML + extração JSON
- **Shopee** — API interna + fallback via Google
- Geração de link de afiliado (ML Cliques + Shopee Affiliate)
- Associação produto ↔ post na fila
- Interface completa com thumbnails, preços e seleção

### ✅ Histórico e Logs
- Tabela `worker_logs` com nível (INFO/ERROR) e referência ao post
- Tabela `batch_history` registrando lotes de processamento
- Tabela `content_history` com histórico de legendas geradas
- Limpeza de logs antigos via API

### ✅ Configurações
- Salvamento automático a cada 30s
- DB (SQLite) + JSON legacy como fallback
- Aba dedicada: Gemini, Instagram, sistema, status da fila

### ✅ API REST completa
~40 endpoints documentados via Swagger em `/docs`.

---

## 🚀 Como rodar

```bash
cd "C:\Users\Windows\Documents\VIDEO EDITOR LOTE"
pip install -r requirements.txt
python main.py
# → http://localhost:5000
# → Swagger: http://localhost:5000/docs
```

### Dependências principais
- Python 3.10+
- FFmpeg (no PATH)
- FastAPI + Uvicorn
- Google Gemini API key (opcional, para IA)
- Instagram Access Token (opcional, para publicação)

---

## 📁 Estrutura

```
video_editor_lote/
│
├── main.py                     # Inicia servidor web (FastAPI + uvicorn)
├── requirements.txt
├── README.md
├── RESUMO_PARA_CONTINUAR.md    # Estado do projeto e roadmap
│
├── uploads/                    # Uploads de vídeos e imagens
├── saida/                      # Vídeos processados (/output/)
├── assets/                     # fundo_padrao.jpg, logo_padrao.png
├── config/                     # app.db, settings.json
│
├── app/                        # Core
│   ├── database.py             # SQLite + migrations
│   ├── repository.py           # CRUD
│   ├── utils.py                # FFmpeg, paths, config
│   ├── video_processor.py      # FFmpeg pipeline
│   ├── gemini_content.py       # Google Gemini API
│   ├── free_ai_content.py      # Gemini + fallback local
│   ├── content_generator.py    # Rascunho local
│   ├── instagram_api.py        # Cliente Instagram Graph API
│   ├── product_search.py       # Busca ML + Shopee
│   └── workers/
│       ├── scheduler.py        # Daemon de publicação
│       ├── publisher.py        # Lógica reutilizável de publicação
│       └── retry.py            # Backoff e reset
│
├── web/                        # Interface web
│   ├── server.py               # FastAPI (lifespan, rotas, health)
│   └── routes/
│       ├── editor.py           # Upload, edição, processamento
│       ├── content.py          # Geração de conteúdo
│       ├── posts.py            # Fila, scheduler, logs
│       ├── products.py         # Busca de produtos
│       └── settings.py         # Configurações
│
├── templates/
│   └── index.html              # Interface completa
└── static/
    ├── css/app.css             # Tema dark
    └── js/app.js               # Lógica frontend
```

---

## 🔄 Pipeline completo

```
PASSO 1 ──── UPLOAD + EDIÇÃO ──────────────────
  • Arrasta vídeos (max 10)
  • Fundo/logo opcionais
  • Configura template, máscara, @, posição
  • "Gerar vídeos" → FFmpeg → /saida/
  • Download em /output/{filename}

PASSO 2 ──── GERAÇÃO DE CONTEÚDO ──────────────
  • Aba "Conteúdo" → fila de vídeos
  • "Gerar com Gemini" → transcrição + legenda
  • Revisa → "Aprovar"

PASSO 3 ──── BUSCAR PRODUTO ───────────────────
  • Aba "Produtos" → busca ML/Shopee
  • Seleciona produto
  • Gera link de afiliado
  • Vincula ao post

PASSO 4 ──── AGENDAR E PUBLICAR ───────────────
  • Aba "Postagens" → fila com status
  • Define data/hora → AGENDADO
  • Scheduler automático publica no horário
  • Ou "Publicar agora" manual
  • Retry automático em caso de erro
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
- [x] Publisher reutilizável (scheduler + manual)
- [x] Publicação Instagram (Graph API v25.0)

**Logs e Histórico:**
- [x] Worker logs
- [x] Batch history
- [x] Content history
- [x] Limpeza de logs antigos

**Produtos (v2.4):**
- [x] Busca Mercado Livre (scraping HTML + JSON)
- [x] Busca Shopee (API + Google fallback)
- [x] Geração de link de afiliado
- [x] Associação produto ↔ post

**PostgreSQL (v2.5):**
- [x] SQLAlchemy ORM para todos os modelos
- [x] SQLite (dev) + PostgreSQL (prod) via DATABASE_URL
- [x] Alembic com migrations
- [x] Tabelas users + accounts
- [x] Script de migração SQLite → PostgreSQL
- [x] Script de backup do banco

**Sistema:**
- [x] Health check (FFmpeg, Gemini, Instagram)
- [x] Configurações salvas automaticamente (30s)
- [x] Dark theme responsivo
- [x] ~40 endpoints REST documentados

### 🔄 Próximos passos
1. **Storage remoto** — Cloudflare R2 / Supabase (v2.6)
2. **Autenticação** — Login, JWT, roles (v2.7)
3. **Testes automatizados** — Unit tests para módulos core (v2.8)
4. **Observabilidade** — Métricas, dashboard
5. **Segurança** — Rate limiting, CORS
6. **Melhorias** — Export CSV, duplicar post, paginação

---

## 🔧 Observações

- FFmpeg precisa estar instalado e no PATH
- Google Gemini: tier gratuito 1.500 req/dia (modelo Flash)
- Instagram: requer token de acesso do Meta (Graph API v25.0)
- Dados salvos em SQLite local (`config/app.db`)
- Sem autenticação — app aberto na rede local

---

## 📖 Como obter credenciais

### Google Gemini
1. Acesse [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Crie uma chave de API (começa com `AIza...`)
3. Configure na aba Configurações > Google Gemini

### Instagram
1. Crie um app no [developers.facebook.com](https://developers.facebook.com)
2. Configure o Instagram Basic Display / Graph API
3. Obtenha o IG User ID e Access Token
4. Configure na aba Configurações > Instagram
