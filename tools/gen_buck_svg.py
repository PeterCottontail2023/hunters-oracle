#!/usr/bin/env python3
"""
Generates static/img/buck.svg: a front-facing, stylized buck-head badge
(blaze-orange glow, dark silhouette, big multi-point rack) drawn entirely
with code -- no external art assets.

Antlers are built with a small recursive branch generator so the rack reads
as a believable "big buck" trophy rack without hand-authored bezier paths.
The rack is deliberately allowed to break out of the top of the badge ring
(a common trophy-badge look) rather than being squeezed to fit inside it.
"""
import math
import os

W, H = 520, 760
CX = 260
CY = 460            # head/badge vertical center (lower half of taller canvas)
R = 230              # badge ring radius

SIL = "#1b1710"       # near-black silhouette (warm dark brown-black)
OUTLINE = "#0c0a07"
BLAZE = "#ff6a00"
BLAZE_DARK = "#c24d00"
CREAM = "#fff3e2"


def antler_branches(x, y, angle_deg, length, depth, width, side, is_brow=False):
    """Recursively emit stroke segments for one antler beam, mirrored by `side` (+1/-1).
    angle_deg is measured from straight-up (0), positive tips the beam toward `side`.
    """
    segs = []
    rad = math.radians(angle_deg)
    x2 = x + side * length * math.sin(rad)
    y2 = y - length * math.cos(rad)
    segs.append(
        f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{SIL}" stroke-width="{width:.1f}" stroke-linecap="round"/>'
    )

    if not is_brow and depth == 3:
        # brow tine near the base, short and angled forward/down
        brow_rad = math.radians(angle_deg - side * 70)
        bx = x + side * 48 * math.sin(brow_rad)
        by = y - 48 * math.cos(brow_rad) + 18
        segs.append(
            f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{bx:.1f}" y2="{by:.1f}" '
            f'stroke="{SIL}" stroke-width="{max(width - 3, 4):.1f}" stroke-linecap="round"/>'
        )

    if depth == 0:
        return segs

    # a side tine branches off partway along this segment, then the main beam continues
    branch_t = 0.58
    bx = x + (x2 - x) * branch_t
    by = y + (y2 - y) * branch_t
    tine_len = length * 0.62
    segs += antler_branches(bx, by, angle_deg - side * 34, tine_len, 0, max(width - 2.2, 3.5), side)
    segs += antler_branches(x2, y2, angle_deg + side * 10, length * 0.86, depth - 1, max(width - 2.2, 3.5), side)
    return segs


def antler(base_x, base_y, side):
    return antler_branches(base_x, base_y, 16, 108, 3, 15, side)


def ear(side):
    # a simple elongated, rotated oval reads cleanly as a deer ear and mirrors perfectly
    cx = CX + side * 112
    cy = CY - 95
    angle = -side * 32
    return (
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="27" ry="72" '
        f'fill="{SIL}" stroke="{OUTLINE}" stroke-width="2" '
        f'transform="rotate({angle:.1f} {cx:.1f} {cy:.1f})"/>'
        f'<ellipse cx="{cx:.1f}" cy="{cy - 8:.1f}" rx="12" ry="48" '
        f'fill="#3a2f22" '
        f'transform="rotate({angle:.1f} {cx:.1f} {cy-8:.1f})"/>'
    )


def build_svg():
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
             f'role="img" aria-label="Hunter\'s Oracle buck badge">']

    parts.append('<defs>')
    parts.append(
        f'<radialGradient id="glow" cx="50%" cy="40%" r="65%">'
        f'<stop offset="0%" stop-color="{BLAZE}" stop-opacity="0.95"/>'
        f'<stop offset="70%" stop-color="{BLAZE_DARK}" stop-opacity="0.9"/>'
        f'<stop offset="100%" stop-color="#171717" stop-opacity="1"/>'
        f'</radialGradient>'
    )
    parts.append('</defs>')

    # badge ring (antlers are allowed to rise above it -- intentional trophy-badge look)
    parts.append(f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="url(#glow)" stroke="{OUTLINE}" stroke-width="7"/>')

    # antlers first so the head silhouette overlaps their base cleanly
    parts += antler(CX - 54, CY - 100, -1)
    parts += antler(CX + 54, CY - 100, 1)

    # ears
    parts.append(ear(-1))
    parts.append(ear(1))

    # head silhouette (front-facing, rounded diamond)
    head = (
        f"M {CX},{CY-95} "
        f"C {CX-45},{CY-90} {CX-72},{CY-55} {CX-78},{CY-10} "
        f"C {CX-82},{CY+30} {CX-65},{CY+70} {CX-40},{CY+100} "
        f"C {CX-25},{CY+120} {CX-15},{CY+132} {CX},{CY+140} "
        f"C {CX+15},{CY+132} {CX+25},{CY+120} {CX+40},{CY+100} "
        f"C {CX+65},{CY+70} {CX+82},{CY+30} {CX+78},{CY-10} "
        f"C {CX+72},{CY-55} {CX+45},{CY-90} {CX},{CY-95} Z"
    )
    parts.append(f'<path d="{head}" fill="{SIL}" stroke="{OUTLINE}" stroke-width="3"/>')

    # brow ridge highlight
    parts.append(
        f'<path d="M {CX-40},{CY-35} C {CX-20},{CY-45} {CX+20},{CY-45} {CX+40},{CY-35}" fill="none" '
        f'stroke="{BLAZE}" stroke-width="4" stroke-opacity="0.35" stroke-linecap="round"/>'
    )

    # eyes
    for dx in (-34, 34):
        parts.append(f'<ellipse cx="{CX+dx}" cy="{CY-2}" rx="9" ry="13" fill="{CREAM}"/>')
        parts.append(f'<ellipse cx="{CX+dx}" cy="{CY+1}" rx="4.5" ry="7" fill="{OUTLINE}"/>')

    # nose/snout
    parts.append(f'<ellipse cx="{CX}" cy="{CY+112}" rx="27" ry="18" fill="{OUTLINE}"/>')
    parts.append(f'<ellipse cx="{CX-9}" cy="{CY+108}" rx="5" ry="4" fill="#3a2f22"/>')
    parts.append(f'<ellipse cx="{CX+9}" cy="{CY+108}" rx="5" ry="4" fill="#3a2f22"/>')

    parts.append('</svg>')
    return "\n".join(parts)


if __name__ == "__main__":
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "img", "buck.svg"))
    with open(out_path, "w") as f:
        f.write(build_svg())
    print("wrote", out_path)
