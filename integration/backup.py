"""Online SQLite backup for all modules, with seven daily restore points."""
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil


def main():
    source = Path(os.getenv("YUEJI_DATA_DIR", "/var/lib/yueji"))
    root = Path(os.getenv("YUEJI_BACKUP_DIR", "/var/backups/yueji"))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    destination = root / stamp
    destination.mkdir(mode=0o700)
    for database in source.rglob("*.sqlite3"):
        target = destination / database.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
        os.chmod(target, 0o600)
    personal_key=source/'.personal-api.key'
    if personal_key.exists():
        shutil.copyfile(personal_key,destination/personal_key.name)
        os.chmod(destination/personal_key.name,0o600)
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for old in root.iterdir():
        if old.is_dir():
            try:
                created = datetime.strptime(old.name, "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if created < cutoff:
                shutil.rmtree(old)
    print(f"SQLite backup completed: {destination.name}")


if __name__ == "__main__":
    main()

