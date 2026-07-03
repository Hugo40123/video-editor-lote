# DECISIONS.md — Decisoes de Arquitetura

## D001 — Web Framework (v2.0)
**FastAPI** — async nativo, OpenAPI automatico, SSE nativo.

## D002 — Banco de Dados (v2.4)
**Dual-database** — SQLite dev, PostgreSQL prod. Alembic migrations.

## D003 — ORM (v2.4)
**SQLAlchemy ORM** — padrao de mercado, migrations oficiais.

## D004 — Repository Pattern (v2.4)
**Funcoes puras** — sem classes de repositorio, sessao por chamada.

## D005 — Processamento de Video (v2.0)
**FFmpeg via subprocess** — controle total sobre filtros e codecs.

## D006 — Frontend (v2.0)
**SPA vanilla** — zero build step, sem node_modules.

## D007 — IA para Legendas (v2.9)
**Groq (Whisper + Llama) como primario, Gemini como alternativa.**

Razao:
- Groq: gratuito (14.400 req/dia), transcricao real via Whisper, muito rapido
- Gemini: gratuito mas limitado, sem transcricao (usa frame), mais lento
- Fallback local sempre disponivel

Fluxo Groq:
1. FFmpeg extrai audio (.mp3)
2. Groq Whisper transcreve (pt-BR)
3. Groq Llama 3.1 gera legenda
4. Se sem audio -> fallback local

## D008 — Preview com Frame (v2.9)
**Frame extraido via FFmpeg** — thumbnail 320px convertida para base64, renderizada no canvas.

Razao:
- Frame da ideia visual do video
- Fundo (assets/) aparece atras
- Permite ajustar posicoes com barras

## D009 — Auto-import para Fila (v2.9)
**Videos processados entram na fila automaticamente** via POST /api/posts apos completar.

Razao:
- Fluxo mais fluido (sem clique manual)
- Auto-switch para aba Conteudo apos 1.5s

## D010 — Cache Busting (v2.9)
**?v=N no src de JS/CSS** — navegador busca versao nova.

Razao:
- Navegadores cacheiam agressivamente
- Sem build step para gerar hashes

## D011 — ffprobe via shutil.which (v2.9)
**NUNCA usar replace("ffmpeg", "ffprobe")** — quebra por causa do nome do diretorio.

Razao:
- Caminho WinGet: ffmpeg-8.1.2-full_build/bin/ffmpeg.EXE
- replace troca "ffmpeg" no diretorio tambem -> caminho invalido
- shutil.which("ffprobe") encontra o caminho correto

## D012 — Posts Orfaos (v2.9)
**cleanup_orphan_posts()** remove posts cujo arquivo nao existe mais.

Razao:
- Arquivos deletados da saida/ nao devem aparecer na fila
- Executado ao carregar a fila (loadPostQueue)

## D013 — Autenticacao (planejado)
**JWT** — previne acesso nao autorizado em rede local.

## D014 — Storage Remoto (planejado)
**Cloudflare R2 ou Supabase** — escalabilidade para videos grandes.
