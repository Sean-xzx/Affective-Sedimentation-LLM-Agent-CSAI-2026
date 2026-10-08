"""Download and verify the frozen tokenizer; never download model weights."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_PATH = ROOT / "docs" / "resources.json"
CACHE = ROOT / ".cache" / "huggingface" / "hub"


def prepare() -> Path:
    from huggingface_hub import snapshot_download

    spec = json.loads(RESOURCE_PATH.read_text(encoding="utf-8"))
    snapshot = Path(snapshot_download(
        repo_id=spec["repo_id"], revision=spec["revision"],
        allow_patterns=list(spec["files"]), cache_dir=str(CACHE), token=False,
    ))
    for name, expected in spec["files"].items():
        actual = hashlib.sha256((snapshot / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Tokenizer integrity check failed: {name}")
    # The scientific code uses the default revision. In this project-local cache,
    # resolve that alias to the explicitly verified revision, then test offline.
    reference = snapshot.parent.parent / "refs" / "main"
    reference.parent.mkdir(parents=True, exist_ok=True)
    reference.write_text(spec["revision"], encoding="ascii")
    print(f"Tokenizer ready: {spec['repo_id']} @ {spec['revision']}")
    print("Verified 4 tokenizer files; downloaded no model weights.")
    return snapshot


if __name__ == "__main__":
    prepare()
