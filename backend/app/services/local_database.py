from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from app.core.config import get_settings

_LOCK = threading.RLock()
_DATA_DIR_OVERRIDE: ContextVar[Path | None] = ContextVar("local_data_dir_override", default=None)
STALE_TEMP_LIMIT = 20
SQLITE_DOCUMENT_TABLE = "local_json_documents"
_MISSING = object()


class LocalDatabaseCorruptionError(RuntimeError):
    def __init__(self, filename: str, path: Path, message: str) -> None:
        super().__init__(f"JSON store is corrupted: {filename}: {message}")
        self.filename = filename
        self.path = path
        self.message = message


def data_dir() -> Path:
    override = _DATA_DIR_OVERRIDE.get()
    if override is not None:
        override.mkdir(parents=True, exist_ok=True)
        return override
    settings = get_settings()
    configured = Path(settings.local_data_dir)
    if configured.is_absolute():
        directory = configured
    else:
        backend_root = Path(__file__).resolve().parents[2]
        directory = backend_root / configured
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def json_path(filename: str) -> Path:
    return data_dir() / filename


def sqlite_path() -> Path:
    override = _DATA_DIR_OVERRIDE.get()
    if override is not None:
        path = override / "local_store.sqlite3"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    settings = get_settings()
    configured = Path(settings.local_sqlite_path)
    if configured.is_absolute():
        path = configured
    else:
        backend_root = Path(__file__).resolve().parents[2]
        path = backend_root / configured
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def storage_backend() -> str:
    return get_settings().local_storage_backend


@contextmanager
def use_data_dir(path: Path):
    resolved = path.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    token = _DATA_DIR_OVERRIDE.set(resolved)
    try:
        yield resolved
    finally:
        _DATA_DIR_OVERRIDE.reset(token)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _payload_hash(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_text(payload).encode("utf-8")).hexdigest()


def _top_level_count(payload: Any) -> int:
    if isinstance(payload, (list, dict)):
        return len(payload)
    if payload is None:
        return 0
    return 1


def _read_json_path(filename: str, default: Any) -> Any:
    path = json_path(filename)
    if not path.exists():
        return copy.deepcopy(default)
    try:
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return copy.deepcopy(default)
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LocalDatabaseCorruptionError(filename, path, str(exc)) from exc


