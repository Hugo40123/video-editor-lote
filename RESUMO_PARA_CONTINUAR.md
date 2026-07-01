# Resumo para continuar o projeto

**Data do resumo:** 2026-06-30 (atualizado v2.3)

**Projeto:** `VideoEditorLote`

**Pasta principal:**
```
C:\Users\Hugo\Documents\APP CRIAÇÃO VIDEO\video_editor_lote
```

**Versão atual:** 2.3.0 — Web App (FastAPI + SQLite + Gemini API + Scheduler)

---

## 🎯 Objetivo geral

Automatizar uma esteira de perfis de afiliados:

1. ✅ **Editar vídeos em lote** — FFmpeg aplica fundo, logo, oculta marca d'água
2. ✅ **Gerar conteúdo de post automaticamente** — Google Gemini transcreve + cria legenda publi
3. ✅ **Scheduler de postagem automática** — Worker em background com retry e lock anti-duplicação
4. 🔄 **Buscar produtos e links de afiliado** — PRÓXIMO GRANDE PASSO (v2.4)
5. 🔄 **Migrar SQLite → PostgreSQL** — Preparar para produção (v2.5)
6. ⏳ **Storage remoto (R2/Supabase)** — Futuro (v2.6)

**Filosofia:** Não é só um editor de vídeo. É uma ferramenta de operação para afiliados:
reduzir trabalho repetitivo, padronizar conteúdo e acelerar a criação de perfis de achadinhos.

---

## 📋 Estado atual do app (v2.3)

### ✅ Mudanças recentes (v2.3 — Scheduler)

| Mudança | Detalhes |
|---|---|
| **Scheduler automático** | Worker daemon em background que publica posts agendados. |
| **Retry com backoff** | 3 tentativas com delay exponencial (5min → 10min → 20min). |
| **Lock anti-duplicação** | Coluna `worker_lock` com timeout de 10min para evitar publicação duplicada. |
| **Novos status** | `PENDENTE` → `AGENDADO` → `PROCESSANDO` → `PUBLICADO` / `ERRO` |
| **Migração automática** | Status antigos (`Pronto`, `Agendado`, `Postado`) convertidos na inicialização. |
| **Worker logs** | Nova tabela `worker_logs` com nível (INFO/ERROR) e referência ao post. |
| **Batch history** | Nova tabela `batch_history` registrando cada lote de processamento. |
| **Publisher reutilizável** | `app/workers/publisher.py` — usado tanto pelo scheduler quanto pelo botão manual. |
| **Health check aprimorado** | `GET /api/health` agora verifica FFmpeg, Gemini e Instagram. |
| **google-genai no requirements** | `google-genai>=1.0.0` adicionado. |
| **Botão duplicar legenda** | Adiciona bloco extra na aba Postagens. |
| **Scheduler control** | Botões ▶ Iniciar / ⏹ Parar na interface. |
| **Datetime-local** | Campo de agendamento mudado para `<input type="datetime-local">`. |
| **Retry count visível** | Mostra número de tentativas no detalhe do post. |

### ✅ Mudanças anteriores (v2.2 — Upload)

| Mudança | Detalhes |
|---|---|
| **Drag & drop upload** | Substitui seletor de pastas nativo. |
| **Upload de vídeos** | Multipart, max 10 arquivos, 500MB cada. |
| **Upload de imagens** | Fundo e logo opcionais, fallback para defaults. |
| **Download de saída** | `GET /output/{filename}` para baixar vídeos processados. |
| **Seletor nativo removido** | Endpoints `select-folder` e `select-file` removidos. |
| **Servir arquivos** | `GET /uploads/{session}/{file}` com proteção path traversal. |

### ✅ Mudanças anteriores (v2.1 — IA)

| Mudança | Detalhes |
|---|---|
| **Google Gemini como única IA** | Upload → transcrição → legenda em 1 chamada. |
| **Ollama/Whisper removidos** | Não usa mais. |
| **Config movida** | Gemini e Instagram para aba Configurações. |

---

### ✅ Funcionalidades atuais

- **Upload drag & drop** — Arraste vídeos (max 10, 500MB cada)
- Edição FFmpeg em lote (3 templates)
- Máscara delogo, @ translúcido, ajuste de posição
- Upload opcional de fundo/logo (fallback para assets padrão)
- Download de vídeos processados (`/output/{filename}`)
- Geração de legenda com Google Gemini + fallback local
- **Scheduler automático** — publica posts agendados a cada 30s
- **Retry** — até 3 tentativas com backoff exponencial
- **Worker logs** — histórico de execução do scheduler
- **Batch history** — registro de lotes processados
- Publicação manual no Instagram
- Configurações salvas automaticamente a cada 30s
- Health check integrado (FFmpeg, Gemini, Instagram)
- Interface responsiva com dark theme

