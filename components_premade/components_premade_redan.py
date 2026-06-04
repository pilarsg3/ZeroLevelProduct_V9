"""
Parametric SFR redan (inner vessel / hot-cold pool separation shell) — ZLP.

Thin shell of revolution separating the hot and cold sodium pools.
The profile specifies the outer surface; the wall grows inward by `thickness`.

Single public function:
    create_redan()  — returns a cq.Workplane hollow shell.
"""

from __future__ import annotations

import math
import cadquery as cq

from profile_from_straight_connections import create_profile_from_straight_connections
from utils import revolve_profile


# ════════════════════════════════════════════════════════════════════════
#  Mitred one-sided offset of an open (r, z) polyline
# ════════════════════════════════════════════════════════════════════════

def _unit(dx: float, dz: float) -> tuple[float, float]:
    L = math.hypot(dx, dz)
    if L < 1e-12:
        raise ValueError("Degenerate (zero-length) segment in redan profile.")
    return dx / L, dz / L


def _line_intersection(
    p1: tuple[float, float], d1: tuple[float, float],
    p2: tuple[float, float], d2: tuple[float, float],
) -> tuple[float, float] | None:
    """Intersection of p1 + s*d1 and p2 + u*d2. None if parallel."""
    a, b = d1[0], -d2[0]
    c, d = d1[1], -d2[1]
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    rx, rz = p2[0] - p1[0], p2[1] - p1[1]
    s = (rx * d - b * rz) / det
    return (p1[0] + s * d1[0], p1[1] + s * d1[1])


def _offset_open_polyline(
    pts: list[tuple[float, float]],
    t: float,
) -> list[tuple[float, float]]:
    """Inward constant-distance offset of an open (r, z) polyline with mitred corners."""
    n = len(pts)
    if n < 2:
        raise ValueError("redan profile needs at least 2 points.")

    dirs: list[tuple[float, float]] = []
    norms: list[tuple[float, float]] = []
    for i in range(n - 1):
        ux, uz = _unit(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        dirs.append((ux, uz))
        norms.append((uz, -ux))  # inward normal (toward axis)

    off: list[tuple[float, float] | None] = [None] * n
    off[0]     = (pts[0][0]     + t * norms[0][0],     pts[0][1]     + t * norms[0][1])
    off[n - 1] = (pts[n - 1][0] + t * norms[n - 2][0], pts[n - 1][1] + t * norms[n - 2][1])

    for i in range(1, n - 1):
        p_a = (pts[i][0] + t * norms[i - 1][0], pts[i][1] + t * norms[i - 1][1])
        p_b = (pts[i][0] + t * norms[i][0],     pts[i][1] + t * norms[i][1])
        inter = _line_intersection(p_a, dirs[i - 1], p_b, dirs[i])
        if inter is None:
            inter = ((p_a[0] + p_b[0]) / 2.0, (p_a[1] + p_b[1]) / 2.0)
        off[i] = inter

    return [p for p in off if p is not None]


# ════════════════════════════════════════════════════════════════════════
#  Public API
# ════════════════════════════════════════════════════════════════════════

def create_redan(
    r_top:    float,           # outer radius of the top rim [m]
    z_top:    float,           # z of the top rim [m]
    r_lower:  float,           # outer radius of the lower cylinder [m]
    z_knee:   float,           # z where the taper meets the lower cylinder [m]
    z_bottom: float,           # z of the bottom [m]
    thickness: float,          # wall thickness [m]
    z_shoulder: float | None,  # if given: vertical section at r_top before the taper
    profile_pts: list[tuple[float, float]] | None,  # custom outer (r, z) points; overrides above
    z_offset: float,           # rigid Z shift [m]
) -> cq.Workplane:
    if thickness <= 0:
        raise ValueError("thickness must be > 0")

    if profile_pts is not None:
        outer = [(float(r), float(z)) for r, z in profile_pts]
        if len(outer) < 2:
            raise ValueError("profile_pts needs at least 2 (r, z) points.")
    else:
        if r_top <= 0 or r_lower <= 0:
            raise ValueError("r_top and r_lower must be > 0")
        if r_top < r_lower:
            raise ValueError(
                f"r_top ({r_top}) must be >= r_lower ({r_lower})."
            )
        if not (z_top > z_knee > z_bottom):
            raise ValueError(
                f"Require z_top > z_knee > z_bottom, got "
                f"{z_top} / {z_knee} / {z_bottom}."
            )
        outer = [(r_top, z_top)]
        if z_shoulder is not None:
            if not (z_top > z_shoulder > z_knee):
                raise ValueError(
                    f"Require z_top > z_shoulder > z_knee, got "
                    f"{z_top} / {z_shoulder} / {z_knee}."
                )
            outer.append((r_top, z_shoulder))
        outer.append((r_lower, z_knee))
        outer.append((r_lower, z_bottom))

    inner = _offset_open_polyline(outer, thickness)

    min_r = min(r for r, _ in (outer + inner))
    if min_r <= 1e-6:
        raise ValueError(
            f"thickness={thickness} pushes the wall onto or across the axis "
            f"(min radius {min_r:.4g})."
        )

    ring = list(outer) + list(reversed(inner))
    profile = create_profile_from_straight_connections(ring, plane="XZ", closed=True)
    solid = revolve_profile(profile, angle=360, axis="Z")

    if z_offset != 0.0:
        solid = solid.translate((0.0, 0.0, z_offset))

    return solid.clean()


# ════════════════════════════════════════════════════════════════════════
#  Standalone demo
# ════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from ocp_vscode import show

    redan = create_redan(
        r_top      = 2.36,
        z_top      = 5.50,
        r_lower    = 1.50,
        z_knee     = 1.60,
        z_bottom   = -0.10,
        thickness  = 0.025,
        z_shoulder = 3.00,
        profile_pts = None,
        z_offset   = 0.0,
    )
    show(redan)
