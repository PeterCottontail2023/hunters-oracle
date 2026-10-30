"""Combines weather, photoperiod, moon phase, and rut signals into one
overall "how good is this day for deer hunting" score.

This is a transparent, documented HEURISTIC, not a scientific model. Weights
and thresholds encode commonly cited deer-movement folklore/field
experience (cold fronts, moderate wind, new-vs-full moon, rut timing). It's
meant as a fun, reasonably-informed planning aid -- not a guarantee.
"""
import datetime as dt

from . import astro, chart, rut, weather, wind as wind_mod

CHART_HOURS = 12

WEATHER_MAX = 40
RUT_MAX = rut.RUT_MAX_POINTS   # 35
MOON_MAX = 15
PHOTOPERIOD_MAX = 10
TOTAL_MAX = WEATHER_MAX + RUT_MAX + MOON_MAX + PHOTOPERIOD_MAX  # 100

_W_COLD_FRONT = 12
_W_WIND = 14
_W_SKY = 8
_W_COMFORT = 6
assert _W_COLD_FRONT + _W_WIND + _W_SKY + _W_COMFORT == WEATHER_MAX

GRADES = [
    (85, "Exceptional"),
    (70, "Great"),
    (55, "Good"),
    (40, "Fair"),
    (0, "Poor"),
]

VERDICTS = {
    "Exceptional": "Call in sick. Skip the wedding. Mark the calendar — this is the kind of day "
                   "you tell stories about for years. Get out there.",
    "Great": "Take off work if you have to, cancel plans with friends — whatever it takes to "
             "get into the woods.",
    "Good": "Solid day to be in the stand. Grab your gear — no excuses needed.",
    "Fair": "Worth a sit if you're itching to go, but no shame in skipping it for one more cup "
            "of coffee.",
    "Poor": "Hit snooze. Mow the lawn, run errands, or scout from the truck — the deer didn't "
            "get the memo and they're not moving much today.",
}


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def grade_for_score(score: float) -> str:
    for threshold, label in GRADES:
        if score >= threshold:
            return label
    return "Poor"


def _avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


# --------------------------------------------------------------------------
# Weather sub-scores
# --------------------------------------------------------------------------
_BAD_SKY_KEYWORDS = ["thunderstorm", "severe", "blizzard", "ice", "freezing", "heavy rain", "heavy snow"]
_MODERATE_BAD_KEYWORDS = ["rain", "snow", "showers", "drizzle", "sleet"]
_GOOD_KEYWORDS = ["sunny", "clear"]
_NEUTRAL_GOOD_KEYWORDS = ["cloudy", "overcast", "fog"]


def _sky_score_period(short_forecast: str, pop) -> float:
    text = (short_forecast or "").lower()
    pop = pop if pop is not None else 0

    if any(k in text for k in _BAD_SKY_KEYWORDS):
        return 0.05
    if any(k in text for k in _MODERATE_BAD_KEYWORDS):
        if pop >= 60:
            return 0.25
        if pop >= 30:
            return 0.55  # light precip can push deer to move before/after
        return 0.7
    if any(k in text for k in _GOOD_KEYWORDS):
        return 0.95
    if any(k in text for k in _NEUTRAL_GOOD_KEYWORDS):
        return 0.8
    return 0.6  # unrecognized description -> mildly neutral


def _wind_score_mph(mph) -> float:
    if mph is None:
        return 0.6
    if 3 <= mph <= 10:
        return 1.0
    if mph < 3:
        return _clamp(0.55 + (mph / 3) * 0.45)
    if mph <= 15:
        return _clamp(1 - (mph - 10) / 10 * 0.4)
    if mph <= 22:
        return _clamp(0.6 - (mph - 15) / 7 * 0.5)
    return 0.08


def _comfort_score_f(temp_f) -> float:
    """Trapezoid peaking ~25-45F, tapering to the extremes."""
    if temp_f is None:
        return 0.6
    if 25 <= temp_f <= 45:
        return 1.0
    if temp_f < 25:
        return _clamp(1 - (25 - temp_f) / 35)  # fades out toward -10F
    return _clamp(1 - (temp_f - 45) / 30)      # fades out toward 75F


