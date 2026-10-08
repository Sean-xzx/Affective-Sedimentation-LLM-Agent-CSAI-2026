"""Material schema, replay derivation, and manifest checks (protocol §3.1–3.2)."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from sprint.histories import full_history_manifest_sha256
from sprint.manifest import (
    D6_INVENTORY_PATH,
    EXPECTED_PROBE_IDS,
    PROBE_FIELDS,
    REVIEW_PASS_MARKER,
    ProbeRow,
    assert_probe_material_rules,
    assert_probe_schema,
    assert_probes_filled,
    assert_probes_reviewed,
    assert_replay_derivation,
    assert_token_balance,
    build_material_manifest,
    build_sprint_manifest,
    canonical_probe_token_ids,
    config_hash,
    derive_all_replay_probe_ids,
    load_probes,
    probe_subset_hash,
    protocol_hash,
    replay_selection_hash,
    sync_probe_derived_fields,
    SPRINT_MANIFEST_PATH,
)
from sprint.renderer import renderer_template_hash

EXPECTED_REPLAY_IDS = {
    "P": ["P-C01", "P-C05", "P-C02"], "A": ["A-C04", "A-C03", "A-C02"],
    "D": ["D-C05", "D-C04", "D-C03"],
}
GOLDEN_FULL_HISTORY_MANIFEST_SHA256 = "b75fe612d978c5e2f647ce037b04087bf7ea6fbdc3d6ca7ff2e074117a5c94f5"
DEV_PROBE_IDS = frozenset(f"{d}-{s}" for d in "PAD" for s in ("D01", "D02"))
FORMAL_PROBE_IDS = frozenset(f"{d}-C{i:02d}" for d in "PAD" for i in range(1, 6))


def derive_replay_probe_ids(dimension: str) -> list[str]:
    return derive_all_replay_probe_ids()[dimension]


def _mock_encode(text: str) -> list[int]:
    return list(range(len(text.split())))


def test_expected_probe_ids():
    ids = list(EXPECTED_PROBE_IDS)
    assert len(ids) == 21
    assert len(set(ids)) == 21
    assert ids[0] == "P-D01"
    assert "D-C05" in ids


def test_load_probes_schema():
    probes = load_probes()
    assert len(probes) == 21
    assert_probe_schema(probes)


def test_dev_formal_disjoint():
    probes = load_probes()
    dev = {row.probe_id for row in probes if row.set == "dev"}
    formal = {row.probe_id for row in probes if row.set == "formal"}
    assert dev == DEV_PROBE_IDS
    assert formal == FORMAL_PROBE_IDS
    assert not dev.intersection(formal)


def test_replay_derivation_per_dimension():
    assert derive_replay_probe_ids("P") == EXPECTED_REPLAY_IDS["P"]
    assert derive_replay_probe_ids("A") == EXPECTED_REPLAY_IDS["A"]
    assert derive_replay_probe_ids("D") == EXPECTED_REPLAY_IDS["D"]
    assert derive_all_replay_probe_ids() == EXPECTED_REPLAY_IDS


def test_replay_derivation_gate():
    assert_replay_derivation()


def test_replay_derivation_raises_under_python_o():
    import subprocess
    import sys
    from pathlib import Path
    code = (
        "import sprint.manifest as m\n"
        "m.derive_all_replay_probe_ids = lambda: {'P': ['X'], 'A': [], 'D': []}\n"
        "try:\n"
        "    m.assert_replay_derivation()\n"
        "    print('NOFAIL')\n"
        "except AssertionError:\n"
        "    print('FAIL_OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-O", "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert result.returncode == 0, result.stderr
    assert "FAIL_OK" in result.stdout
    assert "NOFAIL" not in result.stdout


def test_replay_selection_hash_stable():
    h1 = replay_selection_hash()
    h2 = replay_selection_hash(EXPECTED_REPLAY_IDS)
    assert h1 == h2
    assert len(h1) == 64


def test_probe_subset_hashes():
    probes = load_probes()
    dev_hash = probe_subset_hash(probes, "dev")
    formal_hash = probe_subset_hash(probes, "formal")
    assert dev_hash != formal_hash
    assert len(dev_hash) == 64


def test_probe_subset_hash_includes_material_body():
    probes = load_probes()
    base = probe_subset_hash(probes, "dev")
    row = next(r for r in probes if r.probe_id == "P-D01")
    payload = asdict(row)
    payload["high_option"] = "Draft option text."
    mutated_row = ProbeRow(**payload)
    mutated_probes = [mutated_row if r.probe_id == row.probe_id else r for r in probes]
    assert probe_subset_hash(mutated_probes, "dev") != base


def test_build_material_manifest_fields(monkeypatch, tmp_path):
    frozen_before = (
        D6_INVENTORY_PATH.read_bytes() if D6_INVENTORY_PATH.is_file() else None
    )
    monkeypatch.setattr("sprint.schema.default_token_encoder", lambda: _mock_encode)
    mock_path = tmp_path / "mock_renderer_d6_inventory.json"
    manifest = build_material_manifest(encode=_mock_encode, inventory_path=mock_path)
    assert manifest["d6_inventory_frozen"] is False
    assert manifest["replay_probe_ids"] == EXPECTED_REPLAY_IDS
    assert manifest["tokenizer"] == "qwen3.7-flash-2026-07-15"
    assert manifest["tokenizer_load_id"] == "Qwen/Qwen3-0.6B"
    assert manifest["tokenizer_agent_model"] == "qwen3.7-flash-2026-07-15"
    assert manifest["renderer_hash"] == renderer_template_hash("affect")
    assert manifest["placebo_hash"] == renderer_template_hash("placebo")
    assert len(manifest["formal_probe_hash"]) == 64
    assert len(manifest["dev_probe_hash"]) == 64
    inventory = manifest["renderer_d6_inventory"]
    records = inventory["records"]
    assert len(records) == 14
    assert inventory["tokenizer"] == "injected_encoder"
    assert inventory["tokenizer_load_id"] == "injected_encoder"
    assert manifest["tokenizer"] == "qwen3.7-flash-2026-07-15"
    assert manifest["tokenizer_load_id"] == "Qwen/Qwen3-0.6B"
    assert len(manifest["renderer_d6_inventory_hash"]) == 64
    assert len({r["text_sha256"] for r in records}) == 14
    for record in records:
        assert isinstance(record["text"], str) and record["text"]
        assert record["text_sha256"] == hashlib.sha256(record["text"].encode()).hexdigest()
        assert isinstance(record["token_ids"], list) and record["token_ids"]
        assert record["token_count"] > 0
        assert record["token_count"] == len(record["token_ids"])
        assert len(record["token_ids_sha256"]) == 64
        assert record["token_ids"] == list(range(len(record["text"].split())))
    assert mock_path.is_file()
    frozen_bytes = mock_path.read_bytes()
    assert manifest["renderer_d6_inventory_hash"] == hashlib.sha256(frozen_bytes).hexdigest()
    frozen = json.loads(frozen_bytes.decode("utf-8"))
    assert frozen == inventory
    if frozen_before is not None:
        assert D6_INVENTORY_PATH.read_bytes() == frozen_before


def test_renderer_d6_frozen_inventory_uses_real_tokenizer():
    manifest = build_material_manifest()
    assert manifest["d6_inventory_frozen"] is True
    frozen_bytes = D6_INVENTORY_PATH.read_bytes()
    assert manifest["renderer_d6_inventory_hash"] == hashlib.sha256(frozen_bytes).hexdigest()
    doc = json.loads(frozen_bytes.decode("utf-8"))
    assert doc == manifest["renderer_d6_inventory"]
    assert doc["tokenizer_load_id"] == "Qwen/Qwen3-0.6B"
    assert doc["tokenizer"] == "qwen3.7-flash-2026-07-15"
    assert len(doc["records"]) == 14
    for record in doc["records"]:
        token_ids = record["token_ids"]
        assert isinstance(token_ids, list) and token_ids
        assert token_ids != list(range(len(token_ids)))


def test_real_encode_tmp_path_does_not_overwrite_frozen(tmp_path):
    frozen_before = (
        D6_INVENTORY_PATH.read_bytes() if D6_INVENTORY_PATH.is_file() else None
    )
    out_path = tmp_path / "d6_inventory.json"
    manifest = build_material_manifest(inventory_path=out_path)
    assert manifest["d6_inventory_frozen"] is True
    assert out_path.is_file()
    out_bytes = out_path.read_bytes()
    assert manifest["renderer_d6_inventory_hash"] == hashlib.sha256(out_bytes).hexdigest()
    assert json.loads(out_bytes.decode("utf-8")) == manifest["renderer_d6_inventory"]
    assert manifest["renderer_d6_inventory"]["tokenizer_load_id"] == "Qwen/Qwen3-0.6B"
    if frozen_before is not None:
        assert D6_INVENTORY_PATH.read_bytes() == frozen_before


def test_injected_encoder_cannot_write_frozen_path(monkeypatch):
    monkeypatch.setattr("sprint.schema.default_token_encoder", lambda: _mock_encode)
    with pytest.raises(ValueError, match="injected encoder cannot write"):
        build_material_manifest(encode=_mock_encode, inventory_path=D6_INVENTORY_PATH)


def test_token_balance_mock_encoder():
    assert_token_balance("one two three", "one two four", encode=_mock_encode)
    with pytest.raises(AssertionError, match="Token imbalance"):
        assert_token_balance("one two three four five six", "one", encode=_mock_encode)


def test_token_balance_skips_empty_options():
    assert_token_balance("", "anything", encode=_mock_encode)
    assert_token_balance("filled", "", encode=_mock_encode)


def test_forbidden_label_detection():
    row = ProbeRow(
        probe_id="P-D01",
        target_dimension="P",
        scenario_family="",
        neutral_scenario="A warm response would help.",
        high_option="",
        low_option="",
        semantic_key="P-D01",
        ab_rendering="",
        ba_rendering="",
        token_ids="",
        review_flags="",
        set="dev",
    )
    with pytest.raises(AssertionError, match="forbidden label"):
        assert_probe_material_rules(row)


def test_ab_ba_rendering_when_filled(monkeypatch):
    monkeypatch.setattr("sprint.schema.default_token_encoder", lambda: _mock_encode)
    row = ProbeRow(
        probe_id="P-D01",
        target_dimension="P",
        scenario_family="family",
        neutral_scenario="Neutral setting.",
        high_option="Take the direct route.",
        low_option="Take the scenic route.",
        semantic_key="sk1",
        ab_rendering="Option A\nTake the direct route.\n\nOption B\nTake the scenic route.",
        ba_rendering="Option A\nTake the scenic route.\n\nOption B\nTake the direct route.",
        token_ids=canonical_probe_token_ids(
            "Take the direct route.", "Take the scenic route.", encode=_mock_encode
        ),
        review_flags="",
        set="dev",
    )
    assert_probe_material_rules(row, encode=_mock_encode)


def _scaffold_row(**overrides) -> ProbeRow:
    base = dict(
        probe_id="P-D01",
        target_dimension="P",
        scenario_family="",
        neutral_scenario="",
        high_option="",
        low_option="",
        semantic_key="P-D01",
        ab_rendering="",
        ba_rendering="",
        token_ids="",
        review_flags="",
        set="dev",
    )
    base.update(overrides)
    return ProbeRow(**base)


def test_forbidden_label_in_scenario_family():
    row = _scaffold_row(scenario_family="warm interpersonal setting")
    with pytest.raises(AssertionError, match="forbidden label in scenario_family"):
        assert_probe_material_rules(row)


@pytest.mark.parametrize(
    "field,text",
    [
        ("neutral_scenario", "The P axis should guide the response."),
        ("scenario_family", "Context involving P/A/D labels."),
        ("neutral_scenario", "Follow the D dimension instead."),
        ("neutral_scenario", "Compare outcomes on the A axis."),
    ],
)
def test_pad_axis_label_detection(field, text):
    row = _scaffold_row(**{field: text})
    with pytest.raises(AssertionError, match="P/A/D axis label"):
        assert_probe_material_rules(row)


def test_parenthetical_a_passes_pad_axis_gate():
    row = _scaffold_row(scenario_family="Context for (A) manipulation.")
    assert_probe_material_rules(row)


def test_pad_axis_label_in_options(monkeypatch):
    monkeypatch.setattr("sprint.schema.default_token_encoder", lambda: _mock_encode)
    row = sync_probe_derived_fields(
        _scaffold_row(
            scenario_family="work",
            neutral_scenario="Neutral context.",
            high_option="Choose the path aligned with P/A/D.",
            low_option="Take the scenic route.",
            semantic_key="sk1",
        ),
        encode=_mock_encode,
    )
    with pytest.raises(AssertionError, match="P/A/D axis label"):
        assert_probe_material_rules(row, encode=_mock_encode)


def test_scaffold_empty_body_passes_pad_axis_gate():
    assert_probe_material_rules(_scaffold_row())


def test_action_label_in_scenario_family():
    row = _scaffold_row(scenario_family="context for praise exchange")
    with pytest.raises(AssertionError, match="action label leaked in scenario_family"):
        assert_probe_material_rules(row)


def test_disagreement_passes_action_label_gate():
    row = _scaffold_row(
        neutral_scenario="The team reached disagreement on the timeline.",
    )
    assert_probe_material_rules(row)


def test_disagree_word_fails_action_label_gate():
    row = _scaffold_row(neutral_scenario="You disagree with the proposed plan.")
    with pytest.raises(AssertionError, match="action label leaked"):
        assert_probe_material_rules(row)


def test_praise_word_fails_action_label_gate():
    row = _scaffold_row(neutral_scenario="Offer praise for the effort.")
    with pytest.raises(AssertionError, match="action label leaked"):
        assert_probe_material_rules(row)


def test_partial_option_fill_fails():
    row = _scaffold_row(high_option="Only one side filled.")
    with pytest.raises(AssertionError, match="partial fill"):
        assert_probe_material_rules(row)


def test_token_balance_enforced_when_both_options_filled():
    with pytest.raises(AssertionError, match="Token imbalance"):
        assert_token_balance("one two three four five six", "one", encode=_mock_encode)


def test_material_rules_invokes_token_balance(monkeypatch):
    monkeypatch.setattr("sprint.schema.default_token_encoder", lambda: _mock_encode)
    row = sync_probe_derived_fields(
        ProbeRow(
            probe_id="P-D01",
            target_dimension="P",
            scenario_family="family",
            neutral_scenario="Neutral setting.",
            high_option="Take the direct route.",
            low_option="Take the scenic route.",
            semantic_key="sk1",
            ab_rendering="",
            ba_rendering="",
            token_ids="",
            review_flags="",
            set="dev",
        ),
        encode=_mock_encode,
    )
    calls: list[tuple[str, str]] = []

    def _record(h: str, l: str, encode=None) -> None:
        calls.append((h, l))

    monkeypatch.setattr("sprint.manifest.assert_token_balance", _record)
    assert_probe_material_rules(row, encode=_mock_encode)
    assert calls == [(row.high_option, row.low_option)]


def test_missing_scenario_family_fails_partial_fill():
    row = _scaffold_row(
        neutral_scenario="Context.",
        high_option="Option A text.",
        low_option="Option B text.",
        semantic_key="sk1",
        ab_rendering="Option A\nOption A text.\n\nOption B\nOption B text.",
        ba_rendering="Option A\nOption B text.\n\nOption B\nOption A text.",
        token_ids='{"high":[0],"low":[0]}',
    )
    with pytest.raises(AssertionError, match="partial fill"):
        assert_probe_material_rules(row, encode=_mock_encode)


def test_missing_token_ids_fails_partial_fill():
    row = _scaffold_row(
        scenario_family="work",
        neutral_scenario="Context.",
        high_option="Option A text.",
        low_option="Option B text.",
        semantic_key="sk1",
        ab_rendering="Option A\nOption A text.\n\nOption B\nOption B text.",
        ba_rendering="Option A\nOption B text.\n\nOption B\nOption A text.",
    )
    with pytest.raises(AssertionError, match="partial fill"):
        assert_probe_material_rules(row, encode=_mock_encode)


def test_token_ids_mismatch_fails():
    row = _scaffold_row(
        scenario_family="work",
        neutral_scenario="Context.",
        high_option="Option A text.",
        low_option="Option B text.",
        semantic_key="sk1",
        ab_rendering="Option A\nOption A text.\n\nOption B\nOption B text.",
        ba_rendering="Option A\nOption B text.\n\nOption B\nOption A text.",
        token_ids='{"high":[99],"low":[99]}',
    )
    with pytest.raises(AssertionError, match="token_ids mismatch"):
        assert_probe_material_rules(row, encode=_mock_encode)


def test_sync_probe_derived_fields():
    row = _scaffold_row(
        scenario_family="work",
        neutral_scenario="Context.",
        high_option="Alpha path.",
        low_option="Beta path.",
        semantic_key="sk1",
    )
    synced = sync_probe_derived_fields(row, encode=_mock_encode)
    assert synced.token_ids == canonical_probe_token_ids(
        "Alpha path.", "Beta path.", encode=_mock_encode
    )
    assert "Option A" in synced.ab_rendering


def test_assert_probes_filled_fails_on_scaffold():
    probes = [
        _scaffold_row(
            probe_id=pid,
            target_dimension=pid.split("-", 1)[0],
            set="dev" if pid.endswith(("D01", "D02")) else "formal",
            semantic_key=pid,
        )
        for pid in EXPECTED_PROBE_IDS
    ]
    with pytest.raises(AssertionError, match="unfilled fields"):
        assert_probes_filled(probes, encode=_mock_encode)


def test_assert_probes_filled_passes_on_materials():
    assert_probes_filled()


def test_assert_probes_reviewed_passes_on_materials():
    assert_probes_reviewed()


def test_assert_probes_reviewed_fails_on_empty_flags():
    probes = load_probes()
    unreviewed = [
        ProbeRow(**{**asdict(row), "review_flags": ""})
        if row.probe_id == "P-D01"
        else row
        for row in probes
    ]
    with pytest.raises(AssertionError, match="dual_pass_ok"):
        assert_probes_reviewed(unreviewed)


def test_assert_probes_reviewed_fails_on_scaffold():
    probes = [
        _scaffold_row(
            probe_id=pid,
            target_dimension=pid.split("-", 1)[0],
            set="dev" if pid.endswith(("D01", "D02")) else "formal",
            semantic_key=pid,
            review_flags=REVIEW_PASS_MARKER,
        )
        for pid in EXPECTED_PROBE_IDS
    ]
    with pytest.raises(AssertionError, match="unfilled fields"):
        assert_probes_reviewed(probes, encode=_mock_encode)


def _reviewed_probes() -> list[ProbeRow]:
    return [
        ProbeRow(**{**asdict(row), "review_flags": REVIEW_PASS_MARKER})
        for row in load_probes()
    ]


def test_build_sprint_manifest_rejects_unreviewed():
    unreviewed = [
        ProbeRow(**{**asdict(row), "review_flags": ""})
        for row in load_probes()
    ]
    with pytest.raises(AssertionError, match="dual_pass_ok"):
        build_sprint_manifest(probes=unreviewed, write=False)


def test_build_sprint_manifest_rejects_injected_encoder():
    with pytest.raises(ValueError, match="encode must be None"):
        build_sprint_manifest(probes=_reviewed_probes(), encode=_mock_encode, write=False)


def test_protocol_and_config_hash_distinct():
    p_hash, c_hash = protocol_hash(), config_hash()
    assert len(p_hash) == len(c_hash) == 64
    assert p_hash != c_hash


def test_build_sprint_manifest_d6_bytes_unchanged():
    frozen_before = (
        D6_INVENTORY_PATH.read_bytes() if D6_INVENTORY_PATH.is_file() else None
    )
    build_sprint_manifest(probes=_reviewed_probes(), write=False, freeze_utc="2026-08-06T12:00:00Z")
    if frozen_before is not None:
        assert D6_INVENTORY_PATH.read_bytes() == frozen_before


def test_build_sprint_manifest_writes_tmp_only(tmp_path):
    formal_before = (
        SPRINT_MANIFEST_PATH.read_bytes() if SPRINT_MANIFEST_PATH.is_file() else None
    )
    out = tmp_path / "sprint_manifest.json"
    manifest = build_sprint_manifest(
        probes=_reviewed_probes(),
        manifest_path=out,
        freeze_utc="2026-08-06T12:00:00Z",
    )
    assert out.is_file()
    frozen_bytes = out.read_bytes()
    assert json.loads(frozen_bytes.decode("utf-8")) == manifest
    assert manifest["renderer_d6_inventory_hash"] == hashlib.sha256(
        D6_INVENTORY_PATH.read_bytes()
    ).hexdigest()
    assert manifest["replay_probe_ids"] == EXPECTED_REPLAY_IDS
    assert manifest["replay_selection_hash"] == replay_selection_hash()
    assert manifest["analysis_code_hash"] is not None
    assert manifest["randomization_manifest_hash"] is not None
    assert manifest["enable_thinking"] is False
    assert manifest["requested_model"] == "qwen3.7-flash-2026-07-15"
    assert manifest["tokenizer_load_id"] == "Qwen/Qwen3-0.6B"
    assert len(manifest["protocol_hash"]) == 64
    assert len(manifest["config_hash"]) == 64
    assert manifest["protocol_hash"] != manifest["config_hash"]
    assert manifest["history_manifest_hash"] == GOLDEN_FULL_HISTORY_MANIFEST_SHA256
    assert manifest["freeze_utc"] == "2026-08-06T12:00:00Z"
    if formal_before is not None:
        assert SPRINT_MANIFEST_PATH.read_bytes() == formal_before
    else:
        assert not SPRINT_MANIFEST_PATH.is_file()


def test_build_sprint_manifest_replay_derivation():
    manifest = build_sprint_manifest(
        probes=_reviewed_probes(),
        write=False,
        freeze_utc="2026-08-06T12:00:00Z",
    )
    assert manifest["replay_probe_ids"] == derive_all_replay_probe_ids()
    assert_replay_derivation()


def test_assert_probes_filled_forwards_encode(monkeypatch):
    probes = load_probes()
    calls: list[str] = []

    def _track(row, encode=None):
        calls.append(row.probe_id)

    monkeypatch.setattr("sprint.manifest.assert_probe_material_rules", _track)
    assert_probe_schema(probes, encode=_mock_encode)
    assert len(calls) == 21


def test_token_ids_strip_whitespace_mismatch_fails():
    row = _scaffold_row(
        scenario_family="work",
        neutral_scenario="Context.",
        high_option="Option A text.",
        low_option="Option B text.",
        semantic_key="sk1",
        ab_rendering="Option A\nOption A text.\n\nOption B\nOption B text.",
        ba_rendering="Option A\nOption B text.\n\nOption B\nOption A text.",
        token_ids='  {"high":[99],"low":[99]}  ',
    )
    with pytest.raises(AssertionError, match="token_ids mismatch"):
        assert_probe_material_rules(row, encode=_mock_encode)


def _write_probes(rows: list[ProbeRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROBE_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({f: getattr(row, f) for f in PROBE_FIELDS})


def test_write_probes_round_trip(tmp_path):
    src = load_probes()
    path = tmp_path / "probes.csv"
    _write_probes(src, path=path)
    text = path.read_text(encoding="utf-8")
    assert all(ch.isascii() for ch in text)
    header = text.splitlines()[0]
    assert header.split(",") == list(PROBE_FIELDS)
    roundtrip = load_probes(path=path)
    assert len(roundtrip) == len(src)
    assert [asdict(r) for r in roundtrip] == [asdict(r) for r in src]
