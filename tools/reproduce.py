"""Safe publication commands: numerical demo, read-only verification and tests."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "publication_manifest.json"


def check_manifest(root: Path = ROOT, manifest: Path = MANIFEST) -> int:
    document = json.loads(manifest.read_text(encoding="utf-8"))
    for item in document["protected_files"]:
        path = root / item["path"]
        if not path.is_file():
            raise ValueError(f"Missing protected file: {item['path']}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Protected file changed: {item['path']}")
    return len(document["protected_files"])


def demo() -> dict:
    from sprint.dynamics import assert_golden_dynamics, unit_step_half_times
    from sprint.histories import assert_action_map_sealed, run_history
    from sprint.provider_qwen import CompletionResult
    from sprint.runner import ObservationSpec, SprintRunner
    from sprint.schema import load_config, render_z

    assert_golden_dynamics()
    assert_action_map_sealed()
    _, state = run_history("P+", 1000)
    config = load_config()

    def mock_complete(prompt: str, *, config: dict) -> CompletionResult:
        return CompletionResult(
            choice="A", raw_response='{"choice":"A"}',
            requested_model=config["agent_model"], returned_model=config["agent_model"],
            response_id="offline-demo", latency_ms=0, retry_count=0,
            prompt_tokens=0, completion_tokens=0, total_tokens=0,
        )

    schedule = [ObservationSpec("E", "affect", "P+", 0, 0, "P-D02", order, "")
                for order in ("AB", "BA")]
    with tempfile.TemporaryDirectory(prefix="csai3-demo-") as tmp:
        runner = SprintRunner(config=config, raw_path=Path(tmp) / "raw.jsonl",
                              ckpt_path=Path(tmp) / "checkpoint.json",
                              complete_fn=mock_complete)
        outcome = runner.run(schedule)
        if outcome != {"completed": 2, "attempt_count": 2}:
            raise ValueError(f"Unexpected mock outcome: {outcome}")
    result = {"unit_step_half_times": unit_step_half_times(),
              "development_history": "P+ / seed 1000",
              "rendered_state": list(render_z(state.s)),
              "mock_observations": outcome["completed"], "live_api_attempts": 0}
    print("Demo PASS: numerical controller, history, renderer and mock runner.")
    print(json.dumps(result, indent=2))
    return result


def verify() -> dict:
    count = check_manifest()
    from tools.verify_paper_numbers import main as verify_numbers
    from tools.diagnostics import build

    verify_numbers()
    stored = json.loads((ROOT / "reports" / "secondary_diagnostics.json").read_text(encoding="utf-8"))
    if build(write=False) != stored:
        raise ValueError("Secondary diagnostics do not match the recorded report")
    results = json.loads((ROOT / "reports" / "final_results.json").read_text(encoding="utf-8"))
    summary = {key: results[key] for key in ("theta_E", "p_E", "theta_N", "p_N")}
    print(f"Verify PASS: {count} protected files, locked statistics and secondary diagnostics.")
    print(json.dumps(summary, indent=2))
    return summary


def test() -> int:
    environment = dict(os.environ)
    environment.update(HF_HOME=str(ROOT / ".cache" / "huggingface"),
                       HF_HUB_CACHE=str(ROOT / ".cache" / "huggingface" / "hub"),
                       HF_HUB_OFFLINE="1", TOKENIZERS_PARALLELISM="false",
                       HF_HUB_DISABLE_SYMLINKS_WARNING="1")
    return subprocess.call([sys.executable, "-B", "-m", "pytest", "tests/sprint",
                            "tests/publication", "-q", "-p", "no:cacheprovider"],
                           cwd=ROOT, env=environment)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("demo", "verify", "test"))
    command = parser.parse_args().command
    if command == "test":
        return test()
    {"demo": demo, "verify": verify}[command]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