def score_weather(dawn_periods, dusk_periods, day_periods, prior_dawn_periods):
    dawn_dusk = dawn_periods + dusk_periods

    # cold front / cooling trend
    target_dawn_avg = _avg([p["temp_f"] for p in dawn_periods])
    prior_dawn_avg = _avg([p["temp_f"] for p in prior_dawn_periods])
    trend_note = None
    if target_dawn_avg is not None and prior_dawn_avg is not None:
        delta = prior_dawn_avg - target_dawn_avg  # positive = cooling into target day
        frac = _clamp(0.5 + delta * 0.05)
        trend_note = (
            f"Dawn temps trending {'down' if delta > 0 else 'up' if delta < 0 else 'flat'} "
            f"{abs(delta):.0f}°F vs. the day before."
        )
    else:
        day_temps = [p["temp_f"] for p in day_periods if p["temp_f"] is not None]
        if day_temps:
            swing = max(day_temps) - min(day_temps)
            frac = _clamp(0.35 + swing * 0.02)
            trend_note = f"Limited trend data this far out — using the day's own {swing:.0f}°F swing as a proxy."
        else:
            frac = 0.5
            trend_note = "No temperature data available."
    cold_front_pts = frac * _W_COLD_FRONT

    # wind during the windows that matter (dawn/dusk)
    wind_vals = [p["wind_mph"] for p in dawn_dusk if p["wind_mph"] is not None]
    avg_wind = _avg(wind_vals)
    wind_frac = _wind_score_mph(avg_wind)
    wind_pts = wind_frac * _W_WIND

    # sky / precip, across the full daytime periods
    daytime = [p for p in day_periods if p["is_daytime"]] or day_periods
    sky_fracs = [_sky_score_period(p["short_forecast"], p["pop"]) for p in daytime] or [0.6]
    sky_frac = _avg(sky_fracs)
    sky_pts = sky_frac * _W_SKY
    worst_sky = min(daytime, key=lambda p: _sky_score_period(p["short_forecast"], p["pop"])) if daytime else None

    # temperature comfort, peak/low daytime temps + min wind chill
    day_highs = [p["temp_f"] for p in daytime if p["temp_f"] is not None]
    peak_high = max(day_highs) if day_highs else None
    daytime_low = min(day_highs) if day_highs else None
    comfort_frac = _comfort_score_f(peak_high)
    comfort_pts = comfort_frac * _W_COMFORT

    daytime_chills = [weather.wind_chill_f(p["temp_f"], p["wind_mph"]) for p in daytime]
    daytime_chills = [c for c in daytime_chills if c is not None]
    min_wind_chill = min(daytime_chills) if daytime_chills else None

    total = cold_front_pts + wind_pts + sky_pts + comfort_pts
    return {
        "points": total,
        "max": WEATHER_MAX,
        "avg_wind_mph": avg_wind,
        "peak_high_f": peak_high,
        "daytime_low_f": daytime_low,
        "min_wind_chill_f": min_wind_chill,
        "trend_note": trend_note,
        "sky_summary": worst_sky["short_forecast"] if worst_sky else "No forecast data",
        "sub": {
            "cold_front": {"points": cold_front_pts, "max": _W_COLD_FRONT},
            "wind": {"points": wind_pts, "max": _W_WIND},
            "sky": {"points": sky_pts, "max": _W_SKY},
            "comfort": {"points": comfort_pts, "max": _W_COMFORT},
        },
    }


# --------------------------------------------------------------------------
# Moon + photoperiod
# --------------------------------------------------------------------------
def score_moon(phase_fraction: float):
    dist_to_new = min(phase_fraction, 1 - phase_fraction)  # 0 at new, 0.5 at full
    frac = 1 - (dist_to_new / 0.5)
    pts = MOON_MAX * (0.25 + 0.75 * _clamp(frac))
    return pts


def score_photoperiod(day_length_hrs):
    if day_length_hrs is None:
        return PHOTOPERIOD_MAX * 0.5
    if 9 <= day_length_hrs <= 11.5:
        frac = 1.0
    elif day_length_hrs < 9:
        frac = _clamp(1 - (9 - day_length_hrs) / 2)
    else:
        frac = _clamp(1 - (day_length_hrs - 11.5) / 2.5)
    return PHOTOPERIOD_MAX * frac


# --------------------------------------------------------------------------
# Top-level report builder
# --------------------------------------------------------------------------
def _window(center, before_minutes, after_minutes):
    return center - dt.timedelta(minutes=before_minutes), center + dt.timedelta(minutes=after_minutes)


