from __future__ import annotations
import hashlib, json, os, queue, subprocess, threading, uuid
from collections import deque
from concurrent.futures import ALL_COMPLETED, FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from sprint.histories import build_history_actions, run_history
from sprint.manifest import ProbeRow, config_hash, derive_all_replay_probe_ids, load_probes, protocol_hash
from sprint.provider_qwen import CompletionResult, ProviderError, SchemaError, TransportError, complete_choice, sanitize_log_message
from sprint.renderer import assemble_request, render_event_memory, renderer_template_hash
from sprint.schema import ENDPOINT_RAW_S, ROOT, dependency_lock_sha256, load_config, render_z, signed_z
RAW_DIR = ROOT / "data" / "raw"
DEV_SEED, NCONDS = 1000, ("P-", "P+", "A-", "A+", "D-", "D+")
class RunnerError(Exception): pass
class RunPaused(RunnerError): pass
class RunStopped(RunnerError): pass
class DevelopmentCapExceeded(RunnerError): pass
@dataclass(frozen=True)
class ObservationSpec:
    experiment: str; semantic_block: str; state_or_history: str; history_seed: int; checkpoint: int
    probe_id: str; option_order: str; cell: str
    def observation_key(self) -> tuple: return (self.experiment, self.semantic_block, self.state_or_history, self.history_seed, self.checkpoint, self.probe_id, self.option_order, self.cell)
    def attempt_key(self, n: int) -> tuple: return self.observation_key() + (n,)
def _sched_o(e, st, pr, b, o, seed=0, cp=0, cell=""): return ObservationSpec(e, b, st, seed, cp, pr, o, cell)
def _sched_u(items: list[ObservationSpec]) -> list[ObservationSpec]:
    seen: set[tuple] = set()
    for s in items:
        k = s.observation_key()
        if k in seen: raise ValueError(f"duplicate observation_key: {k!r}")
        seen.add(k)
    return items
def build_stability_schedule() -> list[ObservationSpec]: return _sched_u([_sched_o("stability", f"{d}+", f"{d}-D01", b, o, seed=r) for d in "PAD" for b in ("affect", "placebo") for o in ("AB", "BA") for r in range(3)])
def build_e_dry_run_schedule() -> list[ObservationSpec]: return _sched_u([_sched_o("E", s, f"{s[0]}-D02", b, o) for s in NCONDS for b in ("affect", "placebo") for o in ("AB", "BA")] + [_sched_o("E", "ORIGIN", f"{d}-D02", b, o) for d in "PAD" for b in ("affect", "placebo") for o in ("AB", "BA")])
def build_n_dry_run_schedule() -> list[ObservationSpec]: return _sched_u([ObservationSpec("N", "affect", c, DEV_SEED, 200, "P-D02", o, cell) for c in ("P-", "P+") for o in ("AB", "BA") for cell in ("full", "zero")])
def build_formal_e_schedule() -> list[ObservationSpec]: return _sched_u([_sched_o("E", s, f"{d}-C{i:02d}", b, o) for d in "PAD" for s in (f"{d}-", "ORIGIN", f"{d}+") for i in range(1, 6) for b in ("affect", "placebo") for o in ("AB", "BA")])
def build_formal_n_schedule(cfg: dict | None = None) -> list[ObservationSpec]:
    c, r = cfg or load_config(), derive_all_replay_probe_ids(); return _sched_u([ObservationSpec("N", "affect", cnd, s, 200, p, o, cell) for cnd in NCONDS for s in c["history_seed_ids"] for p in r[cnd[0]] for o in ("AB", "BA") for cell in ("full", "zero")])
def interleave_formal_schedules(master_seed: int = 20260804) -> list[ObservationSpec]:
    return [s for _, s in sorted((hashlib.sha256(f"{master_seed}|interleave|{json.dumps(s.observation_key(), separators=(',',':'))}".encode()).digest(), s) for s in build_formal_e_schedule() + build_formal_n_schedule())]
