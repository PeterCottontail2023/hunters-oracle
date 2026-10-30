"""Hand-rolled inline-SVG meteogram (temp / wind chill / precip chance).

No charting library/dependency -- generated server-side the same way as
tools/gen_buck_svg.py, then embedded directly in the result page.
"""
import math

BLAZE = "#ff6a00"
GOLD = "#ffb400"
PRECIP = "#5b85ab"
GRID = "#3a3228"
TEXT = "#b9ac99"

COLORS = {"temp": BLAZE, "wind_chill": GOLD, "precip": PRECIP}


def _arrow_icon(cx, cy, bearing_deg, size=7, color=TEXT):
    """A small vector arrow pointing 'up' (bearing 0 = north), rotated to
    `bearing_deg` (0=N, clockwise) around its own center. Drawn with plain
    lines rather than a Unicode glyph so it renders identically regardless
    of what fonts are installed on the viewer's machine."""
    tip_y = cy - size
    base_y = cy + size * 0.6
    hw = size * 0.55
    return (
        f'<g transform="rotate({bearing_deg:.1f} {cx:.1f} {cy:.1f})">'
        f'<line x1="{cx:.1f}" y1="{base_y:.1f}" x2="{cx:.1f}" y2="{tip_y:.1f}" '
        f'stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        f'<path d="M {cx - hw:.1f},{tip_y + hw:.1f} L {cx:.1f},{tip_y:.1f} L {cx + hw:.1f},{tip_y + hw:.1f}" '
        f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</g>'
    )


def _nice_step(span, target_ticks=4):
    if span <= 0:
        return 5
    raw = span / target_ticks
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def render_meteogram(points, width=640, height=300):
    """points: list of {hour_label, temp_f, wind_chill_f, pop}. Returns an SVG string."""
    if not points:
        return (f'<svg viewBox="0 0 {width} 120" xmlns="http://www.w3.org/2000/svg">'
                f'<text x="20" y="60" font-size="13" fill="{TEXT}">No hourly forecast data available for this window.</text></svg>')

    n = len(points)
    pad_l, pad_r, pad_t, pad_b = 42, 46, 16, 48
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    temps = [p["temp_f"] for p in points if p["temp_f"] is not None]
    chills = [p["wind_chill_f"] for p in points if p["wind_chill_f"] is not None]
    pool = temps + chills or [0, 100]
    raw_min, raw_max = min(pool), max(pool)
    span = max(raw_max - raw_min, 8)
    step = _nice_step(span)
    t_min = math.floor(raw_min / step) * step - step
    t_max = math.ceil(raw_max / step) * step + step

    def x_of(i):
        return pad_l + (i / max(n - 1, 1)) * plot_w

    def y_of_temp(t):
        return pad_t + (1 - (t - t_min) / (t_max - t_min)) * plot_h

    def y_of_pct(pct):
        return pad_t + (1 - pct / 100.0) * plot_h

    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
             f'font-family="Segoe UI, DejaVu Sans, Arial, sans-serif" '
             f'role="img" aria-label="12-hour temperature, wind chill, and precipitation chance chart">']

    # horizontal gridlines + left (temp) axis labels
    t = t_min
    while t <= t_max + 1e-6:
        y = y_of_temp(t)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
                      f'stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l - 8}" y="{y + 4:.1f}" font-size="11" fill="{TEXT}" '
                      f'text-anchor="end">{int(round(t))}&#176;</text>')
        t += step

    # right (precip %) axis labels
    for pct in (0, 50, 100):
        y = y_of_pct(pct)
        parts.append(f'<text x="{width - pad_r + 8}" y="{y + 4:.1f}" font-size="11" fill="{TEXT}" '
                      f'text-anchor="start">{pct}%</text>')

    # precip-chance bars
    bar_w = max(plot_w / n * 0.5, 3)
    bottom = pad_t + plot_h
    for i, p in enumerate(points):
        pop = p.get("pop") or 0
        x = x_of(i)
        y = y_of_pct(pop)
        parts.append(f'<rect x="{x - bar_w / 2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                      f'height="{max(bottom - y, 0):.1f}" fill="{PRECIP}" fill-opacity="0.38" rx="2"/>')

    # wind-direction flow arrows (where the wind is blowing TOWARD, i.e. where
    # your scent goes) just above the hour-label row -- drawn as vector lines,
    # not a Unicode glyph, so they render identically on any machine/font
    for i, p in enumerate(points):
        bearing = p.get("flow_bearing")
        if bearing is not None:
            parts.append(_arrow_icon(x_of(i), height - 28, bearing))

    # x-axis hour labels
    for i, p in enumerate(points):
        parts.append(f'<text x="{x_of(i):.1f}" y="{height - 10}" font-size="11" fill="{TEXT}" '
                      f'text-anchor="middle">{p["hour_label"]}</text>')

    def line_points(key):
        return [(x_of(i), y_of_temp(p[key])) for i, p in enumerate(points) if p.get(key) is not None]

    def path_d(pts):
        return " ".join(f"{'M' if i == 0 else 'L'} {x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))

    chill_pts = line_points("wind_chill_f")
    if chill_pts:
        parts.append(f'<path d="{path_d(chill_pts)}" fill="none" stroke="{GOLD}" '
                      f'stroke-width="2.5" stroke-dasharray="6,4"/>')
        parts += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{GOLD}"/>' for x, y in chill_pts]

    temp_pts = line_points("temp_f")
    if temp_pts:
        parts.append(f'<path d="{path_d(temp_pts)}" fill="none" stroke="{BLAZE}" stroke-width="3"/>')
        parts += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{BLAZE}"/>' for x, y in temp_pts]

    parts.append("</svg>")
    return "\n".join(parts)
