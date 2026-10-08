from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pytest
from tools import diagnostics
from tools.analysis_core import ANALYSIS_HASH_PATHS, DIMS, NEG, POS
from tools.diagnostics import (DIRECTIONS, d2_saturation_census, d3_origin_split_slopes,
                               d4_n_direction_decomposition)
from sprint.manifest import derive_all_replay_probe_ids
from sprint.schema import load_config
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "sprint_raw.jsonl"
LOCK = ROOT / "reports" / "paper_number_lock.json"
FORMAL_PROBES = tuple(f"{d}-C{i:02d}" for d in DIMS for i in range(1, 6))
needs_raw = pytest.mark.skipif(not RAW.is_file(), reason="locked raw ledger not present")


@pytest.fixture(scope="module")
def built() -> dict:
    return diagnostics.build(write=False)


@pytest.fixture(scope="module")
def lock() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))


def test_diagnostics_outside_sealed_hash_set():
    assert diagnostics.SELF_PATH not in ANALYSIS_HASH_PATHS
    assert all(p.name != "diagnostics.py" for p in ANALYSIS_HASH_PATHS)


@needs_raw
def test_build_leaves_sealed_artifacts_untouched(built):
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (LOCK, ROOT / "reports" / "final_results.json") if p.is_file()}
    diagnostics.build(write=False)
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}
    assert before == after


@needs_raw
def test_provenance_matches_lock(built, lock):
    prov = built["provenance"]
    assert prov["analysis_code_hash"] == lock["analysis_code_hash"]
    assert prov["raw_sha256"] == lock["raw_sha256"]
    assert prov["diagnostics_code_hash"] == hashlib.sha256(diagnostics.SELF_PATH.read_bytes()).hexdigest()
    assert prov["formal_record_count"] == 756


@needs_raw
def test_formal_record_filter_is_pinned():
    from sprint.runner import load_records
    from tools.analysis_core import _formal_records
    assert len(_formal_records(load_records(RAW))) == 756


@needs_raw
def test_d2_partitions_and_saturated_items_are_zero(built):
    d2 = built["D2_saturation_census"]
    assert d2["counts_partition_all_items"]
    assert d2["n_saturated"] + d2["n_informative"] + d2["n_incomplete"] == d2["n_items"] == 15
    assert d2["saturated_items_with_nonzero_effect"] == []
    assert d2["n_informative"] == d2["n_informative_positive"] + d2["n_informative_negative"]


def test_d2_incomplete_surface_is_not_counted_as_informative():
    cs = {}
    for dim in DIMS:
        for probe in [p for p in FORMAL_PROBES if p.startswith(f"{dim}-")]:
            for block in ("affect", "placebo"):
                for state in (f"{dim}-", "ORIGIN", f"{dim}+"):
                    cs[("E", block, state, 0, 0, probe, "")] = 1.0
    del cs[("E", "affect", "ORIGIN", 0, 0, "P-C01", "")]
    effects = {"effects": {p: (None if p == "P-C01" else 0.0) for p in FORMAL_PROBES}}
    d2 = d2_saturation_census(cs, effects)
    assert d2["incomplete_probe_ids"] == ["P-C01"]
    assert d2["n_incomplete"] == 1
    assert d2["n_informative"] == 0
    assert d2["n_saturated"] == 14
    assert d2["counts_partition_all_items"]


@needs_raw
def test_d3_split_reconstructs_theta_E(built, lock):
    split = built["D3_origin_split_slopes"]["theta_E_split"]
    assert split["sum"] == pytest.approx(lock["theta_E"], abs=1e-12)
    assert split["reconstructs_theta_E"]
    assert split["share_lower"] + split["share_upper"] == pytest.approx(1.0, abs=1e-12)
    assert split["share_lower"] == pytest.approx(0.891746, abs=1e-6)


def _synthetic_e_surface(neg: float, org: float, pos: float) -> dict:
    cs = {}
    for dim in DIMS:
        for probe in [p for p in FORMAL_PROBES if p.startswith(f"{dim}-")]:
            for block in ("affect", "placebo"):
                for state, value in ((NEG[dim], neg), ("ORIGIN", org), (POS[dim], pos)):
                    cs[("E", block, state, 0, 0, probe, "")] = value if block == "affect" else 0.0
    return cs


def test_d3_reports_a_theta_E_share_only_when_every_item_is_covered():
    cs = _synthetic_e_surface(0.0, 0.5, 1.0)
    full = d3_origin_split_slopes(cs, theta_e_locked=None)["theta_E_split"]
    assert full["covers_all_items"] is True
    assert full["n_items_covered"] == full["n_items"] == 15
    assert full["uncovered_probe_ids"] == []

    del cs[("E", "affect", "ORIGIN", 0, 0, "P-C01", "")]
    split = d3_origin_split_slopes(cs, theta_e_locked=full["sum"])["theta_E_split"]
    assert split["covers_all_items"] is False
    assert split["n_items_covered"] == 14
    assert split["uncovered_probe_ids"] == ["P-C01"]
    assert split["share_basis"] == "covered_items_only"
    assert split["reconstructs_theta_E"] is False


