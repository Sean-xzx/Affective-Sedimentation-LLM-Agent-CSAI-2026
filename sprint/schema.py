from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Callable, Iterable
import numpy as np
import yaml
ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "sprint_20260810.yaml"
ACTION_MAP_PATH = ROOT / "materials" / "action_map.csv"
DEPENDENCY_LOCK_PATH = ROOT / "requirements.lock"
DIMS = ("P", "A", "D")
TARGET_OF = {"P+": "P", "P-": "P", "A+": "A", "A-": "A", "D+": "D", "D-": "D"}
POS_BOUND = np.array([0.360, 0.472, 0.400], dtype=np.float64)
NEG_MAG = np.array([0.408, 0.240, 0.540], dtype=np.float64)
KAPPA_200 = 0.7643908969485586
ENDPOINT_RAW_S = {
    "P-": np.array([-0.22255053, 0.0, 0.0], dtype=np.float64),
    "P+": np.array([0.25786681, 0.0, 0.0], dtype=np.float64),
    "A-": np.array([0.0, -0.14877657, 0.0], dtype=np.float64),
    "A+": np.array([0.0, 0.25008904, 0.0], dtype=np.float64),
    "D-": np.array([0.0, 0.0, -0.28133731], dtype=np.float64),
    "D+": np.array([0.0, 0.0, 0.18701863], dtype=np.float64),
    "ORIGIN": np.array([0.0, 0.0, 0.0], dtype=np.float64),
}
ENDPOINT_Z_UNROUNDED = {
    "P-": -0.545467, "P+": 0.716297, "A-": -0.619902, "A+": 0.529850,
    "D-": -0.520995, "D+": 0.467547,
}
ENDPOINT_Z_RENDERED = {
    "P-": "-0.545", "P+": "+0.716", "A-": "-0.620", "A+": "+0.530",
    "D-": "-0.521", "D+": "+0.468",
}
@dataclass(frozen=True)
class DynamicsParams:
    lam: float; alpha: float; gamma_0: float; tau: float; p: float; beta: float; T: int; master_seed: int
def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
def dependency_lock_sha256(path: Path = DEPENDENCY_LOCK_PATH) -> str:
    return sha256_file(path)
@lru_cache(maxsize=1)
def default_token_encoder() -> Callable[[str], list[int]]:
    load_id = load_config()["tokenizer_load_id"]
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(load_id, trust_remote_code=True)
    return lambda text: list(tok.encode(text, add_special_tokens=False))
def resolve_token_encoder(encode: Callable[[str], list[int]] | None = None) -> Callable[[str], list[int]]:
    return encode or default_token_encoder()
def dynamics_params(config: dict | None = None) -> DynamicsParams:
    cfg = config or load_config()
    return DynamicsParams(
        lam=float(cfg["lambda"]), alpha=float(cfg["alpha"]),
        gamma_0=float(cfg["gamma_0"]), tau=float(cfg["tau"]),
        p=float(cfg["p"]), beta=float(cfg["beta"]),
        T=int(cfg["T"]), master_seed=int(cfg["master_seed"]),
    )
def as_vec3(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.shape != (3,):
        raise ValueError(f"Expected length-3 vector, got shape {arr.shape}")
    return arr
def signed_z(raw_s: np.ndarray) -> np.ndarray:
    s = as_vec3(raw_s)
    z = np.empty(3, dtype=np.float64)
    for i in range(3):
        z[i] = s[i] / POS_BOUND[i] if s[i] >= 0.0 else s[i] / NEG_MAG[i]
    return z
def round_half_even_3dp(value: float) -> Decimal:
    d = Decimal("0") if value == 0.0 else Decimal(repr(value))
    q = d.quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)
    return Decimal("0.000") if q == 0 else q
def format_signed_3dp(value: float) -> str:
    q = round_half_even_3dp(value)
    if q == 0:
        return "+0.000"
    sign = "+" if q > 0 else "-"
    return f"{sign}{abs(q):.3f}"
def render_z(raw_s: np.ndarray) -> tuple[str, str, str]:
    z = signed_z(raw_s)
    return tuple(format_signed_3dp(float(z[i])) for i in range(3))