---

## 📁 Estrutura do projeto

```
video_editor_lote/
│
├── main.py                     # Inicia o servidor web (FastAPI + uvicorn)
├── requirements.txt            # Dependências (+ google-genai, schedule)
├── README.md                   # Documentação
├── RESUMO_PARA_CONTINUAR.md    # ⬅️ ESTE ARQUIVO — estado do projeto
│
├── uploads/                    # 📁 Vídeos e imagens enviados via upload
│
├── app/                        # 🔧 Core da aplicação
│   ├── __init__.py
│   ├── utils.py                # Config, caminhos, FFmpeg, listagem de vídeos
│   ├── video_processor.py      # FFmpeg e processamento de vídeo
│   ├── gemini_content.py       # Integração Google Gemini
│   ├── free_ai_content.py      # Chama Gemini, fallback local
│   ├── content_generator.py    # Gerador local (rascunho rápido)
│   ├── file_dialog_helper.py   # ⬇️ Não usado (mantido para referência)
│   ├── instagram_api.py        # Cliente da API do Instagram
│   ├── database.py             # SQLite + migrations v2.3 (status, worker_logs, batch_history)
│   ├── repository.py           # CRUD posts, settings, worker_logs, batch_history
│   └── workers/                # 🆕 v2.3 — Workers de background
│       ├── __init__.py
│       ├── scheduler.py        # Daemon thread que publica automaticamente
│       ├── publisher.py        # Lógica de publicação reutilizável
│       └── retry.py            # Backoff exponencial e reset de stuck
│
├── web/                        # Interface web
│   ├── __init__.py
│   ├── server.py               # FastAPI: rotas, lifespan (inicia scheduler), servir arquivos
│   └── routes/
│       ├── __init__.py
│       ├── editor.py           # Upload, edição, thumbnail
│       ├── content.py          # Gemini + rascunho
│       ├── posts.py            # 🆕 Endpoints de scheduler, logs, histórico, manutenção
│       └── settings.py         # Configurações
│
├── templates/
│   └── index.html              # Interface com upload + scheduler control
│
├── static/
│   ├── css/
│   │   └── app.css             # Tema dark + status badges
│   └── js/
│       └── app.js              # Upload, preview, scheduler, logs
│
├── assets/                     # fundo_padrao.jpg, logo_padrao.png
├── entrada/                    # ⬇️ Não usado
└── saida/                      # Vídeos processados (servidos em /output/)
```

---

## ⚙️ Configuração da IA

### Google Gemini

- **API Key:** https://aistudio.google.com/apikey
- **Modelo recomendado:** `gemini-2.0-flash`
- **Tier gratuito:** 1.500 requisições/dia, vídeos até 1h
- **Configurar na aba Configurações > Google Gemini**

### Fluxo

1. Seleciona vídeo na fila da aba Conteúdo
2. "🤖 Gerar com Gemini" → servidor envia para API
3. Gemini transcreve áudio + analisa frames + gera legenda publi
4. Fallback: "📝 Rascunho rápido" se Gemini falhar

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
  • "🤖 Gerar com Gemini" → transcrição + legenda
  • Revisa → "✅ Aprovar"

PASSO 3 ──── AGENDAR E PUBLICAR ───────────────────────────
  • Aba "Postagens" → fila com status
  • Define data/hora → status AGENDADO
  • Scheduler automático publica no horário
  • Ou "📤 Publicar agora" manual
  • Retry automático em caso de erro (máx 3)
  • Histórico de execução em Worker Logs
```

---

## 🛠️ Como rodar

```bash
cd "C:\Users\Hugo\Documents\APP CRIAÇÃO VIDEO\video_editor_lote"
pip install -r requirements.txt
python main.py
# → http://localhost:5000
# → Swagger: http://localhost:5000/docs
```

### Endpoints da API

```
# Sistema
GET  /api/health                      → Health check (+ FFmpeg/Gemini/IG status)

