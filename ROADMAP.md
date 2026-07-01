# Roadmap — VideoEditorLote

> **Versão atual:** v2.5.0 (PostgreSQL)
> **Última atualização:** 2026-07-01

---

## ✅ v2.0 → v2.4 — Concluído

| Versão | Foco | Status |
|---|---|---|
| v2.0 | FastAPI web app | ✅ |
| v2.1 | Google Gemini (IA) | ✅ |
| v2.2 | Upload drag & drop | ✅ |
| v2.3 | Scheduler + Workers | ✅ |
| v2.4 | Busca de Produtos (ML/Shopee) | ✅ |

### Funcionalidades entregues
- Upload drag & drop (max 10, 500MB)
- Edição FFmpeg (3 templates, máscara, @, logo)
- Geração de legenda com Google Gemini + fallback local
- Scheduler automático (daemon, retry backoff, lock anti-duplicação)
- Publicação Instagram (Graph API v25.0)
- Busca Mercado Livre + Shopee
- Links de afiliado (ML Cliques + Shopee Affiliate)
- Worker logs, batch history, content history
- Interface dark theme responsiva
- ~40 endpoints REST com Swagger

---

## 🔄 v2.5 — PostgreSQL (ATUAL)

**Status:** ✅ Implementado
**Objetivo:** Preparar para produção com banco de dados escalável

### O que foi feito
- [x] SQLAlchemy ORM para todos os modelos
- [x] Compatibilidade: SQLite (dev) + PostgreSQL (prod)
- [x] `DATABASE_URL` funcional
- [x] Alembic configurado com migrations
- [x] Migration inicial com `users`, `accounts`, novas colunas
- [x] Script de migração de dados SQLite → PostgreSQL
- [x] Script de backup do banco SQLite
- [x] `_is_postgres()` com suporte a `postgres://` e `postgresql://`

### Pendências
- [ ] Testar migração com PostgreSQL real
- [ ] Adicionar validação de conexão no health check

---

## ⏳ v2.6 — Storage Remoto

**Status:** ❌ Não iniciado
**Objetivo:** Remover dependência de disco local

### Planejado
- [ ] `storage/` provider pattern (Local, R2, Supabase)
- [ ] Mover `uploads/` e `saida/` para storage remoto
- [ ] Salvar `original_url`, `processed_url`, `thumbnail_url`
- [ ] Fluxo: upload → storage → processamento → publicação

---

## ⏳ v2.7 — Autenticação

**Status:** ❌ Não iniciado
**Objetivo:** Login, JWT, roles e sessão

### Planejado
- [ ] Login com JWT
- [ ] `users` e `accounts` já modelados
- [ ] Papéis: admin, operator
- [ ] Auditoria de ações
- [ ] Rotas protegidas por middleware

---

## ⏳ v2.8 — Testes

**Status:** ❌ Não iniciado
**Objetivo:** 80% de cobertura nos módulos críticos

### Planejado
- [ ] `tests/unit/` — testes unitários
- [ ] `tests/integration/` — testes de integração
- [ ] Cobertura: video_processor, publisher, scheduler, instagram_api, product_search

---

## 📋 Backlog

| Item | Prioridade | Esforço |
|---|---|---|
| Observabilidade (CPU, RAM, fila, métricas) | Média | 3 dias |
| Rate limiting + CORS + validação de upload | Média | 2 dias |
| Exportar logs CSV | Baixa | 1 dia |
| Duplicar post / lote | Baixa | 1 dia |
| Clonar configuração entre perfis | Baixa | 1 dia |
| Filtros de histórico (data, status, fonte) | Baixa | 1 dia |
| Progresso upload via WebSocket | Baixa | 2 dias |
| Paginação na API | Baixa | 1 dia |
| Remover `file_dialog_helper.py` (legacy) | Baixa | < 1 dia |
| Mais categorias no gerador local | Baixa | 1 dia |

---

## 🐛 Dívida Técnica

- Sem testes automatizados
- Sem rate limiting
- Sem autenticação
- Scheduler single-thread (1 post/tick)
- Logs sem rotação automática
- SQLite em WAL mode (apenas dev)
