#!/usr/bin/env python3
"""Hunter's Oracle -- local web app entry point."""
import datetime as dt
import webbrowser
import threading
import os

from flask import Flask, render_template, request, redirect, url_for

from oracle.geocode import zip_to_location, GeocodeError
from oracle.weather import WeatherError
from oracle import rut, scoring, stands as stands_mod
from oracle.wind import EIGHT_POINT

app = Flask(__name__)

MAX_DAYS_OUT = 7
GITHUB_HANDLE = "PeterCottontail2023"


@app.context_processor
def inject_globals():
    return {"github_handle": GITHUB_HANDLE}


def today_local():
    return dt.date.today()


@app.route("/", methods=["GET"])
def index():
    start = today_local()
    end = start + dt.timedelta(days=MAX_DAYS_OUT)
    return render_template(
        "index.html",
        today=start.isoformat(),
        max_date=end.isoformat(),
        sign_options=rut.SIGN_LABELS,
        form={},
        error=None,
    )


@app.route("/predict", methods=["POST"])
def predict():
    start = today_local()
    end = start + dt.timedelta(days=MAX_DAYS_OUT)
    zip_code = request.form.get("zip_code", "").strip()
    date_str = request.form.get("hunt_date", "").strip()
    signs = request.form.getlist("signs")
    saw_signs = request.form.get("saw_signs", "no")

    form_echo = {"zip_code": zip_code, "hunt_date": date_str, "signs": signs, "saw_signs": saw_signs}

    def render_error(msg):
        return render_template(
            "index.html",
            today=start.isoformat(),
            max_date=end.isoformat(),
            sign_options=rut.SIGN_LABELS,
            form=form_echo,
            error=msg,
        )

    try:
        target_date = dt.date.fromisoformat(date_str)
    except ValueError:
        return render_error("That doesn't look like a valid date.")

    if not (start <= target_date <= end):
        def short(d):  # portable 'Mon D' (no leading zero) -- %-d/%#d aren't cross-platform
            return f"{d.strftime('%b')} {d.day}"
        return render_error(
            f"Pick a date between today ({short(start)}) and "
            f"{short(end)} — the Oracle only looks {MAX_DAYS_OUT} days out."
        )

    observed_signs = signs if saw_signs == "yes" else []

    try:
        location = zip_to_location(zip_code)
        report = scoring.build_report(location, target_date, observed_signs)
    except GeocodeError as e:
        return render_error(str(e))
    except WeatherError as e:
        return render_error(f"Weather lookup failed: {e}")
    except Exception as e:  # noqa: BLE001 -- surface anything unexpected, don't 500 silently
        return render_error(f"Something went wrong building your forecast: {e}")

    my_stands = stands_mod.load_stands()
    stand_recs = {
        "dawn": stands_mod.stands_for_direction(my_stands, report["wind"]["dawn_dir"]),
        "dusk": stands_mod.stands_for_direction(my_stands, report["wind"]["dusk_dir"]),
    }

    return render_template(
        "result.html", r=report, sign_labels=rut.SIGN_LABELS, form=form_echo,
        stand_recs=stand_recs, has_stands=bool(my_stands),
    )


@app.route("/stands", methods=["GET"])
def manage_stands():
    return render_template("stands.html", stands=stands_mod.load_stands(), directions=EIGHT_POINT, error=None)


@app.route("/stands/add", methods=["POST"])
def add_stand():
    name = request.form.get("name", "").strip()
    directions = request.form.getlist("directions")
    notes = request.form.get("notes", "").strip()
    if not name:
        return render_template("stands.html", stands=stands_mod.load_stands(), directions=EIGHT_POINT,
                                error="Give the stand a name.")
    if not directions:
        return render_template("stands.html", stands=stands_mod.load_stands(), directions=EIGHT_POINT,
                                error="Pick at least one wind direction this stand works for.")
    stands_mod.add_stand(name, directions, notes)
    return redirect(url_for("manage_stands"))


@app.route("/stands/delete/<stand_id>", methods=["POST"])
def delete_stand(stand_id):
    stands_mod.delete_stand(stand_id)
    return redirect(url_for("manage_stands"))


def _open_browser(url):
    import time
    time.sleep(1.0)
    try:
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5151))
    url = f"http://127.0.0.1:{port}/"
    if os.environ.get("ORACLE_NO_BROWSER") != "1":
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()
    print(f"\n  Hunter's Oracle is running at {url}\n  Press Ctrl+C to stop.\n")
    app.run(host="127.0.0.1", port=port, debug=False)
