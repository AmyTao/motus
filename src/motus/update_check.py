from __future__ import annotations

import json
import os
import subprocess
import time
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

_DIST_NAME = "lithosai-motus"
_REPO_URL = "https://github.com/lithos-ai/motus.git"
_CACHE_DIR = Path.home() / ".motus"
_CACHE_PATH = _CACHE_DIR / "update-check.json"
_CACHE_TTL_SECONDS = 60 * 60 * 24
_GIT_TIMEOUT_SECONDS = 2


def maybe_warn_about_update() -> None:
    if os.getenv("MOTUS_SKIP_UPDATE_CHECK", "").lower() in {"1", "true", "yes"}:
        return

    install = _get_git_install_metadata()
    if install is None:
        return

    cached_commit = _get_cached_remote_commit(install["ref"])
    if cached_commit is None:
        return
    if cached_commit == install["commit"]:
        return

    print(
        "A newer Motus CLI is available. Update with:\n"
        "python3 -m pip install --user --upgrade git+https://github.com/lithos-ai/motus.git",
        file=os.sys.stderr,
    )


def _get_git_install_metadata() -> dict[str, str] | None:
    try:
        dist = distribution(_DIST_NAME)
    except PackageNotFoundError:
        return None

    try:
        direct_url_text = dist.read_text("direct_url.json")
    except FileNotFoundError:
        return None
    if not direct_url_text:
        return None

    try:
        direct_url = json.loads(direct_url_text)
    except json.JSONDecodeError:
        return None

    if direct_url.get("url") != _REPO_URL:
        return None

    vcs_info = direct_url.get("vcs_info") or {}
    commit = vcs_info.get("commit_id")
    if not commit:
        return None

    ref = vcs_info.get("requested_revision") or "HEAD"
    return {"commit": commit, "ref": ref}


def _get_cached_remote_commit(ref: str) -> str | None:
    cache = _load_cache()
    now = time.time()
    if (
        cache.get("ref") == ref
        and now - cache.get("checked_at", 0) < _CACHE_TTL_SECONDS
    ):
        commit = cache.get("commit")
        if isinstance(commit, str) and commit:
            return commit

    commit = _fetch_remote_commit(ref)
    if commit is None:
        commit = cache.get("commit") if cache.get("ref") == ref else None
        return commit if isinstance(commit, str) and commit else None

    _save_cache({"checked_at": now, "commit": commit, "ref": ref})
    return commit


def _fetch_remote_commit(ref: str) -> str | None:
    target = ref if ref != "HEAD" else "HEAD"
    try:
        proc = subprocess.run(
            ["git", "ls-remote", _REPO_URL, target],
            capture_output=True,
            check=False,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None

    if proc.returncode != 0:
        return None

    line = proc.stdout.splitlines()[0] if proc.stdout else ""
    commit = line.split()[0] if line else ""
    return commit or None


def _load_cache() -> dict[str, object]:
    try:
        return json.loads(_CACHE_PATH.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def _save_cache(data: dict[str, object]) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(data))
    except OSError:
        pass
