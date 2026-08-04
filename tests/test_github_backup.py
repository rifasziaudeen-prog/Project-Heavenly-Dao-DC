"""Tests for scripts/github_backup.py (off-server GitHub mirror)."""
from __future__ import annotations

from pathlib import Path

import pytest

from config import default as config
from scripts import github_backup as gh


# --------------------------------------------------------------------------- helpers
class FakeResponse:
    def __init__(self, status: int, body) -> None:
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self, content_type=None):
        return self._body


class FakeSession:
    """aiohttp-like session whose request() dispatches to a stateful handler."""

    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[tuple[str, str, dict | None]] = []

    def request(self, method: str, url: str, headers=None, json=None):
        self.calls.append((method, url, json))
        return FakeResponse(*self.handler(method, url, json))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


# --------------------------------------------------------------------------- latest_snapshot
def test_latest_snapshot_picks_newest(tmp_path: Path) -> None:
    (tmp_path / "heavenly_dao_2026-08-03.db").write_bytes(b"a")
    newer = tmp_path / "heavenly_dao_2026-08-04.db"
    newer.write_bytes(b"b")
    assert gh.latest_snapshot(tmp_path) == newer


def test_latest_snapshot_empty_dir_returns_none(tmp_path: Path) -> None:
    assert gh.latest_snapshot(tmp_path) is None


# --------------------------------------------------------------------------- pruning
def _file(name: str, sha: str = "s") -> dict:
    return {"name": name, "sha": sha, "path": f"db-backups/{name}", "type": "file"}


def test_remote_files_to_prune_keeps_newest() -> None:
    files = [
        _file("heavenly_dao_2026-08-03.db", "a"),
        _file("heavenly_dao_2026-08-05.db", "c"),
        _file("heavenly_dao_2026-08-04.db", "b"),
    ]
    pruned = gh.remote_files_to_prune(files, keep=1)
    assert [f["name"] for f in pruned] == [
        "heavenly_dao_2026-08-03.db",
        "heavenly_dao_2026-08-04.db",
    ]


def test_remote_files_to_prune_keeps_all_when_within_keep() -> None:
    files = [_file("heavenly_dao_2026-08-04.db"), _file("heavenly_dao_2026-08-05.db")]
    assert gh.remote_files_to_prune(files, keep=14) == []


# --------------------------------------------------------------------------- run_mirror short-circuits
def test_run_mirror_skips_when_not_configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "GITHUB_BACKUP_TOKEN", "")
    monkeypatch.setattr(config, "GITHUB_BACKUP_REPO", "")
    (tmp_path / "heavenly_dao_2026-08-05.db").write_bytes(b"x")
    msg = __import__("asyncio").run(gh.run_mirror(tmp_path))
    assert "skipped" in msg and "GITHUB_BACKUP_TOKEN" in msg


def test_run_mirror_no_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "GITHUB_BACKUP_TOKEN", "tok")
    monkeypatch.setattr(config, "GITHUB_BACKUP_REPO", "owner/repo")
    msg = __import__("asyncio").run(gh.run_mirror(tmp_path))
    assert "no daily snapshot" in msg


# --------------------------------------------------------------------------- end-to-end push + prune
def test_push_snapshot_creates_branch_uploads_and_prunes(tmp_path: Path) -> None:
    db_file = tmp_path / "heavenly_dao_2026-08-05.db"
    db_file.write_bytes(b"\x00\x01\x02real-bytes")

    # Stateful fake of the GitHub API surface push_snapshot touches.
    existing = {
        "db-backups/heavenly_dao_2026-08-03.db": _file("heavenly_dao_2026-08-03.db", "s3"),
        "db-backups/heavenly_dao_2026-08-04.db": _file("heavenly_dao_2026-08-04.db", "s4"),
    }
    branch_created = {"exists": False}

    def handler(method: str, url: str, payload: dict | None):
        url = url.rstrip("/")
        # Branch existence check
        if method == "GET" and url.endswith("/branches/db-backups"):
            return (404, {"message": "Not Found"}) if not branch_created["exists"] else (200, {})
        # Repo info (default branch)
        if method == "GET" and url.endswith("/repos/owner/repo"):
            return (200, {"default_branch": "main"})
        # Default branch head sha
        if method == "GET" and url.endswith("/branches/main"):
            return (200, {"commit": {"sha": "abc123"}})
        # Create ref
        if method == "POST" and url.endswith("/git/refs"):
            branch_created["exists"] = True
            return (201, {"ref": "refs/heads/db-backups"})
        # Check whether today's file exists remotely
        if method == "GET" and url.endswith("/contents/db-backups/heavenly_dao_2026-08-05.db?ref=db-backups"):
            return (404, {"message": "Not Found"})
        # Upload today's file
        if method == "PUT" and url.endswith("/contents/db-backups/heavenly_dao_2026-08-05.db"):
            existing["db-backups/heavenly_dao_2026-08-05.db"] = _file("heavenly_dao_2026-08-05.db", "s5")
            return (201, {"content": {"sha": "s5"}})
        # List remote folder
        if method == "GET" and url.endswith("/contents/db-backups?ref=db-backups"):
            return (200, list(existing.values()))
        # Delete old snapshot
        if method == "DELETE":
            name = url.rsplit("/", 1)[-1]
            existing.pop(f"db-backups/{name}", None)
            return (200, {"content": {}})
        raise AssertionError(f"Unexpected call: {method} {url}")

    session = FakeSession(handler)
    import asyncio

    summary = asyncio.run(
        gh.push_snapshot(db_file, session, "tok", "owner/repo", branch="db-backups", keep=1)
    )

    assert "Mirrored heavenly_dao_2026-08-05.db to owner/repo:db-backups" in summary
    assert "pruned 2" in summary  # the two old snapshots beyond keep=1
    assert branch_created["exists"] is True
    # The uploaded payload carried the real file bytes (base64).
    put_call = next(c for c in session.calls if c[0] == "PUT")
    import base64

    assert base64.b64decode(put_call[2]["content"]) == b"\x00\x01\x02real-bytes"
    assert put_call[2]["branch"] == "db-backups"
    # Deletes targeted the two oldest snapshots only.
    deletes = [c[1] for c in session.calls if c[0] == "DELETE"]
    assert len(deletes) == 2
    assert all("/heavenly_dao_2026-08-0" in d for d in deletes)
