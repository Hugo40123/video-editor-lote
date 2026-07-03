# CONVENTIONS.md — Convencoes do Projeto (v2.9)

## Idioma

- **Codigo:** Ingles (variacoes, funcoes, classes, comentarios)
- **Interface:** Portugues brasileiro (labels, mensagens, tooltips)
- **Documentacao:** Portugues brasileiro (README, context files)
- **Commit messages:** Ingles (curto, descritivo)

## Nomenclatura

```python
# Variaveis e funcoes: snake_case
video_path = "..."
def process_video(): ...

# Classes: PascalCase
class InstagramClient: ...

# Constantes: UPPER_SNAKE_CASE
MAX_FILE_SIZE = 500 * 1024 * 1024

# IDs: hex UUID sem hifens (32 chars)
post_id = "a1b2c3d4e5f6..."

# Timestamps: ISO format string
created_at = "2026-07-02T19:00:00"
```

## Repository Layer

```python
# CORRETO: Funcoes puras, sessao por chamada
def list_posts(status=None):
    db = get_db()
    try:
        query = db.query(Post)
        if status:
            query = query.filter(Post.status == status)
        return [_post_to_dict(p) for p in query.all()]
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
```

## Rotas Web

```python
# CORRETO: FastAPI router, run_in_executor para bloqueante
router = APIRouter()

@router.get("/api/posts")
async def get_posts():
    return repository.list_posts()

@router.post("/api/process")
async def process_videos(request: ProcessRequest):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, blocking_function, args)
    return result
```

## Banco de Dados

### Status dos Posts (INGLES/UPPERCASE)

```python
STATUS_AGENDADO = "AGENDADO"
STATUS_PROCESSANDO = "PROCESSANDO"
STATUS_PUBLICADO = "PUBLICADO"
STATUS_ERRO = "ERRO"
```

### Schema

- **IDs:** UUID 32 chars hex, sem hifens
- **Timestamps:** Strings ISO
- **Foreign keys:** account_id, post_id, user_id

## FFmpeg / FFprobe

```python
# CORRETO: usar shutil.which para encontrar ffprobe
import shutil
ffprobe = shutil.which("ffprobe") or ffmpeg.replace("ffmpeg", "ffprobe")

# ERRADO: replace quebrado por causa do nome do diretorio
ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")  # NAO FAZER
```

## Cache Busting

```html
<!-- CORRETO: adicionar versao no src -->
<script src="/static/js/app.js?v=9"></script>
<link rel="stylesheet" href="/static/css/app.css?v=7">
```

## Frontend

```javascript
// CORRETO: Estado global via objeto STATE
const STATE = {
    tab: 'editor',
    uploadedVideos: [],
    postQueue: [],
    // ...
};

// CORRETO: Canvas de previsao
function drawPreview() {
    const canvas = document.getElementById('previewCanvas');
    // ... desenha fundo, frame, delogo, logo, @
}
```

## Testes

```python
# CORRETO: test_[acao]_[cenario]_[resultado]
def test_process_video_with_empty_input_returns_empty():
    ...

# Fixtures compartilhadas
@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield session
```

## Anti-Padrao (NAO FAZER)

1. Nao acesse o banco direto — sempre use repository.py
2. Nao use status em portugues — use AGENDADO, PROCESSANDO, PUBLICADO, ERRO
3. Nao importe modulos FFmpeg — sempre use subprocess
4. Nao bloqueie o event loop do FastAPI — use run_in_executor
5. Nao silencie erros com except: pass
6. Nao faca replace("ffmpeg", "ffprobe") — use shutil.which
7. Nao esqueca de atualizar ?v=N no HTML ao mudar JS/CSS
8. Nao crie classes de repositorio — use funcoes puras
