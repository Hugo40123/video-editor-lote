"""Migrate data from SQLite to PostgreSQL.

Usage:
    # Configure PostgreSQL connection
    set DATABASE_URL=postgresql://user:pass@host:5432/dbname

    # Run migration
    python scripts/migrate_to_postgresql.py

    # Or specify URLs directly
    python scripts/migrate_to_postgresql.py ^
        --sqlite "C:\path\to\app.db" ^
        --postgresql "postgresql://user:pass@host:5432/dbname"

This script:
1. Reads all data from SQLite
2. Creates all tables in PostgreSQL (via Alembic)
3. Copies data table by table
4. Verifies row counts
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


# ─── Tables to migrate (in dependency order) ────────────────────────────────

TABLES = [
    "users",
    "accounts",
    "settings",
    "batch_history",
    "worker_logs",
    "content_history",
    "products",
    "posts",
]


def load_sqlite_data(sqlite_url: str) -> dict[str, list[dict]]:
    """Load all data from SQLite database."""
    engine = create_engine(sqlite_url)
    data: dict[str, list[dict]] = {}

    with engine.connect() as conn:
        for table in TABLES:
            # Check if table exists
            result = conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    f"WHERE type='table' AND name='{table}'"
                )
            )
            if not result.fetchone():
                print(f"  ⏭️  Tabela '{table}' não existe no SQLite. Pulando.")
                data[table] = []
                continue

            # Load all rows
            rows = conn.execute(text(f"SELECT * FROM {table}")).fetchall()
            columns = list(rows[0]._mapping.keys()) if rows else []
            data[table] = [dict(row._mapping) for row in rows]
            print(f"  ✅ {table}: {len(data[table])} registros carregados")

    engine.dispose()
    return data


def migrate_to_postgresql(
    pg_url: str, data: dict[str, list[dict]]
) -> None:
    """Migrate data to PostgreSQL."""
    engine = create_engine(pg_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)

    # Create tables via Alembic
    print("\n📦 Executando Alembic migrations no PostgreSQL...")
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", pg_url)
    command.upgrade(alembic_cfg, "head")
    print("  ✅ Migrations aplicadas.")

    session = SessionLocal()

    try:
        for table in TABLES:
            rows = data.get(table, [])
            if not rows:
                print(f"  ⏭️  {table}: sem dados para migrar.")
                continue

            # Check which columns exist in PostgreSQL
            pg_columns = set(
                row[0]
                for row in session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        f"WHERE table_name='{table}'"
                    )
                ).fetchall()
            )

            # Filter rows to only include columns that exist in PostgreSQL
            filtered_rows = []
            for row in rows:
                filtered = {
                    k: v for k, v in row.items() if k in pg_columns
                }
                filtered_rows.append(filtered)

            if not filtered_rows:
                print(f"  ⚠️  {table}: nenhuma coluna compatível encontrada.")
                continue

            # Batch insert
            columns_list = list(filtered_rows[0].keys())
            placeholders = ", ".join([f":{c}" for c in columns_list])
            cols = ", ".join(columns_list)

            batch_size = 100
            for i in range(0, len(filtered_rows), batch_size):
                batch = filtered_rows[i : i + batch_size]
                for row in batch:
                    session.execute(
                        text(
                            f"INSERT INTO {table} ({cols}) "
                            f"VALUES ({placeholders}) "
                            f"ON CONFLICT DO NOTHING"
                        ),
                        row,
                    )
                session.commit()

            print(f"  ✅ {table}: {len(filtered_rows)} registros migrados")

        # Verify counts
        print("\n🔍 Verificando integridade...")
        all_ok = True
        for table in TABLES:
            pg_count = session.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            ).scalar()
            sqlite_count = len(data.get(table, []))
            status = "✅" if pg_count == sqlite_count else "⚠️"
            if pg_count != sqlite_count:
                all_ok = False
            print(
                f"  {status} {table}: "
                f"SQLite={sqlite_count} → PostgreSQL={pg_count}"
            )

        if all_ok:
            print("\n🎉 Migração concluída com sucesso!")
        else:
            print("\n⚠️  Migração concluída com divergências. Verifique acima.")

    except Exception as exc:
        session.rollback()
        print(f"\n❌ Erro durante migração: {exc}")
        raise
    finally:
        session.close()
        engine.dispose()


def parse_args() -> tuple[str, str]:
    """Parse command-line arguments."""
    args = sys.argv[1:]
    sqlite_url = ""
    pg_url = os.environ.get("DATABASE_URL", "")

    for i, arg in enumerate(args):
        if arg in ("--sqlite", "-s") and i + 1 < len(args):
            sqlite_url = args[i + 1]
        elif arg in ("--postgresql", "-p") and i + 1 < len(args):
            pg_url = args[i + 1]
        elif arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)

    if not sqlite_url:
        # Default: local SQLite
        from app.utils import writable_root
        db_path = writable_root() / "config" / "app.db"
        sqlite_url = f"sqlite:///{db_path}"

    if not pg_url:
        print("❌ DATABASE_URL não configurada.")
        print("   Configure a variável de ambiente DATABASE_URL ou use --postgresql.")
        print("   Exemplo: --postgresql postgresql://user:pass@host:5432/dbname")
        sys.exit(1)

    # Validate PostgreSQL URL
    if not (pg_url.startswith("postgresql") or pg_url.startswith("postgres://")):
        print(f"❌ URL inválida: {pg_url[:40]}...")
        print("   Este script requer PostgreSQL. Use DATABASE_URL=postgresql://...")
        sys.exit(1)

    return sqlite_url, pg_url


def main() -> None:
    """Run the SQLite → PostgreSQL migration."""
    print("╔════════════════════════════════════════════╗")
    print("║   Migração SQLite → PostgreSQL            ║")
    print("║   VideoEditorLote v2.5                    ║")
    print("╚════════════════════════════════════════════╝")
    print()

    sqlite_url, pg_url = parse_args()
    print(f"📂 SQLite:     {sqlite_url}")
    print(f"🐘 PostgreSQL: {pg_url}")
    print()

    # Confirm
    print("⚠️  Esta operação IRÁ SOBRESCREVER dados no PostgreSQL.")
    confirm = input("Continuar? (s/N): ").strip().lower()
    if confirm != "s":
        print("Operação cancelada.")
        sys.exit(0)

    print("\n📤 Carregando dados do SQLite...")
    data = load_sqlite_data(sqlite_url)

    print(f"\n📥 Migrando {sum(len(v) for v in data.values())} registros...")
    migrate_to_postgresql(pg_url, data)


if __name__ == "__main__":
    main()
