"""Wind-direction helpers: compass normalization, dominant-direction picking,
and the scent-flow arrow (opposite of the reported "from" direction) used to
reason about which stand keeps a hunter downwind of where deer are expected.
"""
from collections import Counter

# 16-point compass -> degrees (standard "wind FROM" bearing, 0=N, clockwise)
FROM_DEGREES = {
    "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
    "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
    "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
    "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5,
}

# simplify a 16-point reading down to the 8 main points (used for stand matching --
# asking a hunter to tag a stand with 16 directions is overkill)
EIGHT_POINT = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

_SIMPLIFY = {
    "N": "N", "NNE": "NE", "NE": "NE", "ENE": "E",
    "E": "E", "ESE": "SE", "SE": "SE", "SSE": "S",
    "S": "S", "SSW": "SW", "SW": "SW", "WSW": "W",
    "W": "W", "WNW": "NW", "NW": "NW", "NNW": "N",
}

# opposite point, 8-point compass -- the direction scent actually travels TOWARD
_OPPOSITE = {"N": "S", "NE": "SW", "E": "W", "SE": "NW", "S": "N", "SW": "NE", "W": "E", "NW": "SE"}

_ARROW_GLYPH = {"N": "↑", "NE": "↗", "E": "→", "SE": "↘",
                "S": "↓", "SW": "↙", "W": "←", "NW": "↖"}


def simplify(direction: str):
    if not direction:
        return None
    return _SIMPLIFY.get(direction.strip().upper())


def flow_direction(from_direction: str):
    """Where the wind is actually blowing TOWARD (i.e. where your scent goes)."""
    simple = simplify(from_direction)
    return _OPPOSITE.get(simple) if simple else None


def flow_arrow_glyph(from_direction: str):
    flow = flow_direction(from_direction)
    return _ARROW_GLYPH.get(flow, "")


def flow_bearing_degrees(from_direction: str):
    """Degrees (0=N, clockwise) the wind is blowing TOWARD -- for rotating an arrow icon."""
    if not from_direction:
        return None
    deg = FROM_DEGREES.get(direction_16pt(from_direction))
    return (deg + 180) % 360 if deg is not None else None


def direction_16pt(direction: str):
    if not direction:
        return None
    d = direction.strip().upper()
    return d if d in FROM_DEGREES else None


def dominant_direction(periods, key="wind_dir"):
    """Most common simplified (8-point) direction among a list of periods, or None."""
    counts = Counter(simplify(p.get(key)) for p in periods if p.get(key))
    counts.pop(None, None)
    if not counts:
        return None
    return counts.most_common(1)[0][0]
