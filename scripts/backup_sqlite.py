"""Backup SQLite database to a timestamped file.

Usage:
    python scripts/backup_sqlite.py                  # Backup to default location
    python scripts/backup_sqlite.py --output backups/  # Custom output directory
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils import writable_root


def backup_database(output_dir: str | None = None) -> Path:
    """Backup the SQLite database file.

    Args:
        output_dir: Custom output directory. Defaults to config/backups/.

    Returns:
        Path to the backup file.
    """
    db_path = writable_root() / "config" / "app.db"

    if not db_path.is_file():
        print(f"❌ Banco não encontrado: {db_path}")
        print("   Execute o app primeiro para criar o banco.")
        sys.exit(1)

    # Determine output directory
    if output_dir:
        backup_dir = Path(output_dir)
    else:
        backup_dir = writable_root() / "config" / "backups"

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"app_backup_{timestamp}.db"
    backup_path = backup_dir / backup_name

    # Copy the database file
    shutil.copy2(db_path, backup_path)

    # Also backup the WAL and SHM files if they exist
    for ext in [".db-wal", ".db-shm"]:
        wal_path = db_path.parent / f"app{ext}"
        if wal_path.is_file():
            shutil.copy2(wal_path, backup_dir / f"app_backup_{timestamp}{ext}")

    # Report
    size_mb = backup_path.stat().st_size / (1024 * 1024)
    print(f"✅ Backup criado: {backup_path}")
    print(f"   Tamanho: {size_mb:.1f} MB")
    print(f"   Pasta:  {backup_dir.resolve()}")

    return backup_path


def list_backups() -> list[Path]:
    """List all available backups."""
    backup_dir = writable_root() / "config" / "backups"
    if not backup_dir.is_dir():
        return []
    return sorted(backup_dir.glob("app_backup_*.db"), reverse=True)


def main() -> None:
    """Backup the SQLite database."""
    output_dir = None

    for i, arg in enumerate(sys.argv[1:], start=1):
        if arg == "--output" and i < len(sys.argv):
            output_dir = sys.argv[i]
        elif arg in ("--list", "-l"):
            backups = list_backups()
            if backups:
                print("📋 Backups disponíveis:")
                for b in backups:
                    size = b.stat().st_size / (1024 * 1024)
                    print(f"   {b.name} ({size:.1f} MB)")
            else:
                print("Nenhum backup encontrado.")
            return
        elif arg in ("--help", "-h"):
            print(__doc__)
            return

    print("📦 Backup do banco SQLite")
    print("═══════════════════════════")
    backup_database(output_dir)


if __name__ == "__main__":
    main()
