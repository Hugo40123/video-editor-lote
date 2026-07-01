"""VideoEditorLote v2.0 — Web Application

Editor de Vídeos em Lote com interface web, IA local e gestão de postagens.

Uso:
    python main.py          # Inicia o servidor web em http://localhost:5000
"""

from __future__ import annotations

import sys


def main() -> None:
    """Start the web server."""
    import os
    os.environ.setdefault("PORT", "5000")
    os.environ.setdefault("HOST", "127.0.0.1")

    from web.server import run_server
    run_server()


if __name__ == "__main__":
    main()
