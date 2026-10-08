"""Protect the publication interface without invoking a hosted model."""
import hashlib
import json

import pytest

from tools.reproduce import check_manifest, demo


def test_demo_never_constructs_live_client(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("The offline demo attempted to construct a live client")

    monkeypatch.setattr("sprint.provider_qwen.make_client", forbidden)
    result = demo()
    assert result["mock_observations"] == 2
    assert result["live_api_attempts"] == 0


def test_release_integrity_rejects_changed_data(tmp_path):
    data = tmp_path / "data.json"
    data.write_bytes(b'{"value":1}\n')
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"protected_files": [{
        "path": "data.json", "sha256": hashlib.sha256(data.read_bytes()).hexdigest()
    }]}), encoding="utf-8")
    assert check_manifest(tmp_path, manifest) == 1
    data.write_bytes(b'{"value":2}\n')
    with pytest.raises(ValueError, match="Protected file changed"):
        check_manifest(tmp_path, manifest)
