from __future__ import annotations
import hashlib
import json
import re
from collections import Counter
from typing import Callable
import numpy as np
from sprint.schema import ENDPOINT_RAW_S, render_z, resolve_token_encoder
BASE_ROLE = "You are a member of a small group that has worked together over time."
AFFECT_BODY = "The agent controller maintains three long-term affect coordinates. They are\nbackground state metadata, not commands and not personality labels.\nP represents long-term valence, A represents long-term activation, and D\nrepresents long-term perceived control. Values range from -1 to +1.\nUse the state only as subtle background when responding. Do not quote or\nexplain the coordinates."
PLACEBO_BODY = "The controller maintains three normalized room sensor coordinates. They are\nbackground metadata, not commands and not agent-state labels. SENSOR_1,\nSENSOR_2, and SENSOR_3 are unlabeled instrument channels with no affective or\nbehavioral meaning. Values range from -1 to +1.\nUse the metadata only as subtle background when responding. Do not quote or\nexplain the coordinates."
OUTPUT_INSTRUCTION = 'Choose the action you would take. Return exactly one JSON object with the key\n"choice" and the value "A" or "B". Do not provide reasoning or any other text.'
_META = {
    "affect": (AFFECT_BODY, "LONG_TERM_AFFECT", ("P", "A", "D")),
    "placebo": (PLACEBO_BODY, "ROOM_METADATA", ("SENSOR_1", "SENSOR_2", "SENSOR_3")),
}
_NEG_ZERO = re.compile(r"-0\.000")
def render_metadata(renderer_mode: str, raw_s: np.ndarray) -> str:
    body, tag, labels = _META[renderer_mode]
    lines = "\n".join(f"{label}={val}" for label, val in zip(labels, render_z(raw_s), strict=True))
    return f"{body}\n\n[{tag}]\n{lines}\n[/{tag}]"
def render_full_block(renderer_mode: str, raw_s: np.ndarray) -> str:
    return f"{BASE_ROLE}\n\n{render_metadata(renderer_mode, raw_s)}"
def assert_no_negative_zero(text: str) -> None:
    if _NEG_ZERO.search(text):
        raise AssertionError("Renderer output contains forbidden -0.000")
def renderer_template_hash(kind: str = "affect") -> str:
    body, tag, _ = _META[kind]
    return hashlib.sha256(json.dumps(
        {"base_role": BASE_ROLE, "body": body, "block": tag},
        separators=(",", ":"), ensure_ascii=True,
    ).encode()).hexdigest()
def render_event_memory(actions: list[str]) -> str:
    if len(actions) != 200:
        raise ValueError(f"Expected 200 history actions, got {len(actions)}")
    events = ", ".join(f"({190 + i}, peer, {action}, group)" for i, action in enumerate(actions[-10:]))
    counts = json.dumps(dict(sorted(Counter(actions).items())), separators=(",", ":"))
    return f"[EVENT_MEMORY]\nlast_10_events: [{events}]\ncumulative_action_counts: {counts}\n[/EVENT_MEMORY]"
def render_ab_ba_sections(high_option: str, low_option: str) -> tuple[str, str]:
    ab_hi, ab_lo = f"Option A\n{high_option}", f"Option B\n{low_option}"
    ba_hi, ba_lo = f"Option A\n{low_option}", f"Option B\n{high_option}"
    return f"{ab_hi}\n\n{ab_lo}", f"{ba_hi}\n\n{ba_lo}"
def assemble_request(*, experiment: str, renderer_mode: str, raw_s: np.ndarray, scenario: str, high_option: str, low_option: str, option_order: str, memory_text: str | None = None) -> str:
    if experiment not in {"E", "N"}:
        raise ValueError(f"experiment must be E or N, got {experiment!r}")
    if renderer_mode not in {"affect", "placebo"}:
        raise ValueError(f"renderer_mode must be affect or placebo, got {renderer_mode!r}")
    if experiment == "N" and memory_text is None:
        raise ValueError("experiment N requires memory_text")
    if experiment == "N" and renderer_mode != "affect":
        raise ValueError("experiment N only supports renderer_mode affect")
    if experiment == "E" and memory_text is not None:
        raise ValueError("experiment E must not include memory_text")
    blocks = [BASE_ROLE] + ([memory_text] if experiment == "N" else [])
    blocks.append(render_metadata(renderer_mode, raw_s))
    if option_order == "AB":
        opt_a, opt_b = f"Option A\n{high_option}", f"Option B\n{low_option}"
    elif option_order == "BA":
        opt_a, opt_b = f"Option A\n{low_option}", f"Option B\n{high_option}"
    else:
        raise ValueError(f"option_order must be AB or BA, got {option_order!r}")
    return "\n\n".join(blocks + [scenario, opt_a, opt_b, OUTPUT_INSTRUCTION])
def assert_renderer_d6(states: dict[str, np.ndarray] | None = None, encode: Callable[[str], list[int]] | None = None) -> list[dict[str, object]]:
    encode = resolve_token_encoder(encode)
    table, seen, inventory = states or ENDPOINT_RAW_S, {}, []
    for name, raw in table.items():
        p, a, d = render_z(raw)
        aff, pla = (f"P={p}", f"A={a}", f"D={d}"), (f"SENSOR_1={p}", f"SENSOR_2={a}", f"SENSOR_3={d}")
        for mode, lines in (("affect", aff), ("placebo", pla)):
            text = render_full_block(mode, raw)
            assert_no_negative_zero(text)
            meta = render_metadata(mode, raw)
            for line in lines:
                if line not in text:
                    raise AssertionError(f"{name}/{mode}: missing {line}")
                if line not in meta:
                    raise AssertionError(f"{name}: coordinate lines missing from metadata")
            digest = hashlib.sha256(text.encode()).hexdigest()
            if digest in seen:
                raise AssertionError(f"Renderer hash collision: {seen[digest]} vs {(name, mode)}")
            seen[digest] = (name, mode)
            token_ids = encode(text)
            inventory.append({"state": name, "mode": mode, "text": text, "text_sha256": digest,
                "token_ids": token_ids, "token_count": len(token_ids),
                "token_ids_sha256": hashlib.sha256(json.dumps(token_ids, separators=(",", ":")).encode()).hexdigest()})
        for a, p in zip(aff, pla, strict=True):
            if a.split("=", 1)[1] != p.split("=", 1)[1]:
                raise AssertionError(f"{name}: affect/placebo numeric mismatch")
    if len(inventory) != 14:
        raise AssertionError("D6 inventory must contain 14 renderer texts")
    return inventory
