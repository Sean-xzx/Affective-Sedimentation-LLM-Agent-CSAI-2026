from __future__ import annotations
import json
from pathlib import Path
import httpx
import openai
import pytest
from dataclasses import asdict
from sprint.runner import (
    DevelopmentCapExceeded,
    ObservationSpec,
    RunPaused,
    RunnerError,
    RunStopped,
    SprintRunner,
    assert_stability_gate,
    att_key,
    run_stability_gate_only,
    build_e_dry_run_schedule,
    build_formal_e_schedule,
    build_formal_n_schedule,
    build_n_dry_run_schedule,
    build_stability_schedule,
    interleave_formal_schedules,
    obs_key,
    qc_returned_model,
    rebuild_ledger,
    validate_ledger_records,
)
from sprint.provider_qwen import CompletionResult, SchemaError, TransportError
from sprint.schema import load_config
def _ok(choice: str = "A", **kw) -> CompletionResult:
    return CompletionResult(choice=choice, raw_response=f'{{"choice":"{choice}"}}', requested_model="qwen3.7-flash-2026-07-15",
                            returned_model="qwen3.7-flash-2026-07-15", response_id="r1", latency_ms=1, retry_count=0,
                            prompt_tokens=10, completion_tokens=1, total_tokens=11, **kw)
def _mini_schedule() -> list[ObservationSpec]:
    return build_n_dry_run_schedule()[:2]
def test_schedule_counts():
    assert len(build_stability_schedule()) == 36
    assert len(build_e_dry_run_schedule()) == 36
    assert len(build_n_dry_run_schedule()) == 8
    assert len(build_formal_e_schedule()) == 180
    assert len(build_formal_n_schedule()) == 576
    assert len(interleave_formal_schedules()) == 756
def test_observation_and_attempt_keys():
    s = build_stability_schedule()[0]
    assert len(s.observation_key()) == 8
    assert s.attempt_key(0) == s.observation_key() + (0,)
def test_duplicate_completed_and_attempt_keys_fail():
    s = build_n_dry_run_schedule()[0]
    base = {"experiment": s.experiment, "semantic_block": "affect", "condition": s.state_or_history, "history_seed": s.history_seed,
            "checkpoint": 200, "probe_id": s.probe_id, "option_order": s.option_order, "cell": s.cell, "request_attempt": 0,
            "parsed_choice": "A", "error_code": None}
    validate_ledger_records([base])
    with pytest.raises(ValueError, match="duplicate completed"):
        validate_ledger_records([base, dict(base, request_id="x2", request_attempt=1)])
    with pytest.raises(ValueError, match="duplicate attempt_key"):
        validate_ledger_records([base, dict(base, request_id="x2", parsed_choice=None, error_code="transport_error")])
def test_qc_returned_model():
    assert qc_returned_model("m", None) is None
    assert qc_returned_model("m", "m") == "m"
    with pytest.raises(RunStopped, match="returned_model"):
        qc_returned_model("m", "other")
def test_mock_run_writes_jsonl(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("A"))
    out = runner.run(_mini_schedule(), development=True, resume=False)
    assert out["completed"] == 2
    recs = runner.records()
    assert len(recs) == 2
    validate_ledger_records(recs)
    for field in ("protocol_hash", "config_hash", "renderer_text", "parsed_choice", "request_attempt", "error_code", "tools", "search"):
        assert recs[0][field] is not None or field == "error_code"
    assert recs[0]["error_code"] is None
def test_resume_false_rejects_nonempty_raw(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    raw.write_text("{}\n", encoding="utf-8")
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("A"))
    with pytest.raises(RunnerError, match="non-empty raw"):
        runner.run(_mini_schedule(), development=True, resume=False)
def test_resume_skips_completed(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("B"))
    runner.run(_mini_schedule()[:1], development=True, resume=False)
    out = runner.run(_mini_schedule(), development=True, resume=True)
    assert out["completed"] == 2
    assert len(runner.records()) == 2
def test_schema_error_no_provider_retry_counted_once(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    calls = {"n": 0}
    def fail(prompt, config=None):
        calls["n"] += 1
        raise SchemaError("invalid_choice_json", "bad", raw_response="bad")
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=fail)
    runner.run(_mini_schedule()[:1], development=True, resume=False)
    assert calls["n"] == 1
    rec = runner.records()[0]
    assert rec["error_code"] == "invalid_choice_json"
    assert rec["raw_response"]
