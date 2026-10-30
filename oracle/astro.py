"""Offline astronomy: sunrise/sunset (photoperiod) and moon phase.

No external API calls -- both use well-known, widely-published approximate
algorithms (accurate to within a few minutes / a few percent illumination,
which is plenty for a hunting-conditions estimate).
"""
import math
import datetime as dt
from zoneinfo import ZoneInfo

MOON_NAMES = [
    "New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
    "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent",
]


def sun_times(local_date: dt.date, lat: float, lon: float, tz_name: str):
    """Sunrise/sunset for a calendar date at lat/lon, as local-tz datetimes.

    Classic "Sunrise equation" almanac algorithm (Schlyter / NOAA simplified
    form). Returns (sunrise, sunset) or (None, None) for polar day/night.
    """
    tz = ZoneInfo(tz_name)
    zenith = 90.833  # official sunrise/sunset, incl. atmospheric refraction

    def calc(is_sunrise: bool):
        n = local_date.timetuple().tm_yday
        lng_hour = lon / 15.0
        t = n + ((6 - lng_hour) / 24.0) if is_sunrise else n + ((18 - lng_hour) / 24.0)

        m = (0.9856 * t) - 3.289
        l = m + (1.916 * math.sin(math.radians(m))) + (0.020 * math.sin(math.radians(2 * m))) + 282.634
        l %= 360

        ra = math.degrees(math.atan(0.91764 * math.tan(math.radians(l))))
        ra %= 360
        l_quad = math.floor(l / 90) * 90
        ra_quad = math.floor(ra / 90) * 90
        ra = (ra + (l_quad - ra_quad)) / 15.0

        sin_dec = 0.39782 * math.sin(math.radians(l))
        cos_dec = math.cos(math.asin(sin_dec))
        cos_h = (math.cos(math.radians(zenith)) - (sin_dec * math.sin(math.radians(lat)))) / (
            cos_dec * math.cos(math.radians(lat))
        )
        if cos_h > 1 or cos_h < -1:
            return None  # sun never rises / never sets at this latitude+date

        h = (360 - math.degrees(math.acos(cos_h))) if is_sunrise else math.degrees(math.acos(cos_h))
        h /= 15.0

        local_mean_time = h + ra - (0.06571 * t) - 6.622
        ut = (local_mean_time - lng_hour) % 24
        return ut

    sunrise_ut = calc(True)
    sunset_ut = calc(False)
    if sunrise_ut is None or sunset_ut is None:
        return None, None

    def ut_to_local(ut_hours):
        h = int(ut_hours)
        m = int(round((ut_hours - h) * 60))
        if m == 60:
            h, m = h + 1, 0
        naive = dt.datetime.combine(local_date, dt.time(hour=h % 24, minute=m))
        utc_dt = naive.replace(tzinfo=dt.timezone.utc) + dt.timedelta(days=h // 24)
        return utc_dt.astimezone(tz)

    return ut_to_local(sunrise_ut), ut_to_local(sunset_ut)


def day_length_hours(sunrise, sunset):
    if not sunrise or not sunset:
        return None
    return (sunset - sunrise).total_seconds() / 3600.0


LEGAL_HOURS_OFFSET_MIN = 30   # most US states: legal shooting hours start/end
                              # 30 min before sunrise / after sunset. Varies by
                              # state (some use civil-twilight tables instead)
                              # -- always confirm against your state's regs.
STAND_LEAD_TIME_MIN = 30      # get on stand this long before legal light


def legal_shooting_hours(sunrise, sunset):
    """(legal_start, legal_end) -- 30 min before sunrise to 30 min after sunset."""
    if not sunrise or not sunset:
        return None, None
    offset = dt.timedelta(minutes=LEGAL_HOURS_OFFSET_MIN)
    return sunrise - offset, sunset + offset


def best_stand_time(legal_start):
    """When to be settled on stand: STAND_LEAD_TIME_MIN before legal light."""
    if not legal_start:
        return None
    return legal_start - dt.timedelta(minutes=STAND_LEAD_TIME_MIN)


_KNOWN_NEW_MOON = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)
_SYNODIC_MONTH = 29.530588861  # days


def moon_phase(for_dt_utc: dt.datetime):
    """Returns (phase_fraction 0..1 where 0/1=new & 0.5=full, illumination 0..1, name)."""
    days = (for_dt_utc - _KNOWN_NEW_MOON).total_seconds() / 86400.0
    phase = (days % _SYNODIC_MONTH) / _SYNODIC_MONTH
    illumination = (1 - math.cos(2 * math.pi * phase)) / 2
    idx = int((phase * 8) + 0.5) % 8
    return phase, illumination, MOON_NAMES[idx]
