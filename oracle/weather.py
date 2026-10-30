"""National Weather Service (api.weather.gov) forecast retrieval.

The NWS API is free and keyless but requires an identifying User-Agent.
No API key/account needed.
"""
import re
import datetime as dt

import requests

USER_AGENT = "HuntersOracle/1.0 (personal hunting-forecast app)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}


class WeatherError(Exception):
    pass


def _get(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        raise WeatherError(f"Couldn't reach the National Weather Service: {e}") from e
    if resp.status_code != 200:
        raise WeatherError(f"National Weather Service request failed (HTTP {resp.status_code}) for {url}")
    return resp.json()


def get_point_meta(lat: float, lon: float) -> dict:
    """Resolve a lat/lon to its NWS forecast office/grid + hourly forecast URL + timezone."""
    data = _get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}")
    props = data.get("properties", {})
    forecast_hourly_url = props.get("forecastHourly")
    timezone = props.get("timeZone")
    if not forecast_hourly_url or not timezone:
        raise WeatherError("NWS didn't return a usable forecast grid for that location "
                            "(NWS only covers US territory).")
    rel = props.get("relativeLocation", {}).get("properties", {})
    return {
        "forecast_hourly_url": forecast_hourly_url,
        "timezone": timezone,
        "city": rel.get("city"),
        "state": rel.get("state"),
    }


def get_hourly_periods(forecast_hourly_url: str) -> list:
    """Returns the raw list of NWS hourly forecast period dicts (~7 days out)."""
    data = _get(forecast_hourly_url)
    periods = data.get("properties", {}).get("periods")
    if not periods:
        raise WeatherError("NWS returned no hourly forecast periods.")
    return periods


_WIND_RE = re.compile(r"(\d+)\s*(?:to\s*(\d+))?\s*mph", re.I)


def parse_wind_mph(wind_speed_str: str):
    """NWS gives e.g. '10 mph' or '10 to 15 mph' -> average numeric mph (or None)."""
    if not wind_speed_str:
        return None
    m = _WIND_RE.search(wind_speed_str)
    if not m:
        return None
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    return (lo + hi) / 2.0


def wind_chill_f(temp_f, wind_mph):
    """NWS/NWS-standard wind chill formula. Only has a meaningful effect below
    50F and above 3mph; outside that range wind chill == air temp."""
    if temp_f is None or wind_mph is None:
        return None
    if temp_f > 50 or wind_mph <= 3:
        return temp_f
    v16 = wind_mph ** 0.16
    return 35.74 + 0.6215 * temp_f - 35.75 * v16 + 0.4275 * temp_f * v16


def parse_pop(period: dict):
    """Probability of precipitation, 0-100 (or None)."""
    pop = period.get("probabilityOfPrecipitation")
    if isinstance(pop, dict):
        return pop.get("value")
    return pop


def normalize_period(period: dict) -> dict:
    start = dt.datetime.fromisoformat(period["startTime"])
    return {
        "start": start,
        "temp_f": period.get("temperature"),
        "is_daytime": period.get("isDaytime", True),
        "wind_mph": parse_wind_mph(period.get("windSpeed")),
        "wind_dir": period.get("windDirection"),
        "short_forecast": period.get("shortForecast", ""),
        "pop": parse_pop(period),
    }


def hourly_in_range(periods: list, start: dt.datetime, end: dt.datetime) -> list:
    """Normalized hourly periods whose start time falls within [start, end)."""
    out = []
    for p in periods:
        np = normalize_period(p)
        if start <= np["start"] < end:
            out.append(np)
    return out