def _hour_label(t: dt.datetime) -> str:
    """Compact portable hour label, e.g. '6A', '11P' -- avoids %-I/%#I."""
    hour12 = t.strftime("%I").lstrip("0") or "12"
    return f"{hour12}{t.strftime('%p')[0]}"


def build_stand_chart(periods, chart_start: dt.datetime, hours: int = CHART_HOURS):
    """12-hour (by default) temp/wind-chill/precip chart data starting at chart_start."""
    if chart_start is None:
        return [], None, None
    chart_end = chart_start + dt.timedelta(hours=hours)
    window = [p for p in periods if chart_start <= p["start"] < chart_end]
    points = []
    for p in window:
        wc = weather.wind_chill_f(p["temp_f"], p["wind_mph"])
        points.append({
            "hour_label": _hour_label(p["start"]),
            "temp_f": p["temp_f"],
            "wind_chill_f": round(wc, 1) if wc is not None else None,
            "pop": p["pop"] if p["pop"] is not None else 0,
            "wind_dir": wind_mod.simplify(p["wind_dir"]),
            "flow_bearing": wind_mod.flow_bearing_degrees(p["wind_dir"]),
        })
    return points, chart_start, chart_end


def build_report(location: dict, target_date: dt.date, observed_signs: list, now_local: dt.datetime = None):
    """location: {lat, lon, city, state, zip}. Returns a fully-populated dict for rendering."""
    point = weather.get_point_meta(location["lat"], location["lon"])
    periods_raw = weather.get_hourly_periods(point["forecast_hourly_url"])
    periods = [weather.normalize_period(p) for p in periods_raw]
    tz_name = point["timezone"]

    sunrise, sunset = astro.sun_times(target_date, location["lat"], location["lon"], tz_name)
    day_length = astro.day_length_hours(sunrise, sunset)
    legal_start, legal_end = astro.legal_shooting_hours(sunrise, sunset)
    stand_time = astro.best_stand_time(legal_start)

    noon_utc = dt.datetime.combine(target_date, dt.time(12, 0), tzinfo=dt.timezone.utc)
    phase_fraction, illumination, moon_name = astro.moon_phase(noon_utc)

    day_start = dt.datetime.combine(target_date, dt.time(0, 0), tzinfo=periods[0]["start"].tzinfo)
    day_end = day_start + dt.timedelta(days=1)
    day_periods = [p for p in periods if day_start <= p["start"] < day_end]

    if sunrise and sunset:
        dawn_start, dawn_end = _window(sunrise, 45, 75)
        dusk_start, dusk_end = _window(sunset, 75, 45)
    else:
        dawn_start = dawn_end = dusk_start = dusk_end = None
    dawn_periods = [p for p in periods if dawn_start and dawn_start <= p["start"] < dawn_end]
    dusk_periods = [p for p in periods if dusk_start and dusk_start <= p["start"] < dusk_end]

    prior_date = target_date - dt.timedelta(days=1)
    if sunrise:
        prior_sunrise, _ = astro.sun_times(prior_date, location["lat"], location["lon"], tz_name)
        if prior_sunrise:
            p_start, p_end = _window(prior_sunrise, 45, 75)
            prior_dawn_periods = [p for p in periods if p_start <= p["start"] < p_end]
        else:
            prior_dawn_periods = []
    else:
        prior_dawn_periods = []

    data_limited = len(day_periods) == 0
    weather_score = score_weather(dawn_periods, dusk_periods, day_periods or periods[:24], prior_dawn_periods)

    rut_date_model = rut.rut_phase_for_date(target_date, location["lat"])
    rut_result = rut.apply_observed_signs(rut_date_model, observed_signs)

    moon_pts = score_moon(phase_fraction)
    photo_pts = score_photoperiod(day_length)

    total = weather_score["points"] + rut_result["points"] + moon_pts + photo_pts
    total = _clamp(total, 0, TOTAL_MAX)
    grade = grade_for_score(total)

    chart_anchor = stand_time or legal_start or sunrise
    chart_points, chart_start, chart_end = build_stand_chart(periods, chart_anchor)
    chart_svg = chart.render_meteogram(chart_points)
    chart_incomplete = 0 < len(chart_points) < CHART_HOURS

    def fmt(t):
        """Portable 'h:mm AM/PM' (no leading zero) -- %-I/%#I aren't cross-platform."""
        if not t:
            return "n/a"
        s = t.strftime("%I:%M %p")
        return s[1:] if s.startswith("0") else s

    best_window = None
    if dawn_periods or dusk_periods:
        dawn_wind = _avg([p["wind_mph"] for p in dawn_periods if p["wind_mph"] is not None])
        dusk_wind = _avg([p["wind_mph"] for p in dusk_periods if p["wind_mph"] is not None])
        dawn_bad_sky = any(_sky_score_period(p["short_forecast"], p["pop"]) < 0.3 for p in dawn_periods)
        dusk_bad_sky = any(_sky_score_period(p["short_forecast"], p["pop"]) < 0.3 for p in dusk_periods)
        dawn_pref = _wind_score_mph(dawn_wind) - (0.5 if dawn_bad_sky else 0)
        dusk_pref = _wind_score_mph(dusk_wind) - (0.5 if dusk_bad_sky else 0)
        best_window = "dawn" if dawn_pref >= dusk_pref else "dusk"

    target_date_str = f"{target_date.strftime('%A, %B')} {target_date.day}, {target_date.year}"

    dawn_dir = wind_mod.dominant_direction(dawn_periods)
    dusk_dir = wind_mod.dominant_direction(dusk_periods)

    return {
        "location": {**location, "city": location.get("city") or point.get("city"),
                     "state": location.get("state") or point.get("state")},
        "target_date": target_date,
        "target_date_str": target_date_str,
        "timezone": tz_name,
        "generated_at": now_local or dt.datetime.now(),
        "score": round(total, 1),
        "score_pct": round(total / TOTAL_MAX * 100),
        "grade": grade,
        "verdict": VERDICTS.get(grade, ""),
        "data_limited": data_limited,
        "sun": {
            "sunrise": sunrise, "sunset": sunset,
            "sunrise_str": fmt(sunrise), "sunset_str": fmt(sunset),
            "day_length_hrs": round(day_length, 2) if day_length else None,
            "legal_start": legal_start, "legal_end": legal_end,
            "legal_start_str": fmt(legal_start), "legal_end_str": fmt(legal_end),
            "stand_time": stand_time, "stand_time_str": fmt(stand_time),
            "legal_hours_offset_min": astro.LEGAL_HOURS_OFFSET_MIN,
            "stand_lead_time_min": astro.STAND_LEAD_TIME_MIN,
        },
        "windows": {
            "dawn": (fmt(dawn_start), fmt(dawn_end)) if dawn_start else None,
            "dusk": (fmt(dusk_start), fmt(dusk_end)) if dusk_start else None,
            "best": best_window,
        },
        "moon": {
            "phase_fraction": round(phase_fraction, 3),
            "illumination_pct": round(illumination * 100),
            "name": moon_name,
            "points": round(moon_pts, 1),
            "max": MOON_MAX,
        },
        "photoperiod": {
            "points": round(photo_pts, 1),
            "max": PHOTOPERIOD_MAX,
        },
        "weather": weather_score,
        "rut": rut_result,
        "wind": {
            "dawn_dir": dawn_dir,
            "dusk_dir": dusk_dir,
            "dawn_flow_arrow": wind_mod.flow_arrow_glyph(dawn_dir) if dawn_dir else "",
            "dusk_flow_arrow": wind_mod.flow_arrow_glyph(dusk_dir) if dusk_dir else "",
        },
        "chart": {
            "svg": chart_svg,
            "start_str": fmt(chart_start),
            "end_str": fmt(chart_end),
            "incomplete": chart_incomplete,
            "has_data": len(chart_points) > 0,
        },
        "components": [
            {"key": "weather", "label": "Weather", "points": round(weather_score["points"], 1), "max": WEATHER_MAX},
            {"key": "rut", "label": "Rut Activity", "points": round(rut_result["points"], 1), "max": RUT_MAX},
            {"key": "moon", "label": "Moon Phase", "points": round(moon_pts, 1), "max": MOON_MAX},
            {"key": "photoperiod", "label": "Photoperiod", "points": round(photo_pts, 1), "max": PHOTOPERIOD_MAX},
        ],
    }