def obs_key(rec: dict) -> tuple: return (rec["experiment"], rec["semantic_block"], rec["condition"], int(rec["history_seed"]), int(rec["checkpoint"]), rec["probe_id"], rec["option_order"], rec.get("cell", ""))
def att_key(rec: dict) -> tuple: return obs_key(rec) + (int(rec["request_attempt"]),)
def validate_ledger_records(records: list[dict]) -> None:
    done, seen = set(), set()
    for rec in records:
        ok = rec.get("parsed_choice") in ("A", "B") and not rec.get("error_code"); ak = att_key(rec)
        if ak in seen: raise ValueError(f"duplicate attempt_key: {ak!r}")
        seen.add(ak)
        if ok and obs_key(rec) in done: raise ValueError(f"duplicate completed observation_key: {obs_key(rec)!r}")
        if ok: done.add(obs_key(rec))
def qc_returned_model(requested: str, returned: str | None) -> str | None:
    if returned is not None and returned != requested: raise RunStopped(f"returned_model {returned!r} != {requested!r}")
    return returned
def load_records(path: Path) -> list[dict]: return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.is_file() else []
def rebuild_ledger(path: Path) -> dict:
    records = load_records(path); validate_ledger_records(records) if records else None
    tc = frozenset({"transport_exhausted", "transport_error", "transport_retry"})
    completed, last_rid, fail_window, http = set(), {}, [], 0
    for rec in records:
        r = int(rec.get("retry_count") or 0); n = r + 1; http += n
        fail_window.extend([1] * r + [int((rec.get("error_code") or "") in tc)])
        if rec.get("parsed_choice") in ("A", "B") and not rec.get("error_code"): completed.add(obs_key(rec))
        last_rid[obs_key(rec)] = rec["request_id"]
    return {"records": records, "completed": completed, "attempt_count": http, "fail_window": fail_window[-100:], "last_rid": last_rid}
_CHOICE_JSON = frozenset(('{"choice":"A"}', '{"choice":"B"}')); _FORBIDDEN_RESP = ("reasoning_content", "tool_calls", "search_info", "search_results", "web_search")
def assert_stability_gate(records: list[dict], *, expected_model: str | None = None) -> None:
    model = str(expected_model or load_config()["agent_model"]); ok = [r for r in records if r.get("experiment") == "stability" and r.get("parsed_choice") in ("A", "B") and not r.get("error_code")]
    if len(ok) != 36 or len({obs_key(r) for r in ok}) != 36: raise RunnerError(f"expected 36 unique completed stability rows, got {len(ok)}")
    if {obs_key(r) for r in ok} != {s.observation_key() for s in build_stability_schedule()}: raise RunnerError("stability rows mismatch schedule")
    trips: dict[str, tuple[int, set[str]]] = {}
    for rec in ok:
        if rec.get("requested_model") != model or ((ret := rec.get("returned_model")) is not None and ret != model) or rec.get("enable_thinking") is not False or rec.get("tools") != "off" or rec.get("search") != "off": raise RunnerError("request flags or model mismatch")
        raw = rec.get("raw_response") or ""
        if raw not in _CHOICE_JSON or any(t in raw.lower() for t in _FORBIDDEN_RESP): raise RunnerError("raw_response invalid or forbidden content")
        for f in ("renderer_text", "response_id", "request_utc"):
            if not rec.get(f): raise RunnerError(f"missing or empty {f!r}")
        for f in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if not isinstance(rec.get(f), int) or rec[f] < 0: raise RunnerError(f"invalid {f!r}")
        c, o = rec["parsed_choice"], rec["option_order"]
        if o not in ("AB", "BA"): raise RunnerError(f"invalid option_order: {o!r}")
        sem = "high" if (o == "AB") == (c == "A") else "low"; ph = hashlib.sha256(rec["renderer_text"].encode()).hexdigest(); n, s = trips.get(ph, (0, set())); trips[ph] = (n + 1, s | {sem})
    if len(trips) != 12 or any(n != 3 or len(s) != 1 for n, s in trips.values()): raise RunnerError("payload triplet semantic mismatch")
