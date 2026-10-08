from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from sprint.runner import interleave_formal_schedules, obs_key
from sprint.schema import load_config, sha256_file
MANIFEST_PATH = ROOT / "reports" / "randomization_manifest.json"
QC_PATH = ROOT / "reports" / "blind_integrity_qc.json"
RAW_PATH = ROOT / "data" / "raw" / "sprint_raw.jsonl"
REQUIRED_RAW = frozenset({
    "request_id", "experiment", "semantic_block", "condition", "history_seed", "checkpoint",
    "probe_id", "option_order", "cell", "parsed_choice", "error_code", "raw_response",
    "response_format", "protocol_hash", "config_hash",
})
VALID_RAW = frozenset(('{"choice":"A"}', '{"choice":"B"}'))
INVALID_JSON_CODES = frozenset({"invalid_choice_json", "invalid_response_schema"})

def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()
def _tag(prefix: str, label: str, master_seed: int) -> str:
    return f"{prefix}-{hashlib.sha256(f'{master_seed}|{prefix}|{label}'.encode()).hexdigest()[:10]}"
def build_randomization_manifest(master_seed: int | None = None, *, write: bool = True) -> dict:
    cfg = load_config(); ms = int(master_seed if master_seed is not None else cfg["master_seed"])
    blocks = {b: _tag("BL", b, ms) for b in ("affect", "placebo")}
    cells = {"": _tag("CL", "empty", ms), "full": _tag("CL", "full", ms), "zero": _tag("CL", "zero", ms)}
    states = sorted({s.state_or_history for s in interleave_formal_schedules(ms)})
    conditions = {s: _tag("SC", s, ms) for s in states}
    schedule = []
    for idx, spec in enumerate(interleave_formal_schedules(ms)):
        schedule.append({
            "run_index": idx, "opaque_code": f"RUN-{idx + 1:04d}",
            "experiment": spec.experiment, "block_code": blocks[spec.semantic_block],
            "condition_code": conditions[spec.state_or_history], "history_seed": spec.history_seed,
            "checkpoint": spec.checkpoint, "probe_id": spec.probe_id, "option_order": spec.option_order,
            "cell_code": cells[spec.cell],
        })
    doc = {
        "master_seed": ms, "formal_observations_total": len(schedule),
        "block_codes": blocks, "condition_codes": conditions, "cell_codes": cells,
        "schedule": schedule,
    }
    payload = json.dumps(doc, separators=(",", ":"), sort_keys=True)
    doc["file_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
    text = json.dumps(doc, separators=(",", ":"), sort_keys=True)
    if write:
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(text, encoding="utf-8")
    return json.loads(text)
def _manifest_key(entry: dict) -> tuple:
    return (entry["experiment"], entry["block_code"], entry["condition_code"], int(entry["history_seed"]),
            int(entry["checkpoint"]), entry["probe_id"], entry["option_order"], entry["cell_code"])
def _obs_key(rec: dict) -> tuple:
    return (rec["experiment"], rec["semantic_block"], rec["condition"], int(rec["history_seed"]),
            int(rec["checkpoint"]), rec["probe_id"], rec["option_order"], rec.get("cell", ""))
def _att_key(rec: dict) -> tuple:
    return _obs_key(rec) + (int(rec.get("request_attempt") or 0),)
def blind_integrity_qc(*, raw_path: Path | None = None, manifest_path: Path | None = None, write: bool = True) -> dict:
    raw_path = raw_path or RAW_PATH; manifest_path = manifest_path or MANIFEST_PATH
    issues: list[str] = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    schedule = manifest.get("schedule") or []
    opaque = [e.get("opaque_code") for e in schedule]
    mkeys = [_manifest_key(e) for e in schedule]
    report = {
        "mode": "blind", "raw_path": repo_relative(raw_path), "manifest_path": repo_relative(manifest_path),
        "raw_sha256": sha256_file(raw_path) if raw_path.is_file() else None,
        "manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else None,
        "manifest_entry_count": len(schedule), "expected_formal_entries": 756,
        "duplicate_opaque_codes": len(opaque) - len(set(opaque)),
        "duplicate_manifest_keys": len(mkeys) - len(set(mkeys)),
        "manifest_file_sha256_matches": manifest.get("file_sha256") == hashlib.sha256(
            json.dumps({k: v for k, v in manifest.items() if k != "file_sha256"}, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest() if manifest_path.is_file() else False,
        "records_total": 0, "formal_rows": 0, "dev_en_rows": 0, "completed_formal_rows": 0, "invalid_json_rows": 0,
        "duplicate_attempt_keys": 0, "duplicate_completed_observation_keys": 0, "missing_required_fields": 0,
        "response_format_violations": 0, "issues": issues,
    }
    if len(schedule) != 756:
        issues.append(f"manifest schedule length {len(schedule)} != 756")
    if report["duplicate_opaque_codes"]:
        issues.append("duplicate opaque_code values in manifest")
    if report["duplicate_manifest_keys"]:
        issues.append("duplicate manifest observation keys")
    if manifest_path.is_file() and not report["manifest_file_sha256_matches"]:
        issues.append("manifest file_sha256 field mismatch")
    records = []
    if raw_path.is_file():
        for line_no, line in enumerate(raw_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                issues.append(f"raw line {line_no}: invalid JSON"); continue
            records.append(rec)
    report["records_total"] = len(records)
    formal_keys = {s.observation_key() for s in interleave_formal_schedules()}
    seen_attempt, seen_obs = set(), set()
    for rec in records:
        if rec.get("experiment") not in ("E", "N"):
            continue
        obs = _obs_key(rec)
        if obs not in formal_keys:
            report["dev_en_rows"] += 1
            continue
        report["formal_rows"] += 1
        if missing := [f for f in REQUIRED_RAW if f not in rec]:
            report["missing_required_fields"] += 1
            if report["missing_required_fields"] <= 5:
                issues.append(f"missing fields {missing} on request_id={rec.get('request_id')}")
        ok = rec.get("parsed_choice") in ("A", "B") and not rec.get("error_code")
        ak = _att_key(rec)
        if ak in seen_attempt:
            report["duplicate_attempt_keys"] += 1
        seen_attempt.add(ak)
        if ok:
            report["completed_formal_rows"] += 1
            ok_raw = rec.get("raw_response") or ""
            if ok_raw not in VALID_RAW:
                report["response_format_violations"] += 1
            obs = _obs_key(rec)
            if obs in seen_obs:
                report["duplicate_completed_observation_keys"] += 1
            seen_obs.add(obs)
        elif rec.get("error_code"):
            report["invalid_json_rows"] += 1
    if report["duplicate_attempt_keys"]:
        issues.append("duplicate attempt_key in raw")
    if report["duplicate_completed_observation_keys"]:
        issues.append("duplicate completed observation_key in raw")
    report["missing_rate_formal"] = 1.0 - (report["completed_formal_rows"] / max(report["formal_rows"], 1))
    report["pass"] = not issues
    if write:
        QC_PATH.parent.mkdir(parents=True, exist_ok=True)
        QC_PATH.write_text(json.dumps(report, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    return report
def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv or argv[0] == "build":
        build_randomization_manifest(write=True)
        blind_integrity_qc(write=True)
        return 0
    raise SystemExit(f"usage: python -m tools.rand_manifest build")
if __name__ == "__main__":
    raise SystemExit(main())
