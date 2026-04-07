from __future__ import annotations

import json

from motus import update_check


def test_get_git_install_metadata_returns_commit_for_repo(monkeypatch):
    class FakeDistribution:
        @staticmethod
        def read_text(name):
            assert name == "direct_url.json"
            return json.dumps(
                {
                    "url": "https://github.com/lithos-ai/motus.git",
                    "vcs_info": {
                        "commit_id": "abc123",
                        "requested_revision": "main",
                    },
                }
            )

    monkeypatch.setattr(update_check, "distribution", lambda _: FakeDistribution())

    assert update_check._get_git_install_metadata() == {
        "commit": "abc123",
        "ref": "main",
    }


def test_get_cached_remote_commit_uses_fresh_cache(monkeypatch):
    monkeypatch.setattr(
        update_check,
        "_load_cache",
        lambda: {"checked_at": 100.0, "commit": "def456", "ref": "main"},
    )
    monkeypatch.setattr(update_check.time, "time", lambda: 101.0)
    monkeypatch.setattr(update_check, "_fetch_remote_commit", lambda ref: None)

    assert update_check._get_cached_remote_commit("main") == "def456"