def test_transport_then_success_on_resume(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    seq = {"i": 0}
    def flaky(prompt, config=None):
        seq["i"] += 1
        if seq["i"] == 1:
            raise TransportError("transport_exhausted", "429", retry_count=3)
        return _ok("A")
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=flaky)
    runner.run(_mini_schedule()[:1], development=True, resume=False)
    runner.run(_mini_schedule()[:1], development=True, resume=True)
    recs = runner.records()
    assert len(recs) == 2
    assert recs[0]["request_attempt"] == 0 and recs[1]["request_attempt"] == 1
    assert recs[0]["error_code"] == "transport_exhausted"
    assert recs[1]["parsed_choice"] == "A"
    assert recs[1]["retry_of"] == recs[0]["request_id"]
def test_transport_error_no_observation_retry(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    calls = {"n": 0}
    def fail(prompt, config=None):
        calls["n"] += 1
        raise TransportError("transport_error", "400", retry_count=0)
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=fail)
    runner.run(_mini_schedule()[:1], development=True, resume=False)
    assert calls["n"] == 1
    recs = runner.records()
    assert len(recs) == 1
    assert recs[0]["error_code"] == "transport_error"
    calls["n"] = 0
    runner.run(_mini_schedule()[:1], development=True, resume=True)
    assert calls["n"] == 0
    assert len(runner.records()) == 1

def test_same_run_transport_retry_uses_next_attempt(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    seq = {"i": 0}
    def flaky(prompt, config=None):
        seq["i"] += 1
        if seq["i"] == 1:
            raise TransportError("transport_exhausted", "500", retry_count=2)
        return _ok("A")
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=flaky)
    runner.run(_mini_schedule()[:1], development=True, resume=False)
    recs = runner.records()
    assert len(recs) == 2
    assert {r["request_attempt"] for r in recs} == {0, 1}
def test_pending_window_not_duplicated(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    spec = _mini_schedule()[0]
    rec = {"request_id": "done", "experiment": spec.experiment, "semantic_block": "affect", "condition": spec.state_or_history,
           "history_seed": spec.history_seed, "checkpoint": 200, "probe_id": spec.probe_id, "option_order": spec.option_order,
           "cell": spec.cell, "request_attempt": 0, "parsed_choice": "A", "error_code": None, "requested_model": "qwen3.7-flash-2026-07-15"}
    raw.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    ledger = rebuild_ledger(raw)
    SprintRunner(raw_path=raw, ckpt_path=ckpt).save_ckpt(ledger, [{"experiment": spec.experiment, "semantic_block": "affect", "state_or_history": spec.state_or_history,
        "history_seed": spec.history_seed, "checkpoint": 200, "probe_id": spec.probe_id, "option_order": spec.option_order, "cell": spec.cell,
        "request_attempt": 0, "retry_of": None, "request_id": "orphan"}])
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("A"))
    out = runner.run([spec], development=True, resume=True)
    assert out["completed"] == 1
    assert len(runner.records()) == 1
def test_returned_model_mismatch_aborts_run(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    calls = {"n": 0}
    def bad_model(prompt, config=None):
        calls["n"] += 1
        return CompletionResult("A", '{"choice":"A"}', "qwen3.7-flash-2026-07-15", "other-model", "r1", 1, 0)
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=bad_model)
    with pytest.raises(RunStopped, match="returned_model_mismatch"):
        runner.run(_mini_schedule()[:1], development=True, resume=False)
    recs = runner.records()
    assert len(recs) == 1
    assert recs[0]["error_code"] == "returned_model_mismatch"
    assert calls["n"] == 1

