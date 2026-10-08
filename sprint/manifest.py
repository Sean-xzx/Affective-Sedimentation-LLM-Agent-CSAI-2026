from __future__ import annotations
import csv
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
import numpy as np
from sprint.histories import FROZEN_ACTION_MAP_SOURCE_HASH, compute_action_map_hash, derive_measure_seed_ids, full_history_manifest_sha256, load_action_map
from sprint.renderer import assert_renderer_d6, render_ab_ba_sections, renderer_template_hash
from sprint.schema import CONFIG_PATH, ROOT, dependency_lock_sha256, load_config, resolve_token_encoder, sha256_file
PROBES_PATH = ROOT / "materials" / "sprint_probes.csv"
PROTOCOL_PATH = ROOT / "affective-sedimentation-csai-2026-sprint-final.zh.md"
D6_INVENTORY_PATH = ROOT / "reports" / "renderer_d6_inventory.json"
SPRINT_MANIFEST_PATH = ROOT / "reports" / "sprint_manifest.json"
INJECTED_ENCODER_LOAD_ID = "injected_encoder"
REVIEW_PASS_MARKER = "dual_pass_ok"
REPLAY_PREFIX = "20260804|sprint-replay"
CALL_BUDGET_FIELDS = ("experiment_E_observations", "experiment_N_observations", "formal_observations_total", "development_completed_cap", "attempt_pause", "attempt_hard_stop")
PROBE_FIELDS = ("probe_id", "target_dimension", "scenario_family", "neutral_scenario", "high_option", "low_option", "semantic_key", "ab_rendering", "ba_rendering", "token_ids", "review_flags", "set")
_FILLED = PROBE_FIELDS[2:10]
_FORBIDDEN = re.compile(r"\b(PAD|valence|activation|personality|warm|cold|dominant|submissive|extravert|neurotic|affect|emotion|mood|trait)\b", re.IGNORECASE)
_PAD_AXIS = re.compile(r"(?:\bP/A/D\b|\b(?:P|D)\s+(?:axis|dimension|coordinate)\b|\bA\s+(?:axis|dimension|coordinate)\b|(?<![A-Za-z0-9])(?:P|A|D)\s*/\s*(?:P|A|D))", re.IGNORECASE)
_AWORDS = {a: tuple(a.split("_")) for a in (
    "praise", "criticize", "share_good_news", "share_bad_news", "disagree", "concede",
    "express_affection", "provoke", "condescend", "neutral_acknowledgment",
)}
EXPECTED_PROBE_IDS = tuple(
    f"{d}-{s}" for d in ("P", "A", "D") for s in ("D01", "D02", "C01", "C02", "C03", "C04", "C05")
)
@dataclass(frozen=True)
class ProbeRow:
    probe_id: str; target_dimension: str; scenario_family: str; neutral_scenario: str; high_option: str; low_option: str
    semantic_key: str; ab_rendering: str; ba_rendering: str; token_ids: str; review_flags: str; set: str