@needs_raw
def test_d3_headroom_partitions_items_and_bounds_the_upper_half(built):
    head = built["D3_origin_split_slopes"]["origin_headroom"]
    assert head["block"] == "affect"
    assert head["n_at_ceiling_at_origin"] + head["n_with_headroom"] == head["n_items"] == 15
    assert head["n_with_headroom_that_moved_up"] <= head["n_with_headroom"]
    per_item = {r["probe_id"]: r for r in built["D3_origin_split_slopes"]["per_item"]}
    for row in head["per_item"]:
        upper = per_item[row["probe_id"]]["affect"]["upper_contribution"]
        if row["at_ceiling_at_origin"]:
            assert upper <= 0.0
    movers = set(head["probe_ids_with_headroom_that_moved_up"])
    positive_upper = {p for p, r in per_item.items() if (r["affect"]["upper_contribution"] or 0.0) > 0.0}
    assert movers == positive_upper


def test_d3_placebo_zero_flag_is_not_vacuous_on_an_empty_surface():
    assert d3_origin_split_slopes({}, theta_e_locked=None)["placebo_slope_identically_zero"] is False


@needs_raw
def test_d3_half_slope_ratio_is_not_the_contribution_share(built):
    d3 = built["D3_origin_split_slopes"]
    aff = d3["by_block"]["affect"]
    naive = aff["mean_lower_half_slope"] / (aff["mean_lower_half_slope"] + aff["mean_upper_half_slope"])
    assert naive != pytest.approx(d3["theta_E_split"]["share_lower"], abs=1e-4)


@needs_raw
def test_d4_contributions_sum_to_locked_theta_N(built, lock):
    d4 = built["D4_n_direction_decomposition"]
    assert d4["contributions_sum"] == pytest.approx(lock["theta_N"], abs=1e-12)
    assert d4["theta_N_recomputed"] == pytest.approx(lock["theta_N"], abs=1e-12)
    for dim in DIMS:
        assert d4["theta_N_by_dim_recomputed"][dim] == pytest.approx(lock["theta_N_by_dim"][dim], abs=1e-12)
    assert sum(r["share_of_theta_N"] for r in d4["per_direction"]) == pytest.approx(1.0, abs=1e-12)


def test_d4_is_seed_equal_weighted_under_missing_cells():
    cfg = load_config()
    seeds = list(cfg["history_seed_ids"])
    replay = derive_all_replay_probe_ids()
    cs = {}
    for direction in DIRECTIONS:
        for seed in seeds:
            for probe in replay[direction[0]]:
                hit = 1.0 if direction == "A+" else 0.0
                cs[("N", "affect", direction, seed, 200, probe, "full")] = hit
                cs[("N", "affect", direction, seed, 200, probe, "zero")] = 0.0
    dropped = seeds[0]
    for probe in replay["A"][:2]:
        del cs[("N", "affect", "A+", dropped, 200, probe, "full")]
    d4 = d4_n_direction_decomposition(cs, cfg, [])
    seed_equal = (7 * (3 / 18) + 1 / 16) / 8
    pooled = 22 / 142
    assert d4["contributions_sum"] == pytest.approx(seed_equal, abs=1e-12)
    assert d4["contributions_sum"] != pytest.approx(pooled, abs=1e-9)
    assert d4["seed_unit_counts"][str(dropped)] == 16


@needs_raw
def test_d5_is_dose_normalized_and_not_mes_comparable(built):
    d5 = built["D5_n_normalized_sensitivity"]
    assert d5["comparable_to_MES_N"] is False
    assert "not be compared against MES_N" in d5["note"]
    assert d5["n_skipped"] == 0
    seed_means = [v for v in d5["N_k_normalized"].values() if v is not None]
    assert d5["theta_N_normalized"] == pytest.approx(sum(seed_means) / len(seed_means), abs=1e-12)
    for dim in DIMS:
        per_seed = []
        for seed_key in d5["N_k_normalized"]:
            vals = [u["n_hj_normalized"] for u in d5["units"]
                    if u["axis"] == dim and str(u["seed"]) == seed_key]
            if vals:
                per_seed.append(sum(vals) / len(vals))
        assert d5["theta_N_normalized_by_dim"][dim] == pytest.approx(sum(per_seed) / len(per_seed), abs=1e-12)


