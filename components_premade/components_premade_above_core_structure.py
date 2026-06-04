"""
Parametric SFR above-core structure (ACS).

Three bodies unioned:

  Lower shell   [0  → z4]   bottom ring + cone + collar + neck
                             revolved around the LOCAL ORIGIN (cone axis).
                             SOLID — no inner bore.

  Closing plate [z4 - closing_plate_height → z4]
                             solid disk (outer r = top_cyl_outer_r),
                             translated by (top_cyl_offset_x, top_cyl_offset_y).

  Upper cylinder [z4 → z5]  plain solid cylinder,
                             translated by (top_cyl_offset_x, top_cyl_offset_y).

The cone-axis stays on the local origin so the lower shell (and the hex
through-hole pattern beneath it) can be aligned with the reactor core by
the assembly's center_coords. The top cylinder can be displaced sideways
via top_cyl_offset_x/y to clear surrounding components.

Stacking order (bottom → top):
  z=0     bottom face
  z1      bottom ring top          ( = bottom_ring_height )
  z2      cone top = collar bottom ( = z1 + cone_height   )
  z3      collar top = neck bottom ( = z2 + collar_height )
  z4      neck top = cylinder bottom ( = z3 + neck_height )
  z5      cylinder top

Single public function:  create_above_core_structure()
"""

from __future__ import annotations
import math
import cadquery as cq

from profile_from_straight_connections import create_profile_from_straight_connections
from utils import revolve_profile