def test_mismatch_drains_inflight_parallel(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    sched = build_n_dry_run_schedule()[:6]
    lock = __import__("threading").Lock()
    state = {"n": 0, "bad": 2}
    def mixed(prompt, config=None):
        with lock:
            i = state["n"]; state["n"] += 1
        __import__("time").sleep(0.05)
        if i == state["bad"]:
            return CompletionResult("A", '{"choice":"A"}', "qwen3.7-flash-2026-07-15", "other-model", "r1", 1, 0)
        return _ok("A")
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=mixed)
    with pytest.raises(RunStopped, match="returned_model_mismatch"):
        runner.run(sched, development=True, resume=False)
    recs = runner.records()
    assert len(recs) == 6
    assert sum(1 for r in recs if r.get("error_code") == "returned_model_mismatch") == 1
    assert state["n"] == 6

def test_pending_reconcile_synthetic_failure_and_retry(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    spec = _mini_schedule()[0]
    pend = {**asdict(spec), "request_attempt": 0, "retry_of": None, "request_id": "lost"}
    ckpt.write_text(json.dumps({"completed": [], "attempt_count": 0, "fail_window": [], "pending": [pend]}), encoding="utf-8")
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("A"))
    out = runner.run(_mini_schedule()[:1], development=True, resume=True)
    recs = runner.records()
    assert out["completed"] == 1
    assert len(recs) == 2
    assert recs[0]["request_id"] == "lost" and recs[0]["error_code"] == "transport_exhausted"
    assert recs[1]["request_attempt"] == 1 and recs[1]["parsed_choice"] == "A"

def test_mock_run_records_token_usage(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    def ok_tokens(prompt, config=None):
        return CompletionResult("A", '{"choice":"A"}', "qwen3.7-flash-2026-07-15", "qwen3.7-flash-2026-07-15", "r1", 1, 0, 11, 2, 13)
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=ok_tokens)
    runner.run(_mini_schedule()[:1], development=True, resume=False)
    rec = runner.records()[0]
    assert rec["prompt_tokens"] == 11 and rec["completion_tokens"] == 2 and rec["total_tokens"] == 13
def test_transport_row_has_requested_model_and_nulls(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    def fail(prompt, config=None):
        raise TransportError("transport_exhausted", "500", retry_count=3)
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=fail)
    runner.run(_mini_schedule()[:1], development=True, resume=False)
    rec = runner.records()[0]
    assert rec["requested_model"] == "qwen3.7-flash-2026-07-15"
    assert rec["parsed_choice"] is None and rec["returned_model"] is None
    assert rec["raw_response"]
    assert "Bearer" not in rec["raw_response"]
def test_transport_failure_redacts_secrets(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    def fail(prompt, config=None):
        raise TransportError("transport_error", "Authorization: Bearer sk-testsecret123", retry_count=0)
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=fail)
    runner.run(_mini_schedule()[:1], development=True, resume=False)
    rec = runner.records()[0]
    assert rec["error_code"] == "transport_error"
    assert rec["raw_response"]
    assert "sk-testsecret" not in rec["raw_response"]
    assert "[REDACTED]" in rec["raw_response"]

def test_config_attempt_budget_literals():
    cfg = load_config()
    assert cfg["attempt_pause"] == 990
    assert cfg["attempt_hard_stop"] == 1100

def test_pause_and_hard_stop_count_http_attempts(tmp_path):
    spec = _mini_schedule()[0]
    base = {"experiment": spec.experiment, "semantic_block": "affect", "condition": spec.state_or_history, "history_seed": spec.history_seed,
            "checkpoint": 200, "probe_id": spec.probe_id, "option_order": spec.option_order, "cell": spec.cell,
            "parsed_choice": None, "error_code": "transport_exhausted", "retry_count": 3}
    def heavy_retry(prompt, config=None):
        raise TransportError("transport_exhausted", "500", retry_count=3)
    raw1, ckpt1 = tmp_path / "raw1.jsonl", tmp_path / "ckpt1.json"
    raw1.write_text(json.dumps(dict(base, request_id="r0", request_attempt=0)) + "\n", encoding="utf-8")
    cfg = dict(load_config())
    cfg["attempt_pause"] = 5
    cfg["attempt_hard_stop"] = 99
    with pytest.raises(RunPaused):
        SprintRunner(config=cfg, raw_path=raw1, ckpt_path=ckpt1, complete_fn=heavy_retry).run(_mini_schedule()[:1], development=True, resume=True)
    raw2, ckpt2 = tmp_path / "raw2.jsonl", tmp_path / "ckpt2.json"
    raw2.write_text(json.dumps(dict(base, request_id="r0", request_attempt=0)) + "\n", encoding="utf-8")
    cfg2 = dict(load_config())
    cfg2["attempt_pause"] = 99
    cfg2["attempt_hard_stop"] = 7
    with pytest.raises(RunStopped):
        SprintRunner(config=cfg2, raw_path=raw2, ckpt_path=ckpt2, complete_fn=heavy_retry).run(_mini_schedule()[:1], development=True, resume=True)

