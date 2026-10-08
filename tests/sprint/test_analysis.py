from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from sprint.analysis import (
    analysis_code_hash, choice_score, compute_e_effects, compute_n_effects, exact_sign_flip, holm_adjust,
    item_bootstrap_e, missing_sensitivity, rebuild_outputs, semantic_y, two_way_bootstrap_n,
)
from sprint.schema import load_config
from tools.analysis_core import ANALYSIS_HASH_PATHS, two_way_bootstrap_n_draw, _gate_e, _gate_n, _invalid_json_final_count
from tools.rand_manifest import build_randomization_manifest, blind_integrity_qc, repo_relative
ROOT = Path(__file__).resolve().parents[2]
def _rec(experiment, block, condition, probe, order, choice, seed=0, cell=""):
    return {"experiment": experiment, "semantic_block": block, "condition": condition, "history_seed": seed,
            "checkpoint": 200 if experiment == "N" else 0, "probe_id": probe, "option_order": order,
            "cell": cell, "parsed_choice": choice, "error_code": None, "target_dimension": probe[0]}
def _pair(experiment, block, condition, probe, y_ab, y_ba, seed=0, cell=""):
    def row(order: str, y: int) -> dict:
        return _rec(experiment, block, condition, probe, order, "A" if (order == "AB") == y else "B", seed=seed, cell=cell)
    return [row("AB", y_ab), row("BA", y_ba)]
def test_semantic_y_and_choice_score():
    assert semantic_y(_rec("E", "affect", "P+", "P-C01", "AB", "A")) == 1
    assert semantic_y(_rec("E", "affect", "P+", "P-C01", "BA", "B")) == 1
    assert semantic_y(_rec("E", "affect", "P+", "P-C01", "BA", "A")) == 0
    assert choice_score(1, 1) == 1.0
    assert choice_score(1, 0) == 0.5
    assert choice_score(0, 0) == 0.0
def test_exact_sign_flip_golden():
    assert exact_sign_flip([1.0, 1.0, 1.0]) == pytest.approx(1 / 8)
    assert exact_sign_flip([0.8, 0.6, 0.4]) == pytest.approx(1 / 8)
    assert exact_sign_flip([0.0, 0.0, 0.0]) == 1.0
def test_holm_golden():
    assert holm_adjust([0.01, 0.04, 0.03], alpha=0.05) == [True, False, False]
    assert holm_adjust([0.01, 0.02, 0.03], alpha=0.05) == [True, True, True]
def test_compute_e_golden():
    rows = []
    for block, pos, neg in (("affect", 1.0, 0.0), ("placebo", 0.5, 0.5)):
        rows += _pair("E", block, "P+", "P-C01", int(pos == 1.0), int(pos == 1.0))
        rows += _pair("E", block, "P-", "P-C01", int(neg == 1.0), int(neg == 1.0))
    out = compute_e_effects(rows)
    assert out["effects"]["P-C01"] == pytest.approx(1.0 / 1.261, rel=1e-3)
    assert out["theta_E"] == pytest.approx(out["effects"]["P-C01"])
def test_compute_n_golden():
    rows = []
    for cell, val in (("full", 1.0), ("zero", 0.0)):
        rows += _pair("N", "affect", "P+", "P-C01", int(val == 1.0), int(val == 1.0), seed=14, cell=cell)
    out = compute_n_effects(rows, {"history_seed_ids": [14], "master_seed": 20260804, "bootstrap_repetitions": 20})
    assert out["N_k"][14] == pytest.approx(1.0)
    assert out["theta_N"] == pytest.approx(1.0)
def test_missing_sensitivity_golden():
    rows = _pair("E", "affect", "P+", "P-C01", 1, 1) + _pair("E", "affect", "P-", "P-C01", 0, 0)
    rows.append(_rec("E", "placebo", "P+", "P-C01", "AB", "A"))
    rows += _pair("E", "placebo", "P-", "P-C01", 0, 0)
    miss = missing_sensitivity(rows, {"history_seed_ids": [14], "master_seed": 20260804, "bootstrap_repetitions": 20})
    assert miss["E"]["complete"] != miss["E"]["best"]
def test_two_way_bootstrap_multiplicity():
    seeds, items = [14], ["P-C01", "P-C02"]
    n_hj = {("P+", 14, "P-C01"): 1.0, ("P+", 14, "P-C02"): 0.0}
    s_pick = np.array([0, 0, 0, 0], dtype=int)
    i_pick = np.array([0, 0, 0, 1], dtype=int)
    assert two_way_bootstrap_n_draw(n_hj, seeds, items, s_pick, i_pick) == pytest.approx(0.75)
    collapsed = float(np.mean([v for (h, s, p), v in n_hj.items() if s in {14} and p in {"P-C01", "P-C02"}]))
    assert collapsed == pytest.approx(0.5)
    assert two_way_bootstrap_n_draw(n_hj, seeds, items, s_pick, i_pick) != collapsed
def test_analysis_code_hash_covers_implementation():
    import hashlib
    h = hashlib.sha256()
    for path in ANALYSIS_HASH_PATHS:
        h.update(path.read_bytes())
    assert analysis_code_hash() == h.hexdigest()
    assert analysis_code_hash() != hashlib.sha256((ROOT / "sprint" / "analysis.py").read_bytes()).hexdigest()
