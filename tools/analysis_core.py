from __future__ import annotations
import hashlib, json, math, sys
from pathlib import Path
from typing import Iterable
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from sprint.manifest import derive_all_replay_probe_ids
from sprint.runner import interleave_formal_schedules, load_records, obs_key
from sprint.schema import ENDPOINT_Z_RENDERED, load_config, sha256_file
from tools.rand_manifest import MANIFEST_PATH, RAW_PATH, blind_integrity_qc, build_randomization_manifest
ANALYSIS_PATH = ROOT / "sprint" / "analysis.py"
ANALYSIS_HASH_PATHS = tuple(sorted([
    ROOT / "sprint" / "analysis.py",
    ROOT / "tools" / "analysis_core.py",
    ROOT / "tools" / "rand_manifest.py",
], key=lambda p: p.as_posix()))
REPORTS = ROOT / "reports"
DERIVED = ROOT / "data" / "derived"
DIMS = ("P", "A", "D")
POS = {"P": "P+", "A": "A+", "D": "D+"}
NEG = {"P": "P-", "A": "A-", "D": "D-"}
DIR_SIGN = {"P+": 1, "A+": 1, "D+": 1, "P-": -1, "A-": -1, "D-": -1}
RENDERED_Z = {k: float(v.replace("+", "")) for k, v in ENDPOINT_Z_RENDERED.items()}
FORMAL_PROBES = tuple(f"{d}-C{i:02d}" for d in DIMS for i in range(1, 6))
INVALID_JSON_CODES = frozenset({"invalid_choice_json", "invalid_response_schema"})
TRANSPORT_ERROR_CODES = frozenset({"transport_error", "transport_exhausted", "timeout", "rate_limit"})
def analysis_code_hash() -> str:
    h = hashlib.sha256()
    for path in ANALYSIS_HASH_PATHS:
        if path.is_file():
            h.update(path.read_bytes())
    return h.hexdigest()
def decode_manifest(manifest: dict) -> dict[tuple, dict]:
    inv = {v: k for k, v in manifest["block_codes"].items()}
    inv.update({v: k for k, v in manifest["condition_codes"].items()})
    inv.update({v: k for k, v in manifest["cell_codes"].items()})
    return {(e["experiment"], inv[e["block_code"]], inv[e["condition_code"]], int(e["history_seed"]),
             int(e["checkpoint"]), e["probe_id"], inv[e["cell_code"]]): e for e in manifest["schedule"]}
def semantic_y(rec: dict) -> int:
    return 1 if (rec["option_order"] == "AB") == (rec["parsed_choice"] == "A") else 0
def choice_score(y_ab: float, y_ba: float) -> float:
    return (y_ab + y_ba) / 2.0
def _base_key(rec: dict) -> tuple:
    k = obs_key(rec); return k[:-2] + (k[-1],)
def _final_records_by_obs(records: Iterable[dict]) -> dict[tuple, dict]:
    finals: dict[tuple, dict] = {}
    for rec in records:
        k = obs_key(rec)
        att = int(rec.get("request_attempt") or 0)
        if k not in finals or att >= int(finals[k].get("request_attempt") or 0):
            finals[k] = rec
    return finals
def _invalid_json_final_count(records: Iterable[dict], experiment: str) -> int:
    finals = _final_records_by_obs(records)
    return sum(
        1 for k, rec in finals.items()
        if k[0] == experiment and (
            rec.get("error_code") in INVALID_JSON_CODES
            or (rec.get("error_code") and rec.get("error_code") not in TRANSPORT_ERROR_CODES
                and rec.get("parsed_choice") not in ("A", "B"))
        )
    )
def _n_item_unit_complete(pairs: dict[tuple, dict[str, dict]], direction: str, seed: int, probe: str) -> bool:
    for cell in ("full", "zero"):
        orders = pairs.get(("N", "affect", direction, seed, 200, probe, cell))
        if not orders or "AB" not in orders or "BA" not in orders:
            return False
    return True