# Upload e Edição
GET  /api/editor/templates            → Lista templates
GET  /api/editor/ffmpeg-check         → Verifica FFmpeg
GET  /api/editor/upload-limits        → Limites (max 10, 500MB)
POST /api/editor/upload               → Upload vídeos (multipart)
POST /api/editor/upload-image         → Upload imagem (fundo/logo)
POST /api/editor/thumbnail            → Thumbnail
POST /api/editor/process              → Inicia processamento
GET  /api/editor/stream/{id}          → SSE progresso

# Arquivos
GET  /uploads/{session}/{file}        → Servir uploads
GET  /output/{filename}               → Download vídeos

# Conteúdo
POST /api/content/generate-local      → Rascunho rápido
POST /api/content/generate-ai         → Gera com Gemini
POST /api/content/test-gemini         → Testa conexão

# Postagens
GET  /api/posts                       → Lista fila
POST /api/posts                       → Adiciona à fila
PUT  /api/posts/{id}                  → Atualiza item
DELETE /api/posts/{id}                → Remove
POST /api/posts/{id}/publish          → Publicar agora
GET  /api/posts/output/videos         → Lista saída
GET  /api/posts/stats/summary         → Status da fila

# 🆕 Scheduler
GET  /api/posts/scheduler/status      → Scheduler rodando?
POST /api/posts/scheduler/start       → Iniciar scheduler
POST /api/posts/scheduler/stop        → Parar scheduler

# 🆕 Logs e Histórico
GET  /api/posts/logs                  → Logs do worker (?post_id=&level=&limit=)
POST /api/posts/logs/clean            → Limpar logs antigos
GET  /api/posts/batch-history         → Histórico de lotes
POST /api/posts/batch-history         → Registrar lote
GET  /api/posts/content-history       → Histórico de conteúdo
POST /api/posts/maintenance/reset-stuck → Resetar posts travados

# Configurações
GET  /api/settings                    → Lê configurações
PUT  /api/settings                    → Salva configurações
```

---

## 📊 Próximos passos (roadmap)

### ✅ Concluído (v2.3)

- [x] Scheduler automático (worker daemon, 30s)
- [x] Retry com backoff exponencial (máx 3)
- [x] Lock anti-duplicação (worker_lock)
- [x] Status: PENDENTE → AGENDADO → PROCESSANDO → PUBLICADO / ERRO
- [x] Worker logs (tabela + API + interface)
- [x] Batch history (tabela + API + interface)
- [x] Publisher reutilizável (scheduler + manual)
- [x] Health check (FFmpeg, Gemini, Instagram)
- [x] requirements.txt atualizado (google-genai)
- [x] Botão duplicar legenda
- [x] Migração automática de status antigos

### Prioridade alta (v2.4 — Produto + Afiliado)

1. **Busca de produto na Shopee/Mercado Livre**
   - Identificar produto pelo vídeo/legenda
   - Buscar item parecido
   - Gerar/salvar link de afiliado
   - Associar cada vídeo ao produto correspondente

### Prioridade média (v2.5 — PostgreSQL)

2. **Migrar SQLite → PostgreSQL**
   - Implementar DATABASE_URL funcional
   - Alembic para migrations
   - Tabelas: contents, products, posts, settings, logs
   - Manter SQLite apenas em dev

### Prioridade futura (v2.6 — Storage)

3. **Storage remoto (Cloudflare R2 / Supabase)**
   - StorageProvider (Local, R2, Supabase)
   - Upload → Storage → URL pública → Publicação
   - Salvar original_url e processed_url

### Pequenas pendências

4. Barra de progresso de upload por arquivo
5. Remover file_dialog_helper.py (não usado)
6. Adicionar mais categorias no gerador local

---

## 🐛 Dívida técnica conhecida

- **Sem testes automatizados** — Toda a validação é manual
- **Sem rate limiting** — Upload e processamento sem proteção
- **Sem autenticação** — App aberto para qualquer um na rede
- **SQLite em WAL mode** — Funciona para dev, mas precisa de PostgreSQL em produção
- **Scheduler single-thread** — Publica 1 post por tick. Se tiver muitos posts agendados ao mesmo tempo, pode atrasar
- **Logs sem rotação** — worker_logs cresce indefinidamente (limpeza manual via API)

---

## 🔒 Observações de segurança

- Não expor `instagram_access_token` ou `gemini_api_key`
- Token e chave salvos localmente no SQLite
- Tier gratuito do Gemini pode usar dados para treinamento
- Uploads com proteção contra path traversal
- Scheduler roda como daemon thread (sem acesso externo direto)
- Health check não expõe credenciais
