"""Recompute primary statistics from frozen raw data and assert lock equality."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis_core import rebuild_outputs

LOCK_PATH = ROOT / "reports" / "paper_number_lock.json"
TOL = 1e-12


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=0.0, abs_tol=TOL)


def _assert_dict_floats(left: dict, right: dict, prefix: str = "") -> None:
    for key in sorted(right):
        path = f"{prefix}.{key}" if prefix else key
        lv, rv = left[key], right[key]
        if isinstance(rv, dict):
            _assert_dict_floats(lv, rv, path)
        elif isinstance(rv, list):
            for i, (a, b) in enumerate(zip(lv, rv, strict=True)):
                if not _close(float(a), float(b)):
                    raise AssertionError(f"{path}[{i}] mismatch: {a} vs {b}")
        else:
            if not _close(float(lv), float(rv)):
                raise AssertionError(f"{path} mismatch: {lv} vs {rv}")


def main() -> int:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    rebuilt = rebuild_outputs(write=False)
    checks = {
        "raw_sha256": rebuilt["raw_sha256"],
        "analysis_code_hash": rebuilt["analysis_code_hash"],
        "theta_E": rebuilt["theta_E"],
        "theta_N": rebuilt["theta_N"],
        "p_E": rebuilt["p_E"],
        "p_N": rebuilt["p_N"],
        "theta_E_by_dim": rebuilt["theta_E_by_dim"],
        "theta_N_by_dim": rebuilt["theta_N_by_dim"],
        "N_k": {str(k): v for k, v in rebuilt["N_k"].items()},
        "bootstrap_E_by_dim": rebuilt["bootstrap_E_by_dim"],
        "bootstrap_N": list(rebuilt["bootstrap_N"]),
        "holm_axis_reject": rebuilt["holm_axis_reject"],
        "axis_p_E": rebuilt["axis_p_E"],
    }
    for gate in ("E", "N"):
        for field in ("mes_pass", "sign_pass", "pair_pass", "invalid_pass", "discordance_pass"):
            checks[f"gates.{gate}.{field}"] = rebuilt["gates"][gate][field]
    for key, expected in lock.items():
        if key == "sprint_manifest_sha256":
            continue
        if key == "gates":
            for gate in ("E", "N"):
                for field, val in expected[gate].items():
                    actual = rebuilt["gates"][gate][field]
                    if actual != val:
                        raise AssertionError(f"gates.{gate}.{field}: {actual} vs {val}")
            continue
        actual = checks.get(key, rebuilt.get(key))
        if isinstance(expected, dict):
            _assert_dict_floats(actual, expected, key)
        elif isinstance(expected, list):
            for i, (a, b) in enumerate(zip(actual, expected, strict=True)):
                if isinstance(b, bool):
                    if a != b:
                        raise AssertionError(f"{key}[{i}] mismatch: {a} vs {b}")
                elif not _close(float(a), float(b)):
                    raise AssertionError(f"{key}[{i}] mismatch: {a} vs {b}")
        elif isinstance(expected, bool):
            if actual != expected:
                raise AssertionError(f"{key} mismatch: {actual} vs {expected}")
        elif isinstance(expected, str):
            if str(actual) != expected:
                raise AssertionError(f"{key} mismatch: {actual} vs {expected}")
        elif not _close(float(actual), float(expected)):
            raise AssertionError(f"{key} mismatch: {actual} vs {expected}")
    print("verify_paper_numbers: all locked fields match rebuild within tolerance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