def _n_direction_and_seed_checks(records: Iterable[dict], cfg: dict) -> dict:
    pairs = _pair_map(records)
    replay = derive_all_replay_probe_ids()
    seeds = list(cfg["history_seed_ids"])
    per_direction: dict[str, int] = {}
    seed_direction_min = math.inf
    for direction in DIR_SIGN:
        complete = sum(
            1 for seed in seeds for probe in replay[direction[0]]
            if _n_item_unit_complete(pairs, direction, seed, probe)
        )
        per_direction[direction] = complete
    for seed in seeds:
        for direction in DIR_SIGN:
            dim = direction[0]
            cnt = sum(1 for probe in replay[dim] if _n_item_unit_complete(pairs, direction, seed, probe))
            seed_direction_min = min(seed_direction_min, cnt)
    direction_missing = {d: 24 - per_direction[d] for d in DIR_SIGN}
    return {
        "direction_complete": per_direction,
        "direction_missing": direction_missing,
        "direction_pair_pass": all(m <= 2 for m in direction_missing.values()),
        "seed_direction_min_items": 0 if seed_direction_min is math.inf else int(seed_direction_min),
        "seed_direction_pass": seed_direction_min >= 2 if seed_direction_min is not math.inf else False,
    }
def _pair_map(records: Iterable[dict]) -> dict[tuple, dict[str, dict]]:
    out: dict[tuple, dict[str, dict]] = {}
    for rec in records:
        if rec.get("parsed_choice") not in ("A", "B") or rec.get("error_code"):
            continue
        out.setdefault(_base_key(rec), {})[rec["option_order"]] = rec
    return out
def cs_from_records(records: Iterable[dict], *, sensitivity: str = "complete") -> dict[tuple, float | None]:
    scores: dict[tuple, float | None] = {}
    for base, orders in _pair_map(records).items():
        if "AB" in orders and "BA" in orders:
            scores[base] = choice_score(semantic_y(orders["AB"]), semantic_y(orders["BA"]))
        elif sensitivity == "complete":
            scores[base] = None
        else:
            rec = orders.get("AB") or orders.get("BA")
            y = float(semantic_y(rec))
            scores[base] = y if sensitivity == "best" else 0.5
    return scores
def position_discordance(records: Iterable[dict], *, dim: str | None = None) -> float:
    vals = []
    for orders in _pair_map(records).values():
        if "AB" not in orders or "BA" not in orders:
            continue
        if dim is not None and orders["AB"]["target_dimension"] != dim:
            continue
        vals.append(abs(semantic_y(orders["AB"]) - semantic_y(orders["BA"])))
    return float(np.mean(vals)) if vals else float("nan")
def _z_span(dim: str) -> float:
    return RENDERED_Z[POS[dim]] - RENDERED_Z[NEG[dim]]
def _e_unit(cs: dict[tuple, float | None], dim: str, probe_id: str) -> float | None:
    slopes = {}
    for block in ("affect", "placebo"):
        pos = cs.get(("E", block, POS[dim], 0, 0, probe_id, ""))
        neg = cs.get(("E", block, NEG[dim], 0, 0, probe_id, ""))
        if pos is None or neg is None:
            return None
        slopes[block] = (pos - neg) / _z_span(dim)
    return slopes["affect"] - slopes["placebo"]
def compute_e_effects(records: Iterable[dict], *, sensitivity: str = "complete") -> dict:
    cs = cs_from_records(records, sensitivity=sensitivity)
    effects = {probe: _e_unit(cs, probe.split("-", 1)[0], probe) for probe in FORMAL_PROBES}
    usable = [v for v in effects.values() if v is not None]
    by_dim = {d: [effects[p] for p in FORMAL_PROBES if p.startswith(f"{d}-") and effects[p] is not None] for d in DIMS}
    return {"effects": effects, "theta_E": float(np.mean(usable)) if usable else float("nan"),
            "theta_E_by_dim": {d: float(np.mean(v)) if v else float("nan") for d, v in by_dim.items()}, "n_units": len(usable)}