def _sha256_json(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
def protocol_hash(path: Path = PROTOCOL_PATH) -> str:
    return sha256_file(path)
def config_hash(path: Path = CONFIG_PATH) -> str:
    return sha256_file(path)
def call_budget_hash(cfg: dict[str, object]) -> str:
    return _sha256_json({k: cfg[k] for k in CALL_BUDGET_FIELDS})
def assert_history_seed_ids(cfg: dict[str, object]) -> None:
    if (expected := derive_measure_seed_ids()) != cfg["history_seed_ids"]: raise AssertionError(f"history_seed_ids {cfg['history_seed_ids']} != {expected}")
def _optional_file_hash(path: Path) -> str | None: return sha256_file(path) if path.is_file() else None
def _git_output(args: list[str]) -> str:
    try: return subprocess.run(args, capture_output=True, text=True, check=True, cwd=ROOT).stdout
    except (OSError, subprocess.CalledProcessError): return "unknown"
def load_probes(path: Path = PROBES_PATH) -> list[ProbeRow]:
    rows: list[ProbeRow] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise AssertionError("sprint_probes.csv missing header")
        if missing := [f for f in PROBE_FIELDS if f not in reader.fieldnames]:
            raise AssertionError(f"sprint_probes.csv missing columns: {missing}")
        for raw in reader:
            if not any(raw.get(f, "").strip() for f in PROBE_FIELDS):
                continue
            rows.append(ProbeRow(**{f: raw[f].strip() for f in PROBE_FIELDS}))
    return rows
def probe_subset_hash(probes: list[ProbeRow], subset: str) -> str:
    payload = sorted((asdict(r) for r in probes if r.set == subset), key=lambda item: item["probe_id"])
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()
def assert_token_balance(high_option: str, low_option: str, encode: Callable[[str], list[int]] | None = None) -> None:
    if not high_option.strip() or not low_option.strip():
        return
    enc = resolve_token_encoder(encode)
    hi, lo = enc(high_option), enc(low_option)
    diff = abs(len(hi) - len(lo))
    if diff > 3 or diff / max(len(hi), len(lo), 1) > 0.10:
        raise AssertionError(f"Token imbalance: high={len(hi)} low={len(lo)} diff={diff}")
def canonical_probe_token_ids(high_option: str, low_option: str, encode: Callable[[str], list[int]] | None = None) -> str:
    enc = resolve_token_encoder(encode)
    return json.dumps({"high": enc(high_option), "low": enc(low_option)}, separators=(",", ":"))
def sync_probe_derived_fields(row: ProbeRow, encode: Callable[[str], list[int]] | None = None) -> ProbeRow:
    payload = asdict(row)
    payload["ab_rendering"], payload["ba_rendering"] = render_ab_ba_sections(row.high_option, row.low_option)
    payload["token_ids"] = canonical_probe_token_ids(row.high_option, row.low_option, encode=encode)
    return ProbeRow(**payload)
def assert_probe_material_rules(row: ProbeRow, encode: Callable[[str], list[int]] | None = None) -> None:
    hi, lo = row.high_option.strip(), row.low_option.strip()
    if hi or lo:
        if missing := [f for f in _FILLED if not getattr(row, f).strip()]:
            raise AssertionError(f"{row.probe_id}: partial fill requires {missing}")
    for field in ("scenario_family", "neutral_scenario", "high_option", "low_option"):
        if not (text := getattr(row, field).strip()):
            continue
        pid = row.probe_id
        if _FORBIDDEN.search(text):
            raise AssertionError(f"{pid}: forbidden label in {field}")
        if _PAD_AXIS.search(text):
            raise AssertionError(f"{pid}: P/A/D axis label in {field}")
        lower = text.lower()
        for action, words in _AWORDS.items():
            leaked = (len(words) == 1 and re.search(rf"\b{re.escape(words[0])}\b", lower)) or (
                len(words) > 1 and (action in lower or all(re.search(rf"\b{re.escape(w)}\b", lower) for w in words))
            )
            if leaked:
                raise AssertionError(f"{pid}: action label leaked in {field}")
    if hi and lo:
        assert_token_balance(row.high_option, row.low_option, encode=encode)
        ab, ba = render_ab_ba_sections(row.high_option, row.low_option)
        enc = resolve_token_encoder(encode)
        canon = json.dumps({"high": enc(row.high_option), "low": enc(row.low_option)}, separators=(",", ":"))
        for field, expected in (("ab_rendering", ab), ("ba_rendering", ba), ("token_ids", canon)):
            if (got := getattr(row, field).strip()) and got != expected:
                raise AssertionError(f"{row.probe_id}: {field} mismatch")
def assert_probe_schema(probes: list[ProbeRow] | None = None, *, require_filled: bool = False, encode: Callable[[str], list[int]] | None = None) -> None:
    table = probes if probes is not None else load_probes()
    ids = [r.probe_id for r in table]
    if len(ids) != 21 or len(set(ids)) != 21 or set(ids) != set(EXPECTED_PROBE_IDS):
        raise AssertionError(f"Expected 21 unique probes, got {len(ids)}")
    dev, formal = {r.probe_id for r in table if r.set == "dev"}, {r.probe_id for r in table if r.set == "formal"}
    exp_dev = frozenset(f"{d}-{s}" for d in "PAD" for s in ("D01", "D02"))
    exp_formal = frozenset(f"{d}-C{i:02d}" for d in "PAD" for i in range(1, 6))
    if dev != exp_dev or formal != exp_formal or dev & formal:
        raise AssertionError("Dev/formal partition mismatch")
    for row in table:
        if row.target_dimension and row.target_dimension != row.probe_id.split("-", 1)[0]:
            raise AssertionError(f"{row.probe_id}: bad target_dimension")
        assert_probe_material_rules(row, encode=encode)
        if require_filled and (missing := [f for f in _FILLED if not getattr(row, f).strip()]):
            raise AssertionError(f"{row.probe_id}: unfilled fields {missing}")
def assert_probes_filled(probes: list[ProbeRow] | None = None, encode: Callable[[str], list[int]] | None = None) -> None:
    assert_probe_schema(probes, require_filled=True, encode=encode)
def assert_probes_reviewed(probes: list[ProbeRow] | None = None, encode: Callable[[str], list[int]] | None = None) -> None:
    assert_probes_filled(probes, encode=encode)
    for row in (probes if probes is not None else load_probes()):
        if REVIEW_PASS_MARKER not in row.review_flags:
            raise AssertionError(f"{row.probe_id}: missing review marker {REVIEW_PASS_MARKER!r}")
def derive_all_replay_probe_ids() -> dict[str, list[str]]:
    return {dim: [pid for _, pid in sorted((hashlib.sha256(f"{REPLAY_PREFIX}|{dim}|{pid}".encode()).digest(), pid) for pid in (f"{dim}-C{i:02d}" for i in range(1, 6)))[:3]] for dim in "PAD"}
def replay_selection_hash(replay: dict[str, list[str]] | None = None) -> str:
    return _sha256_json(replay if replay is not None else derive_all_replay_probe_ids())
def assert_replay_derivation() -> None:
    exp = {"P": ["P-C01", "P-C05", "P-C02"], "A": ["A-C04", "A-C03", "A-C02"], "D": ["D-C05", "D-C04", "D-C03"]}
    if (got := derive_all_replay_probe_ids()) != exp:
        raise AssertionError(f"Replay probe derivation mismatch: {got}")
def _d6_text(inv: list[dict[str, object]], cfg: dict[str, object], *, frozen: bool) -> str:
    meta = ({"tokenizer": cfg["tokenizer"], "tokenizer_load_id": cfg["tokenizer_load_id"]} if frozen
            else {"tokenizer": INJECTED_ENCODER_LOAD_ID, "tokenizer_load_id": INJECTED_ENCODER_LOAD_ID})
    return json.dumps({**meta, "records": inv}, separators=(",", ":"), sort_keys=True)
def _assert_frozen_d6_file(computed_hash: str) -> None:
    if not D6_INVENTORY_PATH.is_file():
        raise AssertionError("frozen D6 inventory file missing")
    if computed_hash != hashlib.sha256(D6_INVENTORY_PATH.read_bytes()).hexdigest():
        raise AssertionError("D6 inventory hash mismatch with frozen file")
def build_material_manifest(config: dict | None = None, encode: Callable[[str], list[int]] | None = None, inventory_path: Path | None = None, probes: list[ProbeRow] | None = None, persist_d6: bool = True) -> dict[str, object]:
    cfg, probe_table, replay = config or load_config(), probes or load_probes(), derive_all_replay_probe_ids()
    assert_history_seed_ids(cfg)
    inv = assert_renderer_d6(encode=resolve_token_encoder(encode))
    frozen = encode is None
    d6_text = _d6_text(inv, cfg, frozen=frozen)
    doc, inv_hash = json.loads(d6_text), hashlib.sha256(d6_text.encode()).hexdigest()
    if inventory_path is not None:
        if not frozen and inventory_path.resolve() == D6_INVENTORY_PATH.resolve():
            raise ValueError("injected encoder cannot write to frozen D6 inventory path")
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(d6_text, encoding="utf-8")
    elif frozen and persist_d6:
        D6_INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        D6_INVENTORY_PATH.write_text(d6_text, encoding="utf-8")
    elif frozen:
        _assert_frozen_d6_file(inv_hash)
    return {
        "formal_probe_hash": probe_subset_hash(probe_table, "formal"), "dev_probe_hash": probe_subset_hash(probe_table, "dev"),
        "replay_probe_ids": replay, "replay_selection_hash": replay_selection_hash(replay), "renderer_hash": renderer_template_hash("affect"),
        "placebo_hash": renderer_template_hash("placebo"), "renderer_d6_inventory": doc, "renderer_d6_inventory_hash": inv_hash,
        "d6_inventory_frozen": frozen, "tokenizer": cfg["tokenizer"], "tokenizer_load_id": cfg["tokenizer_load_id"], "tokenizer_agent_model": cfg["agent_model"],
    }
def build_sprint_manifest(*, config: dict | None = None, probes: list[ProbeRow] | None = None, encode: Callable[[str], list[int]] | None = None, manifest_path: Path | None = None, freeze_utc: str | None = None, write: bool = True) -> dict[str, object]:
    if encode is not None:
        raise ValueError("sprint manifest requires frozen D6 inventory (encode must be None)")
    cfg = config or load_config()
    assert_history_seed_ids(cfg)
    probe_table = probes if probes is not None else load_probes()
    assert_probes_reviewed(probe_table, encode=encode)
    material = build_material_manifest(config=cfg, encode=None, probes=probe_table, persist_d6=False)
    if not material["d6_inventory_frozen"]:
        raise ValueError("sprint manifest requires d6_inventory_frozen")
    replay = derive_all_replay_probe_ids()
    assert_replay_derivation()
    if replay != material["replay_probe_ids"]:
        raise AssertionError("replay_probe_ids mismatch between sprint and material manifests")
    manifest: dict[str, object] = {
        "protocol_hash": protocol_hash(), "config_hash": config_hash(), "source_commit": _git_output(["git", "rev-parse", "HEAD"]).strip(),
        "worktree_status": _git_output(["git", "status", "--porcelain"]), "dependency_lock_hash": dependency_lock_sha256(),
        "python_version": sys.version.split()[0], "numpy_version": np.__version__, "occ_pad_hash": FROZEN_ACTION_MAP_SOURCE_HASH,
        "action_map_hash": compute_action_map_hash(load_action_map()), "history_manifest_hash": full_history_manifest_sha256(),
        "formal_probe_hash": material["formal_probe_hash"], "dev_probe_hash": material["dev_probe_hash"], "replay_probe_ids": replay,
        "replay_selection_hash": replay_selection_hash(replay), "renderer_hash": material["renderer_hash"], "placebo_hash": material["placebo_hash"],
        "renderer_d6_inventory_hash": material["renderer_d6_inventory_hash"], "randomization_manifest_hash": _optional_file_hash(ROOT / "reports" / "randomization_manifest.json"),
        "analysis_code_hash": _optional_file_hash(ROOT / "sprint" / "analysis.py"), "requested_model": cfg["agent_model"], "provider_region": cfg["provider_region"],
        "tokenizer": cfg["tokenizer"], "tokenizer_load_id": cfg["tokenizer_load_id"], "enable_thinking": cfg["enable_thinking"],
        "call_budget_hash": call_budget_hash(cfg), "freeze_utc": freeze_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if write:
        target = manifest_path or SPRINT_MANIFEST_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    return manifest