def test_bootstrap_small():
    rows = []
    for probe in ("P-C01", "P-C02"):
        rows += _pair("E", "affect", "P+", probe, 1, 1) + _pair("E", "affect", "P-", probe, 0, 0)
        rows += _pair("E", "placebo", "P+", probe, 0, 0) + _pair("E", "placebo", "P-", probe, 0, 0)
    cfg = {"master_seed": 20260804, "bootstrap_repetitions": 50, "history_seed_ids": [14]}
    e_ci = item_bootstrap_e(rows, cfg, reps=50)
    assert e_ci["P"][0] <= e_ci["P"][1]
    n_rows = _pair("N", "affect", "P+", "P-C01", 1, 1, seed=14, cell="full") + _pair("N", "affect", "P+", "P-C01", 1, 1, seed=14, cell="zero")
    lo, hi = two_way_bootstrap_n(n_rows, cfg, reps=50)
    assert lo <= hi
def test_randomization_manifest_sealed():
    doc = build_randomization_manifest(write=False)
    assert doc["master_seed"] == 20260804
    assert len(doc["schedule"]) == 756
    assert len({e["opaque_code"] for e in doc["schedule"]}) == 756
    assert doc["file_sha256"] is not None
def test_rebuild_hash_stable(tmp_path):
    raw = ROOT / "data" / "raw" / "sprint_raw.jsonl"
    if not raw.is_file():
        pytest.skip("formal raw not present")
    build_randomization_manifest(write=True)
    out1 = rebuild_outputs(write=True)
    p = ROOT / "reports" / "final_results.json"
    h1 = p.read_bytes()
    out2 = rebuild_outputs(write=True)
    h2 = p.read_bytes()
    assert h1 == h2
    assert out1["analysis_code_hash"] == out2["analysis_code_hash"]
def test_paper_number_lock_matches_rebuild():
    lock_path = ROOT / "reports" / "paper_number_lock.json"
    if not lock_path.is_file():
        pytest.skip("paper_number_lock.json not present")
    import subprocess
    import sys
    proc = subprocess.run(
        [sys.executable, "-m", "tools.verify_paper_numbers"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def _cfg_mini():
    return {"history_seed_ids": [14], "master_seed": 20260804, "bootstrap_repetitions": 20,
            "MES_E": 0.10, "MES_N": 0.10, "alpha_E_one_sided": 0.05, "alpha_N_one_sided": 0.05}


def _full_n_rows(seed=14):
    from sprint.manifest import derive_all_replay_probe_ids
    rows = []
    for direction in ("P+", "P-", "A+", "A-", "D+", "D-"):
        for probe in derive_all_replay_probe_ids()[direction[0]]:
            for cell in ("full", "zero"):
                rows += _pair("N", "affect", direction, probe, 1, 1, seed=seed, cell=cell)
    return rows


def test_gate_n_substructure_passes_perfect():
    cfg = load_config() if (ROOT / "configs" / "sprint_20260810.yaml").is_file() else _cfg_mini()
    raw = ROOT / "data" / "raw" / "sprint_raw.jsonl"
    if raw.is_file():
        from sprint.runner import load_records
        from tools.analysis_core import _formal_records
        rows = _formal_records(load_records(raw))
    else:
        pytest.skip("formal raw not present")
        rows = []
    gate = _gate_n([r for r in rows if r.get("experiment") == "N"], cfg)
    assert gate["direction_pair_pass"] is True
    assert gate["seed_direction_pass"] is True
    assert gate["invalid_json"] == 0


def test_gate_n_direction_fail_synthetic():
    cfg = _cfg_mini()
    rows = _full_n_rows()
    # Drop all P+ item units for seed 14 (3 probes × both cells incomplete)
    rows = [r for r in rows if not (r["condition"] == "P+" and r["history_seed"] == 14)]
    gate = _gate_n(rows, cfg)
    assert gate["direction_pair_pass"] is False


def test_gate_n_seed_direction_fail_synthetic():
    cfg = _cfg_mini()
    rows = _full_n_rows()
    # Remove one full probe (P-C01) for P+ direction — leaves 2/3 item units
    rows = [r for r in rows if not (r["condition"] == "P+" and r["probe_id"] == "P-C01")]
    gate = _gate_n(rows, cfg)
    assert gate["seed_direction_min_items"] == 2
    rows = [r for r in rows if not (r["condition"] == "P+" and r["probe_id"] in ("P-C01", "P-C05"))]
    gate = _gate_n(rows, cfg)
    assert gate["seed_direction_pass"] is False


def test_invalid_json_counts_final_schema_not_transport():
    base = _rec("E", "affect", "P+", "P-C01", "AB", "A")
    transport = dict(base, request_id="t1", request_attempt=0, parsed_choice=None, error_code="transport_error")
    success = dict(base, request_id="t2", request_attempt=1, parsed_choice="A", error_code=None)
    assert _invalid_json_final_count([transport, success], "E") == 0
    invalid = dict(base, request_id="i1", request_attempt=0, parsed_choice=None, error_code="invalid_choice_json")
    assert _invalid_json_final_count([invalid], "E") == 1


def test_qc_reports_use_repo_relative_paths():
    build_randomization_manifest(write=True)
    report = blind_integrity_qc(write=True)
    for key in ("raw_path", "manifest_path"):
        assert not report[key].startswith("C:\\")
        assert "Users" not in report[key]
    for path in (ROOT / report["raw_path"], ROOT / report["manifest_path"]):
        assert path.is_file() or report["raw_path"].endswith("sprint_raw.jsonl")
    for name in ("blind_integrity_qc.json", "integrity_report.json"):
        text = (ROOT / "reports" / name).read_text(encoding="utf-8") if (ROOT / "reports" / name).is_file() else ""
        if text:
            assert "C:\\Users" not in text


def test_blind_qc_runs():
    build_randomization_manifest(write=True)
    report = blind_integrity_qc(write=True)
    assert report["mode"] == "blind"
    assert "pass" in report
    assert report["manifest_entry_count"] == 756
    assert report["formal_rows"] == 756
    assert report["dev_en_rows"] == 44
    assert report["pass"] is True
