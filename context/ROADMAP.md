# ROADMAP.md — Roadmap do Projeto

## Versao Atual: v2.9

Status: **Producao** — Groq integrado, previsao com frame, auto-import na fila.

---

## Historico de Versoes

### v2.0 — Web Application
- Migracao de desktop (CustomTkinter) para web (FastAPI)
- Interface SPA com 5 abas
- Upload e processamento via FFmpeg
- 3 templates de video

### v2.1 — Conteudo com IA
- Integração Google Gemini
- Transcricao de audio automatica
- Geracao de captions para Instagram
- Fallback para gerador local

### v2.2 — Publicacao Instagram
- Instagram Graph API v25.0
- Upload de video via resumable upload
- Publicacao automatica
- Scheduler daemon thread

### v2.3 — Produtos e Afiliacao
- Scraping Mercado Livre (ofertas + JSON)
- Scraping Shopee (API interna + Google fallback)
- Geracao de links de afiliado
- Associacao produto-post

### v2.4 — Database Migration
- SQLAlchemy ORM (8 tabelas)
- Dual-database SQLite/PostgreSQL
- Alembic migrations
- Repository pattern

### v2.5 — Testes e Qualidade
- 114 testes (unit + integration)
- Fixtures compartilhadas

### v2.6 — Workers e Resiliencia
- Retry com backoff exponencial
- Worker lock para evitar duplicacao
- Stuck post reset
- Health check endpoint

### v2.7 — Frontend Melhorias
- Dark theme completo
- Preview de canvas em tempo real
- SSE para progresso
- Auto-save de configuracoes

### v2.8 — Documentacao e Migracao
- Scripts de backup SQLite
- Migracao para PostgreSQL
- Context files

### v2.9 — Groq + Previsao + Auto-import (ATUAL)
- **Groq API** integrada (Whisper transcricao + Llama legenda)
- **Preview com frame** do video no canvas
- **Imagem de fundo** aparece na previsao
- **Auto-import** apos processar (video vai para fila automaticamente)
- **Auto-switch** para aba Conteudo apos processar
- **Links de download** clicaveis no log
- **Cleanup de posts orfaos** (arquivos deletados)
- **Bug fix:** ffprobe path (shutil.which)
- **Bug fix:** missing JS functions (loadSchedulerStatus, etc)
- **Cache busting** no HTML (?v=N)
- **iniciar.bat** para executar o app

---

## Proximos Passos (Planejado)

### Prioridade Alta
- [ ] Autenticacao (JWT) — Seguranca em rede local
- [ ] Storage remoto — Cloudflare R2 ou Supabase
- [ ] CORS e rate limiting

### Prioridade Media
- [ ] Log rotation
- [ ] Observabilidade / metricas
- [ ] CSV export

### Prioridade Baixa
- [ ] Multi-usuario com perfis
- [ ] Webhooks para notificacoes
- [ ] Mobile app

---

## Debito Tecnico Conhecido

### Critico
- [ ] Nenhuma autenticacao (aberto em rede local)
- [ ] Sem CORS configurado

### Medio
- [ ] Scheduler single-threaded (1 post por tick)
- [ ] Sem log rotation
- [ ] Sem cleanup automatico de uploads antigos

### Baixo
- [ ] Frontend sem framework (manutencao manual)
- [ ] Sem metricas de performance
