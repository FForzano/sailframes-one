"""Data schemas for SailFrames analysis engine.

Defines structured models for sessions, boats, maneuvers, legs,
and analysis results used throughout the processing pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ManeuverType(str, Enum):
    TACK = "tack"
    GYBE = "gybe"


class PointOfSail(str, Enum):
    UPWIND = "upwind"
    DOWNWIND = "downwind"
    REACHING = "reaching"
    CLOSE_REACH = "close_reach"
    BROAD_REACH = "broad_reach"


class LegType(str, Enum):
    UPWIND = "upwind"
    DOWNWIND = "downwind"
    REACH = "reach"


@dataclass
class BoatProfile:
    boat_id: str
    name: str
    boat_class: str  # e.g. "Sonar 23", "J/80"
    sail_number: Optional[str] = None
    crew_weight_kg: Optional[float] = None
    jib_type: Optional[str] = None
    main_type: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class GpsPoint:
    timestamp: float  # unix epoch
    lat: float
    lon: float
    speed_kts: float
    heading_deg: float
    fix_quality: int = 0


@dataclass
class ImuReading:
    timestamp: float
    heading_deg: float
    pitch_deg: float
    heel_deg: float
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0


@dataclass
class WindReading:
    timestamp: float
    apparent_speed_kts: float
    apparent_angle_deg: float  # 0=bow, 180=stern, positive=starboard


@dataclass
class PressureReading:
    timestamp: float
    pressure_hpa: float
    temperature_c: float


@dataclass
class Maneuver:
    maneuver_type: ManeuverType
    start_time: float
    end_time: float
    duration_sec: float
    speed_loss_kts: float  # speed before minus minimum speed during
    speed_before_kts: float
    speed_min_kts: float
    speed_after_kts: float
    recovery_time_sec: float  # time to regain 90% of entry speed
    heading_change_deg: float
    max_heel_deg: Optional[float] = None
    distance_lost_m: Optional[float] = None
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None


@dataclass
class StraightLineLeg:
    leg_type: LegType
    start_time: float
    end_time: float
    duration_sec: float
    distance_nm: float
    avg_speed_kts: float
    max_speed_kts: float
    avg_vmg_kts: float
    avg_heel_deg: Optional[float] = None
    avg_twa_deg: Optional[float] = None
    std_heading_deg: float = 0.0  # heading stability
    num_points: int = 0
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None


@dataclass
class PolarPoint:
    twa_deg: float  # true wind angle bucket center
    tws_kts: float  # true wind speed bucket center
    boat_speed_kts: float  # average or max boat speed
    vmg_kts: float
    sample_count: int = 0


@dataclass
class VmgResult:
    timestamp: float
    vmg_kts: float
    twa_deg: float
    boat_speed_kts: float
    tws_kts: Optional[float] = None
    optimal_vmg_kts: Optional[float] = None  # from polar
    vmg_efficiency: Optional[float] = None  # actual/optimal ratio


@dataclass
class SessionMetadata:
    device_id: str
    date: str  # YYYY-MM-DD
    start_time: float
    end_time: float
    duration_sec: float
    boat: Optional[BoatProfile] = None
    wind_avg_kts: Optional[float] = None
    wind_dir_avg_deg: Optional[float] = None
    distance_nm: Optional[float] = None
    max_speed_kts: Optional[float] = None
    num_tacks: int = 0
    num_gybes: int = 0


@dataclass
class SessionData:
    """Container for all sensor data in a session."""
    metadata: SessionMetadata
    gps: list[GpsPoint] = field(default_factory=list)
    imu: list[ImuReading] = field(default_factory=list)
    wind: list[WindReading] = field(default_factory=list)
    pressure: list[PressureReading] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Complete analysis output for a session."""
    session: SessionMetadata
    maneuvers: list[Maneuver] = field(default_factory=list)
    legs: list[StraightLineLeg] = field(default_factory=list)
    polar_points: list[PolarPoint] = field(default_factory=list)
    vmg_series: list[VmgResult] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


# =============================================================================
# Race Dashboard Models
# =============================================================================

@dataclass
class Regatta:
    """A regatta/series containing multiple races."""
    regatta_id: str
    name: str  # "J/80 Spring Series 2026"
    venue: str  # "Courageous Sailing Center"
    boat_class: str  # "J/80"
    start_date: str  # "2026-04-27"
    end_date: str  # "2026-05-25"
    race_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class StartFinishLine:
    """Start or finish line defined by two endpoints."""
    pin_lat: float  # Pin end coordinates
    pin_lon: float
    boat_lat: float  # Committee boat end
    boat_lon: float


@dataclass
class RaceBoat:
    """A boat entry in a race."""
    device_id: str  # "E1", "E2", etc.
    boat_name: str  # "Defiance"
    sail_number: str  # "123"
    session_path: Optional[str] = None  # Auto-matched session path


@dataclass
class StartAnalysis:
    """Start line analysis for a single boat."""
    time_to_line_sec: float  # Seconds from gun to crossing line
    distance_at_gun_m: float  # Distance from line at start signal
    speed_at_gun_kts: float  # Boat speed at gun
    line_end: str  # "pin" or "boat" - which end was closer
    ocs: bool  # Over early (crossed before gun)


@dataclass
class BoatRaceResult:
    """Race results for a single boat."""
    device_id: str
    finish_position: int  # Manual entry (1-based)
    elapsed_sec: float
    delta_to_leader_sec: float
    avg_speed_kts: float
    max_speed_kts: float
    tack_count: int
    gybe_count: int
    distance_nm: float
    start_analysis: Optional[StartAnalysis] = None


@dataclass
class RaceResults:
    """Computed results for a race."""
    finish_order: list[str] = field(default_factory=list)  # device_ids
    boat_results: dict = field(default_factory=dict)  # device_id -> BoatRaceResult
    computed_at: str = ""


@dataclass
class Mark:
    """A course mark (buoy) placed on the map."""
    mark_id: str
    name: str  # "Windward", "Leeward A", "Gate Port"
    mark_type: str  # "windward" | "leeward" | "gate_port" | "gate_stbd" | "offset" | "start_pin" | "start_boat" | "finish_pin" | "finish_boat" | "custom"
    lat: float
    lon: float


@dataclass
class Race:
    """A single race with boats, times, and results."""
    race_id: str
    name: str  # "Race 1"
    date: str  # "2026-05-04"
    start_time: str  # ISO timestamp (gun time)
    end_time: str  # ISO timestamp
    boats: list[RaceBoat] = field(default_factory=list)
    regatta_id: Optional[str] = None
    start_line: Optional[StartFinishLine] = None
    finish_line: Optional[StartFinishLine] = None
    marks: list[Mark] = field(default_factory=list)
    course: list[str] = field(default_factory=list)  # ordered mark_ids defining leg sequence
    finish_order: list[str] = field(default_factory=list)  # Manual entry
    results: Optional[RaceResults] = None
    created_at: str = ""
    updated_at: str = ""
