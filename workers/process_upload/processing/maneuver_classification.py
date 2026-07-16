"""Pluggable maneuver classifiers — Stage 2 of the two-stage detection
pipeline. Stage 1 (``maneuvers._detect_candidates``) segments the track into
roughly-constant-heading legs and produces a ``ManeuverCandidate`` (with a
``features`` dict) for every turn between two legs — deliberately WITHOUT
deciding what kind of turn it is. A classifier here maps each candidate to a
``ManeuverType`` — or to ``None`` meaning "false alarm, not a real maneuver",
so Stage 2 both *rejects* and *labels*. All of the "what maneuver is this"
judgement lives here, not in Stage 1.

Add a classifier by writing a function with the ``ManeuverClassifier``
signature and registering it below; swap ``ACTIVE_CLASSIFIER`` to experiment
(constant, not env-configurable — change it and rebuild the worker image, same
idiom as ``wind_estimation.ACTIVE_STRATEGY``).

Three classifiers are described here:

- ``probabilistic`` (default): a soft-evidence confidence score with a
  threshold — replaces the old rigid rules. It weighs the heading-change
  magnitude, whether the bow/stern crossed the wind, and the speed loss into a
  maneuver-confidence; below the threshold it returns ``None`` (false alarm).
  It then labels the turn TACK (bow crosses head-to-wind, needs a wide
  rotation), GYBE (stern crosses dead-downwind, allowed with a modest
  rotation), or COURSE_CHANGE (a clear heading shift on the SAME tack — a pure
  point-of-sail change, e.g. close-hauled → reach). See
  ``probabilistic_classifier``.
- ``geometric`` (kept for rollback/comparison): the previous rule — tack if the
  average absolute angle to the wind axis is < 90° (bow crosses the wind), else
  gybe. Never returns ``None`` or ``COURSE_CHANGE``.
- ``_ml_classifier`` (FUTURE, NOT registered): a trained XGBoost/NN model that
  maps ``candidate.features`` to {tack, gybe, course_change} or ``None`` (false
  alarm). Left as a stub so the seam is visible without pulling in ML deps. The
  ``probabilistic`` weights below are the natural hand-tuned seed for it.
"""

import math
import os
from typing import Callable, Optional

from .models import ManeuverCandidate, ManeuverType

ManeuverClassifier = Callable[[ManeuverCandidate], "Optional[ManeuverType]"]


def geometric_classifier(cand: ManeuverCandidate) -> "Optional[ManeuverType]":
    """Tack = the bow crosses head-to-wind (both headings within 90° of the
    wind axis); gybe = the stern crosses (both beyond 90°). Reads the
    classifier inputs from the candidate's feature dict. Returns TACK or GYBE
    only — never ``None`` (no false-alarm rejection) and never ``COURSE_CHANGE``.
    Kept registered for rollback/comparison against ``probabilistic``."""
    rel_before = cand.features["rel_before"]
    rel_after = cand.features["rel_after"]
    avg_abs_rel = (abs(rel_before) + abs(rel_after)) / 2
    return ManeuverType.TACK if avg_abs_rel < 90 else ManeuverType.GYBE


# --------------------------------------------------------------------------- #
# Probabilistic classifier — tunable constants
# --------------------------------------------------------------------------- #
# Module constants, same idiom as ACTIVE_CLASSIFIER / wind_estimation.
# ACTIVE_STRATEGY: change them and rebuild the worker image. The defaults are
# calibrated to reproduce the previous tack/gybe behavior on clean tracks;
# re-tune on a handful of real sessions if detection is too eager/shy.

# "Is this a real maneuver" — logistic confidence: bias + weighted evidence.
CONF_BIAS = -1.5
W_ANGLE = 2.0          # heading-change magnitude
W_SPEED = 1.5          # speed CHANGE (either direction) through the turn
W_CROSS = 1.5          # bow/stern crossed the wind axis
W_TURN = 1.0           # turn sharpness (max turn rate)
W_CROSS_NO_AXIS = 0.4  # crossing evidence is weak when the axis is synthetic
# Not crossing the wind is the SIGNATURE of a course change (same tack, e.g.
# bolina->lasco), not an anomaly — so it must not be penalized much harder
# than crossing; the type ramps below (not this credit) are what keeps a tiny
# same-tack wiggle from being confused with a genuine course change.
NO_CROSS_CREDIT = 0.6

