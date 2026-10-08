from __future__ import annotations
import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
import numpy as np
from scipy.optimize import linprog
from sprint.dynamics import ControllerState, run_sequence
from sprint.schema import ACTION_MAP_PATH, ENDPOINT_RAW_S, ENDPOINT_Z_UNROUNDED, KAPPA_200, TARGET_OF, dynamics_params, signed_z
EXPECTED_LISTENER_VECTORS = {
    "praise": (+0.320, +0.240, -0.192), "criticize": (-0.270, +0.090, -0.540),
    "share_good_news": (+0.320, -0.160, -0.160), "share_bad_news": (-0.320, -0.160, -0.400),
    "disagree": (-0.180, -0.240, -0.240), "concede": (+0.360, -0.180, +0.240),
    "express_affection": (+0.210, +0.070, +0.140), "provoke": (-0.408, +0.472, +0.200),
    "condescend": (-0.210, -0.070, +0.280), "neutral_acknowledgment": (0.0, 0.0, 0.0),
}
HISTORY_COUNTS: dict[str, dict[str, int]] = {
    "ZERO": {"neutral_acknowledgment": 200},
    "P-": {"share_bad_news": 78, "provoke": 39, "condescend": 83},
    "P+": {"praise": 84, "share_good_news": 29, "concede": 87},
    "A-": {"disagree": 103, "concede": 68, "condescend": 29},
    "A+": {"praise": 100, "express_affection": 14, "provoke": 86},
    "D-": {"praise": 12, "criticize": 109, "share_good_news": 79},
    "D+": {"concede": 89, "provoke": 44, "condescend": 67},
}
N_BLOCKS, BLOCK_SIZE = 10, 20
FROZEN_ACTION_MAP_SOURCE_HASH = "ed00da0e3ceb6bc2436539621fe91d9b87390bed11303eb818f2566277be6fcf"
_AXIS = {"P": 0, "A": 1, "D": 2}
@dataclass(frozen=True)
class ActionRow:
    action: str; listener_label: str; intensity: float; pad: np.ndarray; source_page: str; source_hash: str
    @property
    def listener_vector(self) -> np.ndarray: return self.pad * self.intensity
def compute_action_map_hash(rows: list[ActionRow]) -> str:
    payload = [{"action": r.action, "listener_label": r.listener_label, "intensity": f"{r.intensity:.12f}",
                "pad": [f"{x:.12f}" for x in r.pad.tolist()], "source_page": r.source_page} for r in rows]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
def load_action_map(path=ACTION_MAP_PATH) -> list[ActionRow]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [ActionRow(
            action=raw["action"], listener_label=raw["listener_label"], intensity=float(raw["intensity"]),
            pad=np.array([float(raw["pad_P"]), float(raw["pad_A"]), float(raw["pad_D"])]),
            source_page=raw["source_page"], source_hash=raw["source_hash"],
        ) for raw in csv.DictReader(handle)]
    if [r.action for r in rows] != list(EXPECTED_LISTENER_VECTORS):
        raise AssertionError(f"Action map row order must match freeze table: {[r.action for r in rows]}")
    return rows
def action_index(rows: list[ActionRow] | None = None) -> dict[str, ActionRow]:
    return {row.action: row for row in (rows or load_action_map())}
def assert_listener_vectors(rows: list[ActionRow] | None = None) -> None:
    for row in rows or load_action_map():
        expected = np.asarray(EXPECTED_LISTENER_VECTORS[row.action], dtype=np.float64)
        if np.max(np.abs(row.listener_vector - expected)) >= 1e-12:
            raise AssertionError(f"{row.action}: listener_vector {row.listener_vector} != {expected}")
def assert_action_map_sealed() -> None:
    rows = load_action_map()
    digest = compute_action_map_hash(rows)
    if digest != FROZEN_ACTION_MAP_SOURCE_HASH:
        raise AssertionError(f"Action map hash {digest} != {FROZEN_ACTION_MAP_SOURCE_HASH}")
    for row in rows:
        if row.source_hash != FROZEN_ACTION_MAP_SOURCE_HASH:
            raise AssertionError(f"{row.action}: source_hash {row.source_hash} != frozen hash")
    assert_listener_vectors(rows)
def block_subseed(master_seed: int, history_seed: int, block: int) -> int:
    material = f"{master_seed}|{history_seed}|{block}".encode("ascii")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], byteorder="big", signed=False)
def derive_measure_seed_ids() -> list[int]:
    return [sid for _, sid in sorted(
        (hashlib.sha256(f"20260804|measure|{sid}".encode()).digest(), sid) for sid in range(30)
    )[:8]]
def _finish_lrm_remainder(need: int, remainder_order: list[str], out: dict[str, int], remaining: dict[str, int], block_id: int, block_size: int) -> None:
    if need <= 0:
        return
    if not remainder_order:
        raise AssertionError(f"LRM remainder allocation impossible for block {block_id}: no actions with remaining quota")
    idx, n_actions = 0, len(remainder_order)
    while need > 0:
        action = remainder_order[idx % n_actions]
        if out[action] < remaining[action]:
            out[action] += 1
            need -= 1
        idx += 1
        if idx > n_actions * block_size:
            raise AssertionError(f"LRM allocation stuck block {block_id}")
