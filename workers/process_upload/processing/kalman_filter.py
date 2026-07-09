"""Generic, domain-agnostic Kalman filter building blocks — no GPS, lat/lon,
knots, IMU, or UWB knowledge here; that belongs to the caller (e.g.
``track.py``). Three pieces, each an independent extension point:

- ``MotionModel`` — *how the state propagates over time* (the ``F``/``Q`` of
  a predict step). Subclass to change dynamics; nothing else changes.
- ``Measurement`` — *one observation*, carrying its own measurement model
  ``h(x)``, Jacobian ``H(x)``, and noise ``R``. Heterogeneous by design: a
  4-component GPS fix, a 1-component UWB range, and a 2-component compass
  reading are all just ``Measurement`` instances with different dimensions.
- ``KalmanFilter`` — the fusion core. ``predict(dt)`` uses the motion model;
  ``update(measurement)`` folds in one observation. Knows nothing about what
  any sensor *is*.

**Why not filterpy here.** We wrap no external filter: filterpy (and most
libraries) fix the measurement dimension ``dim_z`` at construction, so a
single filter instance can't fuse a 4-D GPS fix and a 1-D UWB range — the
exact heterogeneity this design exists to support. The update below is the
standard EKF correction (~8 lines, Joseph-form covariance update for
numerical stability, identical to what those libraries do internally) and
adapts to any ``z``/``H``/``R`` shape purely from the arrays passed in. If a
model's Jacobian ever gets painful to derive by hand, the fallback is an
Unscented KF (filterpy has one) — but that's a per-model choice, not a
reason to give up variable-dimension measurements everywhere.

The update is written in Extended-KF form (``y = z - h(x)``, ``H = H(x)``),
which subsumes the linear case (``h(x) = H·x``, constant ``H``) — so a
linear GPS-only fusion and a future nonlinear UWB/compass fusion run through
the very same code path.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np


class MotionModel:
    """How the state vector propagates over a time step ``dt`` — the predict
    half of the filter. Subclass to change the dynamics (constant-velocity
    today; a constant-acceleration or constant-turn-rate model, or one with
    an explicit heading/yaw-rate state for IMU fusion, would be new
    subclasses). ``dim`` is the state dimension; ``F``/``Q`` are the
    transition matrix and process-noise covariance for a given ``dt`` (both
    time-varying, since real samples don't arrive at a fixed rate)."""

    dim: int

    def F(self, dt: float) -> np.ndarray:
        raise NotImplementedError

    def Q(self, dt: float) -> np.ndarray:
        raise NotImplementedError


class ConstantVelocity2D(MotionModel):
    """2D constant-velocity model, state ``[x, y, vx, vy]``: position drifts
    by velocity·dt, velocity is a random walk driven by unmodeled
    acceleration. ``accel_variance`` (``(m/s^2)^2``) is how much the velocity
    is expected to change per second — the single knob trading responsiveness
    against smoothing."""

    dim = 4

    def __init__(self, accel_variance: float):
        self._accel_variance = accel_variance

    def F(self, dt: float) -> np.ndarray:
        return np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=float)

    def Q(self, dt: float) -> np.ndarray:
        # Discretized continuous-white-noise-acceleration process noise
        # (standard constant-velocity form).
        q = self._accel_variance
        return q * np.array([
            [dt**4 / 4, 0, dt**3 / 2, 0],
            [0, dt**4 / 4, 0, dt**3 / 2],
            [dt**3 / 2, 0, dt**2, 0],
            [0, dt**3 / 2, 0, dt**2],
        ], dtype=float)


@dataclass
class Measurement:
    """One observation, in the filter's state space. ``z`` is the raw reading
    (any dimension), ``R`` its noise covariance, and the two callables are the
    measurement model:

    - ``predict_z(x)`` = ``h(x)``: what this sensor *would* read if the true
      state were ``x`` (for GPS: the position/velocity components of ``x``
      directly; for a UWB range: the distance from ``x`` to a known anchor).
    - ``jacobian(x)`` = ``H(x)`` = ``∂h/∂x``: constant for a linear sensor,
      state-dependent for a nonlinear one (UWB range, compass heading).

    Building these by hand is fiddly for the common linear case, so use
    ``linear_measurement`` instead of constructing directly when ``h`` is just
    ``H·x``."""

    timestamp: float
    z: np.ndarray
    R: np.ndarray
    predict_z: Callable[[np.ndarray], np.ndarray]
    jacobian: Callable[[np.ndarray], np.ndarray]


def linear_measurement(timestamp: float, z, H, R) -> Measurement:
    """Build a ``Measurement`` for a sensor whose reading is a *linear*
    function of the state, ``h(x) = H·x`` with a constant ``H`` — the GPS
    case (``H`` picks out the observed state components). Nonlinear sensors
    construct ``Measurement`` directly with their own ``predict_z``/
    ``jacobian``."""
    H = np.asarray(H, dtype=float)
    return Measurement(
        timestamp=timestamp,
        z=np.asarray(z, dtype=float),
        R=np.asarray(R, dtype=float),
        predict_z=lambda x: H @ x,
        jacobian=lambda x: H,
    )


class KalmanFilter:
    """Sequential predict/update fusion core, parameterized by a
    ``MotionModel``. Holds the running state ``x`` and covariance ``P``.

    Usage is one ``predict(dt)`` per observation arrival, followed by
    ``update(measurement)`` with whatever sensor produced it — so several
    sensors reporting at different rates are handled by merging all their
    ``Measurement``s into one timeline ordered by timestamp and walking it,
    rather than assuming one synchronized reading per step."""

    def __init__(self, model: MotionModel, initial_state, initial_covariance):
        self.model = model
        self.x = np.asarray(initial_state, dtype=float)
        self.P = np.asarray(initial_covariance, dtype=float)

    def predict(self, dt: float) -> np.ndarray:
        """Propagate the state forward by ``dt`` seconds under the motion
        model, inflating covariance by the process noise."""
        dt = max(dt, 1e-3)
        F = self.model.F(dt)
        Q = self.model.Q(dt)
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q
        return self.x

    def update(self, m: Measurement) -> np.ndarray:
        """Fold in one measurement (Extended-KF correction). Works for a
        measurement of any dimension — ``m.z``/``m.R`` and ``m.jacobian(x)``
        set the shapes; nothing here is hard-coded to the state or sensor
        dimension."""
        H = m.jacobian(self.x)
        y = m.z - m.predict_z(self.x)          # innovation
        PHT = self.P @ H.T
        S = H @ PHT + m.R                       # innovation covariance
        K = PHT @ np.linalg.inv(S)              # Kalman gain
        self.x = self.x + K @ y
        I_KH = np.eye(self.model.dim) - K @ H
        # Joseph form — stays symmetric positive-definite even with a
        # suboptimal gain, unlike the shorter ``(I - K H) P``.
        self.P = I_KH @ self.P @ I_KH.T + K @ m.R @ K.T
        return self.x