def test_pause_at_990_and_hard_stop_at_1100(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    cfg = dict(__import__("sprint.schema", fromlist=["load_config"]).load_config())
    cfg["attempt_pause"] = 2
    cfg["attempt_hard_stop"] = 3
    runner = SprintRunner(config=cfg, raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("A"))
    sched = build_n_dry_run_schedule()
    runner.run(sched[:2], development=True, resume=False)
    with pytest.raises(RunPaused):
        runner.run(sched[2:], development=True, resume=True)
    cfg["attempt_pause"] = 99
    runner2 = SprintRunner(config=cfg, raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("A"))
    with pytest.raises(RunStopped):
        runner2.run(sched[3:], development=True, resume=True)
def test_development_cap(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    cfg = dict(__import__("sprint.schema", fromlist=["load_config"]).load_config())
    cfg["development_completed_cap"] = 1
    runner = SprintRunner(config=cfg, raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("A"))
    runner.run(_mini_schedule()[:1], development=True, resume=False)
    with pytest.raises(DevelopmentCapExceeded):
        runner.run(_mini_schedule()[1:], development=True, resume=True)
def test_schema_failures_do_not_trigger_rolling_pause(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    cfg = dict(load_config())
    cfg["attempt_pause"] = 9999
    spec = _mini_schedule()[0]
    rows = []
    for i in range(100):
        rows.append({"experiment": spec.experiment, "semantic_block": "affect", "condition": f"X-{i}", "history_seed": i,
                     "checkpoint": 200, "probe_id": f"P-{i:03d}", "option_order": "AB", "cell": "", "request_id": f"r{i}",
                     "request_attempt": 0, "parsed_choice": None, "error_code": "invalid_choice_json", "retry_count": 0})
    raw.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    runner = SprintRunner(config=cfg, raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("A"))
    out = runner.run(_mini_schedule()[:1], development=True, resume=True)
    assert out["completed"] == 1

def test_fail_window_internal_retries_on_success(tmp_path):
    raw = tmp_path / "raw.jsonl"
    spec = _mini_schedule()[0]
    rec = {"experiment": spec.experiment, "semantic_block": "affect", "condition": spec.state_or_history, "history_seed": spec.history_seed,
           "checkpoint": 200, "probe_id": spec.probe_id, "option_order": spec.option_order, "cell": spec.cell, "request_id": "r0", "request_attempt": 0,
           "parsed_choice": "A", "error_code": None, "retry_count": 3}
    raw.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    ledger = rebuild_ledger(raw)
    assert ledger["attempt_count"] == 4
    assert ledger["fail_window"] == [1, 1, 1, 0]

def test_fail_window_terminal_transport_and_schema(tmp_path):
    raw = tmp_path / "raw.jsonl"
    spec = _mini_schedule()[0]
    base = {"experiment": spec.experiment, "semantic_block": "affect", "condition": spec.state_or_history, "history_seed": spec.history_seed,
            "checkpoint": 200, "probe_id": spec.probe_id, "option_order": spec.option_order, "cell": spec.cell, "request_attempt": 0, "retry_count": 3}
    transport = dict(base, request_id="t", parsed_choice=None, error_code="transport_exhausted")
    schema = dict(base, request_id="s", request_attempt=1, parsed_choice=None, error_code="invalid_choice_json", retry_count=0)
    raw.write_text("\n".join(json.dumps(x) for x in (transport, schema)) + "\n", encoding="utf-8")
    assert rebuild_ledger(raw)["fail_window"] == [1, 1, 1, 1, 0]

def test_rolling_pause_counts_success_internal_retries(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    cfg = dict(load_config()); cfg["attempt_pause"] = 9999
    spec = _mini_schedule()[0]
    base = {"experiment": spec.experiment, "semantic_block": "affect", "history_seed": spec.history_seed,
            "checkpoint": 200, "probe_id": spec.probe_id, "option_order": spec.option_order, "cell": spec.cell, "retry_count": 3}
    rows = [dict(base, condition=f"X-{i}", request_id=f"t{i}", request_attempt=0, parsed_choice=None, error_code="transport_exhausted") for i in range(23)]
    rows.append(dict(base, condition="Y-ok", request_id="ok", request_attempt=0, parsed_choice="A", error_code=None))
    raw.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    def fail(prompt, config=None):
        raise TransportError("transport_exhausted", "500", retry_count=3)
    runner = SprintRunner(config=cfg, raw_path=raw, ckpt_path=ckpt, complete_fn=fail)
    with pytest.raises(RunPaused, match="rolling failure"):
        runner.run(_mini_schedule()[:1], development=True, resume=True)

def test_rolling_failure_pause(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    cfg = dict(__import__("sprint.schema", fromlist=["load_config"]).load_config())
    cfg["attempt_pause"] = 9999
    spec = _mini_schedule()[0]
    base = {"experiment": spec.experiment, "semantic_block": "affect", "condition": spec.state_or_history, "history_seed": spec.history_seed,
            "checkpoint": 200, "probe_id": spec.probe_id, "option_order": spec.option_order, "cell": spec.cell, "parsed_choice": None, "error_code": "transport_exhausted", "retry_count": 0}
    raw.write_text("\n".join(json.dumps(dict(base, request_id=f"r{i}", request_attempt=i)) for i in range(99)) + "\n", encoding="utf-8")
    def fail(prompt, config=None):
        raise TransportError("transport_exhausted", "500", retry_count=3)
    runner = SprintRunner(config=cfg, raw_path=raw, ckpt_path=ckpt, complete_fn=fail)
    with pytest.raises(RunPaused, match="rolling failure"):
        runner.run(_mini_schedule()[:1], development=True, resume=True)

def test_rolling_failure_pause_counts_http_units(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    cfg = dict(load_config()); cfg["attempt_pause"] = 9999
    spec = _mini_schedule()[0]
    base = {"experiment": spec.experiment, "semantic_block": "affect", "condition": spec.state_or_history, "history_seed": spec.history_seed,
            "checkpoint": 200, "probe_id": spec.probe_id, "option_order": spec.option_order, "cell": spec.cell,
            "parsed_choice": None, "error_code": "transport_exhausted", "retry_count": 3}
    raw.write_text("\n".join(json.dumps(dict(base, request_id=f"r{i}", request_attempt=i)) for i in range(24)) + "\n", encoding="utf-8")
    def fail(prompt, config=None):
        raise TransportError("transport_exhausted", "500", retry_count=3)
    runner = SprintRunner(config=cfg, raw_path=raw, ckpt_path=ckpt, complete_fn=fail)
    with pytest.raises(RunPaused, match="rolling failure"):
        runner.run(_mini_schedule()[:1], development=True, resume=True)
def test_single_writer_serializes(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("A"))
    runner.run(build_n_dry_run_schedule(), development=True, resume=False)
    lines = raw.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 8
    validate_ledger_records([json.loads(x) for x in lines])
def test_max_workers_six(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    active = {"n": 0, "max": 0}
    lock = __import__("threading").Lock()
    def slow(prompt, config=None):
        with lock:
            active["n"] += 1; active["max"] = max(active["max"], active["n"])
        __import__("time").sleep(0.05)
        with lock: active["n"] -= 1
        return _ok("A")
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=slow)
    runner.run(build_n_dry_run_schedule(), development=True, resume=False)
    assert active["max"] <= 6

def test_formal_schedule_rejected_under_development(tmp_path):
    ok_fn = lambda prompt, config=None: _ok("A")
    for sched in (build_formal_e_schedule(), build_formal_n_schedule(), interleave_formal_schedules()):
        raw, ckpt = tmp_path / f"raw-{id(sched)}.jsonl", tmp_path / f"ckpt-{id(sched)}.json"
        runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=ok_fn)
        with pytest.raises(RunnerError, match="development=False"):
            runner.run(sched, development=True, resume=False)
    for name, sched in (("stability", build_stability_schedule()), ("e", build_e_dry_run_schedule()), ("n", build_n_dry_run_schedule())):
        raw, ckpt = tmp_path / f"{name}.jsonl", tmp_path / f"{name}-ckpt.json"
        SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=ok_fn).run(sched, development=True, resume=False)

def test_stale_ckpt_completed_ignored_when_raw_disagrees(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    spec = _mini_schedule()[0]
    rec = {"request_id": "done", "experiment": spec.experiment, "semantic_block": "affect", "condition": spec.state_or_history,
           "history_seed": spec.history_seed, "checkpoint": 200, "probe_id": spec.probe_id, "option_order": spec.option_order,
           "cell": spec.cell, "request_attempt": 0, "parsed_choice": "A", "error_code": None, "requested_model": "qwen3.7-flash-2026-07-15", "retry_count": 0}
    raw.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    stale_key = list(build_n_dry_run_schedule()[1].observation_key())
    ckpt.write_text(json.dumps({"completed": [stale_key], "attempt_count": 99, "fail_window": [], "pending": None}), encoding="utf-8")
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("B"))
    out = runner.run(_mini_schedule(), development=True, resume=True)
    assert out["completed"] == 2
    assert len(runner.records()) == 2

def _run_stability_records(tmp_path, complete_fn=None):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=complete_fn or (lambda prompt, config=None: _ok("A")))
    runner.run(build_stability_schedule(), development=True, resume=False)
    return runner.records()

def test_assert_stability_gate_pass(tmp_path):
    assert_stability_gate(_run_stability_records(tmp_path))
    sub = tmp_path / "null"; sub.mkdir()
    null_fn = lambda prompt, config=None: CompletionResult("A", '{"choice":"A"}', "qwen3.7-flash-2026-07-15", None, "r9", 1, 0, 10, 1, 11)
    assert_stability_gate(_run_stability_records(sub, complete_fn=null_fn))

def test_assert_stability_gate_incomplete_count(tmp_path):
    recs = _run_stability_records(tmp_path)
    with pytest.raises(RunnerError, match="36 unique completed"):
        assert_stability_gate(recs[:-1])

def test_assert_stability_gate_unparseable_row(tmp_path):
    recs = _run_stability_records(tmp_path)
    recs[0]["parsed_choice"] = None
    recs[0]["error_code"] = "invalid_choice_json"
    with pytest.raises(RunnerError, match="36 unique completed"):
        assert_stability_gate(recs)

def test_assert_stability_gate_semantic_triplet_mismatch(tmp_path):
    recs = _run_stability_records(tmp_path)
    by_text: dict[str, list] = {}
    for r in recs:
        by_text.setdefault(r["renderer_text"], []).append(r)
    tgt = next(g for g in by_text.values() if len(g) == 3)
    tgt[0]["parsed_choice"] = "B" if tgt[0]["parsed_choice"] == "A" else "A"
    with pytest.raises(RunnerError, match="payload triplet"):
        assert_stability_gate(recs)

def test_assert_stability_gate_requested_model_mismatch(tmp_path):
    recs = _run_stability_records(tmp_path)
    recs[0]["requested_model"] = "other-model"
    with pytest.raises(RunnerError, match="request flags or model mismatch"):
        assert_stability_gate(recs)

def test_assert_stability_gate_returned_model_mismatch(tmp_path):
    recs = _run_stability_records(tmp_path)
    recs[0]["returned_model"] = "other-model"
    with pytest.raises(RunnerError, match="request flags or model mismatch"):
        assert_stability_gate(recs)

def test_assert_stability_gate_enable_thinking(tmp_path):
    recs = _run_stability_records(tmp_path)
    recs[0]["enable_thinking"] = True
    with pytest.raises(RunnerError, match="request flags or model mismatch"):
        assert_stability_gate(recs)

def test_assert_stability_gate_tools_search_off(tmp_path):
    recs = _run_stability_records(tmp_path)
    assert all(r.get("tools") == "off" and r.get("search") == "off" for r in recs)
    recs[0]["tools"] = "on"
    with pytest.raises(RunnerError, match="request flags or model mismatch"):
        assert_stability_gate(recs)

def test_assert_stability_gate_null_tokens_reject(tmp_path):
    recs = _run_stability_records(tmp_path)
    recs[0]["prompt_tokens"] = None
    with pytest.raises(RunnerError, match="invalid 'prompt_tokens'"):
        assert_stability_gate(recs)

def test_whitespace_response_passes_stability_gate(tmp_path):
    from types import SimpleNamespace
    from sprint.provider_qwen import complete_choice
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=1, total_tokens=11)
    resp = SimpleNamespace(id="r1", model="qwen3.7-flash-2026-07-15", choices=[SimpleNamespace(message=SimpleNamespace(content='\n {"choice":"A"} \n'))], usage=usage)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: resp)))
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: complete_choice(prompt, config=load_config(), client=client, sleep=lambda _: None))
    runner.run(build_stability_schedule(), development=True, resume=False)
    recs = runner.records()
    assert all(r["raw_response"] == '{"choice":"A"}' for r in recs)
    assert_stability_gate(recs)

