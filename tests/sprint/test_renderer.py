"""Gate D6 and renderer assembly checks (protocol §3.3–3.6)."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from sprint.histories import build_history_actions, derive_measure_seed_ids, run_history
from sprint.renderer import (
    AFFECT_BODY,
    BASE_ROLE,
    OUTPUT_INSTRUCTION,
    PLACEBO_BODY,
    assemble_request,
    assert_no_negative_zero,
    assert_renderer_d6,
    render_ab_ba_sections,
    render_event_memory,
    render_full_block,
    render_metadata,
    renderer_template_hash,
)
from sprint.schema import ENDPOINT_RAW_S, ENDPOINT_Z_RENDERED, TARGET_OF, render_z


def test_r1_and_placebo_templates_verbatim():
    assert BASE_ROLE == (
        "You are a member of a small group that has worked together over time."
    )
    assert "long-term affect coordinates" in AFFECT_BODY
    assert "room sensor coordinates" in PLACEBO_BODY
    assert '[LONG_TERM_AFFECT]' in render_metadata("affect", np.zeros(3))
    assert '[ROOM_METADATA]' in render_metadata("placebo", np.zeros(3))
    assert "Return exactly one JSON object" in OUTPUT_INSTRUCTION


def test_endpoint_rendered_z_matches_protocol():
    idx = {"P": 0, "A": 1, "D": 2}
    for name, raw in ENDPOINT_RAW_S.items():
        rendered = render_z(raw)
        if name == "ORIGIN":
            assert rendered == ("+0.000", "+0.000", "+0.000")
            continue
        axis = TARGET_OF[name]
        axis_idx = idx[axis]
        assert rendered[axis_idx] == ENDPOINT_Z_RENDERED[name]
        for j in range(3):
            if j != axis_idx:
                assert rendered[j] == "+0.000"


def test_renderer_d6_no_collision_and_no_negative_zero():
    def _mock_encode(text: str) -> list[int]:
        return list(range(len(text)))

    inventory = assert_renderer_d6(encode=_mock_encode)
    assert len(inventory) == 14
    assert len({r["text_sha256"] for r in inventory}) == 14
    for record in inventory:
        assert isinstance(record["text"], str) and record["text"]
        assert record["text_sha256"] == hashlib.sha256(record["text"].encode()).hexdigest()
        assert isinstance(record["token_ids"], list) and record["token_ids"]
        assert record["token_count"] > 0
        assert record["token_count"] == len(record["token_ids"])
        assert len(record["token_ids_sha256"]) == 64
        assert record["token_ids_sha256"] == hashlib.sha256(
            json.dumps(record["token_ids"], separators=(",", ":")).encode()
        ).hexdigest()
    for name, raw in ENDPOINT_RAW_S.items():
        assert_no_negative_zero(render_full_block("affect", raw))
        assert_no_negative_zero(render_full_block("placebo", raw))


def test_renderer_d6_defaults_encode(monkeypatch):
    def _mock_encode(text: str) -> list[int]:
        return [len(text)]

    monkeypatch.setattr("sprint.schema.default_token_encoder", lambda: _mock_encode)
    inventory = assert_renderer_d6()
    assert len(inventory) == 14
    assert all(
        isinstance(r["text"], str)
        and isinstance(r["token_ids"], list)
        and r["token_count"] > 0
        and len(r["token_ids_sha256"]) == 64
        for r in inventory
    )


def test_affect_placebo_share_numeric_tokens():
    for name, raw in ENDPOINT_RAW_S.items():
        p, a, d = render_z(raw)
        aff_lines = (f"P={p}", f"A={a}", f"D={d}")
        pla_lines = (f"SENSOR_1={p}", f"SENSOR_2={a}", f"SENSOR_3={d}")
        aff, pla = render_metadata("affect", raw), render_metadata("placebo", raw)
        for aff_line, pla_line in zip(aff_lines, pla_lines, strict=True):
            assert aff_line in aff, name
            assert pla_line in pla, name
            assert aff_line.split("=", 1)[1] == pla_line.split("=", 1)[1], name


def test_renderer_hashes_unique_across_states():
    digests = set()
    for name, raw in ENDPOINT_RAW_S.items():
        for mode in ("affect", "placebo"):
            digest = hashlib.sha256(render_full_block(mode, raw).encode()).hexdigest()
            assert digest not in digests
            digests.add(digest)


def test_renderer_template_hashes_stable():
    assert len(renderer_template_hash("affect")) == 64
    assert renderer_template_hash("affect") != renderer_template_hash("placebo")


def test_ab_ba_swap_preserves_semantic_mapping():
    high, low = "High path text.", "Low path text."
    ab_section, ba_section = render_ab_ba_sections(high, low)
    assert ab_section.startswith(f"Option A\n{high}")
    assert f"Option B\n{low}" in ab_section
    assert ba_section.startswith(f"Option A\n{low}")
    assert f"Option B\n{high}" in ba_section
    assert ab_section != ba_section


def test_event_memory_deterministic_and_last_ten():
    actions = build_history_actions("P+", history_seed=0)
    memory = render_event_memory(actions)
    assert memory.startswith("[EVENT_MEMORY]")
    assert "last_10_events:" in memory
    assert "cumulative_action_counts:" in memory
    assert "peer" in memory and "group" in memory
    assert "praise" in memory
    for turn in range(190, 200):
        assert f"({turn}, peer," in memory, f"missing turn {turn} in last-10 sequence"
    assert "(200, peer," not in memory
    assert "(189, peer," not in memory
    forbidden = ("valence", "emotion", "personality", "PAD")
    assert not any(word in memory.lower() for word in forbidden)
    h = lambda acts: hashlib.sha256(render_event_memory(acts).encode()).hexdigest()
    assert h(actions) == h(actions)


N_HISTORY_CONDITIONS = ("P+", "P-", "A+", "A-", "D+", "D-")
_AFFECT_TAG = ("[LONG_TERM_AFFECT]", "[/LONG_TERM_AFFECT]")


def _without_affect_block(text: str) -> str:
    start = text.index(_AFFECT_TAG[0])
    end = text.index(_AFFECT_TAG[1]) + len(_AFFECT_TAG[1])
    return text[:start] + text[end:]


def _affect_block(text: str) -> str:
    start = text.index(_AFFECT_TAG[0])
    end = text.index(_AFFECT_TAG[1]) + len(_AFFECT_TAG[1])
    return text[start:end]


@pytest.mark.parametrize("condition", N_HISTORY_CONDITIONS)
@pytest.mark.parametrize("seed", derive_measure_seed_ids())
def test_full_and_zero_share_memory_hash(condition: str, seed: int):
    actions = build_history_actions(condition, history_seed=seed)
    memory_text = render_event_memory(actions)
    memory_hash = hashlib.sha256(memory_text.encode()).hexdigest()
    _, final_state = run_history(condition, history_seed=seed)
    full_s = final_state.s
    zero_s = ENDPOINT_RAW_S["ORIGIN"]
    assert not np.allclose(full_s, zero_s)
    shared = dict(
        experiment="N",
        renderer_mode="affect",
        scenario="Scenario text.",
        high_option="High path.",
        low_option="Low path.",
        option_order="AB",
        memory_text=memory_text,
    )
    full_req = assemble_request(**shared, raw_s=full_s)
    zero_req = assemble_request(**shared, raw_s=zero_s)
    assert memory_text in full_req
    assert memory_text in zero_req
    assert full_req.count("[EVENT_MEMORY]") == 1
    assert zero_req.count("[EVENT_MEMORY]") == 1
    assert hashlib.sha256(memory_text.encode()).hexdigest() == memory_hash
    assert "P=+0.000" in zero_req and "A=+0.000" in zero_req and "D=+0.000" in zero_req
    p, a, d = render_z(full_s)
    assert (p, a, d) != ("+0.000", "+0.000", "+0.000")
    assert f"P={p}" in full_req
    assert _without_affect_block(full_req) == _without_affect_block(zero_req)
    assert _affect_block(full_req) != _affect_block(zero_req)


def test_assemble_request_e_rejects_memory():
    with pytest.raises(ValueError, match="memory_text"):
        assemble_request(
            experiment="E",
            renderer_mode="affect",
            raw_s=ENDPOINT_RAW_S["P+"],
            scenario="Scenario text.",
            high_option="Do one thing.",
            low_option="Do another thing.",
            option_order="AB",
            memory_text=render_event_memory(build_history_actions("P+", history_seed=0)),
        )


def test_assemble_request_block_order():
    raw = ENDPOINT_RAW_S["P+"]
    actions = build_history_actions("P+", history_seed=0)
    memory = render_event_memory(actions)
    req_e = assemble_request(
        experiment="E",
        renderer_mode="affect",
        raw_s=raw,
        scenario="Scenario text.",
        high_option="Do one thing.",
        low_option="Do another thing.",
        option_order="AB",
    )
    req_n = assemble_request(
        experiment="N",
        renderer_mode="affect",
        raw_s=raw,
        scenario="Scenario text.",
        high_option="Do one thing.",
        low_option="Do another thing.",
        option_order="BA",
        memory_text=memory,
    )
    assert req_e.index(BASE_ROLE) < req_e.index("[LONG_TERM_AFFECT]")
    assert req_e.index("Scenario text.") < req_e.index("Option A")
    assert req_e.index("Option A") < req_e.index("Option B")
    assert req_e.endswith(OUTPUT_INSTRUCTION)
    assert "[EVENT_MEMORY]" not in req_e
    assert req_n.index(BASE_ROLE) < req_n.index("[EVENT_MEMORY]")
    assert req_n.index("[EVENT_MEMORY]") < req_n.index("[LONG_TERM_AFFECT]")


def test_assemble_request_n_rejects_placebo():
    memory = render_event_memory(build_history_actions("P+", history_seed=0))
    with pytest.raises(ValueError, match="renderer_mode affect"):
        assemble_request(
            experiment="N",
            renderer_mode="placebo",
            raw_s=ENDPOINT_RAW_S["P+"],
            scenario="Scenario text.",
            high_option="A",
            low_option="B",
            option_order="AB",
            memory_text=memory,
        )


def test_assemble_request_n_requires_memory():
    with pytest.raises(ValueError, match="memory_text"):
        assemble_request(
            experiment="N",
            renderer_mode="affect",
            raw_s=ENDPOINT_RAW_S["ORIGIN"],
            scenario="S",
            high_option="H",
            low_option="L",
            option_order="AB",
        )


def test_event_memory_wrong_length():
    with pytest.raises(ValueError, match="200"):
        render_event_memory(["praise"] * 10)
