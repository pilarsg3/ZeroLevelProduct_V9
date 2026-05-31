"""
Parametric SFR redan (inner vessel / hot-cold pool separation shell) — ZLP.

The redan is the thin shell of revolution that separates the hot and cold
sodium pools in a pool-type SFR.  Its half-section (the black A–B–C polyline
in the reference sketch) is:

        A ─────────┐                z_top      (large radius r_top)
                   │  top cylinder
                   │
        shoulder ──┤                z_shoulder (optional — kink where taper begins)
                    \\
                     \\  taper
                      \\
        B ─────────────┤            z_knee     (lower radius r_lower)
                       │
                       │  lower cylinder
                       │
        C ─────────────┘            z_bottom   (lower radius r_lower)

Semantics of the three anchor points (see esfr_smr_full_reactor_with_redan_example1.py):
    A  — intersection of the reactor top plate and the inner wall of the
         reactor vessel:           (r_top,   z_top)
    B  — where the top of the core begins:   (r_lower, z_knee)
    C  — the bottom of the core; in practice the shell extends down to rest
         on top of the strongback:           (r_lower, z_bottom)

The A–B–C polyline is taken as ONE SURFACE of the wall (the outer surface by
default, `thickness_side="in"`, so the supplied radii stay flush with the
vessel inner wall / clear the core).  A constant-`thickness` shell is grown
to the chosen side by mitred offset, then the closed half-section is revolved
360° about Z — exactly the same pattern as create_strongback /
create_above_core_structure.

All dimensions are in the model's length unit (metres in the ZLP assemblies).
`thickness` therefore defaults to 0.025 m (= 25 mm), matching the drawing.

No hardcoded reactor dimensions: every geometric quantity is a required
argument (mirroring create_reactor_vessel / create_strongback), so the
reactor-specific values live in the assembly/example file.

Single public function:
    create_redan()  — returns a single cq.Workplane solid (a hollow shell).
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
    """Intersection of p1 + s*d1 and p2 + u*d2. None if (near-)parallel."""
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
    side: int,
) -> list[tuple[float, float]]:
    """
    Offset an open polyline of (r, z) points by a constant distance `t`,
    perpendicular to each segment, all to the same side.

      side = -1 : offset toward the axis (-r)   — wall grows inward
      side = +1 : offset away from the axis (+r) — wall grows outward

    Endpoints use a flat (butt) cap; interior vertices use a true mitre
    (intersection of the two adjacent offset edges), so corners stay sharp
    and the resulting band is gap-free.
    """
    n = len(pts)
    if n < 2:
        raise ValueError("redan profile needs at least 2 points.")

    dirs: list[tuple[float, float]] = []
    norms: list[tuple[float, float]] = []
    for i in range(n - 1):
        ux, uz = _unit(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        dirs.append((ux, uz))
        # outer normal = edge direction rotated +90° = (-uz, ux)
        nx, nz = (-uz, ux)
        if side < 0:
            nx, nz = -nx, -nz
        norms.append((nx, nz))

    off: list[tuple[float, float] | None] = [None] * n
    off[0]     = (pts[0][0]     + t * norms[0][0],     pts[0][1]     + t * norms[0][1])
    off[n - 1] = (pts[n - 1][0] + t * norms[n - 2][0], pts[n - 1][1] + t * norms[n - 2][1])

    for i in range(1, n - 1):
        p_a = (pts[i][0] + t * norms[i - 1][0], pts[i][1] + t * norms[i - 1][1])
        p_b = (pts[i][0] + t * norms[i][0],     pts[i][1] + t * norms[i][1])
        inter = _line_intersection(p_a, dirs[i - 1], p_b, dirs[i])
        if inter is None:                       # collinear edges → average
            inter = ((p_a[0] + p_b[0]) / 2.0, (p_a[1] + p_b[1]) / 2.0)
        off[i] = inter

    return [p for p in off if p is not None]


# ════════════════════════════════════════════════════════════════════════
#  Public API
# ════════════════════════════════════════════════════════════════════════

def create_redan(
    # ── Anchor A — top, at the vessel inner wall / top plate ──────────────
    r_top:   float,            # radius at A [m]
    z_top:   float,            # z of A [m]

    # ── Anchors B and C — lower cylinder wrapping the core ────────────────
    r_lower: float,            # radius of the lower cylinder (B and C) [m]
    z_knee:  float,            # z of B (top of core / top of lower cylinder) [m]
    z_bottom: float,           # z of C (bottom; rests on the strongback) [m]

    # ── Wall ──────────────────────────────────────────────────────────────
    thickness: float = 0.025,  # wall thickness [m]  (25 mm)

    # ── Shape options ─────────────────────────────────────────────────────
    z_shoulder: float | None = None,   # if given: cylindrical top section
                                       # from z_top down to z_shoulder at
                                       # r_top, then taper to (r_lower, z_knee).
                                       # if None: single straight taper A→B.
    thickness_side: str = "in",        # "in"  → wall grows toward the axis
                                       #         (A–B–C is the OUTER surface)
                                       # "out" → wall grows away from the axis
                                       #         (A–B–C is the INNER surface)

    # ── Advanced override ─────────────────────────────────────────────────
    profile_pts: list[tuple[float, float]] | None = None,  # outer half-section
                                       # (r, z) points, top→bottom. If given,
                                       # all the named anchors are ignored and
                                       # only `thickness`/`thickness_side` apply.

    # ── Global position ───────────────────────────────────────────────────
    z_offset: float = 0.0,             # rigid Z shift applied at the end [m]

    # ── Penetrations (IHX / pump pass-throughs) ───────────────────────────
    penetrations: list[tuple[float, float, float]] | None = None,
                                       # [(x, y, r), ...] world-frame XY centres
                                       # and radii.  A vertical cylinder of
                                       # radius r centred at (x, y) is cut,
                                       # creating a clean hole wherever the
                                       # taper crosses it.
) -> cq.Workplane:
    """
    Build the redan by offsetting the A–B–C half-section to a constant-
    thickness band and revolving it 360° about Z.

    Returns
    -------
    cq.Workplane
        A single hollow shell solid (no point of the section touches the
        axis, so the revolve yields a tube-like shell, not a filled solid).
    """
    if thickness <= 0:
        raise ValueError("thickness must be > 0")
    if thickness_side not in ("in", "out"):
        raise ValueError("thickness_side must be 'in' or 'out'")

    # ── Build / accept the OUTER half-section polyline (top → bottom) ─────
    if profile_pts is not None:
        outer = [(float(r), float(z)) for r, z in profile_pts]
        if len(outer) < 2:
            raise ValueError("profile_pts needs at least 2 (r, z) points.")
    else:
        if r_top <= 0 or r_lower <= 0:
            raise ValueError("r_top and r_lower must be > 0")
        if r_top < r_lower:
            raise ValueError(
                f"r_top ({r_top}) must be >= r_lower ({r_lower}); the redan "
                f"tapers inward from top to bottom."
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

    # ── Grow the constant-thickness wall to the chosen side ──────────────
    side = -1 if thickness_side == "in" else +1
    inner = _offset_open_polyline(outer, thickness, side)

    # ── Guard against the wall crossing the axis ─────────────────────────
    min_r = min(r for r, _ in (outer + inner))
    if min_r <= 1e-6:
        raise ValueError(
            f"thickness={thickness} pushes the wall onto / across the axis "
            f"(min radius {min_r:.4g}). Reduce thickness or use "
            f"thickness_side='out'."
        )

    # ── Closed half-section ring: outer top→bottom, then inner bottom→top ─
    ring = list(outer) + list(reversed(inner))

    profile = create_profile_from_straight_connections(ring, plane="XZ", closed=True)
    solid = revolve_profile(profile, angle=360, axis="Z")

    if penetrations:
        all_pts = profile_pts if profile_pts is not None else outer
        z_cut_bot = min(z for _, z in all_pts) - 1.0
        z_cut_top = max(z for _, z in all_pts) + 1.0
        for px, py, pr in penetrations:
            cutter = (
                cq.Workplane("XY")
                .workplane(offset=z_cut_bot)
                .center(px, py)
                .circle(pr)
                .extrude(z_cut_top - z_cut_bot)
            )
            solid = solid.cut(cutter)

    if z_offset != 0.0:
        solid = solid.translate((0.0, 0.0, z_offset))

    return solid.clean()


# ════════════════════════════════════════════════════════════════════════
#  Standalone demo
# ════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from ocp_vscode import show

    redan = create_redan(
        r_top    = 2.36,    # A — vessel inner wall
        z_top    = 5.50,    # A — top plate level
        r_lower  = 1.50,    # B, C — lower cylinder around the core
        z_knee   = 1.60,    # B — top of core
        z_bottom = -0.10,   # C — strongback top
        thickness   = 0.025,
        z_shoulder  = 3.00,
        thickness_side = "in",
    )
    show(redan)

