# AGENT.md — Contexto para Agentes de IA

## Visao Geral do Projeto

**VideoEditorLote v2.9** e uma ferramenta de automacao de marketing de afiliados em portugues brasileiro. O sistema processa videos em lote via FFmpeg, gera legendas para Instagram usando IA (Groq ou Gemini), busca produtos em marketplaces brasileiros (Mercado Livre e Shopee), e publica automaticamente no Instagram.

## Stack Tecnologica

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy ORM, Alembic
- **Frontend:** HTML/CSS/JS vanilla (SPA com sidebar), tema dark
- **Banco de Dados:** SQLite (dev) / PostgreSQL (producao)
- **Processamento de Video:** FFmpeg via subprocess
- **IA:** Groq (Whisper + Llama 3.1) ou Google Gemini
- **Scraping:** cloudscraper, BeautifulSoup4, lxml
- **Publicacao:** Instagram Graph API v25.0

## Estrutura de Diretorios

```
video_editor_lote/
├── main.py                    # Entry point -> web.server.run_server()
├── iniciar.bat                # Atalho para executar o app
├── app/                       # Core business logic
│   ├── models.py              # SQLAlchemy ORM (8 tabelas)
│   ├── database.py            # Engine singleton, migrations, helpers
│   ├── repository.py          # CRUD layer (~800 linhas)
│   ├── utils.py               # Paths, FFmpeg detection, settings I/O
│   ├── video_processor.py     # FFmpeg pipeline (3 templates)
│   ├── gemini_content.py      # Gemini API (frame-based)
│   ├── groq_content.py        # Groq API (Whisper + Llama)
│   ├── free_ai_content.py     # AI orchestrator (Groq/Gemini -> fallback local)
│   ├── content_generator.py   # Gerador local de captions
│   ├── instagram_api.py       # Instagram Graph API client
│   ├── product_search.py      # Scraping ML + Shopee (~683 linhas)
│   └── workers/
│       ├── scheduler.py       # Daemon thread, tick 30s
│       ├── publisher.py       # Logica compartilhada de publicacao
│       └── retry.py           # Exponential backoff, stuck reset
├── web/
│   ├── server.py              # FastAPI app, lifespan, static files
│   └── routes/
│       ├── editor.py          # Upload, processamento, SSE progress
│       ├── content.py         # Geracao de conteudo (Groq/Gemini/local)
│       ├── posts.py           # CRUD posts, publicacao, scheduler
│       ├── products.py        # Busca marketplace, afiliacao
│       └── settings.py        # Config dual-write (DB + JSON)
├── templates/
│   └── index.html             # SPA completa (5 abas) v2.9
├── static/
│   ├── css/app.css            # Dark theme, responsive
│   └── js/app.js              # Frontend logic (~1600 linhas)
├── config/
│   ├── settings.json          # Config persistente (legacy)
│   └── app.db                 # SQLite database
├── alembic/                   # Schema migrations
├── scripts/                   # Backup e migracao PostgreSQL
├── tests/                     # 114 testes (unit + integration)
├── context/                   # Documentacao do projeto
│   ├── AGENT.md               # Este arquivo
│   ├── ARCHITECTURE.md        # Arquitetura do sistema
│   ├── CONVENTIONS.md         # Convencoes de codigo
│   ├── ROADMAP.md             # Roadmap e proximos passos
│   └── DECISIONS.md           # Decisoes de arquitetura
├── entrada/                   # Videos de entrada
├── saida/                     # Videos processados
└── assets/                    # Imagens padrao (fundo, logo)
```

## Fluxo Principal

1. **Upload** -> Usuario faz upload de videos (max 10, 500MB cada)
2. **Processamento** -> FFmpeg aplica template, fundo, logo, textos, delogo
3. **Fila** -> Videos processados entram automaticamente na fila de posts
4. **Conteudo** -> IA (Groq/Gemini) transcreve audio e gera caption
5. **Produtos** -> Busca automatica no ML/Shopee, gera links de afiliado
6. **Agendamento** -> Scheduler daemon publica automaticamente
7. **Publicacao** -> Instagram Graph API faz upload e publica

## Modulos-Chave

### IA: Groq (Recomendado) vs Gemini

| | Groq | Gemini |
|--|------|--------|
| Custo | Gratis (14.400 req/dia) | Gratis (limitado) |
| Transcricao | Whisper large-v3 (rapido) | Via frame (sem transcricao) |
| Geração | Llama 3.1 (instantaneo) | Gemini Flash |
| Autenticacao | Chave API (gsk_...) | Chave API (AIza... ou AQ...) |

### Previa do Canvas

O canvas (142x252px) renderiza:
- Imagem de fundo (assets/fundo_padrao.jpg ou upload)
- Frame do video (extracao via FFmpeg)
- Area do video com deslocamento (barras de ajuste)
- Mascara delogo (se ativa)
- Logo (se ativa)
- Texto @ centralizado (se ativo)

### Auto-import para Fila

Apos processar videos, eles sao adicionados automaticamente a fila de posts.
A fila limpa posts orfaos (arquivos deletados) ao carregar.

## Banco de Dados (8 tabelas)

| Tabela | Descricao |
|--------|-----------|
| User | Preparacao para auth futuro |
| Account | Multi-perfil Instagram |
| Post | Entidade central (22 colunas) |
| ContentHistory | Historico de conteudos gerados |
| Product | Produtos de marketplaces |
| Setting | Key-value store |
| WorkerLog | Log de atividade dos workers |
| BatchHistory | Historico de processamentos |

## Regras de Trabalho

- **Toda atualização** deve seguir este fluxo ao finalizar:
  1. Commitar as mudanças no git com mensagem descritiva em inglês
  2. Atualizar os arquivos da pasta `context/` se houver mudanças na arquitetura, convenções ou decisões
  3. Executar `iniciar.bat` automaticamente ao finalizar para validar

## Cuidados ao Modificar

- **Repository layer** e a unica forma de acessar o banco
- **Status dos posts** usa valores em ingles/uppercase: AGENDADO, PROCESSANDO, PUBLICADO, ERRO
- **IDs** sao UUIDs de 32 caracteres hex (sem hifens)
- **Timestamps** sao strings ISO format
- **FFmpeg** e chamado via subprocess
- **ffprobe** deve ser encontrado via shutil.which("ffprobe"), NAO por replace do path do ffmpeg
- **Rotas web** usam run_in_executor para operacoes bloqueantes
- **Settings** tem dual-write: DB e primario, JSON e fallback legacy
- **Cache busting** no HTML: usar ?v=N no src do JS/CSS ao alterar