def test_run_stability_gate_only_mock(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("A"))
    out = run_stability_gate_only(runner, resume=False)
    assert out["completed"] == 36
    recs = runner.records()
    assert all(r["experiment"] == "stability" for r in recs)
    assert len(recs) == 36

def test_assert_stability_gate_forbidden_response_content(tmp_path):
    recs = _run_stability_records(tmp_path)
    recs[0]["raw_response"] = '{"choice":"A","reasoning_content":"hidden"}'
    with pytest.raises(RunnerError, match="raw_response invalid"):
        assert_stability_gate(recs)

def test_assert_stability_gate_missing_fields(tmp_path):
    recs = _run_stability_records(tmp_path)
    del recs[0]["response_id"]
    with pytest.raises(RunnerError, match="missing or empty 'response_id'"):
        assert_stability_gate(recs)
    sub = tmp_path / "tok"; sub.mkdir()
    recs2 = _run_stability_records(sub)
    recs2[0]["prompt_tokens"] = None
    with pytest.raises(RunnerError, match="invalid 'prompt_tokens'"):
        assert_stability_gate(recs2)

def test_stability_schedule_payload_triplets(tmp_path):
    import hashlib
    sched = build_stability_schedule()
    assert len(sched) == 36
    groups: dict[str, list] = {}
    runner = SprintRunner(raw_path=tmp_path / "r.jsonl", ckpt_path=tmp_path / "c.json", complete_fn=lambda prompt, config=None: _ok("A"))
    for spec in sched:
        row = runner.probes[spec.probe_id]
        text, *_ = __import__("sprint.runner", fromlist=["_prompt"])._prompt(spec, row)
        groups.setdefault(hashlib.sha256(text.encode()).hexdigest(), []).append(spec)
    assert len(groups) == 12
    assert all(len(v) == 3 for v in groups.values())

