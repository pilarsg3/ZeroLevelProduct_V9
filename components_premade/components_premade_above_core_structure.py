"""
Parametric SFR above-core structure (ACS).

Two bodies unioned:

  Lower shell    [0  → z3]   bottom ring + cone + neck
                             revolved around the LOCAL ORIGIN (cone axis).
                             Hollow shell — wall thickness = wall_t.

  Top cylinder   [z3 → z4]   plain solid cylinder (outer r = top_cyl_outer_r),
                             translated by (top_cyl_offset_x, top_cyl_offset_y).
                             The former separate closing plate has been merged
                             into this single cylinder.

The cone-axis stays on the local origin so the lower shell (and the hex
through-hole pattern beneath it) can be aligned with the reactor core by
the assembly's center_coords. The top cylinder can be displaced sideways
via top_cyl_offset_x/y to clear surrounding components.

Stacking order (bottom → top):
  z=0     bottom face
  z1      bottom ring top            ( = bottom_ring_height )
  z2      cone top = neck bottom     ( = z1 + cone_height   )
  z3      neck top = cylinder bottom ( = z2 + neck_height   )
  z4      cylinder top               ( = z3 + top_cyl_height )

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

    # ── Wall thickness (uniform) ──────────────────────────────────────────
    wall_t: float,

    # ── Cone + bottom ring — lower / cone axis ────────────────────────────
    cone_bottom_outer_r: float,
    cone_height:         float,
    bottom_ring_height:  float,

    # ── Top cylinder offset relative to the lower-shell (cone) axis ──────
    # The lower shell (cone + neck) sits on the local origin. The top
    # cylinder is translated by this offset. Set to (0, 0) for a coaxial
    # component; nonzero to displace the top cylinder sideways (e.g. to
    # clear pumps / IHX nozzles in the assembly).
    top_cyl_offset_x: float,
    top_cyl_offset_y: float,

    # ── Optional flow holes on the cone ───────────────────────────────────
    flow_hole_groups: list[dict] | None = None,

    # ── Control rod drive lines — CRDL (hex pattern: 1 + 6) ──────────────
    # dict with keys:
    #   "through_d":          inner bore diameter [m]                (e.g. 0.080)
    #   "pitch":              center-to-center hex ring spacing [m]  (default 0.300)
    #   "pipe_wall_t":        tube wall thickness [m]                (default 0.0)
    #   "pipe_extend_bottom": protrusion below z=0 [m]               (default 0.0)
    #   "pipe_extend_top":    protrusion above top cylinder [m]      (default 0.0)
    crdl: dict | None = None,

    # ── Bottom perforated plate (fits inside the lower shell at z=0) ────
    # dict with keys:
    #   "thickness": plate thickness [m]
    # Outer radius is cone_bottom_outer_r - wall_t (inner radius of the shell),
    # so the plate sits inside the hollow cone.
    # Holes are punched at each CRDL centre, sized to the pipe outer diameter,
    # so the CRDL tubes pass through cleanly.
    bottom_plate: dict | None = None,

    # ── Global position ───────────────────────────────────────────────────
    z_bottom: float = 0.0,

) -> cq.Workplane:
    """
    Build the above-core structure as a fused Workplane of two solids:

      1. ``lower_shell`` [0 → z3] — bottom ring + cone + neck.
      2. ``top_cyl``     [z3 → z4] — a single solid cylinder (the former
         closing plate is merged into this cylinder).

    Boolean ops (flow holes, bottom holes) are applied to each part before
    the final union. The straight section above the cone is a single neck at
    ``neck_outer_r``; there is no separate collar band, and the top cylinder
    is a single body with no separate closing plate.
    """
    # ── Validate ─────────────────────────────────────────────────────────
    checks = [
        (neck_outer_r > wall_t,              "neck_outer_r > wall_t"),
        (cone_bottom_outer_r > neck_outer_r, "cone_bottom_outer_r > neck_outer_r"),
    ]
    for ok, msg in checks:
        if not ok:
            raise ValueError(f"Validation failed: {msg}")
    for name, val in [
        ("top_cyl_height", top_cyl_height),
        ("top_cyl_outer_r", top_cyl_outer_r),
        ("neck_height", neck_height),
        ("cone_height", cone_height), ("bottom_ring_height", bottom_ring_height),
        ("wall_t", wall_t),
    ]:
        if val <= 0:
            raise ValueError(f"{name} must be > 0")

    # ── Z levels ──────────────────────────────────────────────────────────
    z1 = bottom_ring_height
    z2 = z1 + cone_height        # cone top = neck bottom
    z3 = z2 + neck_height        # ← axis split (neck top = cylinder bottom)
    z4 = z3 + top_cyl_height

    # ── 1. Lower shell (hollow — wall thickness wall_t) ───────────────────
    # The lower shell sits on the LOCAL ORIGIN. The top cylinder + closing
    # plate are the ones that carry top_cyl_offset_x/y. This way the cone /
    # cone-axis hole pattern stay on the assembly's central axis (and so can
    # be aligned with the reactor core), while the top cylinder gets
    # displaced sideways.
    lower_pts = [
        # outer face (upward)
        (cone_bottom_outer_r,          0),
        (cone_bottom_outer_r,          z1),
        (neck_outer_r,                 z2),
        (neck_outer_r,                 z3),
        # inner face (downward) — uniform wall thickness wall_t
        (neck_outer_r - wall_t,        z3),
        (neck_outer_r - wall_t,        z2),
        (cone_bottom_outer_r - wall_t, z1),
        (cone_bottom_outer_r - wall_t, 0),
    ]
    lower_solid = _revolve_closed(lower_pts)

    # ── 2. Top cylinder (single solid — closing plate merged in) ──────────
    # One plain solid cylinder spanning [z3 → z4], translated to the
    # top-cylinder offset. This replaces the former separate closing plate
    # and upper cylinder (which were coaxial and the same radius, so their
    # union was always a single cylinder).
    top_cyl = (
        cq.Workplane("XY")
        .workplane(offset=z3)
        .circle(top_cyl_outer_r)
        .extrude(top_cyl_height)
    )
    if top_cyl_offset_x != 0.0 or top_cyl_offset_y != 0.0:
        top_cyl = top_cyl.translate((top_cyl_offset_x, top_cyl_offset_y, 0))

    # ── 3. Flow holes → applied to lower_solid only ───────────────────────
    # Cutters are drilled radially (horizontal axis pointing toward the cone
    # centre) so they appear as circles on the cone surface, not rectangles.
    if flow_hole_groups:
        for group in flow_hole_groups:
            hole_r  = float(group["hole_r"])
            z_c     = float(group["z_center"])
            n       = int(group["n_holes"])
            start_a = float(group.get("start_angle_deg", 0.0))
            if z_c < 0 or z_c > z3:
                raise ValueError(f"z_center={z_c} outside [0, {z3:.4f}] (lower shell range)")
            if z_c <= z1:
                r_out = cone_bottom_outer_r
            elif z_c <= z2:
                frac  = (z_c - z1) / (z2 - z1)
                r_out = cone_bottom_outer_r + frac * (neck_outer_r - cone_bottom_outer_r)
            else:
                r_out = neck_outer_r
            EPS_h = 1e-4
            for i in range(n):
                a     = math.radians(start_a + 360.0 * i / n)
                cos_a = math.cos(a)
                sin_a = math.sin(a)
                # Workplane sits just outside the outer surface; normal points
                # radially inward so the extrusion drills straight through.
                plane = cq.Plane(
                    origin=((r_out + EPS_h) * cos_a,
                            (r_out + EPS_h) * sin_a,
                            z_c),
                    xDir=(0, 0, 1),
                    normal=(-cos_a, -sin_a, 0),
                )
                cutter = (
                    cq.Workplane(plane)
                    .circle(hole_r)
                    .extrude(wall_t + 2 * EPS_h)
                )
                lower_solid = lower_solid.cut(cutter)

    # ── 4. Control rod drive lines — CRDL (1 + 6 hex pattern) ───────────
    # through_d = inner bore; pipe_wall_t = tube wall; extend_bottom/top
    # control how far the tubes protrude beyond the structure faces.
    if crdl:
        through_d          = float(crdl["through_d"])
        pitch              = float(crdl.get("pitch", 0.300))
        pipe_wall_t        = float(crdl.get("pipe_wall_t", 0.0))
        pipe_extend_bottom = float(crdl.get("pipe_extend_bottom", 0.0))
        pipe_extend_top    = float(crdl.get("pipe_extend_top",    0.0))

        if through_d <= 0:
            raise ValueError("through_d must be > 0")

        through_r    = through_d / 2.0
        pipe_outer_r = through_r + pipe_wall_t
        pipe_z0      = -pipe_extend_bottom          # pipe bottom (≤ 0)
        pipe_z1      = z4 + pipe_extend_top         # pipe top   (≥ z4)
        pipe_h       = pipe_z1 - pipe_z0

        centers = [(0.0, 0.0)]
        for i in range(6):
            a = math.radians(60.0 * i)
            centers.append((pitch * math.cos(a), pitch * math.sin(a)))

        EPS = 1e-4
        for hx, hy in centers:
            bore_cutter = (
                cq.Workplane("XY")
                .workplane(offset=pipe_z0 - EPS)
                .circle(through_r)
                .extrude(pipe_h + 2 * EPS)
                .translate((hx, hy, 0))
            )
            if pipe_wall_t > 0:
                pipe_outer_cyl = (
                    cq.Workplane("XY")
                    .workplane(offset=pipe_z0)
                    .circle(pipe_outer_r)
                    .extrude(pipe_h)
                    .translate((hx, hy, 0))
                )
                lower_solid = lower_solid.union(pipe_outer_cyl)
            lower_solid = lower_solid.cut(bore_cutter)
            top_cyl     = top_cyl.cut(bore_cutter)

    # ── 5. Bottom perforated plate ────────────────────────────────────────
    if bottom_plate:
        plate_t = float(bottom_plate["thickness"])
        plate_r = cone_bottom_outer_r - wall_t

        plate = (
            cq.Workplane("XY")
            .workplane(offset=-plate_t)
            .circle(plate_r)
            .extrude(plate_t)
        )

        if crdl:
            p_bore_r = float(crdl["through_d"]) / 2.0 + float(crdl.get("pipe_wall_t", 0.0))
            p_pitch  = float(crdl.get("pitch", 0.300))
            p_centers = [(0.0, 0.0)]
            for i in range(6):
                a = math.radians(60.0 * i)
                p_centers.append((p_pitch * math.cos(a), p_pitch * math.sin(a)))

            EPS = 1e-4
            for hx, hy in p_centers:
                hole = (
                    cq.Workplane("XY")
                    .workplane(offset=-plate_t - EPS)
                    .circle(p_bore_r)
                    .extrude(plate_t + 2 * EPS)
                    .translate((hx, hy, 0))
                )
                plate = plate.cut(hole)

        lower_solid = lower_solid.union(plate)

    # ── 6. Final z translation ────────────────────────────────────────────
    if z_bottom != 0.0:
        lower_solid = lower_solid.translate((0, 0, z_bottom))
        top_cyl     = top_cyl.translate((0, 0, z_bottom))

    # ── 7. Assemble ───────────────────────────────────────────────────────
    return lower_solid.union(top_cyl).clean()


if __name__ == "__main__":
    from ocp_vscode import show

    assy = create_above_core_structure(
        top_cyl_outer_r      = 1.843,
        top_cyl_height       = 1.008,
        neck_outer_r         = 1.1085,
        neck_height          = 0.661,   # = old collar_height (0.092) + neck_height (0.569)
        wall_t               = 0.025,
        cone_height          = 2.429,
        cone_bottom_outer_r  = 1.403,
        bottom_ring_height   = 0.498,
        top_cyl_offset_x     = 0.6056,
        top_cyl_offset_y     = 0.0,
        crdl = {
            "through_d":          0.080,
            "pitch":              0.300,
            "pipe_wall_t":        0.005,
            "pipe_extend_bottom": 0.300,
            "pipe_extend_top":    0.300,
        },
        bottom_plate = {
            "thickness": 0.050,
        },
    )
    show(assy)