# Evidence ramps: (lo, hi) map a raw quantity to [0, 1] (0 below lo, 1 above hi).
ANGLE_RAMP = (15.0, 90.0)     # |heading change|, degrees
# Relative speed CHANGE through the turn (fraction of entry speed), in EITHER
# direction — heading up typically sheds speed, bearing away typically gains
# it (a reach is faster than close-hauled), so only measuring loss would
# structurally miss/under-score course changes that speed the boat up.
SPEED_CHANGE_RAMP = (0.05, 0.35)
# max |turn rate|, deg/s — the low end MUST stay at/below
# maneuvers.TURN_RATE_THRESHOLD (not imported here to avoid a circular import:
# maneuvers.py imports this module) so a just-detected turn already carries
# partial evidence instead of scoring 0 right at its own detection threshold.
TURN_RATE_RAMP = (2.0, 12.0)

# Accept a candidate as a maneuver only above this confidence.
DETECT_THRESHOLD = 0.5

# Per-type magnitude ramps — encode the asymmetry the user described: a tack
# needs a wide rotation, a gybe can be modest, a course change (same tack) needs
# a clear heading shift to stand out from ordinary steering.
TACK_ANGLE_RAMP = (40.0, 120.0)
GYBE_ANGLE_RAMP = (20.0, 90.0)
COURSE_ANGLE_RAMP = (30.0, 90.0)


def _ramp(x: float, lo: float, hi: float) -> float:
    """Clamped linear ramp: 0 at/below ``lo``, 1 at/above ``hi``, linear between."""
    if hi <= lo:
        return 1.0 if x >= hi else 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def probabilistic_classifier(cand: ManeuverCandidate) -> "Optional[ManeuverType]":
    """Soft-evidence maneuver classifier (default). Two decisions from one set
    of evidence already present on the candidate:

    1. *Is it a maneuver?* A logistic confidence over three signals the user
       cares about — a big heading change, the bow/stern crossing the wind, and
       a speed CHANGE (drop or gain — a tack/gybe typically sheds speed but a
       bear-away onto a reach typically gains it, so only checking for loss
       would miss half of real course changes) all push it up (a synthetic wind
       axis down-weights the crossing term). Below ``DETECT_THRESHOLD`` the
       candidate is rejected (``None``).
    2. *Which kind?* The wind geometry (``rel_before``/``rel_after``) fixes the
       family — a sign flip near head-to-wind is a TACK, near dead-downwind a
       GYBE, no sign flip (same tack) a COURSE_CHANGE — and a per-type magnitude
       ramp decides whether the rotation is decisive enough (a tack needs more
       than a gybe; a small change on the same tack is just steering, not a
       course change).

    The confidence and per-type scores are written back onto ``cand.features``
    (persisted as JSON on ``session_maneuvers.features``) so the UI and a future
    training set can read them without a DB migration."""
    f = cand.features
    rel_before = f["rel_before"]
    rel_after = f["rel_after"]
    avg_abs_rel = f.get("avg_abs_rel", (abs(rel_before) + abs(rel_after)) / 2.0)
    had_wind_axis = bool(f.get("had_wind_axis", 1.0))

    delta = abs(cand.heading_change_deg)
    speed_before = max(cand.speed_before_kts, 0.1)
    # Largest relative speed swing in either direction: a drop through the turn
    # (speed_min) or a gain by the time it settles (speed_after) — whichever is
    # bigger is the real signal, since which one shows up depends on the point
    # of sail being entered, not on whether a maneuver happened.
    speed_drop_rel = (cand.speed_before_kts - cand.speed_min_kts) / speed_before
    speed_gain_rel = (cand.speed_after_kts - cand.speed_before_kts) / speed_before
    speed_change_rel = max(speed_drop_rel, speed_gain_rel, 0.0)
    turn_rate = f.get("max_abs_turn_rate") or 0.0

    angle_ev = _ramp(delta, *ANGLE_RAMP)
    speed_ev = _ramp(speed_change_rel, *SPEED_CHANGE_RAMP)
    turn_ev = _ramp(turn_rate, *TURN_RATE_RAMP)

    # A sign flip of the heading-to-axis angle means the boat crossed the wind
    # line — near 0° that is head-to-wind (a tack), near ±180° dead-downwind (a
    # gybe); avg_abs_rel tells the two apart. No flip ⇒ same tack ⇒ course change.
    crossed = (rel_before >= 0) != (rel_after >= 0)
    w_cross = W_CROSS if had_wind_axis else W_CROSS_NO_AXIS
    cross_ev = 1.0 if crossed else NO_CROSS_CREDIT

    z = (CONF_BIAS
         + W_ANGLE * angle_ev
         + W_SPEED * speed_ev
         + w_cross * cross_ev
         + W_TURN * turn_ev)
    conf = _sigmoid(z)

    tack_like = crossed and avg_abs_rel < 90.0
    gybe_like = crossed and avg_abs_rel >= 90.0
    course_like = not crossed
    score_tack = _ramp(delta, *TACK_ANGLE_RAMP) if tack_like else 0.0
    score_gybe = _ramp(delta, *GYBE_ANGLE_RAMP) if gybe_like else 0.0
    score_course = _ramp(delta, *COURSE_ANGLE_RAMP) if course_like else 0.0

    f["maneuver_confidence"] = round(conf, 4)
    f["type_scores"] = {
        "tack": round(score_tack, 4),
        "gybe": round(score_gybe, 4),
        "course_change": round(score_course, 4),
    }

    # At most one family is non-zero (they are mutually exclusive by geometry),
    # so the argmax picks the geometry-determined type — but only if the turn is
    # both confident enough and decisive enough for that type.
    best = max(score_tack, score_gybe, score_course)
    if conf < DETECT_THRESHOLD or best <= 0.0:
        return None
    if best == score_tack:
        return ManeuverType.TACK
    if best == score_gybe:
        return ManeuverType.GYBE
    return ManeuverType.COURSE_CHANGE