def _connect_sqlite() -> sqlite3.Connection:
    connection = sqlite3.connect(sqlite_path())
    connection.row_factory = sqlite3.Row
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SQLITE_DOCUMENT_TABLE} (
            filename TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            top_level_count INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    return connection


def _read_sqlite_document(filename: str) -> Any:
    connection = _connect_sqlite()
    try:
        row = connection.execute(
            f"SELECT payload FROM {SQLITE_DOCUMENT_TABLE} WHERE filename = ?",
            (filename,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return _MISSING
    try:
        return json.loads(str(row["payload"]))
    except json.JSONDecodeError as exc:
        raise LocalDatabaseCorruptionError(filename, sqlite_path(), str(exc)) from exc


def _write_sqlite_document(filename: str, payload: Any) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    connection = _connect_sqlite()
    try:
        connection.execute(
            f"""
            INSERT INTO {SQLITE_DOCUMENT_TABLE}
                (filename, payload, payload_sha256, top_level_count, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                payload = excluded.payload,
                payload_sha256 = excluded.payload_sha256,
                top_level_count = excluded.top_level_count,
                updated_at = excluded.updated_at
            """,
            (filename, content, _payload_hash(payload), _top_level_count(payload), _now_iso()),
        )
        connection.commit()
    finally:
        connection.close()


def read_json_file(filename: str, default: Any) -> Any:
    with _LOCK:
        if storage_backend() == "sqlite":
            payload = _read_sqlite_document(filename)
            if payload is not _MISSING:
                return payload
        return _read_json_path(filename, default)


def _cleanup_stale_temp_files(path: Path) -> dict[str, int]:
    temp_files = list(path.parent.glob(f".{path.name}.*.tmp"))
    with suppress(OSError):
        temp_files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    stats = {
        "matched": len(temp_files),
        "attempted": max(0, len(temp_files) - STALE_TEMP_LIMIT),
        "deleted": 0,
        "failed": 0,
    }
    for temp_file in temp_files[STALE_TEMP_LIMIT:]:
        try:
            temp_file.unlink()
            stats["deleted"] += 1
        except FileNotFoundError:
            stats["deleted"] += 1
        except PermissionError:
            stats["failed"] += 1
    return stats


def cleanup_temp_files(*filenames: str) -> dict[str, dict[str, int]]:
    with _LOCK:
        results: dict[str, dict[str, int]] = {}
        for filename in filenames:
            path = json_path(filename)
            results[filename] = _cleanup_stale_temp_files(path)
        return results


def write_json_file(filename: str, payload: Any) -> None:
    with _LOCK:
        if storage_backend() == "sqlite":
            _write_sqlite_document(filename, payload)
            return
        path = json_path(filename)
        temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        _cleanup_stale_temp_files(path)
        temp_path.write_text(content, encoding="utf-8")
        try:
            temp_path.replace(path)
        except PermissionError:
            path.write_text(content, encoding="utf-8")
            with suppress(FileNotFoundError, PermissionError):
                temp_path.unlink(missing_ok=True)


def update_json_file(filename: str, default: Any, updater: Callable[[Any], Any]) -> Any:
    """Run a whole-document JSON read-modify-write under one process lock."""

    with _LOCK:
        payload = read_json_file(filename, default)
        updated = updater(payload)
        write_json_file(filename, updated)
        return updated


def list_json_store_files() -> list[str]:
    with _LOCK:
        return sorted(path.name for path in data_dir().glob("*.json") if path.is_file())


def list_sqlite_documents() -> list[dict[str, Any]]:
    with _LOCK:
        path = sqlite_path()
        if not path.exists():
            return []
        connection = _connect_sqlite()
        try:
            rows = connection.execute(
                f"""
                SELECT filename, payload_sha256, top_level_count, updated_at
                FROM {SQLITE_DOCUMENT_TABLE}
                ORDER BY filename
                """
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) for row in rows]


def get_storage_status() -> dict[str, Any]:
    with _LOCK:
        path = sqlite_path()
        documents = list_sqlite_documents()
        return {
            "active_backend": storage_backend(),
            "data_dir": str(data_dir()),
            "sqlite_path": str(path),
            "sqlite_exists": path.exists(),
            "json_file_count": len(list_json_store_files()),
            "sqlite_document_count": len(documents),
            "sqlite_documents": documents,
        }


def migrate_json_to_sqlite(
    *,
    filenames: list[str] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    with _LOCK:
        selected = sorted(set(filenames or list_json_store_files()))
        existing = {record["filename"] for record in list_sqlite_documents()}
        migrated: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        for filename in selected:
            if not filename.endswith(".json"):
                skipped.append({"filename": filename, "reason": "not_json_store_file"})
                continue
            path = json_path(filename)
            if not path.exists():
                skipped.append({"filename": filename, "reason": "json_file_missing"})
                continue
            if filename in existing and not overwrite:
                skipped.append({"filename": filename, "reason": "sqlite_document_exists"})
                continue
            payload = _read_json_path(filename, None)
            _write_sqlite_document(filename, payload)
            migrated.append(
                {
                    "filename": filename,
                    "top_level_count": _top_level_count(payload),
                    "payload_sha256": _payload_hash(payload),
                }
            )
        return {
            "sqlite_path": str(sqlite_path()),
            "overwrite": overwrite,
            "requested_count": len(selected),
            "migrated_count": len(migrated),
            "skipped_count": len(skipped),
            "migrated": migrated,
            "skipped": skipped,
        }


def verify_sqlite_against_json(*, filenames: list[str] | None = None) -> dict[str, Any]:
    with _LOCK:
        selected = sorted(set(filenames or list_json_store_files()))
        documents = {record["filename"]: record for record in list_sqlite_documents()}
        results: list[dict[str, Any]] = []
        all_match = True
        for filename in selected:
            if not filename.endswith(".json"):
                results.append({"filename": filename, "status": "skipped", "reason": "not_json_store_file"})
                continue
            path = json_path(filename)
            if not path.exists():
                all_match = False
                results.append({"filename": filename, "status": "missing_json"})
                continue
            if filename not in documents:
                all_match = False
                results.append({"filename": filename, "status": "missing_sqlite_document"})
                continue
            json_payload = _read_json_path(filename, None)
            sqlite_payload = _read_sqlite_document(filename)
            json_hash = _payload_hash(json_payload)
            sqlite_hash = _payload_hash(sqlite_payload)
            count_match = _top_level_count(json_payload) == _top_level_count(sqlite_payload)
            hash_match = json_hash == sqlite_hash
            matches = count_match and hash_match
            all_match = all_match and matches
            results.append(
                {
                    "filename": filename,
                    "status": "match" if matches else "mismatch",
                    "json_top_level_count": _top_level_count(json_payload),
                    "sqlite_top_level_count": _top_level_count(sqlite_payload),
                    "json_sha256": json_hash,
                    "sqlite_sha256": sqlite_hash,
                    "count_match": count_match,
                    "hash_match": hash_match,
                }
            )
        return {
            "sqlite_path": str(sqlite_path()),
            "checked_count": len([item for item in results if item.get("status") != "skipped"]),
            "all_match": all_match,
            "results": results,
        }
