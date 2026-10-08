"""Secondary and diagnostic analyses (protocol 4.1 origin deviation, 4.2 normalized N
sensitivity, 4.3 secondary results).

This module is deliberately excluded from ANALYSIS_HASH_PATHS so that running it cannot
change analysis_code_hash or any value sealed in reports/paper_number_lock.json. It
reads the locked raw ledger and recomputes nothing that a primary gate depends on.

Two unit systems appear here and must not be mixed. Experiment E quantities are
CS per rendered-z; MES_E is stated in the same unit. Experiment N primary quantities are
direction-corrected CS, and MES_N is stated in that unit, so the dose-normalized
sensitivity in D5 (CS per rendered-z) is NOT comparable to MES_N.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from tools.analysis_core import (DIMS, FORMAL_PROBES, NEG, POS, REPORTS, RENDERED_Z, _formal_records,
                                 _gate_e, _gate_n, analysis_code_hash, compute_e_effects,
                                 compute_n_effects, cs_from_records, exact_sign_flip,
                                 missing_sensitivity)
from tools.rand_manifest import RAW_PATH
from sprint.manifest import derive_all_replay_probe_ids
from sprint.runner import assert_stability_gate, load_records
from sprint.schema import load_config, sha256_file

SELF_PATH = Path(__file__).resolve()
OUT_PATH = REPORTS / "secondary_diagnostics.json"
DIRECTIONS = ("P+", "P-", "A+", "A-", "D+", "D-")
DIR_SIGN_MAP = {"P+": 1, "A+": 1, "D+": 1, "P-": -1, "A-": -1, "D-": -1}
ORIGIN_Z = 0.0
UNITS = {
    "e_dj": "CS per rendered-z (Experiment E; same unit as MES_E)",
    "half_slope": "CS per rendered-z measured within one half-interval; a local slope, "
                  "NOT an additive share of theta_E",
    "contribution": "CS per rendered-z over the full axis span; the lower and upper "
                    "contributions sum exactly to e_dj and to theta_E",
    "n_hj": "direction-corrected CS (Experiment N; same unit as MES_N)",
    "n_hj_normalized": "direction-corrected CS per rendered-z; a dose-normalized "
                       "sensitivity that is NOT comparable to MES_N",
}


def _probes(dim: str) -> list[str]:
    return [p for p in FORMAL_PROBES if p.startswith(f"{dim}-")]


def _e_cell(cs: dict, block: str, state: str, probe: str) -> float | None:
    return cs.get(("E", block, state, 0, 0, probe, ""))


def _mean(values: list[float]) -> float | None:
    """Order-invariant mean.

    math.fsum is correctly rounded, so a permutation of the same values cannot change the
    last bit of the result. Plain sum() can, and a one-ULP drift is indistinguishable at a
    glance from a real change, which would make the reproduction check unreadable.
    """
    return math.fsum(values) / len(values) if values else None


def _self_hash() -> str:
    return hashlib.sha256(SELF_PATH.read_bytes()).hexdigest()


def d1_e_response_surface(cs: dict) -> list[dict]:
    rows = []
    for dim in DIMS:
        for probe in _probes(dim):
            for block in ("affect", "placebo"):
                for label, state, z in (("negative", NEG[dim], RENDERED_Z[NEG[dim]]),
                                        ("origin", "ORIGIN", ORIGIN_Z),
                                        ("positive", POS[dim], RENDERED_Z[POS[dim]])):
                    rows.append({"probe_id": probe, "axis": dim, "block": block, "state": label,
                                 "rendered_z": z, "cs": _e_cell(cs, block, state, probe)})
    return rows


def d2_saturation_census(cs: dict, effects: dict) -> dict:
    items = []
    for dim in DIMS:
        for probe in _probes(dim):
            cells = [_e_cell(cs, b, s, probe) for b in ("affect", "placebo")
                     for s in (NEG[dim], "ORIGIN", POS[dim])]
            complete = all(v is not None for v in cells)
            constant = complete and len(set(cells)) == 1
            if not complete:
                status = "incomplete"
            elif constant:
                status = "saturated"
            else:
                status = "informative"
            items.append({"probe_id": probe, "axis": dim, "status": status,
                          "cells_complete": complete, "n_cells_present": sum(v is not None for v in cells),
                          "constant_across_all_six_cells": constant,
                          "constant_value": cells[0] if constant else None,
                          "at_ceiling": constant and cells[0] == 1.0,
                          "e_dj": effects["effects"][probe]})
    by_status = {s: [i for i in items if i["status"] == s] for s in ("saturated", "informative", "incomplete")}
    informative = by_status["informative"]
    return {
        "items": items,
        "n_items": len(items),
        "n_saturated": len(by_status["saturated"]),
        "n_informative": len(informative),
        "n_incomplete": len(by_status["incomplete"]),
        "counts_partition_all_items": sum(len(v) for v in by_status.values()) == len(items),
        "n_saturated_at_ceiling": sum(1 for i in by_status["saturated"] if i["at_ceiling"]),
        "saturated_probe_ids": [i["probe_id"] for i in by_status["saturated"]],
        "informative_probe_ids": [i["probe_id"] for i in informative],
        "incomplete_probe_ids": [i["probe_id"] for i in by_status["incomplete"]],
        "n_informative_positive": sum(1 for i in informative if i["e_dj"] is not None and i["e_dj"] > 0),
        "n_informative_negative": sum(1 for i in informative if i["e_dj"] is not None and i["e_dj"] < 0),
        "saturated_items_with_nonzero_effect": [i["probe_id"] for i in by_status["saturated"]
                                                if i["e_dj"] not in (None, 0.0)],
        "informative_item_mean_effect": _mean([i["e_dj"] for i in informative if i["e_dj"] is not None]),
        "by_axis": {d: {"n_items": len(_probes(d)),
                        "n_saturated": sum(1 for i in items if i["axis"] == d and i["status"] == "saturated"),
                        "n_informative": sum(1 for i in items if i["axis"] == d and i["status"] == "informative"),
                        "n_incomplete": sum(1 for i in items if i["axis"] == d and i["status"] == "incomplete")}
                    for d in DIMS},
    }


def _origin_headroom(cs: dict, block: str = "affect") -> dict:
    """How many items could still move upward from the origin render.

    CS is capped at 1.0, so an item already at 1.0 under the origin render cannot
    register a positive upper-half effect. A small upper half is therefore ambiguous
    between insensitivity and absent headroom, and the two must be counted separately.
    """
    rows = []
    for dim in DIMS:
        for probe in _probes(dim):
            org = _e_cell(cs, block, "ORIGIN", probe)
            pos = _e_cell(cs, block, POS[dim], probe)
            rows.append({"probe_id": probe, "axis": dim, "cs_origin": org, "cs_positive": pos,
                         "at_ceiling_at_origin": org == 1.0,
                         "has_headroom": org is not None and org < 1.0,
                         "moved_up": (org is not None and pos is not None
                                      and org < 1.0 and pos > org)})
    with_headroom = [r for r in rows if r["has_headroom"]]
    return {
        "block": block,
        "n_items": len(rows),
        "n_at_ceiling_at_origin": sum(1 for r in rows if r["at_ceiling_at_origin"]),
        "n_with_headroom": len(with_headroom),
        "probe_ids_with_headroom": [r["probe_id"] for r in with_headroom],
        "n_with_headroom_that_moved_up": sum(1 for r in with_headroom if r["moved_up"]),
        "probe_ids_with_headroom_that_moved_up": [r["probe_id"] for r in with_headroom if r["moved_up"]],
        "by_axis": {d: {"n_at_ceiling_at_origin": sum(1 for r in rows if r["axis"] == d
                                                      and r["at_ceiling_at_origin"]),
                        "n_with_headroom": sum(1 for r in with_headroom if r["axis"] == d)}
                    for d in DIMS},
        "per_item": rows,
        "note": "An upper-half effect is only measurable for items with headroom. "
                "n_with_headroom bounds how much of the upper half could ever have been seen.",
    }


def d3_origin_split_slopes(cs: dict, theta_e_locked: float | None = None) -> dict:
    per_item = []
    for dim in DIMS:
        z_pos, z_neg = RENDERED_Z[POS[dim]], RENDERED_Z[NEG[dim]]
        span = z_pos - z_neg
        for probe in _probes(dim):
            row: dict = {"probe_id": probe, "axis": dim, "span": span}
            halves = {}
            for block in ("affect", "placebo"):
                neg = _e_cell(cs, block, NEG[dim], probe)
                org = _e_cell(cs, block, "ORIGIN", probe)
                pos = _e_cell(cs, block, POS[dim], probe)
                if None in (neg, org, pos):
                    row[block] = {"lower_half_slope": None, "upper_half_slope": None,
                                  "lower_contribution": None, "upper_contribution": None}
                    halves[block] = None
                    continue
                halves[block] = (org - neg, pos - org)
                row[block] = {"lower_half_slope": (org - neg) / (ORIGIN_Z - z_neg),
                              "upper_half_slope": (pos - org) / (z_pos - ORIGIN_Z),
                              "lower_contribution": (org - neg) / span,
                              "upper_contribution": (pos - org) / span}
            if halves["affect"] and halves["placebo"]:
                row["e_lower"] = (halves["affect"][0] - halves["placebo"][0]) / span
                row["e_upper"] = (halves["affect"][1] - halves["placebo"][1]) / span
            else:
                row["e_lower"] = row["e_upper"] = None
            per_item.append(row)

    by_block = {}
    for block in ("affect", "placebo"):
        def col(key: str, rows: list[dict]) -> list[float]:
            return [r[block][key] for r in rows if r[block][key] is not None]
        by_block[block] = {
            "n_items_used": len(col("lower_half_slope", per_item)),
            "mean_lower_half_slope": _mean(col("lower_half_slope", per_item)),
            "mean_upper_half_slope": _mean(col("upper_half_slope", per_item)),
            "mean_lower_contribution": _mean(col("lower_contribution", per_item)),
            "mean_upper_contribution": _mean(col("upper_contribution", per_item)),
            "by_axis": {d: {"mean_lower_half_slope": _mean(col("lower_half_slope", [r for r in per_item if r["axis"] == d])),
                            "mean_upper_half_slope": _mean(col("upper_half_slope", [r for r in per_item if r["axis"] == d])),
                            "mean_lower_contribution": _mean(col("lower_contribution", [r for r in per_item if r["axis"] == d])),
                            "mean_upper_contribution": _mean(col("upper_contribution", [r for r in per_item if r["axis"] == d]))}
                        for d in DIMS},
        }

    # An item without a complete affect+placebo x {neg, origin, pos} surface cannot be
    # split, so it drops out of the halves while still counting in theta_E. When that
    # happens the halves are a subset mean and share_lower is NOT a share of theta_E.
    covered = [r for r in per_item if r["e_lower"] is not None and r["e_upper"] is not None]
    covers_all = len(covered) == len(per_item) and bool(per_item)
    lower = _mean([r["e_lower"] for r in covered])
    upper = _mean([r["e_upper"] for r in covered])
    total = (lower + upper) if (lower is not None and upper is not None) else None
    reconstructs = (covers_all and theta_e_locked is not None and total is not None
                    and abs(total - theta_e_locked) < 1e-12)
    aff = by_block["affect"]
    ratio = (aff["mean_lower_half_slope"] / aff["mean_upper_half_slope"]
             if aff["mean_upper_half_slope"] else None)
    placebo_values = [v for r in per_item for v in r["placebo"].values() if v is not None]
    return {
        "per_item": per_item,
        "by_block": by_block,
        "theta_E_split": {
            "lower_half": lower, "upper_half": upper, "sum": total,
            "share_lower": (lower / total) if total else None,
            "share_upper": (upper / total) if total else None,
            "n_items": len(per_item),
            "n_items_covered": len(covered),
            "uncovered_probe_ids": [r["probe_id"] for r in per_item if r not in covered],
            "covers_all_items": covers_all,
            "reconstructs_theta_E": reconstructs,
            "share_basis": "theta_E" if reconstructs else "covered_items_only",
        },
        "affect_half_slope_ratio_lower_over_upper": ratio,
        "origin_headroom": _origin_headroom(cs, "affect"),
        "placebo_slope_identically_zero": (bool(placebo_values)
                                           and all(v == 0.0 for v in placebo_values)),
        "note": "share_lower is a share of theta_E only when share_basis is 'theta_E'; "
                "otherwise the halves cover a subset of items and do not sum to theta_E. "
                "The half slopes are local slopes over unequal intervals, so their ratio "
                "is a different quantity from the contribution share.",
    }


def d4_n_direction_decomposition(cs: dict, cfg: dict, saturated_ids: list[str]) -> dict:
    replay = derive_all_replay_probe_ids()
    seeds = list(cfg["history_seed_ids"])
    units: dict[tuple, float] = {}
    full_cs: dict[tuple, float] = {}
    zero_cs: dict[tuple, float] = {}
    for direction in DIRECTIONS:
        dim, sign = direction[0], DIR_SIGN_MAP[direction]
        for seed in seeds:
            for probe in replay[dim]:
                full = cs.get(("N", "affect", direction, seed, 200, probe, "full"))
                zero = cs.get(("N", "affect", direction, seed, 200, probe, "zero"))
                if full is None or zero is None:
                    continue
                units[(direction, seed, probe)] = sign * (full - zero)
                full_cs[(direction, seed, probe)] = full
                zero_cs[(direction, seed, probe)] = zero
    seed_totals = {s: sum(1 for (h, k, j) in units if k == s) for s in seeds}
    live_seeds = [s for s in seeds if seed_totals[s] > 0]

    per_direction = []
    for direction in DIRECTIONS:
        keys = [k for k in units if k[0] == direction]
        contrib_terms, full_terms, zero_terms, contrast_terms = [], [], [], []
        for seed in live_seeds:
            sk = [k for k in keys if k[1] == seed]
            if not sk:
                continue
            contrib_terms.append(math.fsum(units[k] for k in sk) / seed_totals[seed])
            full_terms.append(_mean([full_cs[k] for k in sk]))
            zero_terms.append(_mean([zero_cs[k] for k in sk]))
            contrast_terms.append(_mean([units[k] for k in sk]))
        per_direction.append({
            "direction": direction, "axis": direction[0], "sign": DIR_SIGN_MAP[direction],
            "n_cells": len(keys), "n_seeds_present": len(contrib_terms),
            "mean_cs_full": _mean(full_terms), "mean_cs_zero": _mean(zero_terms),
            "mean_signed_contrast": _mean(contrast_terms),
            "contribution_to_theta_N": _mean(contrib_terms) if contrib_terms else None,
        })
    total = math.fsum(r["contribution_to_theta_N"] or 0.0 for r in per_direction)
    for row in per_direction:
        row["share_of_theta_N"] = (row["contribution_to_theta_N"] / total) if total else None

    by_axis = {}
    for dim in DIMS:
        terms = []
        for seed in live_seeds:
            sk = [k for k in units if k[0][0] == dim and k[1] == seed]
            if sk:
                terms.append(_mean([units[k] for k in sk]))
        by_axis[dim] = _mean(terms)

    replay_rows = [{"axis": d, "probe_id": p, "saturated_in_E": p in saturated_ids}
                   for d in DIMS for p in sorted(replay[d])]
    return {
        "per_direction": per_direction,
        "seed_weighting": "seed-equal, matching theta_N = mean_k N_k",
        "contributions_sum": total,
        "theta_N_recomputed": total,
        "theta_N_by_dim_recomputed": by_axis,
        "n_units": len(units),
        "seed_unit_counts": {str(s): seed_totals[s] for s in seeds},
        "directions_with_zero_contribution": [r["direction"] for r in per_direction
                                              if r["contribution_to_theta_N"] == 0.0],
        "replay_probe_saturation": replay_rows,
        "n_replay_probes": len(replay_rows),
        "n_replay_probes_saturated_in_E": sum(1 for r in replay_rows if r["saturated_in_E"]),
        "replay_saturation_by_axis": {d: {"n_probes": len(replay[d]),
                                          "n_saturated": sum(1 for r in replay_rows
                                                             if r["axis"] == d and r["saturated_in_E"])}
                                      for d in DIMS},
    }


def d5_n_normalized_sensitivity(records: list[dict], cs: dict, cfg: dict) -> dict:
    replay = derive_all_replay_probe_ids()
    seeds = list(cfg["history_seed_ids"])
    dim_index = {d: i for i, d in enumerate(DIMS)}
    z_target: dict[tuple, float] = {}
    for rec in records:
        if rec.get("experiment") != "N" or rec.get("cell") != "full":
            continue
        key = (rec["condition"], int(rec["history_seed"]), rec["probe_id"])
        z_target[key] = float(rec["rendered_z"][dim_index[rec["condition"][0]]])
    units, skipped = [], 0
    for direction in DIRECTIONS:
        dim, sign = direction[0], DIR_SIGN_MAP[direction]
        for seed in seeds:
            for probe in replay[dim]:
                full = cs.get(("N", "affect", direction, seed, 200, probe, "full"))
                zero = cs.get(("N", "affect", direction, seed, 200, probe, "zero"))
                z = z_target.get((direction, seed, probe))
                if full is None or zero is None or z is None or abs(z) == 0.0:
                    skipped += 1
                    continue
                units.append({"direction": direction, "axis": dim, "seed": seed, "probe_id": probe,
                              "abs_z_target": abs(z), "n_hj": sign * (full - zero),
                              "n_hj_normalized": sign * (full - zero) / abs(z)})
    per_seed = {str(s): _mean([u["n_hj_normalized"] for u in units if u["seed"] == s]) for s in seeds}
    seed_means = [v for v in per_seed.values() if v is not None]
    by_dim = {}
    for dim in DIMS:
        terms = [_mean([u["n_hj_normalized"] for u in units if u["axis"] == dim and u["seed"] == s])
                 for s in seeds]
        by_dim[dim] = _mean([t for t in terms if t is not None])
    return {
        "units": units,
        "n_units": len(units),
        "n_skipped": skipped,
        "seed_weighting": "seed-equal, matching the primary theta_N aggregation",
        "abs_z_target_min": min((u["abs_z_target"] for u in units), default=None),
        "abs_z_target_max": max((u["abs_z_target"] for u in units), default=None),
        "N_k_normalized": per_seed,
        "theta_N_normalized": _mean(seed_means),
        "theta_N_normalized_by_dim": by_dim,
        "all_seed_means_positive": all(v > 0 for v in seed_means) if seed_means else None,
        "unit": UNITS["n_hj_normalized"],
        "comparable_to_MES_N": False,
        "note": "Protocol 4.2 dose-normalized sensitivity. Reported in CS per rendered-z, "
                "whereas theta_N and MES_N are in direction-corrected CS. It does not "
                "replace the primary theta_N and must not be compared against MES_N.",
    }


def _min_units_for(alpha: float) -> int:
    k = 1
    while 2.0 ** -k > alpha:
        k += 1
    return k


def _floor_row(name: str, values: list[float], alpha: float) -> dict:
    nonzero = [v for v in values if v != 0.0]
    k = len(nonzero)
    floor = 2.0 ** -k if k else 1.0
    observed = exact_sign_flip(values) if values else 1.0
    return {"test": name, "n_units": len(values), "n_nonzero_units": k,
            "observed_p": observed, "attainable_floor_p": floor,
            "observed_equals_floor": observed == floor,
            "can_reach_alpha": floor <= alpha,
            "min_nonzero_units_for_alpha": _min_units_for(alpha)}


def d6_pvalue_floor_census(effects: dict, n_effects: dict, cfg: dict) -> dict:
    alpha_e = float(cfg["alpha_E_one_sided"])
    alpha_n = float(cfg["alpha_N_one_sided"])
    e_units = [v for v in effects["effects"].values() if v is not None]
    n_units = [v for v in n_effects["N_k"].values() if v == v]
    rows = [_floor_row("E_overall", e_units, alpha_e), _floor_row("N_overall", n_units, alpha_n)]
    for dim in DIMS:
        axis_units = [effects["effects"][p] for p in _probes(dim) if effects["effects"][p] is not None]
        rows.append(_floor_row(f"E_axis_{dim}", axis_units, alpha_e))
    items_per_axis = len(_probes(DIMS[0]))
    best_axis_p = 2.0 ** -items_per_axis
    holm_first_threshold = alpha_e / len(DIMS)
    return {
        "tests": rows,
        "sign_flip_holds_exact_zeros_fixed": True,
        "holm_axis_analysis": {
            "items_per_axis": items_per_axis,
            "best_attainable_axis_p": best_axis_p,
            "holm_first_threshold": holm_first_threshold,
            "rejection_attainable": best_axis_p <= holm_first_threshold,
            "note": "With this many items per axis no possible outcome can clear the first Holm step.",
        },
    }


def d7_determinism_census(all_records: list[dict]) -> dict:
    """Protocol 3.9 stability gate, recomputed from the ledger.

    Twelve fixed payloads were each requested three times at temperature 0 before formal
    collection. What this can and cannot support has to be stated precisely.

    It CAN support: repeated identical requests returned the same extracted choice, on
    development probes, before formal collection.

    It CANNOT support: that the 756 formal observations have zero within-condition variance.
    No formal condition was ever repeated, so that variance is unestimated, not measured to
    be zero. Nor can it support byte-identity of the model's output: the provider layer
    stores a reconstructed canonical string (see raw_response_is_reconstructed), so every
    valid row holds one of exactly two values by construction and the original text is gone.
    The completion-token spreads below record that four payloads were billed a differing
    token count; with the text discarded, a differing response and provider-side usage
    accounting are equally consistent with that, so the spreads are reported as an
    unresolved discrepancy and support neither reading.
    """
    rows = [r for r in all_records if r.get("experiment") == "stability"]
    payloads: dict[str, list[dict]] = {}
    for rec in rows:
        # group exactly as the runner's gate does: one payload per full prompt text
        ph = hashlib.sha256((rec.get("renderer_text") or "").encode()).hexdigest()
        payloads.setdefault(ph, []).append(rec)

    def spread(recs: list[dict], field: str) -> int | None:
        vals = [r.get(field) for r in recs if isinstance(r.get(field), int)]
        return (max(vals) - min(vals)) if len(vals) == len(recs) and vals else None

    agree = [k for k, v in payloads.items() if len({r.get("parsed_choice") for r in v}) == 1]
    completion_spreads = {k: spread(v, "completion_tokens") for k, v in payloads.items()}
    prompt_spreads = {k: spread(v, "prompt_tokens") for k, v in payloads.items()}
    nonzero_completion = sorted(s for s in completion_spreads.values() if s)
    all_parse = all(r.get("parsed_choice") in ("A", "B") for r in rows)

    try:
        assert_stability_gate(all_records)
        gate_pass, gate_error = True, None
    except Exception as exc:                      # RunnerError, or a missing prerequisite
        gate_pass, gate_error = False, f"{type(exc).__name__}: {exc}"

    return {
        "gate_pass": gate_pass,
        "gate_error": gate_error,
        "gate_implementation": "sprint.runner.assert_stability_gate (the same check the "
                               "runner applied before formal collection)",
        "n_rows": len(rows),
        "n_payloads": len(payloads),
        "repeats_per_payload": sorted({len(v) for v in payloads.values()}),
        "all_rows_parse_to_a_choice": all_parse,
        "n_payloads_with_identical_choice": len(agree),
        "raw_response_is_reconstructed": True,
        "distinct_raw_response_values": sorted({str(r.get("raw_response")) for r in rows}),
        "raw_response_note": "provider_qwen.complete_choice stores f'{\"choice\":\"<c>\"}', not "
                             "the provider's text. Response-text identity across repeats is "
                             "therefore NOT verifiable from this ledger.",
        "n_payloads_with_identical_completion_tokens": sum(
            1 for s in completion_spreads.values() if s == 0),
        "completion_token_spreads": sorted(s for s in completion_spreads.values() if s is not None),
        "max_completion_token_spread": max(nonzero_completion, default=0),
        "n_payloads_with_varying_completion_tokens": len(nonzero_completion),
        "completion_token_spread_note": "unresolved: the raw text is not retained, so a "
                                        "differing response and provider-side usage "
                                        "accounting are equally consistent with these "
                                        "spreads. This is not evidence of either.",
        "n_payloads_with_identical_prompt_tokens": sum(1 for s in prompt_spreads.values() if s == 0),
        "requested_models": sorted({str(r.get("requested_model")) for r in rows}),
        "returned_models": sorted({str(r.get("returned_model")) for r in rows}),
        "temperatures": sorted({r.get("temperature") for r in rows}),
        "decoding_flags": sorted({f"thinking={r.get('enable_thinking')},tools={r.get('tools')},"
                                  f"search={r.get('search')}" for r in rows}),
        "n_errors": sum(1 for r in rows if r.get("error_code")),
        "total_retries": sum(int(r.get("retry_count") or 0) for r in rows),
        "formal_conditions_with_repeats": 0,
        "within_condition_variance_estimated": False,
        "scope": "development probes at checkpoint 0; establishes repeat-stability of the "
                 "extracted choice for those payloads only. The 756 formal observations were "
                 "each collected once, so their within-condition variance is unestimated.",
    }


def _formal_fingerprint(all_records: list[dict], cfg: dict) -> str:
    """Digest of every formal quantity the paper reports, for isolation testing."""
    def stringify(obj):
        if isinstance(obj, dict):
            return {"|".join(map(str, k)) if isinstance(k, tuple) else str(k): stringify(v)
                    for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [stringify(v) for v in obj]
        return obj

    records = _formal_records(all_records)
    e_rows = [r for r in records if r.get("experiment") == "E"]
    n_rows = [r for r in records if r.get("experiment") == "N"]
    # Gates and missing-sensitivity are included so a leak into discordance, pair
    # completeness or invalid-JSON counts would move the fingerprint. Bootstrap
    # intervals are deterministic functions of the same formal CS cells, so they
    # move exactly when those cells move and are not recomputed here.
    payload = {
        "cs": stringify(cs_from_records(records)),
        "E": stringify(compute_e_effects(e_rows)),
        "N": stringify(compute_n_effects(n_rows, cfg)),
        "gate_E": stringify(_gate_e(records, cfg)),
        "gate_N": stringify(_gate_n(records, cfg)),
        "missing_sensitivity": stringify(missing_sensitivity(records, cfg)),
        "n_formal": len(records),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=repr).encode()).hexdigest()


def _dev_isolation_check(all_records: list[dict], cfg: dict) -> dict:
    """Demonstrate, rather than assert, that development rows reach no formal quantity.

    Every non-formal row is perturbed (its choice flipped) and then, separately, deleted
    outright; the full formal pipeline is recomputed each time. Flipping catches a value
    leak, deletion catches an aggregation leak. If any formal cell, estimand, interval or
    gate input depended on a development row, the fingerprint would move.
    """
    formal_ids = {id(r) for r in _formal_records(all_records)}
    before = _formal_fingerprint(all_records, cfg)
    perturbed, n_touched = [], 0
    for rec in all_records:
        if id(rec) in formal_ids:
            perturbed.append(rec)
            continue
        clone = dict(rec)
        clone["parsed_choice"] = {"A": "B", "B": "A"}.get(clone.get("parsed_choice"), "A")
        perturbed.append(clone)
        n_touched += 1
    after = _formal_fingerprint(perturbed, cfg)
    without = _formal_fingerprint([r for r in all_records if id(r) in formal_ids], cfg)
    return {
        "n_development_rows_perturbed": n_touched,
        "n_formal_rows_untouched": len(formal_ids),
        "formal_fingerprint_before": before,
        "formal_fingerprint_after_flip": after,
        "formal_fingerprint_without_dev_rows": without,
        "formal_output_unchanged": before == after == without,
        "covers": "all formal CS cells; both E and N estimand sets; both primary gate "
                  "objects (including discordance, pair completeness, invalid-JSON counts "
                  "and p-values); and missing-data sensitivity. Bootstrap intervals are "
                  "deterministic functions of the same CS cells and therefore move with them.",
    }


def d8_dev_probe_headroom(all_records: list[dict], formal_cs: dict, cfg: dict) -> dict:
    """Are probes with headroom reachable by the process that authored the formal set?

    Post-hoc exploratory diagnostic. It was not pre-registered; it was written after the
    formal ceiling was observed, and no gate, estimand or interval depends on it.

    The pre-formal E dry run applied the same affect/placebo contrast to three development
    probes disjoint from the formal set. This block answers one narrow existence question:
    the same authoring process did produce items that are not pinned at the ceiling.

    It does NOT explain why the formal fifteen saturated, and it does not generalize to
    forced-choice probing in general. Three items chosen for a dry run are not a sample of
    anything; a different formal set drawn by the same process could saturate again. Protocol
    line 927 forbids development data from standing in for formal results, and
    isolation_check demonstrates that these rows reach no formal quantity.
    """
    formal_ids = {id(r) for r in _formal_records(all_records)}
    dry = [r for r in all_records
           if id(r) not in formal_ids and r.get("experiment") == "E"]
    dev_cs = cs_from_records(dry)
    dev_values = [v for v in dev_cs.values() if v is not None]
    # like for like: the dry run mirrors Experiment E, so compare against formal E cells only
    formal_values = [v for key, v in formal_cs.items() if key[0] == "E" and v is not None]

    def census(values: list[float]) -> dict:
        return {"n_cells": len(values),
                "n_at_ceiling": sum(1 for v in values if v == 1.0),
                "n_at_floor": sum(1 for v in values if v == 0.0),
                "n_intermediate": sum(1 for v in values if v not in (0.0, 1.0)),
                "distinct_values": sorted({v for v in values})}

    per_probe: dict[str, dict] = {}
    for key, value in dev_cs.items():
        probe, block, cond = key[5], key[1], key[2]
        per_probe.setdefault(probe, {}).setdefault(block, {})[cond] = value
    return {
        "development": census(dev_values),
        "formal_E_for_contrast": census(formal_values),
        "dev_probe_ids": sorted(per_probe),
        "per_probe": per_probe,
        "isolation_check": _dev_isolation_check(all_records, cfg),
        "status": "post-hoc exploratory diagnostic",
        "pre_registered": False,
        "admissible_use": "existence only, and only as a post-hoc exploratory observation: "
                          "probes with headroom are reachable by the same authoring process "
                          "that produced the formal set",
        "inadmissible_uses": [
            "reporting this as a pre-registered or confirmatory result",
            "attributing the formal ceiling to probe selection rather than to the model, the "
            "renderer, or the forced-choice format",
            "any claim about forced-choice probing in general",
            "any statement about the size or sign of the affect contrast",
        ],
        "note": "Protocol 927 forbids development data from substituting for formal results. "
                "Three probes cannot establish an effect and are not used for one.",
    }


def build(*, raw_path: Path | None = None, write: bool = True) -> dict:
    raw_path = raw_path or RAW_PATH
    cfg = load_config()
    all_records = load_records(raw_path)
    records = _formal_records(all_records)
    cs = cs_from_records(records)
    effects = compute_e_effects([r for r in records if r.get("experiment") == "E"])
    n_effects = compute_n_effects([r for r in records if r.get("experiment") == "N"], cfg)
    d2 = d2_saturation_census(cs, effects)
    out = {
        "provenance": {
            "raw_sha256": sha256_file(raw_path) if raw_path.is_file() else None,
            "analysis_code_hash": analysis_code_hash(),
            "diagnostics_code_hash": _self_hash(),
            "formal_record_count": len(records),
            "ledger_record_count": len(all_records),
            "source": "tools/diagnostics.py (outside ANALYSIS_HASH_PATHS)",
        },
        "units": UNITS,
        "D1_e_response_surface": d1_e_response_surface(cs),
        "D2_saturation_census": d2,
        "D3_origin_split_slopes": d3_origin_split_slopes(cs, effects["theta_E"]),
        "D4_n_direction_decomposition": d4_n_direction_decomposition(cs, cfg, d2["saturated_probe_ids"]),
        "D5_n_normalized_sensitivity": d5_n_normalized_sensitivity(records, cs, cfg),
        "D6_pvalue_floor_census": d6_pvalue_floor_census(effects, n_effects, cfg),
        "D7_determinism_census": d7_determinism_census(all_records),
        "D8_dev_probe_headroom": d8_dev_probe_headroom(all_records, cs, cfg),
    }
    if write:
        REPORTS.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    build(write=True)
    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
