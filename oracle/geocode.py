"""US zip code -> lat/lon, via the free, keyless zippopotam.us API."""
import requests


class GeocodeError(Exception):
    pass


def zip_to_location(zip_code: str) -> dict:
    zip_code = (zip_code or "").strip()
    if not (zip_code.isdigit() and len(zip_code) == 5):
        raise GeocodeError(f"‘{zip_code}’ doesn't look like a 5-digit US zip code.")

    try:
        resp = requests.get(f"https://api.zippopotam.us/us/{zip_code}", timeout=10)
    except requests.RequestException as e:
        raise GeocodeError(f"Couldn't reach the zip-code lookup service: {e}") from e

    if resp.status_code == 404:
        raise GeocodeError(f"Zip code {zip_code} wasn't found. (US zip codes only.)")
    if resp.status_code != 200:
        raise GeocodeError(f"Zip-code lookup failed (HTTP {resp.status_code}).")

    try:
        data = resp.json()
        place = data["places"][0]
        return {
            "zip": zip_code,
            "lat": float(place["latitude"]),
            "lon": float(place["longitude"]),
            "city": place["place name"],
            "state": place["state abbreviation"],
        }
    except (KeyError, IndexError, ValueError) as e:
        raise GeocodeError(f"Unexpected response from zip-code lookup service: {e}") from e