def compute_n_effects(records: Iterable[dict], cfg: dict | None = None, *, sensitivity: str = "complete") -> dict:
    cfg = cfg or load_config(); cs = cs_from_records(records, sensitivity=sensitivity)
    replay = derive_all_replay_probe_ids(); seeds = list(cfg["history_seed_ids"]); n_hj = {}
    for direction in DIR_SIGN:
        dim = direction[0]; sign = DIR_SIGN[direction]
        for seed in seeds:
            for probe in replay[dim]:
                full = cs.get(("N", "affect", direction, seed, 200, probe, "full"))
                zero = cs.get(("N", "affect", direction, seed, 200, probe, "zero"))
                if full is None or zero is None:
                    continue
                n_hj[(direction, seed, probe)] = sign * (full - zero)
    n_k = {seed: float(np.mean([v for (h, s, p), v in n_hj.items() if s == seed])) if any(s == seed for _, s, _ in n_hj) else float("nan") for seed in seeds}
    usable = [v for v in n_k.values() if not math.isnan(v)]
    by_dim = {d: [v for (h, s, p), v in n_hj.items() if h[0] == d] for d in DIMS}
    return {"n_hj": n_hj, "N_k": n_k, "theta_N": float(np.mean(usable)) if usable else float("nan"),
            "theta_N_by_dim": {d: float(np.mean(v)) if v else float("nan") for d, v in by_dim.items()}, "n_seeds": len(usable)}
def exact_sign_flip(values: list[float]) -> float:
    m = len(values); obs = sum(values) / m; cnt = 0
    for mask in range(1 << m):
        total = sum(v if (mask >> i) & 1 else -v for i, v in enumerate(values) if v != 0.0)
        if total / m >= obs:
            cnt += 1
    return cnt / (1 << m)
def holm_adjust(p_values: list[float], alpha: float = 0.05) -> list[bool]:
    m = len(p_values); order = sorted(range(m), key=lambda i: p_values[i]); rej = [False] * m
    for rank, idx in enumerate(order):
        if p_values[idx] <= alpha / (m - rank):
            rej[idx] = True
        else:
            break
    return rej
def _rng(master_seed: int, tag: str) -> np.random.Generator:
    seed = int.from_bytes(hashlib.sha256(f"{master_seed}|bootstrap|{tag}".encode()).digest()[:8], "big")
    return np.random.default_rng(seed)
def item_bootstrap_e(records: Iterable[dict], cfg: dict | None = None, reps: int | None = None) -> dict[str, tuple[float, float]]:
    cfg = cfg or load_config(); reps = int(reps or cfg["bootstrap_repetitions"]); rng = _rng(int(cfg["master_seed"]), "E-item"); out = {}
    for dim in DIMS:
        probes = [p for p in FORMAL_PROBES if p.startswith(f"{dim}-")]; base = compute_e_effects(records)["effects"]
        units = [base[p] for p in probes if base[p] is not None]
        if not units:
            out[dim] = (float("nan"), float("nan")); continue
        draws = [float(np.mean([units[i] for i in rng.integers(0, len(units), size=len(units))])) for _ in range(reps)]
        out[dim] = (float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975)))
    return out
def two_way_bootstrap_n(records: Iterable[dict], cfg: dict | None = None, reps: int | None = None) -> tuple[float, float]:
    cfg = cfg or load_config(); reps = int(reps or cfg["bootstrap_repetitions"]); rng = _rng(int(cfg["master_seed"]), "N-two-way")
    replay = derive_all_replay_probe_ids(); seeds = list(cfg["history_seed_ids"]); items = sorted({p for d in DIMS for p in replay[d]})
    base = compute_n_effects(records, cfg); draws = []
    for _ in range(reps):
        s_pick = rng.integers(0, len(seeds), size=len(seeds)); i_pick = rng.integers(0, len(items), size=len(items))
        s_mult = np.bincount(s_pick, minlength=len(seeds)); i_mult = np.bincount(i_pick, minlength=len(items))
        vals = []
        for (h, s, p), v in base["n_hj"].items():
            si, pi = seeds.index(s), items.index(p)
            w = int(s_mult[si]) * int(i_mult[pi])
            if w:
                vals.extend([v] * w)
        draws.append(float(np.mean(vals)) if vals else float("nan"))
    draws = [d for d in draws if not math.isnan(d)]
    return (float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))) if draws else (float("nan"), float("nan"))
def two_way_bootstrap_n_draw(n_hj: dict[tuple, float], seeds: list[int], items: list[str], s_pick: np.ndarray, i_pick: np.ndarray) -> float:
    s_mult = np.bincount(s_pick, minlength=len(seeds)); i_mult = np.bincount(i_pick, minlength=len(items))
    vals = []
    for (h, s, p), v in n_hj.items():
        w = int(s_mult[seeds.index(s)]) * int(i_mult[items.index(p)])
        if w:
            vals.extend([v] * w)
    return float(np.mean(vals)) if vals else float("nan")