def _dedup(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    EPS = 1e-9
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > EPS or abs(p[1] - out[-1][1]) > EPS:
            out.append(p)
    return out


def _revolve_closed(pts: list[tuple[float, float]]) -> cq.Workplane:
    profile = create_profile_from_straight_connections(_dedup(pts), plane="XZ", closed=True)
    return revolve_profile(profile, angle=360, axis="Z")


def create_above_core_structure(
    # ── Top cylinder — upper axis (0, 0) ─────────────────────────────────
    top_cyl_outer_r: float,
    top_cyl_height:  float,

    # ── Neck — lower / cone axis ──────────────────────────────────────────
    neck_outer_r: float,
    neck_height:  float,

    # ── Collar — lower / cone axis ────────────────────────────────────────
    collar_outer_r: float,
    collar_height:  float,

    # ── Wall thickness (uniform) ──────────────────────────────────────────
    wall_t: float,

    # ── Cone + bottom ring — lower / cone axis ────────────────────────────
    cone_bottom_outer_r: float,
    cone_height:         float,
    bottom_ring_height:  float,

    # ── Closing plate ─────────────────────────────────────────────────────
    closing_plate_height: float,

    # ── Top cylinder offset relative to the lower-shell (cone) axis ──────
    # The lower shell (cone + collar + neck) sits on the local origin. The
    # top cylinder + closing plate are translated by this offset. Set to
    # (0, 0) for a coaxial component; nonzero to displace the top cylinder
    # sideways (e.g. to clear pumps / IHX nozzles in the assembly).
    top_cyl_offset_x: float,
    top_cyl_offset_y: float,

    # ── Optional flow holes on the cone ───────────────────────────────────
    flow_hole_groups: list[dict] | None = None,

    # ── Optional through-holes in the bottom (hex pattern: 1 + 6) ─────────
    # dict with keys:
    #   "through_d":    through-hole diameter [m]                   (e.g. 0.080)
    #   "counter_d":    counterbore diameter   [m]                  (e.g. 0.142)
    #   "counter_depth": counterbore depth from top of plate [m]    (default = closing_plate_height)
    #   "pitch":        center-to-center spacing of the hex ring [m] (default 0.300)
    bottom_holes: dict | None = None,

    # ── Global position ───────────────────────────────────────────────────
    z_bottom: float = 0.0,

) -> cq.Workplane:
    """
    Build the above-core structure as a fused Workplane of three solids:

      1. ``lower_shell``   [0 → z4] — bottom ring + cone + collar + neck.
      2. ``closing_plate`` [z4 - closing_plate_height → z4]
      3. ``upper_cyl``     [z4 → z5]

    Boolean ops (flow holes, bottom holes) are applied to each part before
    the final union.
    """
    # ── Validate ─────────────────────────────────────────────────────────
    checks = [
        (collar_outer_r >= neck_outer_r,     "collar_outer_r >= neck_outer_r"),
        (neck_outer_r > wall_t,              "neck_outer_r > wall_t"),
        (cone_bottom_outer_r > neck_outer_r, "cone_bottom_outer_r > neck_outer_r"),
        (closing_plate_height > 0,           "closing_plate_height > 0"),
    ]
    for ok, msg in checks:
        if not ok:
            raise ValueError(f"Validation failed: {msg}")
    for name, val in [
        ("top_cyl_height", top_cyl_height),
        ("top_cyl_outer_r", top_cyl_outer_r),
        ("neck_height", neck_height), ("collar_height", collar_height),
        ("cone_height", cone_height), ("bottom_ring_height", bottom_ring_height),
        ("wall_t", wall_t),
    ]:
        if val <= 0:
            raise ValueError(f"{name} must be > 0")

    # ── Z levels ──────────────────────────────────────────────────────────
    z1 = bottom_ring_height
    z2 = z1 + cone_height
    z3 = z2 + collar_height
    z4 = z3 + neck_height        # ← axis split
    z5 = z4 + top_cyl_height

    # ── 1. Lower shell (solid — no inner bore) ────────────────────────────
    # The lower shell sits on the LOCAL ORIGIN. The top cylinder + closing
    # plate are the ones that carry top_cyl_offset_x/y. This way the cone /
    # collar / cone-axis hole pattern stay on the assembly's central axis
    # (and so can be aligned with the reactor core), while the top cylinder
    # gets displaced sideways.
    lower_pts = [
        # outer (upward)
        (cone_bottom_outer_r, 0),
        (cone_bottom_outer_r, z1),
        (neck_outer_r,        z2),
        (collar_outer_r,      z2),
        (collar_outer_r,      z3),
        (neck_outer_r,        z3),
        (neck_outer_r,        z4),
        # close along the axis back down to z=0
        (0,                   z4),
        (0,                   0),
    ]
    lower_solid = _revolve_closed(lower_pts)

    # ── 2. Closing plate ──────────────────────────────────────────────────
    # Full disk; translated to the top-cylinder offset.
    closing_plate = (
        cq.Workplane("XY")
        .workplane(offset=z4 - closing_plate_height)
        .circle(top_cyl_outer_r)
        .extrude(closing_plate_height)
    )
    if top_cyl_offset_x != 0.0 or top_cyl_offset_y != 0.0:
        closing_plate = closing_plate.translate((top_cyl_offset_x, top_cyl_offset_y, 0))

    # ── 3. Upper cylinder ─────────────────────────────────────────────────
    upper_solid = (
        cq.Workplane("XY")
        .workplane(offset=z4)
        .circle(top_cyl_outer_r)
        .extrude(top_cyl_height)
    )
    if top_cyl_offset_x != 0.0 or top_cyl_offset_y != 0.0:
        upper_solid = upper_solid.translate((top_cyl_offset_x, top_cyl_offset_y, 0))

    # ── 4. Flow holes → applied to lower_solid only ───────────────────────
    if flow_hole_groups:
        for group in flow_hole_groups:
            hole_r  = float(group["hole_r"])
            z_c     = float(group["z_center"])
            n       = int(group["n_holes"])
            start_a = float(group.get("start_angle_deg", 0.0))
            if z_c < 0 or z_c > z4:
                raise ValueError(f"z_center={z_c} outside [0, {z4:.4f}] (lower shell range)")
            if z_c <= z1:
                r_mid = cone_bottom_outer_r - wall_t / 2.0
            elif z_c <= z2:
                frac  = (z_c - z1) / (z2 - z1)
                r_out = cone_bottom_outer_r + frac * (neck_outer_r - cone_bottom_outer_r)
                r_mid = r_out - wall_t / 2.0
            else:
                r_mid = neck_outer_r - wall_t / 2.0
            for i in range(n):
                a  = math.radians(start_a + 360.0 * i / n)
                hx = r_mid * math.cos(a)
                hy = r_mid * math.sin(a)
                cutter = (
                    cq.Workplane("XY").workplane(offset=z_c)
                    .circle(hole_r).extrude(wall_t * 2)
                    .translate((hx, hy, -wall_t))
                )
                lower_solid = lower_solid.cut(cutter)

    # ── 5. Bottom hex through-holes + counterbores ────────────────────────
    # Through-holes go through lower_solid + closing_plate + upper_solid.
    # Counterbores are pocketed into the closing_plate.
    if bottom_holes:
        through_d     = float(bottom_holes["through_d"])
        counter_d     = float(bottom_holes["counter_d"])
        counter_depth = float(bottom_holes.get("counter_depth", closing_plate_height))
        pitch         = float(bottom_holes.get("pitch", 0.300))

        if counter_d <= through_d:
            raise ValueError("counter_d must be greater than through_d")
        if counter_depth <= 0 or counter_depth > closing_plate_height:
            raise ValueError(f"counter_depth ({counter_depth}) must be in (0, closing_plate_height={closing_plate_height}]")

        through_r = through_d / 2.0
        counter_r = counter_d / 2.0

        centers = [(0.0, 0.0)]
        for i in range(6):
            a = math.radians(60.0 * i)
            centers.append((pitch * math.cos(a), pitch * math.sin(a)))

        EPS = 1e-4
        for hx, hy in centers:
            through_cutter = (
                cq.Workplane("XY")
                .workplane(offset=-EPS)
                .circle(through_r)
                .extrude(z5 + 2 * EPS)
                .translate((hx, hy, 0))
            )
            lower_solid   = lower_solid.cut(through_cutter)
            closing_plate = closing_plate.cut(through_cutter)
            upper_solid   = upper_solid.cut(through_cutter)

            counter_cutter = (
                cq.Workplane("XY")
                .workplane(offset=z4 - counter_depth)
                .circle(counter_r)
                .extrude(counter_depth + EPS)
                .translate((hx, hy, 0))
            )
            closing_plate = closing_plate.cut(counter_cutter)

    # ── 6. Final z translation ────────────────────────────────────────────
    if z_bottom != 0.0:
        lower_solid   = lower_solid.translate((0, 0, z_bottom))
        closing_plate = closing_plate.translate((0, 0, z_bottom))
        upper_solid   = upper_solid.translate((0, 0, z_bottom))

    # ── 7. Assemble ───────────────────────────────────────────────────────
    return lower_solid.union(closing_plate).union(upper_solid).clean()


if __name__ == "__main__":
    from ocp_vscode import show

    assy = create_above_core_structure(
        top_cyl_outer_r      = 1.843,
        top_cyl_height       = 1.008,
        neck_outer_r         = 1.1085,
        neck_height          = 0.569,
        collar_outer_r       = 1.1085,
        collar_height        = 0.092,
        wall_t               = 0.025,
        cone_height          = 2.429,
        cone_bottom_outer_r  = 1.403,
        bottom_ring_height   = 0.498,
        closing_plate_height = 0.050,
        top_cyl_offset_x     = 0.6056,
        top_cyl_offset_y     = 0.0,
        bottom_holes = {
            "through_d":     0.080,
            "counter_d":     0.142,
            "counter_depth": 0.050,
            "pitch":         0.300,
        },
    )
    show(assy)