CLASSIFIERS: "dict[str, ManeuverClassifier]" = {
    "probabilistic": probabilistic_classifier,
    "geometric": geometric_classifier,
}

# Change this (and rebuild the worker image) to switch classifiers.
ACTIVE_CLASSIFIER = "probabilistic"


def classify_maneuver(cand: ManeuverCandidate) -> "Optional[ManeuverType]":
    """Dispatch to the active classifier. ``None`` = false alarm → the caller
    (``detect_maneuvers``) drops the candidate."""
    return CLASSIFIERS[ACTIVE_CLASSIFIER](cand)


# --------------------------------------------------------------------------- #
# FUTURE: ML classifier seam — deliberately NOT registered / not active.
# --------------------------------------------------------------------------- #

# Env var pointing at the trained model artifact (local path or object-store
# URI). The classifier *selection* is a compile-time constant (ACTIVE_CLASSIFIER);
# only the trained weights are provided at runtime via this env var. Do NOT wire
# ACTIVE_CLASSIFIER itself to an env var — that would break the wind-module idiom.
MANEUVER_MODEL_PATH_ENV = "MANEUVER_MODEL_PATH"


def _load_maneuver_model():
    """FUTURE: lazily load + cache the Step-2 model artifact from
    ``os.environ[MANEUVER_MODEL_PATH_ENV]``. Import sklearn/xgboost/torch INSIDE
    this function so the deps are only required once the ML path is active.
    Not called until ``_ml_classifier`` is registered."""
    path = os.environ.get(MANEUVER_MODEL_PATH_ENV)
    raise NotImplementedError(
        f"Maneuver model loading not implemented yet (would load from {path!r})."
    )


def _ml_classifier(cand: ManeuverCandidate) -> "Optional[ManeuverType]":
    """FUTURE Step 2 — NOT registered / not active. Intended shape once it
    lands:

      1. lazily load a model artifact (``_load_maneuver_model``), cached
         module-level;
      2. build the feature vector from ``cand.features`` in the order given by
         ``maneuver_features.ENABLED_FEATURES`` / ``FEATURE_SCHEMA_VERSION`` —
         the exact training-time order;
      3. predict a label and map it to {TACK, GYBE, COURSE_CHANGE};
      4. below a confidence threshold, return ``None`` (false alarm) or fall
         back to ``geometric_classifier``.

    Registering this also requires the ``course_change`` enum member (already
    present) + the DB CHECK migration (already applied) + adding the ML deps to
    ``requirements.txt``.
    """
    raise NotImplementedError("ML maneuver classifier not implemented yet")