def distribute_counts_across_blocks(total_counts: dict[str, int], action_order: list[str], n_blocks: int = N_BLOCKS, block_size: int = BLOCK_SIZE) -> list[dict[str, int]]:
    remaining = {a: total_counts[a] for a in action_order if a in total_counts}
    if sum(remaining.values()) != n_blocks * block_size:
        raise AssertionError("History totals must equal n_blocks * block_size")
    blocks: list[dict[str, int]] = []
    for block_id in range(n_blocks):
        blocks_left, total_rem = n_blocks - block_id, sum(remaining.values())
        if total_rem != block_size * blocks_left:
            raise AssertionError(f"Remaining total {total_rem} != {block_size * blocks_left}")
        present = [a for a in action_order if remaining.get(a, 0) > 0]
        raw = {a: block_size * remaining[a] / total_rem for a in present}
        floors = {a: min(int(np.floor(raw[a])), remaining[a]) for a in present}
        need = block_size - sum(floors.values())
        remainder_order = sorted(present, key=lambda a: (-(raw[a] - np.floor(raw[a])), action_order.index(a)))
        out = dict(floors)
        _finish_lrm_remainder(need, remainder_order, out, remaining, block_id, block_size)
        if sum(out.values()) != block_size:
            raise AssertionError("Block allocation does not sum to block_size")
        for action, count in out.items():
            remaining[action] -= count
            if remaining[action] < 0:
                raise AssertionError("Negative remaining count")
        blocks.append(out)
    if any(v != 0 for v in remaining.values()):
        raise AssertionError(f"Leftover counts after allocation: {remaining}")
    return blocks
def build_history_actions(condition: str, history_seed: int, master_seed: int | None = None, rows: list[ActionRow] | None = None) -> list[str]:
    action_order = [r.action for r in (rows or load_action_map())]
    ms = dynamics_params().master_seed if master_seed is None else master_seed
    actions: list[str] = []
    for block_id, counts in enumerate(distribute_counts_across_blocks(HISTORY_COUNTS[condition], action_order)):
        multiset = [a for a in action_order for _ in range(counts.get(a, 0))]
        if len(multiset) != BLOCK_SIZE:
            raise AssertionError("Block multiset size mismatch")
        rng = np.random.Generator(np.random.PCG64(block_subseed(ms, history_seed, block_id)))
        rng.shuffle(multiset)
        actions.extend(multiset)
    if len(actions) != 200:
        raise AssertionError(f"History length {len(actions)} != 200")
    got = Counter(actions)
    for action, count in HISTORY_COUNTS[condition].items():
        if got[action] != count:
            raise AssertionError(f"{condition} seed={history_seed}: {action} count {got[action]} != {count}")
    return actions
def run_history(condition: str, history_seed: int, master_seed: int | None = None, rows: list[ActionRow] | None = None) -> tuple[list[str], ControllerState]:
    actions = build_history_actions(condition, history_seed, master_seed=master_seed, rows=rows)
    final, _ = run_sequence(np.vstack([action_index(rows)[a].listener_vector for a in actions]))
    return actions, final
def _history_entry(condition: str, history_seed: int) -> dict:
    actions, final = run_history(condition, history_seed)
    return {"condition": condition, "history_seed": history_seed, "actions": actions,
            "s_200": [f"{x:.12f}" for x in final.s.tolist()]}
def _hist_sha(entry: dict) -> str:
    return hashlib.sha256(json.dumps(entry, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
def history_manifest_sha256(condition: str = "P+", history_seed: int = 0) -> str:
    return _hist_sha(_history_entry(condition, history_seed))
def full_history_manifest_sha256(seed_ids: list[int] | None = None, conditions: list[str] | None = None) -> str:
    seeds = seed_ids if seed_ids is not None else list(range(30))
    conds = conditions if conditions is not None else sorted(HISTORY_COUNTS)
    return _hist_sha({"histories": [_history_entry(c, s) for c in conds for s in seeds]})
def lp_endpoint_residual(raw_s: np.ndarray, rows: list[ActionRow] | None = None) -> float:
    vectors = np.vstack([r.listener_vector for r in (rows or load_action_map())]).T
    mu, k = np.asarray(raw_s, dtype=np.float64) / KAPPA_200, vectors.shape[1]
    c = np.concatenate([np.zeros(k), np.ones(3), np.ones(3)])
    a_eq = np.zeros((4, k + 6))
    a_eq[0:3, 0:k], a_eq[0:3, k:k + 3], a_eq[0:3, k + 3:k + 6] = vectors, np.eye(3), -np.eye(3)
    a_eq[3, 0:k] = 1.0
    result = linprog(c, A_eq=a_eq, b_eq=np.concatenate([mu, [1.0]]),
                     bounds=[(0.0, None)] * (k + 6), method="highs")
    if not result.success:
        raise RuntimeError(f"Endpoint LP failed: {result.message}")
    return float(np.sum(result.x[k:k + 6]))
def assert_endpoints_reachable(rows: list[ActionRow] | None = None) -> None:
    table = rows or load_action_map()
    for name, raw in ENDPOINT_RAW_S.items():
        if name == "ORIGIN":
            continue
        if lp_endpoint_residual(raw, rows=table) >= 1e-10:
            raise AssertionError(f"{name} LP residual >= 1e-10")
        z, dim = signed_z(raw), TARGET_OF[name]
        if abs(float(z[_AXIS[dim]]) - ENDPOINT_Z_UNROUNDED[name]) >= 5e-7:
            raise AssertionError(f"{name} unrounded z {z[_AXIS[dim]]} != {ENDPOINT_Z_UNROUNDED[name]}")
        for axis, j in zip(("P", "A", "D"), range(3)):
            if axis != dim and abs(raw[j]) > 0.0:
                raise AssertionError(f"{name} off-axis raw s not zero")
