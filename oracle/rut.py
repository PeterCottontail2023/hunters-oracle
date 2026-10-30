"""Whitetail rut-timing heuristic + user-observed sign blending.

Rut timing is primarily photoperiod-driven and is well known to shift later
at lower latitudes (and gets more erratic / double-peaked in the Deep
South). The bands below are a rough, widely-cited approximation -- NOT a
precise regional forecast. Confidence is intentionally marked lower outside
the Midwest/Northeast "textbook" latitude band.

Max contribution to the overall score: RUT_MAX_POINTS (see scoring.py).
"""
import datetime as dt

RUT_MAX_POINTS = 35

# (min_lat, peak_day_of_year, confidence)
_LATITUDE_BANDS = [
    (45, 308, "medium"),   # far north: ~Nov 4
    (40, 314, "high"),     # upper Midwest/Northeast: ~Nov 10
    (35, 319, "high"),     # mid-latitude "textbook" belt: ~Nov 15
    (30, 330, "medium"),   # mid-south: ~Nov 26
    (-90, 350, "low"),     # deep south: ~Dec 16, highly variable/double-peaked
]

_PHASES = [
    # (lo_offset, hi_offset, name, points, blurb)
    (-999, -25, "Early Season", 2,
     "Bucks are mostly still in bachelor groups or just starting to spar; rut pressure is minimal."),
    (-25, -10, "Pre-Rut / Seeking", 24,
     "Scraping and rubbing are ramping up fast as bucks begin searching for the first receptive does."),
    (-10, -3, "Chasing Phase", 35,
     "Bucks are cruising and chasing does in daylight — historically one of the best windows of the season."),
    (-3, 3, "Peak Breeding / Lockdown", 14,
     "Mature bucks are often locked down tending a doe and less visible, though overall deer movement stays elevated."),
    (3, 10, "Post-Rut Lull", 6,
     "Bucks are recovering from the peak push; daylight movement typically drops off for several days."),
    (10, 35, "Second Rut Potential", 18,
     "Does that weren't bred the first cycle come back into estrus ~28 days later, which can trigger a secondary chase phase."),
    (35, 999, "Late Season", 4,
     "Outside the primary rut window — movement here is driven mostly by weather and feeding pressure, not breeding."),
]

# user-observed sign -> (floor_points, label, confidence_bump_text)
SIGN_FLOORS = {
    "chasing": (33, "You reported seeing active chasing"),
    "tending_grunting": (28, "You reported tending grunts/vocalization"),
    "fresh_scrapes": (22, "You reported fresh scrapes"),
    "fresh_rubs": (18, "You reported fresh rubs"),
    "does_bunched": (20, "You reported does acting bunched up/nervous"),
}

SIGN_LABELS = {
    "chasing": "Saw a buck actively chasing a doe",
    "tending_grunting": "Heard grunting / tending vocalization",
    "fresh_scrapes": "Found fresh scrapes",
    "fresh_rubs": "Found fresh rubs",
    "does_bunched": "Does acting bunched up / nervous",
}


def estimate_peak_rut_day(lat: float):
    for min_lat, peak_day, confidence in _LATITUDE_BANDS:
        if lat >= min_lat:
            return peak_day, confidence
    return _LATITUDE_BANDS[-1][1], _LATITUDE_BANDS[-1][2]


def rut_phase_for_date(target_date: dt.date, lat: float):
    peak_day, confidence = estimate_peak_rut_day(lat)
    doy = target_date.timetuple().tm_yday
    offset = doy - peak_day
    for lo, hi, name, points, blurb in _PHASES:
        if lo <= offset < hi:
            return {
                "phase": name,
                "points": points,
                "blurb": blurb,
                "offset_days": offset,
                "confidence": confidence,
            }
    # fallback (shouldn't hit given -999/999 bounds above)
    lo, hi, name, points, blurb = _PHASES[-1]
    return {"phase": name, "points": points, "blurb": blurb, "offset_days": offset, "confidence": confidence}


def apply_observed_signs(date_model: dict, observed_signs: list):
    """Blend user field observations in: ground-truth signs can only raise the
    rut-activity estimate (never lower it below what the calendar model says),
    since a sign you *saw* is stronger evidence than a sign you *didn't see*
    (which could just mean you weren't in the woods, not that nothing's happening).
    """
    result = dict(date_model)
    result["observed_signs"] = list(observed_signs or [])
    result["sign_notes"] = []

    if not observed_signs:
        return result

    best_floor = 0
    for sign in observed_signs:
        floor, note = SIGN_FLOORS.get(sign, (0, None))
        if note:
            result["sign_notes"].append(note)
        best_floor = max(best_floor, floor)

    if best_floor > result["points"]:
        result["points"] = best_floor
        result["boosted_by_field_signs"] = True
        result["confidence"] = "high"  # direct observation trumps the calendar model
    else:
        result["boosted_by_field_signs"] = False

    return result
