"""Persisted list of the user's own stands, each tagged with which wind
directions (the "FROM" direction, matching forecast convention) keep it
scent-safe -- i.e. the directions under which this stand's position carries
the hunter's scent away from where deer are expected, based on the
hunter's own knowledge of their land. The app only handles matching that
against the forecast; it has no way to know your terrain itself.
"""
import json
import os
import uuid

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STANDS_FILE = os.path.join(DATA_DIR, "stands.json")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_stands() -> list:
    if not os.path.exists(STANDS_FILE):
        return []
    try:
        with open(STANDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_stands(stands: list):
    _ensure_data_dir()
    with open(STANDS_FILE, "w", encoding="utf-8") as f:
        json.dump(stands, f, indent=2)


def add_stand(name: str, good_from_directions: list, notes: str = ""):
    stands = load_stands()
    stands.append({
        "id": uuid.uuid4().hex[:8],
        "name": name.strip(),
        "good_from_directions": good_from_directions,
        "notes": notes.strip(),
    })
    save_stands(stands)
    return stands


def delete_stand(stand_id: str):
    stands = [s for s in load_stands() if s["id"] != stand_id]
    save_stands(stands)
    return stands


def stands_for_direction(stands: list, direction: str):
    """Stands tagged as good for this (8-point, simplified) wind direction."""
    if not direction:
        return []
    return [s for s in stands if direction in s.get("good_from_directions", [])]
