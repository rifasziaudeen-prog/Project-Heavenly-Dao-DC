"""scripts/github_backup.py — off-server database mirror to GitHub.

Pushes the daily SQLite snapshot to a dedicated branch in a GitHub repository
so a hosting-provider purge (e.g. wispbyte's 14-day inactivity rule) can never
permanently destroy player data.

How it works
------------
* Reads GITHUB_BACKUP_TOKEN / GITHUB_BACKUP_REPO / GITHUB_BACKUP_BRANCH /
  GITHUB_BACKUP_KEEP from `.env` (loaded by ``config.default``).
* Uses the GitHub REST Contents API over ``aiohttp`` (already a dependency),
  so the server needs no git installation or credential manager.
* Mirrors the newest ``backups/heavenly_dao_*.db`` snapshot into a
  ``db-backups/`` folder on the branch, keeping the newest N files.

Security
--------
* Player data is sensitive — point GITHUB_BACKUP_REPO at a **PRIVATE** repo.
* The token needs only "Contents: read and write" on that repo. It lives in
  `.env`, which is git-ignored — never committed.

Usage
-----
    python scripts/github_backup.py                # push newest snapshot
    python scripts/github_backup.py path/to.db     # push a specific file
"""
from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path

import aiohttp

from config import default as config

_API = "https://api.github.com"
_REMOTE_DIR = "db-backups"


# --------------------------------------------------------------------------- pure helpers
def latest_snapshot(backup_dir: Path) -> Path | None:
    """Newest ``heavenly_dao_*.db`` file in the backup dir (by name = by date)."""
    matches = list(Path(backup_dir).glob("heavenly_dao_*.db"))
    return max(matches, key=lambda p: p.name) if matches else None


def remote_files_to_prune(files: list[dict], keep: int) -> list[dict]:
    """Oldest snapshots to delete once more than ``keep`` exist.

    ``files`` are the Contents-API entries ({name, sha, path, type}) for the
    remote ``db-backups/`` folder. Names sort lexically = chronologically for
    ``heavenly_dao_YYYY-MM-DD.db``, so pruning the oldest is deterministic.
    """
    if keep < 1:
        return files
    ordered = sorted(files, key=lambda f: f.get("name", ""))
    return ordered[:-keep] if len(ordered) > keep else []


# --------------------------------------------------------------------------- GitHub API
def _url(repo: str, suffix: str) -> str:
    return f"{_API}/repos/{repo}/{suffix}"


async def _request(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    token: str,
    payload: dict | None = None,
) -> tuple[int, object | None]:
    """One authenticated GitHub API call. Returns (status, parsed json)."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        async with session.request(method, url, headers=headers, json=payload) as resp:
            if resp.status == 204:
                return resp.status, None
            body = await resp.json(content_type=None)
            return resp.status, body
    except (aiohttp.ClientError, ValueError) as exc:
        raise RuntimeError(f"GitHub API {method} {url} failed: {exc}") from exc


async def _ensure_branch(session, token: str, repo: str, branch: str) -> None:
    """Create the backup branch from the default branch if it doesn't exist."""
    status, _ = await _request(session, "GET", _url(repo, f"branches/{branch}"), token)
    if status == 200:
        return

    status, repo_info = await _request(session, "GET", _url(repo, ""), token)
    if status != 200:
        raise RuntimeError(
            f"Could not read repo {repo} (status {status}) — is the token valid "
            "with 'Contents: read and write' on that repo?"
        )
    default_branch: str = repo_info["default_branch"]

    status, branch_info = await _request(
        session, "GET", _url(repo, f"branches/{default_branch}"), token
    )
    if status != 200:
        raise RuntimeError(f"Could not read default branch {default_branch} (status {status})")
    head_sha: str = branch_info["commit"]["sha"]

    status, _ = await _request(
        session,
        "POST",
        _url(repo, "git/refs"),
        token,
        {"ref": f"refs/heads/{branch}", "sha": head_sha},
    )
    # 201 created; 422 = raced with another creation — both fine.
    if status not in (201, 422):
        raise RuntimeError(f"Could not create branch {branch} (status {status})")


