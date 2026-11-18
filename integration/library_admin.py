"""Offline, backed-up removal of explicitly selected books across A/B/C.

Billing ledgers, credentials, sessions and every unselected book are preserved.
Run only while the web service is stopped and analysis jobs have finished.
"""
import argparse
import json
import os
import re
import sqlite3
import shutil
from datetime import datetime, timezone
from pathlib import Path


def purge_books(data_dir: Path, expected: dict[str, str], backup_root: Path):
    if not expected:
        raise ValueError("必须明确指定要移除的书籍编号与标题")
    data_dir, backup_root = Path(data_dir), Path(backup_root)
    paths = {"plot": data_dir / "plot.sqlite3", "characters": data_dir / "characters.sqlite3",
             "qa": data_dir / "qa/yueji.sqlite3", "integration": data_dir / "integration.sqlite3"}
    if not all(p.exists() for p in paths.values()):
        raise ValueError("数据目录不完整，未执行删除")
    connections = {name: sqlite3.connect(path, timeout=30) for name, path in paths.items()}
    identifiers = tuple(expected)
    placeholders = ",".join("?" for _ in identifiers)
    backup = backup_root / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    try:
        active = connections["integration"].execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
        if active:
            raise ValueError("仍有分析任务运行，请等待完成后再替换书库")
        actual = dict(connections["plot"].execute(f"SELECT id,title FROM books WHERE id IN ({placeholders})", identifiers))
        if actual != expected:
            raise ValueError("书籍编号或标题与待删除清单不一致，未执行删除")
        backup.mkdir(parents=True, mode=0o700)
        for name, src in connections.items():
            destination = backup / paths[name].relative_to(data_dir)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(destination) as target:
                src.backup(target)
            destination.chmod(0o600)
        personal_key=data_dir/'.personal-api.key'
        if personal_key.exists():
            shutil.copyfile(personal_key,backup/personal_key.name)
            (backup/personal_key.name).chmod(0o600)
        for db in connections.values():
            db.execute("PRAGMA foreign_keys=OFF")
            db.execute("BEGIN IMMEDIATE")
        plot = connections["plot"]
        for table in ["artifacts", "tasks"]:
            plot.execute(f"DELETE FROM {table} WHERE book_id IN ({placeholders})", identifiers)
        plot.execute(f"DELETE FROM books WHERE id IN ({placeholders})", identifiers)
        characters = connections["characters"]
        characters.execute(f"DELETE FROM name_identity_evidence WHERE name_id IN (SELECT id FROM names WHERE book_id IN ({placeholders}))", identifiers)
        characters.execute(f"DELETE FROM relation_evidence WHERE relation_id IN (SELECT id FROM relations WHERE book_id IN ({placeholders}))", identifiers)
        tables = [r[0] for r in characters.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table) or table == "call_log":
                continue
            columns = {r[1] for r in characters.execute(f'PRAGMA table_info("{table}")')}
            if "book_id" in columns:
                characters.execute(f'DELETE FROM "{table}" WHERE book_id IN ({placeholders})', identifiers)
        characters.execute(f"DELETE FROM books WHERE id IN ({placeholders})", identifiers)
        qa = connections["qa"]
        qa.execute(f"DELETE FROM knowledge WHERE book_id IN ({placeholders})", identifiers)
        qa.execute(f"DELETE FROM answers WHERE json_valid(body) AND json_extract(body,'$.book_id') IN ({placeholders})", identifiers)
        # These content-addressed entries cannot be selected by book ID.
        # Keep them so deleting one book does not clear other books' caches;
        # the corrected chapter/text version has independent retrieval keys.
        qa.execute(f"DELETE FROM books WHERE id IN ({placeholders})", identifiers)
        connections["integration"].execute(f"DELETE FROM jobs WHERE book_id IN ({placeholders})", identifiers)
        if connections["integration"].execute("SELECT 1 FROM sqlite_master WHERE name='character_checks'").fetchone():
            connections["integration"].execute(f"DELETE FROM character_checks WHERE book_id IN ({placeholders})", identifiers)
        for table in ("identity_checks","identity_links","alias_inventory","alias_scan_cache","profile_summaries"):
            if connections["integration"].execute("SELECT 1 FROM sqlite_master WHERE name=?",(table,)).fetchone():
                connections["integration"].execute(f"DELETE FROM {table} WHERE book_id IN ({placeholders})",identifiers)
        if connections['integration'].execute("SELECT 1 FROM sqlite_master WHERE name='reader_progress'").fetchone():
            connections['integration'].execute(f'DELETE FROM reader_progress WHERE book_id IN ({placeholders})',identifiers)
        for name, db in connections.items():
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError(f"{name} 外键检查未通过，已回滚")
        for db in connections.values():
            db.commit()
        remaining = [{"id": r[0], "title": r[1]} for r in plot.execute("SELECT id,title FROM books ORDER BY created_at")]
        return {"removed": list(expected.values()), "remaining": remaining, "backup_directory": str(backup), "billing_records_preserved": True}
    except Exception:
        for db in connections.values():
            db.rollback()
        raise
    finally:
        for db in connections.values():
            db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("/var/lib/yueji"))
    parser.add_argument("--manifest", type=Path, required=True, help="JSON object mapping exact book IDs to titles")
    parser.add_argument("--backup-root", type=Path, default=Path("/var/backups/yueji/library-replacements"))
    args = parser.parse_args()
    expected = json.loads(args.manifest.read_text())
    print(json.dumps(purge_books(args.data_dir, expected, args.backup_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
