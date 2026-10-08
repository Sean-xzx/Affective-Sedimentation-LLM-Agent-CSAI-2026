"""Gate D1 (+ supporting normalization checks) for sprint dynamics."""

from __future__ import annotations

import math
from decimal import Decimal

import numpy as np
import pytest

from sprint.dynamics import (
    assert_golden_dynamics,
    gamma_at,
    kappa_200,
    step,
    ControllerState,
)
from sprint.schema import (
    ENDPOINT_RAW_S,
    ENDPOINT_Z_RENDERED,
    ENDPOINT_Z_UNROUNDED,
    KAPPA_200,
    TARGET_OF,
    dynamics_params,
    format_signed_3dp,
    render_z,
    round_half_even_3dp,
    signed_z,
)


def test_first_gamma_is_gamma0():
    params = dynamics_params()
    assert gamma_at(0, params) == params.gamma_0


def test_golden_dynamics_d1():
    assert_golden_dynamics()
    assert abs(kappa_200() - KAPPA_200) <= 1e-12


def test_golden_dynamics_raises_under_python_o():
    import subprocess
    import sys
    code = (
        "import sprint.dynamics as d\n"
        "d.unit_step_half_times = lambda *a, **k: {'epsilon': 0, 'm': 0, 's': 0}\n"
        "try:\n"
        "    d.assert_golden_dynamics()\n"
        "    print('NOFAIL')\n"
        "except AssertionError:\n"
        "    print('FAIL_OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-O", "-c", code],
        capture_output=True,
        text=True,
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
    )
    assert result.returncode == 0, result.stderr
    assert "FAIL_OK" in result.stdout
    assert "NOFAIL" not in result.stdout


def test_no_clip_and_no_alias():
    state = ControllerState.zero()
    nxt = step(state, np.array([0.1, -0.2, 0.3]), t=0)
    assert nxt.epsilon is not state.epsilon
    assert nxt.m is not state.m
    assert nxt.s is not state.s
    assert np.isfinite(nxt.s).all()


def test_endpoint_z_tables():
    for name, raw in ENDPOINT_RAW_S.items():
        if name == "ORIGIN":
            assert np.all(raw == 0.0)
            assert render_z(raw) == ("+0.000", "+0.000", "+0.000")
            continue
        z = signed_z(raw)
        dim = TARGET_OF[name]
        idx = {"P": 0, "A": 1, "D": 2}[dim]
        assert abs(float(z[idx]) - ENDPOINT_Z_UNROUNDED[name]) < 5e-7
        rendered = render_z(raw)
        assert rendered[idx] == ENDPOINT_Z_RENDERED[name]
        for j in range(3):
            if j != idx:
                assert abs(raw[j]) == 0.0
                assert rendered[j] == "+0.000"


def test_negative_zero_rendering():
    assert round_half_even_3dp(0.0) == Decimal("0")
    assert round_half_even_3dp(-0.0) == Decimal("0")
    assert format_signed_3dp(-0.0) == "+0.000"
    assert format_signed_3dp(0.0) == "+0.000"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0005, "+0.000"),
        (0.0015, "+0.002"),
        (0.0025, "+0.002"),
        (-0.0005, "+0.000"),
        (-0.0015, "-0.002"),
        (-0.0025, "-0.002"),
    ],
)
def test_round_half_even_halfway_cases(value: float, expected: str):
    assert format_signed_3dp(value) == expected


def test_round_half_even_avoids_str_float_artifacts():
    # 2.675 is a classic str(float) rounding pitfall; repr keeps the float exact.
    value = math.nextafter(0.0025, 0.0)
    assert round_half_even_3dp(value) == Decimal("0.002")
    assert format_signed_3dp(value) == "+0.002"