def next_attempt(spec: ObservationSpec, ledger: dict) -> tuple[int, str | None]:
    obs = spec.observation_key(); reqs = [int(r["request_attempt"]) for r in ledger["records"] if obs_key(r) == obs]
    return max(reqs, default=-1) + 1, ledger["last_rid"].get(obs) if reqs else None
def _prompt(spec: ObservationSpec, row: ProbeRow):
    mem_t = mem_h = None
    if spec.experiment == "N":
        mem_t = render_event_memory(build_history_actions(spec.state_or_history, spec.history_seed)); mem_h = hashlib.sha256(mem_t.encode()).hexdigest()
        raw = run_history(spec.state_or_history, spec.history_seed)[1].s if spec.cell == "full" else ENDPOINT_RAW_S["ORIGIN"]; mode = "affect"
    else: raw, mode = ENDPOINT_RAW_S[spec.state_or_history], spec.semantic_block
    text = assemble_request(experiment="N" if spec.experiment == "N" else "E", renderer_mode=mode, raw_s=raw, scenario=row.neutral_scenario, high_option=row.high_option, low_option=row.low_option, option_order=spec.option_order, memory_text=mem_t)
    return text, raw, render_z(raw), mem_t, mem_h, mode
class RawWriter:
    def __init__(self, path: Path):
        self._path = path; path.parent.mkdir(parents=True, exist_ok=True); self._err = None
        self._q: queue.Queue = queue.Queue(); threading.Thread(target=self._loop, daemon=True).start()
    def _loop(self):
        with self._path.open("a", encoding="utf-8") as fh:
            while (item := self._q.get()) is not None:
                rec, done = item
                try: fh.write(json.dumps(rec, separators=(",", ":"), ensure_ascii=True) + "\n"); fh.flush(); os.fsync(fh.fileno())
                except Exception as exc: self._err = exc
                done.set()
    def write(self, rec: dict):
        if self._err: raise self._err
        done = threading.Event(); self._q.put((rec, done)); done.wait()
        if self._err: raise self._err
    def close(self): self._q.put(None)
