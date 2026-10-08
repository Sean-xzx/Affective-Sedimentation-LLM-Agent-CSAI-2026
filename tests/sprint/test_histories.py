"""Gates D2–D5 for discrete histories and appraisal mapping."""

from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

EXPECTED_A_BAR = {
    "ZERO": (0.0, 0.0, 0.0), "P-": (-0.291510, +0.000590, -0.000800),
    "P+": (+0.337400, -0.000700, +0.000560), "A-": (-0.000750, -0.194950, -0.001400),
    "A+": (-0.000740, +0.327860, -0.000200), "D-": (-0.001550, +0.000250, -0.369020),
    "D+": (+0.000090, +0.000290, +0.244600),
}
FORMAL_HISTORY_SEED_IDS = [14, 24, 5, 18, 22, 13, 1, 26]
DEV_HISTORY_SEED = 1000
RETENTION_BAND = (0.745779, 0.754021)
NEAR_AXIS_MAX = 0.015
GOLDEN_HISTORY_MANIFEST_SHA256 = "52d8e0eea4c20fb22968cbc675d3e65498530d23f72ac248ad1f69307c1f9467"
GOLDEN_FULL_HISTORY_MANIFEST_SHA256 = "b75fe612d978c5e2f647ce037b04087bf7ea6fbdc3d6ca7ff2e074117a5c94f5"
DEPENDENCY_LOCK_SHA256 = "c902457b38b3fc7ff010108cd4e0a12d3e0d6eebde80055453467c2ed00950ac"

from sprint.dynamics import append_true_zero, retention_ratio
from sprint.histories import (
    FROZEN_ACTION_MAP_SOURCE_HASH,
    HISTORY_COUNTS,
    assert_action_map_sealed,
    assert_endpoints_reachable,
    assert_listener_vectors,
    action_index,
    block_subseed,
    compute_action_map_hash,
    derive_measure_seed_ids,
    distribute_counts_across_blocks,
    full_history_manifest_sha256,
    history_manifest_sha256,
    load_action_map,
    run_history,
    _finish_lrm_remainder,
)
from sprint.schema import TARGET_OF, dependency_lock_sha256, dynamics_params, load_config, signed_z


def mean_appraisal(condition: str, rows=None):
    from sprint.histories import HISTORY_COUNTS, action_index
    table, counts = action_index(rows), HISTORY_COUNTS[condition]
    if (total := sum(counts.values())) != 200:
        raise AssertionError(f"{condition} counts sum to {total}, expected 200")
    return sum(count * table[a].listener_vector for a, count in counts.items()) / total


def max_off_axis_z(condition: str, state):
    z = signed_z(state.s)
    if condition == "ZERO":
        return float(np.max(np.abs(z)))
    target = TARGET_OF[condition]
    axis_map = {"P": 0, "A": 1, "D": 2}
    return float(np.max(np.abs([z[j] for axis, j in axis_map.items() if axis != target])))


def run_full_matrix(seed_ids=None, conditions=None):
    from sprint.histories import HISTORY_COUNTS, run_history
    seeds = seed_ids if seed_ids is not None else list(range(30))
    conds = conditions or list(HISTORY_COUNTS)
    return {(c, s): run_history(c, s)[1] for c in conds for s in seeds}


def test_listener_vectors_from_pad_d3():
    assert_listener_vectors()


def test_action_map_sealed():
    assert_action_map_sealed()


def test_action_map_source_hash_frozen():
    rows = load_action_map()
    digest = compute_action_map_hash(rows)
    assert digest == FROZEN_ACTION_MAP_SOURCE_HASH
    assert all(row.source_hash == FROZEN_ACTION_MAP_SOURCE_HASH for row in rows)


def test_dependency_lock_hash_d3():
    assert dependency_lock_sha256() == DEPENDENCY_LOCK_SHA256


def test_block_subseed_encoding():
    assert f"{20260804}|{0}|{0}".encode("ascii") == b"20260804|0|0"
    assert block_subseed(20260804, 0, 0) == 7939102487417877292


def test_measure_seed_derivation_d3():
    expected = [14, 24, 5, 18, 22, 13, 1, 26]
    assert derive_measure_seed_ids() == expected
    assert derive_measure_seed_ids() == FORMAL_HISTORY_SEED_IDS
    assert DEV_HISTORY_SEED == 1000
    assert DEV_HISTORY_SEED not in FORMAL_HISTORY_SEED_IDS