def missing_sensitivity(records: Iterable[dict], cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    return {"E": {m: compute_e_effects(records, sensitivity=m)["theta_E"] for m in ("complete", "best", "worst")},
            "N": {m: compute_n_effects(records, cfg, sensitivity=m)["theta_N"] for m in ("complete", "best", "worst")}}
def _gate_e(records: Iterable[dict], cfg: dict) -> dict:
    e_rows = [r for r in records if r.get("experiment") == "E"]; pairs = _pair_map(e_rows)
    complete_pairs = sum(1 for o in pairs.values() if "AB" in o and "BA" in o)
    invalid = _invalid_json_final_count(records, "E"); eff = compute_e_effects(e_rows); units = [v for v in eff["effects"].values() if v is not None]
    p = exact_sign_flip(units) if units else 1.0
    disc = position_discordance(e_rows); disc_d = {d: position_discordance(e_rows, dim=d) for d in DIMS}
    return {"complete_pairs": complete_pairs, "planned_pairs": 90, "invalid_json": invalid, "position_discordance": disc,
            "position_discordance_by_dim": disc_d, "theta_E": eff["theta_E"], "p_E": p, "mes_pass": eff["theta_E"] >= cfg["MES_E"],
            "pair_pass": complete_pairs >= 89, "invalid_pass": invalid <= 1, "units_complete": len(units) == 15,
            "discordance_pass": disc <= 0.25 and all(disc_d[d] <= 0.35 for d in DIMS), "sign_pass": p <= cfg["alpha_E_one_sided"]}
def _gate_n(records: Iterable[dict], cfg: dict) -> dict:
    n_rows = [r for r in records if r.get("experiment") == "N"]; pairs = _pair_map(n_rows)
    complete_pairs = sum(1 for o in pairs.values() if "AB" in o and "BA" in o)
    invalid = _invalid_json_final_count(records, "N"); eff = compute_n_effects(n_rows, cfg); seeds = [v for v in eff["N_k"].values() if not math.isnan(v)]
    p = exact_sign_flip(seeds) if seeds else 1.0
    disc = position_discordance(n_rows); disc_d = {d: position_discordance(n_rows, dim=d) for d in DIMS}
    sub = _n_direction_and_seed_checks(n_rows, cfg)
    return {"complete_pairs": complete_pairs, "planned_pairs": 288, "invalid_json": invalid, "position_discordance": disc,
            "position_discordance_by_dim": disc_d, "theta_N": eff["theta_N"], "p_N": p, "mes_pass": eff["theta_N"] >= cfg["MES_N"],
            "pair_pass": complete_pairs >= 283, "invalid_pass": invalid <= 5, "seeds_complete": len(seeds) == 8,
            "discordance_pass": disc <= 0.25 and all(disc_d[d] <= 0.35 for d in DIMS), "sign_pass": p <= cfg["alpha_N_one_sided"],
            **sub}
def _write_svg(path: Path, title: str, labels: list[str], values: list[float], hline: float | None = None) -> None:
    w, h, pad = 640, 360, 50; finite = [abs(v) for v in values if not math.isnan(v)]; vmax = max(finite + [0.1]); bars = []
    slot = (w - 2 * pad) / max(len(values), 1)
    for i, v in enumerate(values):
        if math.isnan(v): continue
        x = pad + i * slot + slot * 0.15; bw = slot * 0.7; bh = (v / vmax) * (h / 2 - pad)
        y, height = (h / 2 - bh, bh) if bh >= 0 else (h / 2, -bh)
        bars += [f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{height:.1f}" fill="#3366aa"/>',
                 f'<text x="{x + bw/2:.1f}" y="{h - 10}" font-size="10" text-anchor="middle">{labels[i]}</text>']
    mid = f'<line x1="{pad}" y1="{h/2:.1f}" x2="{w-pad}" y2="{h/2:.1f}" stroke="#999"/>'
    hl = f'<line x1="{pad}" y1="{h/2 - (hline/vmax)*(h/2-pad):.1f}" x2="{w-pad}" y2="{h/2 - (hline/vmax)*(h/2-pad):.1f}" stroke="#cc3333" stroke-dasharray="4"/>' if hline is not None else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><text x="{pad}" y="24" font-size="16">{title}</text>{mid}{hl}{"".join(bars)}</svg>', encoding="utf-8")
def _formal_records(records: list[dict]) -> list[dict]:
    keys = {s.observation_key() for s in interleave_formal_schedules()}; return [r for r in records if obs_key(r) in keys]
def rebuild_outputs(*, raw_path: Path | None = None, manifest_path: Path | None = None, write: bool = True) -> dict:
    raw_path = raw_path or RAW_PATH; manifest_path = manifest_path or MANIFEST_PATH; cfg = load_config()
    if not manifest_path.is_file(): build_randomization_manifest(write=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")); records = _formal_records(load_records(raw_path))
    blind = blind_integrity_qc(raw_path=raw_path, manifest_path=manifest_path, write=write)
    e = compute_e_effects(records); n = compute_n_effects(records, cfg); gate_e = _gate_e(records, cfg); gate_n = _gate_n(records, cfg)
    axis_p = [exact_sign_flip([v for p, v in e["effects"].items() if p.startswith(f"{d}-") and v is not None]) if any(p.startswith(f"{d}-") and e["effects"][p] is not None for p in e["effects"]) else 1.0 for d in DIMS]
    out = {"analysis_code_hash": analysis_code_hash(), "randomization_manifest_hash": manifest.get("file_sha256"),
           "raw_sha256": sha256_file(raw_path) if raw_path.is_file() else None, "theta_E": e["theta_E"], "theta_E_by_dim": e["theta_E_by_dim"],
           "p_E": gate_e["p_E"], "theta_N": n["theta_N"], "theta_N_by_dim": n["theta_N_by_dim"], "N_k": n["N_k"], "p_N": gate_n["p_N"],
           "bootstrap_E_by_dim": item_bootstrap_e(records, cfg), "bootstrap_N": two_way_bootstrap_n(records, cfg),
           "missing_sensitivity": missing_sensitivity(records, cfg), "gates": {"E": gate_e, "N": gate_n},
           "holm_axis_reject": holm_adjust(axis_p, alpha=cfg["alpha_E_one_sided"]), "axis_p_E": axis_p, "blind_qc_pass": blind.get("pass")}
    integrity = {"blind_qc": blind, "formal_record_count": len(records), "gates": out["gates"], "analysis_code_hash": out["analysis_code_hash"]}
    paths = {"final_results": REPORTS / "final_results.json", "integrity_report": REPORTS / "integrity_report.json",
             "main_table": REPORTS / "main_results_table.tex", "fig_e": ROOT / "paper" / "figures" / "fig_theta_e.svg",
             "fig_n": ROOT / "paper" / "figures" / "fig_theta_n.svg", "derived": DERIVED / "analysis_summary.json"}
    if write:
        REPORTS.mkdir(parents=True, exist_ok=True); DERIVED.mkdir(parents=True, exist_ok=True)
        paths["final_results"].write_text(json.dumps(out, separators=(",", ":"), sort_keys=True), encoding="utf-8")
        paths["integrity_report"].write_text(json.dumps(integrity, separators=(",", ":"), sort_keys=True), encoding="utf-8")
        paths["derived"].write_text(json.dumps(out, separators=(",", ":"), sort_keys=True), encoding="utf-8")
        paths["main_table"].write_text("\n".join(["Metric & Value \\\\", f"$\\theta_E$ & {e['theta_E']:.4f} \\\\", f"$\\theta_N$ & {n['theta_N']:.4f} \\\\"]) + "\n", encoding="utf-8")
        _write_svg(paths["fig_e"], "Experiment E item effects", list(e["effects"].keys()), list(e["effects"].values()), hline=cfg["MES_E"])
        _write_svg(paths["fig_n"], "Experiment N seed effects", [str(k) for k in n["N_k"].keys()], list(n["N_k"].values()), hline=cfg["MES_N"])
    out["output_paths"] = {k: str(v) for k, v in paths.items()}; return out
def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv or argv[0] == "rebuild": rebuild_outputs(write=True); return 0
    raise SystemExit("usage: python -m tools.analysis_core rebuild")
if __name__ == "__main__":
    raise SystemExit(main())
