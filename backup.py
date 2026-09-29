"""Consistent SQLite backup, including while the kiosk is running."""
import sqlite3
from datetime import datetime
from pathlib import Path
from .db import default_db_path


def main():
    source = default_db_path()
    if not source.exists():
        raise SystemExit("Brak bazy danych. Najpierw uruchom kiosk.")
    directory = Path(__file__).resolve().parent.parent / "backups"
    directory.mkdir(exist_ok=True)
    target = directory / f"kiosk-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3"
    original = sqlite3.connect(source)
    copy = sqlite3.connect(target)
    try:
        original.backup(copy)
        if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Kopia nie przeszla kontroli integralnosci.")
    finally:
        copy.close()
        original.close()
    print(f"Kopia zapasowa: {target}")


if __name__ == "__main__":
    main()