def test_config_history_seed_ids_match_derivation():
    cfg = load_config()
    expected = [14, 24, 5, 18, 22, 13, 1, 26]
    assert cfg["history_seed_ids"] == expected
    assert cfg["history_seed_ids"] == derive_measure_seed_ids()
    assert DEV_HISTORY_SEED == 1000
    assert DEV_HISTORY_SEED not in cfg["history_seed_ids"]


def test_config_api_frozen_fields():
    """§3.7 API freeze fields must load with protocol literals (tools/search as str)."""
    cfg = load_config()
    assert cfg["agent_model"] == "qwen3.7-flash-2026-07-15"
    assert cfg["temperature"] == 0
    assert cfg["top_p"] == 1
    assert cfg["max_tokens"] == 16
    assert cfg["request_seed"] is None
    assert cfg["enable_thinking"] is False
    assert cfg["tools"] == "off"
    assert isinstance(cfg["tools"], str)
    assert cfg["search"] == "off"
    assert isinstance(cfg["search"], str)
    assert cfg["response_format"] == {"type": "json_object"}
    assert cfg["tokenizer"] == "qwen3.7-flash-2026-07-15"
    assert cfg["tokenizer_load_id"] == "Qwen/Qwen3-0.6B"
    assert cfg["agent_model"] == "qwen3.7-flash-2026-07-15"
    assert cfg["max_workers"] == 6
    assert cfg["timeout_seconds"] == 30
    assert cfg["max_retries"] == 3


def test_config_provider_region():
    cfg = load_config()
    assert isinstance(cfg["provider_region"], str)
    assert cfg["provider_region"].strip() != ""


def test_mean_appraisal_matches_protocol():
    for condition, expected in EXPECTED_A_BAR.items():
        got = mean_appraisal(condition)
        assert np.allclose(got, np.asarray(expected), atol=1e-12, rtol=0.0), (
            condition,
            got,
            expected,
        )


def test_endpoints_lp_d2():
    assert_endpoints_reachable()


def test_history_counts_and_length():
    params = dynamics_params()
    for condition in HISTORY_COUNTS:
        actions, final = run_history(condition, history_seed=0)
        assert len(actions) == params.T
        assert Counter(actions) == Counter(HISTORY_COUNTS[condition])
        assert np.isfinite(final.s).all()


def test_formal_seeds_and_matrix_d3_d4():
    assert derive_measure_seed_ids() == FORMAL_HISTORY_SEED_IDS
    matrix = run_full_matrix(seed_ids=list(range(30)))
    assert len(matrix) == 30 * 7
    for (condition, seed), state in matrix.items():
        off = max_off_axis_z(condition, state)
        assert off <= NEAR_AXIS_MAX + 1e-15, (condition, seed, off)


def test_retention_d5_all_nonzero_seeds():
    for condition in HISTORY_COUNTS:
        if condition == "ZERO":
            continue
        for seed in range(30):
            _, state = run_history(condition, seed)
            after = append_true_zero(state, n=100, start_t=200)
            ratio = retention_ratio(state, after)
            assert RETENTION_BAND[0] <= ratio <= RETENTION_BAND[1], (
                condition,
                seed,
                ratio,
            )


def test_golden_history_manifest_hash():
    digest = history_manifest_sha256(condition="P+", history_seed=0)
    assert digest == GOLDEN_HISTORY_MANIFEST_SHA256, digest


def test_full_history_manifest_hash_d3():
    digest = full_history_manifest_sha256()
    assert digest == GOLDEN_FULL_HISTORY_MANIFEST_SHA256, digest


