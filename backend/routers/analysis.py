"""Per-session analysis endpoints (``/api/analysis/*``).

Serves the precomputed ``analysis.json`` for a session, plus narrow views over
it (maneuvers, legs, polar, stats). The sub-views call ``_analysis_by_prefix``
in this same module, so they stay co-located.

Two ways to address a session: the usual ``{device_id}/{date}`` pair (device-
sourced sessions), or ``/session/{session_id}`` (manual/GPX-sourced sessions,
which have no device — see ``routers/sessions.py`` + ``services/gpx_processing.py``).
Both resolve to the same blob-store prefix shape and share the loading logic.

⚠️ The ``/session/{id}`` routes are declared *before* ``/{device_id}/{date}``:
both are two path segments, and FastAPI/Starlette matches routes in
registration order, so the literal-first-segment route must come first or
``/session/42`` would be swallowed by ``{device_id}={date}="session"/"42"``.
"""

from fastapi import APIRouter, HTTPException

from ._common import DATA_PREFIX, load_json_or_404, repos

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _analysis_by_prefix(prefix: str) -> dict:
    return load_json_or_404(f"{prefix}analysis.json")


def _manual_session_prefix(session_id: int) -> str:
    session = repos.sessions.get_by_id(session_id)
    if session is None or session.source != "manual":
        raise HTTPException(404, f"Session not found: {session_id}")
    return f"{DATA_PREFIX}/manual/{session_id}/"


@router.get("/session/{session_id}")
def get_analysis_by_session(session_id: int):
    """Get full analysis results for a manual (device-less) session."""
    return _analysis_by_prefix(_manual_session_prefix(session_id))


@router.get("/session/{session_id}/maneuvers")
def get_maneuvers_by_session(session_id: int):
    analysis = get_analysis_by_session(session_id)
    return {
        "maneuvers": analysis.get("maneuvers", []),
        "summary": analysis.get("maneuver_summary", {}),
    }


@router.get("/session/{session_id}/legs")
def get_legs_by_session(session_id: int):
    analysis = get_analysis_by_session(session_id)
    return {
        "legs": analysis.get("legs", []),
        "comparison": analysis.get("leg_comparison", {}),
    }


@router.get("/session/{session_id}/polar")
def get_polar_by_session(session_id: int):
    analysis = get_analysis_by_session(session_id)
    return {"polar": analysis.get("polar", {})}


@router.get("/session/{session_id}/stats")
def get_stats_by_session(session_id: int):
    analysis = get_analysis_by_session(session_id)
    return {
        "violin": analysis.get("violin", {}),
        "correlations": analysis.get("correlations", {}),
        "session_stats": analysis.get("session_stats", {}),
        "leg_ranking": analysis.get("leg_ranking", []),
    }


@router.get("/{device_id}/{date}")
def get_analysis(device_id: str, date: str):
    """Get full analysis results for a session."""
    return _analysis_by_prefix(f"{DATA_PREFIX}/{device_id}/{date}/")


@router.get("/{device_id}/{date}/maneuvers")
def get_maneuvers(device_id: str, date: str):
    """Get maneuver detection results."""
    analysis = get_analysis(device_id, date)
    return {
        "maneuvers": analysis.get("maneuvers", []),
        "summary": analysis.get("maneuver_summary", {}),
    }


@router.get("/{device_id}/{date}/legs")
def get_legs(device_id: str, date: str):
    """Get straight-line leg analysis."""
    analysis = get_analysis(device_id, date)
    return {
        "legs": analysis.get("legs", []),
        "comparison": analysis.get("leg_comparison", {}),
    }


@router.get("/{device_id}/{date}/polar")
def get_polar(device_id: str, date: str):
    """Get polar diagram data."""
    analysis = get_analysis(device_id, date)
    return {"polar": analysis.get("polar", {})}


@router.get("/{device_id}/{date}/stats")
def get_stats(device_id: str, date: str):
    """Get statistical analysis (violin, correlations)."""
    analysis = get_analysis(device_id, date)
    return {
        "violin": analysis.get("violin", {}),
        "correlations": analysis.get("correlations", {}),
        "session_stats": analysis.get("session_stats", {}),
        "leg_ranking": analysis.get("leg_ranking", []),
    }