class SprintRunner:
    def __init__(self, *, config: dict | None = None, raw_path: Path | None = None, ckpt_path: Path | None = None, complete_fn: Callable[..., CompletionResult] | None = None):
        self.cfg = config or load_config(); self.raw = raw_path or RAW_DIR / "sprint_raw.jsonl"; self.ckpt = ckpt_path or RAW_DIR / "checkpoint.json"
        self.workers = int(self.cfg["max_workers"]); assert self.workers == 6; self.complete_fn = complete_fn or complete_choice; self.probes = {r.probe_id: r for r in load_probes()}
        try: head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=ROOT).stdout.strip()
        except (OSError, subprocess.CalledProcessError): head = "unknown"
        self._meta = (protocol_hash(), config_hash(), dependency_lock_sha256(), head, str(self.cfg["agent_model"]))
    def records(self) -> list[dict]: return load_records(self.raw)
    def save_ckpt(self, ledger: dict, pending: list[dict] | None) -> None:
        self.ckpt.parent.mkdir(parents=True, exist_ok=True); doc = {"completed": [list(x) for x in ledger["completed"]], "attempt_count": ledger["attempt_count"], "fail_window": ledger["fail_window"], "pending": pending}
        with self.ckpt.open("w", encoding="utf-8") as fh: fh.write(json.dumps(doc, separators=(",", ":"), sort_keys=True)); fh.flush(); os.fsync(fh.fileno())
    def _base(self, spec: ObservationSpec, row: ProbeRow, req: int, retry_of: str | None) -> dict:
        text, raw, rz, mem_t, mem_h, mode = _prompt(spec, row); z = signed_z(raw); m, c = self._meta, self.cfg
        return {"request_id": str(uuid.uuid4()), "retry_of": retry_of, "experiment": spec.experiment, "semantic_block": mode, "condition": spec.state_or_history, "history_seed": spec.history_seed, "checkpoint": spec.checkpoint, "raw_s": [float(x) for x in raw.tolist()], "raw_z": [float(x) for x in z.tolist()], "rendered_z": list(rz), "renderer_text": text, "renderer_hash": renderer_template_hash(mode), "memory_text": mem_t, "memory_hash": mem_h, "probe_id": spec.probe_id, "target_dimension": row.target_dimension, "option_order": spec.option_order, "semantic_key": row.semantic_key, "temperature": c["temperature"], "top_p": c["top_p"], "max_tokens": c["max_tokens"], "response_format": c["response_format"], "enable_thinking": c["enable_thinking"], "tools": c["tools"], "search": c["search"], "error_code": None, "protocol_hash": m[0], "config_hash": m[1], "lock_hash": m[2], "code_commit": m[3], "request_attempt": req, "cell": spec.cell, "requested_model": m[4], "request_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    def _nulls(self) -> dict: return {"raw_response": None, "parsed_choice": None, "returned_model": None, "response_id": None, "latency_ms": None, "prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    def _finalize(self, rec: dict, outcome) -> dict:
        tok = {k: getattr(outcome, k, None) for k in ("prompt_tokens", "completion_tokens", "total_tokens")} if isinstance(outcome, (CompletionResult, SchemaError)) else dict.fromkeys(("prompt_tokens", "completion_tokens", "total_tokens"))
        if isinstance(outcome, CompletionResult):
            try: qc_returned_model(outcome.requested_model, outcome.returned_model)
            except RunStopped: return rec | self._nulls() | tok | {"error_code": "returned_model_mismatch", "returned_model": outcome.returned_model, "retry_count": outcome.retry_count, "raw_response": sanitize_log_message(f"returned_model {outcome.returned_model!r} != {outcome.requested_model!r}")}
            rec |= {"raw_response": sanitize_log_message(outcome.raw_response), "parsed_choice": outcome.choice, "requested_model": outcome.requested_model, "returned_model": outcome.returned_model, "response_id": outcome.response_id, "latency_ms": outcome.latency_ms, "retry_count": outcome.retry_count, "error_code": None, **tok}
        elif isinstance(outcome, SchemaError): rec |= self._nulls() | {"raw_response": sanitize_log_message(outcome.raw_response or str(outcome)), "error_code": outcome.code, "retry_count": outcome.retry_count, **tok}
        elif isinstance(outcome, (TransportError, ProviderError)): rec |= self._nulls() | {"raw_response": sanitize_log_message(outcome.raw_response or str(outcome)), "error_code": outcome.code, "retry_count": outcome.retry_count}
        else: raise outcome
        return rec
    def _gate(self, ledger: dict, development: bool) -> None:
        if ledger["attempt_count"] >= int(self.cfg["attempt_hard_stop"]): raise RunStopped(str(self.cfg["attempt_hard_stop"]))
        if ledger["attempt_count"] >= int(self.cfg["attempt_pause"]): raise RunPaused(str(self.cfg["attempt_pause"]))
        fw = ledger["fail_window"]
        if len(fw) == 100 and sum(fw) > 5: raise RunPaused("rolling failure rate > 5%")
        cap = int(self.cfg["development_completed_cap"])
        if development and sum(1 for r in ledger["records"] if r.get("parsed_choice") in ("A", "B") and not r.get("error_code")) >= cap:
            raise DevelopmentCapExceeded(str(cap))
    def _needs_retry(self, spec: ObservationSpec, ledger: dict) -> bool:
        rows = [r for r in ledger["records"] if obs_key(r) == spec.observation_key()]
        if not rows: return True
        last = rows[-1]; code = last.get("error_code") or ""
        if last.get("parsed_choice") in ("A", "B") and not code: return False
        return code == "transport_exhausted"
    def _reconcile_pending(self, w: RawWriter, ckpt_pending: list[dict]) -> None:
        if not ckpt_pending: return
        ledger = rebuild_ledger(self.raw); raw_ids = {r["request_id"] for r in ledger["records"]}
        for pend in ckpt_pending:
            if pend["request_id"] in raw_ids: continue
            spec = ObservationSpec(pend["experiment"], pend["semantic_block"], pend["state_or_history"], int(pend["history_seed"]), int(pend["checkpoint"]), pend["probe_id"], pend["option_order"], pend.get("cell", ""))
            if spec.observation_key() in ledger["completed"]: continue
            rec = self._base(spec, self.probes[spec.probe_id], int(pend["request_attempt"]), pend.get("retry_of"))
            rec["request_id"] = pend["request_id"]
            w.write(rec | self._nulls() | {"error_code": "transport_exhausted", "retry_count": 0, "raw_response": "transport_exhausted"})
        self.save_ckpt(rebuild_ledger(self.raw), None)
    def run(self, schedule: list[ObservationSpec], *, development: bool = True, resume: bool = True) -> dict:
        if not resume and self.raw.is_file() and self.raw.read_text(encoding="utf-8").strip():
            raise RunnerError("non-empty raw requires resume=True or a fresh raw_path")
        if development and (len(schedule) > int(self.cfg["development_completed_cap"]) or any((s.experiment == "E" and "-D02" not in s.probe_id) or (s.experiment == "N" and s.probe_id != "P-D02") for s in schedule)):
            raise RunnerError("formal or oversized schedule requires development=False")
        ckpt_pending = json.loads(self.ckpt.read_text(encoding="utf-8")).get("pending") if resume and self.ckpt.is_file() else None
        w = RawWriter(self.raw); pending: list[dict] = []; lock = threading.Lock(); work: deque[ObservationSpec] = deque(schedule); retried: set[tuple] = set(); abort: RunnerError | None = None
        if resume and ckpt_pending: self._reconcile_pending(w, ckpt_pending)
        try:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                inflight: dict = {}
                def _commit(fut):
                    nonlocal abort
                    spec, rec, pend = inflight.pop(fut)
                    try: rec = self._finalize(rec, fut.result())
                    except Exception as exc: rec = self._finalize(rec, exc)
                    with lock:
                        w.write(rec); ledger = rebuild_ledger(self.raw)
                        pending[:] = [p for p in pending if p["request_id"] != pend["request_id"]]
                        self.save_ckpt(ledger, pending or None)
                        if rec.get("error_code") == "returned_model_mismatch" and abort is None: abort = RunStopped("returned_model_mismatch")
                    if abort is None and self._needs_retry(spec, ledger):
                        obs = spec.observation_key()
                        if obs not in retried: retried.add(obs); work.append(spec)
                def _drain(all_done: bool = False):
                    while inflight:
                        done, _ = wait(inflight, return_when=ALL_COMPLETED if all_done else FIRST_COMPLETED)
                        for fut in list(done): _commit(fut)
                        if not all_done: return
                while (work or inflight) and abort is None:
                    try: ledger = rebuild_ledger(self.raw); self._gate(ledger, development)
                    except RunnerError as exc: abort = exc; break
                    while work and len(inflight) < self.workers and abort is None:
                        spec = work[0]
                        if spec.observation_key() in ledger["completed"] or not self._needs_retry(spec, ledger):
                            work.popleft(); continue
                        req, retry_of = next_attempt(spec, ledger)
                        if spec.attempt_key(req) in {att_key(r) for r in ledger["records"]}:
                            work.popleft(); continue
                        rec = self._base(spec, self.probes[spec.probe_id], req, retry_of)
                        pend = {**asdict(spec), "request_attempt": req, "retry_of": retry_of, "request_id": rec["request_id"]}
                        with lock: pending.append(pend); self.save_ckpt(rebuild_ledger(self.raw), pending)
                        inflight[pool.submit(self.complete_fn, rec["renderer_text"], config=self.cfg)] = (spec, rec, pend)
                        work.popleft()
                    if abort is not None: break
                    if inflight: _drain()
                if inflight: _drain(all_done=True)
                if abort is not None: raise abort
        finally: w.close(); ledger = rebuild_ledger(self.raw)
        return {"completed": len(ledger["completed"]), "attempt_count": ledger["attempt_count"]}
def run_stability_gate_only(runner: SprintRunner | None = None, *, resume: bool = True) -> dict:
    r = runner or SprintRunner(); out = r.run(build_stability_schedule(), development=True, resume=resume); assert_stability_gate(r.records()); return out