@needs_raw
def test_d5_normalization_is_exactly_n_hj_over_abs_z(built):
    d5 = built["D5_n_normalized_sensitivity"]
    assert d5["units"]
    for unit in d5["units"]:
        assert unit["abs_z_target"] > 0.0
        assert unit["n_hj_normalized"] == unit["n_hj"] / unit["abs_z_target"]
    assert d5["unit"] == built["units"]["n_hj_normalized"]
    assert d5["abs_z_target_min"] == min(u["abs_z_target"] for u in d5["units"])
    assert d5["abs_z_target_max"] == max(u["abs_z_target"] for u in d5["units"])


@needs_raw
def test_d7_reproduces_the_protocol_3_9_stability_gate(built):
    d7 = built["D7_determinism_census"]
    assert d7["n_rows"] == 36 and d7["n_payloads"] == 12
    assert d7["repeats_per_payload"] == [3]
    assert d7["all_rows_parse_to_a_choice"]
    assert d7["n_payloads_with_identical_choice"] == 12
    assert d7["n_errors"] == 0
    assert d7["gate_pass"] and d7["gate_error"] is None
    assert d7["temperatures"] == [0]
    assert d7["requested_models"] == d7["returned_models"]
    # the gate covers development payloads; it estimates nothing about the formal grid
    assert d7["formal_conditions_with_repeats"] == 0
    assert d7["within_condition_variance_estimated"] is False


@needs_raw
def test_d7_does_not_claim_response_text_identity(built):
    """raw_response is rebuilt by the provider, so text identity is unverifiable."""
    d7 = built["D7_determinism_census"]
    assert d7["raw_response_is_reconstructed"] is True
    # every accepted row carries one of exactly two canonical strings by construction,
    # which is why counting identical response text would have been vacuous
    assert d7["distinct_raw_response_values"] == ['{"choice":"A"}', '{"choice":"B"}']
    assert "n_payloads_with_identical_response_text" not in d7


@needs_raw
def test_d7_records_the_completion_token_spread(built):
    """Record the spread; do not read it as evidence about the discarded response text."""
    from sprint.runner import load_records
    rows = [r for r in load_records(RAW) if r.get("experiment") == "stability"]
    by_payload: dict[str, list[int]] = {}
    for rec in rows:
        key = hashlib.sha256(rec["renderer_text"].encode()).hexdigest()
        by_payload.setdefault(key, []).append(rec["completion_tokens"])
    expected = sorted(max(v) - min(v) for v in by_payload.values())
    d7 = built["D7_determinism_census"]
    assert d7["completion_token_spreads"] == expected
    assert d7["max_completion_token_spread"] == max(expected)
    assert d7["n_payloads_with_varying_completion_tokens"] == sum(1 for s in expected if s)
    assert (d7["n_payloads_with_identical_completion_tokens"]
            + d7["n_payloads_with_varying_completion_tokens"] == d7["n_payloads"])
    assert d7["n_payloads_with_identical_prompt_tokens"] == 12
    # the spread is billing metadata; the text it would describe was discarded
    assert "unresolved" in d7["completion_token_spread_note"]
    assert "accounting" in d7["completion_token_spread_note"]


def test_d7_gate_requires_the_whole_protocol_3_9_condition():
    """A single well-behaved payload must not pass: 3.9 demands the full 36-row schedule."""
    base = dict(experiment="stability", semantic_block="affect", condition="P+",
                probe_id="P-D01", option_order="AB", parsed_choice="A",
                raw_response='{"choice":"A"}', renderer_text="payload one",
                completion_tokens=10, prompt_tokens=100, total_tokens=110, temperature=0,
                requested_model="m", returned_model="m", enable_thinking=False,
                tools="off", search="off", error_code=None, retry_count=0)
    one_payload = diagnostics.d7_determinism_census([dict(base) for _ in range(3)])
    assert one_payload["gate_pass"] is False
    assert "36" in one_payload["gate_error"]
    # the descriptive counters still report what was seen
    assert one_payload["n_payloads_with_identical_choice"] == 1
    empty = diagnostics.d7_determinism_census([])
    assert empty["gate_pass"] is False and empty["gate_error"]


@needs_raw
def test_d7_gate_fails_when_a_repeat_disagrees():
    from sprint.runner import load_records
    records = [dict(r) for r in load_records(RAW)]
    target = next(r for r in records if r.get("experiment") == "stability")
    target["parsed_choice"] = "B" if target["parsed_choice"] == "A" else "A"
    broken = diagnostics.d7_determinism_census(records)
    assert broken["gate_pass"] is False
    assert broken["n_payloads_with_identical_choice"] == 11