def test_crash_after_raw_before_ckpt_clear(tmp_path):
    raw, ckpt = tmp_path / "raw.jsonl", tmp_path / "ckpt.json"
    spec = _mini_schedule()[0]
    rec = {"request_id": "done", "experiment": spec.experiment, "semantic_block": "affect", "condition": spec.state_or_history,
           "history_seed": spec.history_seed, "checkpoint": 200, "probe_id": spec.probe_id, "option_order": spec.option_order,
           "cell": spec.cell, "request_attempt": 0, "parsed_choice": "A", "error_code": None, "requested_model": "qwen3.7-flash-2026-07-15", "retry_count": 0}
    raw.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    ledger = rebuild_ledger(raw)
    SprintRunner(raw_path=raw, ckpt_path=ckpt).save_ckpt(ledger, [{"experiment": spec.experiment, "semantic_block": "affect", "state_or_history": spec.state_or_history,
        "history_seed": spec.history_seed, "checkpoint": 200, "probe_id": spec.probe_id, "option_order": spec.option_order, "cell": spec.cell,
        "request_attempt": 1, "retry_of": "done", "request_id": "orphan"}])
    runner = SprintRunner(raw_path=raw, ckpt_path=ckpt, complete_fn=lambda prompt, config=None: _ok("A"))
    out = runner.run([spec], development=True, resume=True)
    assert out["completed"] == 1
    assert len(runner.records()) == 1