GOLDEN_BLOCK_COUNTS = {
    "ZERO": [{"neutral_acknowledgment": 20}] * 10,
    "P-": [
        {"share_bad_news": 8, "provoke": 4, "condescend": 8},
        {"share_bad_news": 8, "provoke": 4, "condescend": 8},
        {"share_bad_news": 8, "provoke": 4, "condescend": 8},
        {"share_bad_news": 8, "provoke": 4, "condescend": 8},
        {"share_bad_news": 8, "provoke": 4, "condescend": 8},
        {"share_bad_news": 8, "provoke": 4, "condescend": 8},
        {"share_bad_news": 7, "provoke": 4, "condescend": 9},
        {"share_bad_news": 8, "provoke": 4, "condescend": 8},
        {"share_bad_news": 8, "provoke": 3, "condescend": 9},
        {"share_bad_news": 7, "provoke": 4, "condescend": 9},
    ],
    "P+": [
        {"praise": 8, "share_good_news": 3, "concede": 9},
        {"praise": 8, "share_good_news": 3, "concede": 9},
        {"praise": 8, "share_good_news": 3, "concede": 9},
        {"praise": 9, "share_good_news": 3, "concede": 8},
        {"praise": 8, "share_good_news": 3, "concede": 9},
        {"praise": 9, "share_good_news": 3, "concede": 8},
        {"praise": 8, "share_good_news": 3, "concede": 9},
        {"praise": 9, "share_good_news": 3, "concede": 8},
        {"praise": 9, "share_good_news": 2, "concede": 9},
        {"praise": 8, "share_good_news": 3, "concede": 9},
    ],
    "A-": [
        {"disagree": 10, "concede": 7, "condescend": 3},
        {"disagree": 10, "concede": 7, "condescend": 3},
        {"disagree": 10, "concede": 7, "condescend": 3},
        {"disagree": 10, "concede": 7, "condescend": 3},
        {"disagree": 10, "concede": 7, "condescend": 3},
        {"disagree": 11, "concede": 6, "condescend": 3},
        {"disagree": 10, "concede": 7, "condescend": 3},
        {"disagree": 10, "concede": 7, "condescend": 3},
        {"disagree": 11, "concede": 7, "condescend": 2},
        {"disagree": 11, "concede": 6, "condescend": 3},
    ],
    "A+": [
        {"praise": 10, "express_affection": 1, "provoke": 9},
        {"praise": 10, "express_affection": 1, "provoke": 9},
        {"praise": 10, "express_affection": 2, "provoke": 8},
        {"praise": 10, "express_affection": 1, "provoke": 9},
        {"praise": 10, "express_affection": 2, "provoke": 8},
        {"praise": 10, "express_affection": 1, "provoke": 9},
        {"praise": 10, "express_affection": 2, "provoke": 8},
        {"praise": 10, "express_affection": 1, "provoke": 9},
        {"praise": 10, "express_affection": 2, "provoke": 8},
        {"praise": 10, "express_affection": 1, "provoke": 9},
    ],
    "D-": [
        {"praise": 1, "criticize": 11, "share_good_news": 8},
        {"praise": 1, "criticize": 11, "share_good_news": 8},
        {"praise": 1, "criticize": 11, "share_good_news": 8},
        {"praise": 1, "criticize": 11, "share_good_news": 8},
        {"praise": 1, "criticize": 11, "share_good_news": 8},
        {"praise": 1, "criticize": 11, "share_good_news": 8},
        {"praise": 1, "criticize": 11, "share_good_news": 8},
        {"praise": 2, "criticize": 10, "share_good_news": 8},
        {"praise": 2, "criticize": 11, "share_good_news": 7},
        {"praise": 1, "criticize": 11, "share_good_news": 8},
    ],
    "D+": [
        {"concede": 9, "provoke": 4, "condescend": 7},
        {"concede": 9, "provoke": 4, "condescend": 7},
        {"concede": 9, "provoke": 4, "condescend": 7},
        {"concede": 9, "provoke": 5, "condescend": 6},
        {"concede": 9, "provoke": 4, "condescend": 7},
        {"concede": 9, "provoke": 5, "condescend": 6},
        {"concede": 9, "provoke": 4, "condescend": 7},
        {"concede": 8, "provoke": 5, "condescend": 7},
        {"concede": 9, "provoke": 5, "condescend": 6},
        {"concede": 9, "provoke": 4, "condescend": 7},
    ],
}


def test_distribute_counts_block_snapshot():
    action_order = [row.action for row in load_action_map()]
    for condition, expected_blocks in GOLDEN_BLOCK_COUNTS.items():
        got = distribute_counts_across_blocks(
            HISTORY_COUNTS[condition],
            action_order,
        )
        assert got == expected_blocks, condition


def test_distribute_counts_empty_remainder_order_raises():
    with pytest.raises(AssertionError, match="no actions with remaining quota"):
        _finish_lrm_remainder(
            need=3,
            remainder_order=[],
            out={},
            remaining={},
            block_id=0,
            block_size=20,
        )