@needs_raw
def test_d8_compares_development_and_formal_cells_like_for_like(built):
    d8 = built["D8_dev_probe_headroom"]
    assert d8["dev_probe_ids"] == ["A-D02", "D-D02", "P-D02"]
    dev, formal = d8["development"], d8["formal_E_for_contrast"]
    # the dry run mirrors E only: 3 probes x 3 conditions x 2 blocks, and 15 x 3 x 2
    assert dev["n_cells"] == 18
    assert formal["n_cells"] == 90
    for census in (dev, formal):
        assert (census["n_at_ceiling"] + census["n_at_floor"]
                + census["n_intermediate"]) == census["n_cells"]
    # the only supported reading: probes with headroom exist, from the same process
    assert dev["n_at_ceiling"] < dev["n_cells"]
    assert dev["n_at_ceiling"] / dev["n_cells"] < formal["n_at_ceiling"] / formal["n_cells"]
    assert len(d8["inadmissible_uses"]) >= 3
    # written after the ceiling was observed: it must never read as a pre-registered result
    assert d8["status"] == "post-hoc exploratory diagnostic"
    assert d8["pre_registered"] is False
    assert "post-hoc exploratory" in d8["admissible_use"]


@needs_raw
def test_d8_development_rows_cannot_reach_any_formal_quantity(built):
    """Demonstrate the fence instead of asserting it."""
    check = built["D8_dev_probe_headroom"]["isolation_check"]
    assert check["n_formal_rows_untouched"] == 756
    assert check["n_development_rows_perturbed"] > 0
    assert check["formal_fingerprint_after_flip"] == check["formal_fingerprint_before"]
    assert check["formal_fingerprint_without_dev_rows"] == check["formal_fingerprint_before"]
    assert check["formal_output_unchanged"] is True


@needs_raw
def test_formal_fingerprint_detects_a_formal_perturbation():
    """The isolation check would be worthless if the fingerprint were insensitive."""
    from sprint.runner import load_records
    cfg = load_config()
    records = [dict(r) for r in load_records(RAW)]
    before = diagnostics._formal_fingerprint(records, cfg)
    formal_ids = {id(r) for r in diagnostics._formal_records(records)}
    target = next(r for r in records if id(r) in formal_ids and r.get("parsed_choice"))
    target["parsed_choice"] = "B" if target["parsed_choice"] == "A" else "A"
    assert diagnostics._formal_fingerprint(records, cfg) != before


def test_mean_is_invariant_to_summation_order():
    values = [1.0, 0.5, 1.0, 0.0, 1 / 3, 2 / 3, 0.5, 0.25, 1 / 7, 1 / 9, 0.75, 1 / 11]
    reference = diagnostics._mean(values)
    for shift in range(len(values)):
        assert diagnostics._mean(values[shift:] + values[:shift]) == reference
    assert diagnostics._mean(list(reversed(values))) == reference
    assert diagnostics._mean([]) is None


@needs_raw
def test_committed_report_reproduces_from_current_code_and_data():
    on_disk = json.loads(diagnostics.OUT_PATH.read_text(encoding="utf-8"))
    rebuilt = json.loads(json.dumps(diagnostics.build(write=False), sort_keys=True))
    assert on_disk["provenance"] == rebuilt["provenance"]
    assert on_disk == rebuilt


@needs_raw
def test_committed_report_records_the_code_that_produced_it():
    on_disk = json.loads(diagnostics.OUT_PATH.read_text(encoding="utf-8"))
    expected = hashlib.sha256(diagnostics.SELF_PATH.read_bytes()).hexdigest()
    assert on_disk["provenance"]["diagnostics_code_hash"] == expected


@needs_raw
def test_d6_every_reported_p_sits_on_its_floor(built, lock):
    rows = {r["test"]: r for r in built["D6_pvalue_floor_census"]["tests"]}
    assert rows["E_overall"]["observed_p"] == pytest.approx(lock["p_E"], abs=1e-15)
    assert rows["N_overall"]["observed_p"] == pytest.approx(lock["p_N"], abs=1e-15)
    for row in rows.values():
        assert row["attainable_floor_p"] == pytest.approx(2.0 ** -row["n_nonzero_units"], abs=1e-15)
        assert row["observed_equals_floor"]
    for dim, locked_p in zip(DIMS, lock["axis_p_E"]):
        assert rows[f"E_axis_{dim}"]["observed_p"] == pytest.approx(locked_p, abs=1e-15)
        assert not rows[f"E_axis_{dim}"]["can_reach_alpha"]


@needs_raw
def test_d6_holm_axis_rejection_was_impossible(built):
    holm = built["D6_pvalue_floor_census"]["holm_axis_analysis"]
    assert holm["items_per_axis"] == 5
    assert holm["best_attainable_axis_p"] == pytest.approx(0.03125)
    assert holm["holm_first_threshold"] == pytest.approx(0.05 / 3)
    assert holm["rejection_attainable"] is False