async def push_snapshot(
    db_file: Path,
    session: aiohttp.ClientSession,
    token: str,
    repo: str,
    branch: str = "db-backups",
    keep: int = 14,
) -> str:
    """Upload ``db_file`` to the backup branch and prune old snapshots.

    Returns a human-readable summary. Raises RuntimeError on API failures.
    """
    await _ensure_branch(session, token, repo, branch)

    remote_path = f"{_REMOTE_DIR}/{db_file.name}"
    content = base64.b64encode(Path(db_file).read_bytes()).decode("ascii")

    status, existing = await _request(
        session, "GET", _url(repo, f"contents/{remote_path}?ref={branch}"), token
    )
    payload: dict = {
        "message": f"Backup {db_file.name}",
        "content": content,
        "branch": branch,
    }
    if status == 200 and isinstance(existing, dict):
        payload["sha"] = existing["sha"]  # overwrite in place

    status, _ = await _request(
        session, "PUT", _url(repo, f"contents/{remote_path}"), token, payload
    )
    if status not in (200, 201):
        raise RuntimeError(
            f"Upload of {remote_path} failed (status {status}) — is the repo "
            "private and the token scoped to it?"
        )

    pruned: list[str] = []
    prune_failures = 0
    status, files = await _request(
        session, "GET", _url(repo, f"contents/{_REMOTE_DIR}?ref={branch}"), token
    )
    if status == 200 and isinstance(files, list):
        snapshots = [f for f in files if f.get("type") == "file"]
        for old in remote_files_to_prune(snapshots, keep):
            status, _ = await _request(
                session,
                "DELETE",
                _url(repo, f"contents/{old['path']}"),
                token,
                {"message": f"Prune {old['name']}", "sha": old["sha"], "branch": branch},
            )
            if status in (200, 204):
                pruned.append(old["name"])
            else:
                prune_failures += 1  # best-effort: don't fail the whole mirror

    summary = f"Mirrored {db_file.name} to {repo}:{branch}"
    if pruned:
        summary += f" (pruned {len(pruned)} old snapshot{'s' if len(pruned) > 1 else ''})"
    if prune_failures:
        summary += f" ({prune_failures} prune{'s' if prune_failures > 1 else ''} failed)"
    return summary


# --------------------------------------------------------------------------- entry points
async def run_mirror(backup_dir: Path | None = None) -> str:
    """Push the newest snapshot to GitHub — no-op (with a message) if unconfigured.

    Callable both from the CLI and from the bot's daily ``backup_loop``.
    """
    if not (config.GITHUB_BACKUP_TOKEN and config.GITHUB_BACKUP_REPO):
        return (
            "GitHub backup mirror skipped — set GITHUB_BACKUP_TOKEN and "
            "GITHUB_BACKUP_REPO in .env to enable"
        )
    directory = backup_dir or config.BACKUP_DIR
    snapshot = latest_snapshot(directory)
    if snapshot is None:
        return f"GitHub backup mirror skipped — no daily snapshot found in {directory}"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        return await push_snapshot(
            snapshot,
            session,
            config.GITHUB_BACKUP_TOKEN,
            config.GITHUB_BACKUP_REPO,
            config.GITHUB_BACKUP_BRANCH,
            config.GITHUB_BACKUP_KEEP,
        )


async def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target:
        path = Path(target)
        if not path.is_file():
            print(f"File not found: {path}")
            return
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            print(
                await push_snapshot(
                    path,
                    session,
                    config.GITHUB_BACKUP_TOKEN,
                    config.GITHUB_BACKUP_REPO,
                    config.GITHUB_BACKUP_BRANCH,
                    config.GITHUB_BACKUP_KEEP,
                )
            )
    else:
        print(await run_mirror())


if __name__ == "__main__":
    asyncio.run(main())
