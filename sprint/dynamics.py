from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from sprint.schema import KAPPA_200, DynamicsParams, as_vec3, dynamics_params
@dataclass
class ControllerState:
    epsilon: np.ndarray; m: np.ndarray; s: np.ndarray
    @classmethod
    def zero(cls) -> "ControllerState":
        z = np.zeros(3, dtype=np.float64); return cls(epsilon=z.copy(), m=z.copy(), s=z.copy())
    def copy(self) -> "ControllerState": return ControllerState(epsilon=self.epsilon.copy(), m=self.m.copy(), s=self.s.copy())
def gamma_at(t: int, params: DynamicsParams) -> float:
    return params.gamma_0 / ((1.0 + t / params.tau) ** params.p)
def step(state: ControllerState, appraisal: np.ndarray, t: int, params: DynamicsParams | None = None) -> ControllerState:
    p = params or dynamics_params()
    if p.beta != 0:
        raise AssertionError("Main model forbids beta feedback.")
    a = as_vec3(appraisal)
    eps_next = p.lam * state.epsilon + (1.0 - p.lam) * a
    m_next = (1.0 - p.alpha) * state.m + p.alpha * eps_next
    g = gamma_at(t, p)
    s_next = (1.0 - g) * state.s + g * m_next
    for name, arr in (("appraisal", a), ("epsilon", eps_next), ("m", m_next), ("s", s_next)):
        if not np.isfinite(arr).all():
            raise AssertionError(f"{name} contains NaN or Inf: {arr}")
    if eps_next is state.epsilon or m_next is state.m or s_next is state.s:
        raise AssertionError("State update aliased into previous buffers.")
    return ControllerState(epsilon=eps_next, m=m_next, s=s_next)
def run_sequence(appraisals: np.ndarray, params: DynamicsParams | None = None, initial: ControllerState | None = None) -> tuple[ControllerState, list[ControllerState]]:
    p = params or dynamics_params()
    app = np.asarray(appraisals, dtype=np.float64)
    if app.ndim == 1:
        app = np.repeat(app.reshape(-1, 1), 3, axis=1)
    if app.ndim != 2 or app.shape[1] != 3:
        raise ValueError(f"appraisals must be (T,3), got {app.shape}")
    state = initial.copy() if initial is not None else ControllerState.zero()
    trajectory: list[ControllerState] = []
    for t, a_t in enumerate(app):
        state = step(state, a_t, t=t, params=p)
        trajectory.append(state.copy())
    return state, trajectory
def first_ge_half(series: np.ndarray, half: float) -> int:
    for idx, value in enumerate(series, start=1):
        if value >= half - 1e-15:
            return idx
    raise AssertionError("Series never reached half level.")
def unit_step_half_times(params: DynamicsParams | None = None) -> dict[str, int]:
    p = params or dynamics_params()
    _, traj = run_sequence(np.ones((max(p.T, 120), 3), dtype=np.float64), params=p)
    return {name: first_ge_half(np.array([getattr(s, name)[0] for s in traj]), 0.5)
            for name in ("epsilon", "m", "s")}
def unit_pulse_peak_and_half(params: DynamicsParams | None = None) -> dict[str, dict[str, int]]:
    p = params or dynamics_params()
    apps = np.zeros((max(p.T, 150), 3), dtype=np.float64)
    apps[0] = 1.0
    _, traj = run_sequence(apps, params=p)
    out: dict[str, dict[str, int]] = {}
    for name in ("epsilon", "m", "s"):
        series = np.array([getattr(s, name)[0] for s in traj], dtype=np.float64)
        peak_idx = int(np.argmax(series)) + 1
        half = float(series[peak_idx - 1]) / 2.0
        below = next((i for i in range(peak_idx, len(series) + 1) if series[i - 1] < half - 1e-15), None)
        if below is None:
            raise AssertionError(f"{name} never fell below half-peak")
        out[name] = {"peak": peak_idx, "half_after_peak": below}
    return out
def kappa_200(params: DynamicsParams | None = None) -> float:
    p = params or dynamics_params()
    final, _ = run_sequence(np.ones((p.T, 3), dtype=np.float64), params=p)
    return float(final.s[0])
def assert_golden_dynamics(params: DynamicsParams | None = None) -> None:
    p = params or dynamics_params()
    if (st := unit_step_half_times(p)) != {"epsilon": 1, "m": 8, "s": 69}:
        raise AssertionError(f"unit step half times mismatch: {st}")
    pulse = unit_pulse_peak_and_half(p)
    for name, peak, half in (("epsilon", 1, 2), ("m", 3, 11), ("s", 21, 110)):
        if pulse[name]["peak"] != peak or pulse[name]["half_after_peak"] != half:
            raise AssertionError(f"pulse mismatch for {name}: {pulse[name]}")
    if abs(kappa_200(p) - KAPPA_200) > 1e-12:
        raise AssertionError(f"kappa_200 mismatch: {kappa_200(p)!r} vs {KAPPA_200!r}")
def append_true_zero(state: ControllerState, n: int, start_t: int, params: DynamicsParams | None = None) -> ControllerState:
    p, cur, zero = params or dynamics_params(), state.copy(), np.zeros(3, dtype=np.float64)
    for offset in range(n):
        cur = step(cur, zero, t=start_t + offset, params=p)
    return cur
def retention_ratio(before: ControllerState, after: ControllerState) -> float:
    b = float(np.linalg.norm(before.s))
    if b == 0.0:
        raise ZeroDivisionError("Cannot compute retention from zero state.")
    return float(np.linalg.norm(after.s)) / b
