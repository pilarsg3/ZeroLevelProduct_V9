"""
component_material_zones.py
───────────────────────────
Each premade component declares its MATERIAL ZONES here — analogous to the
connection points in ``component_anchors.py``. A zone is a named region of the
component made of one material: a solid steel part, or a fluid region (a bore,
a cavity, a pool side). The homogeniser asks a component for its zones, measures
each zone's volume, looks up the material the user assigned to that zone name,
and conserves atoms into a single cylinder.

Why this lives in its own file (same reasoning as anchors)
──────────────────────────────────────────────────────────
The "what parts does this component have, and how big is each" knowledge is
component-specific. Keeping it out of the generic homogeniser means adding a new
component is a one-function change, and the homogeniser never grows an
``if obj_type == ...`` ladder.

A zone function takes the component's dict and returns::

    {"zones":    [Zone(name, role, volume_model_units3), ...],
     "cylinder": {"radius": R, "z_bottom": z0, "height": H}}   # model units

``role`` ("solid"/"fluid") is informational — atom conservation treats both
identically. Volumes are in the model's own length unit cubed; the homogeniser
converts to cm³ using its ``length_unit``.

The user's component dict assigns a material to each declared zone name::

    "materials": {"structure": "ss316", "tube_side": "na2", "shell_side": "na1"}

Zone names that don't match a declared zone (or declared zones with no material)
raise a clear error in the homogeniser — that is how the binding is checked.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple


@dataclass
class Zone:
    name: str
    role: str       # "solid" | "fluid"  (informational)
    volume: float   # model length-units cubed


# ─────────────────────────────────────────────────────────────────────────────
# Small reusable helpers
# ─────────────────────────────────────────────────────────────────────────────
def _ihx_z_layout(spec: Dict[str, Any]) -> Dict[str, float]:
    z_lp_top = float(spec["lower_plenum_height"])
    z_up_bot = z_lp_top + float(spec["bundle_height"])
    z_up_top = z_up_bot + float(spec["upper_plenum_height"])
    return {"z_lp_top": z_lp_top, "z_up_bot": z_up_bot, "z_up_top": z_up_top}


def _ihx_ring_positions(spec: Dict[str, Any]) -> List[Tuple[float, float, float, float]]:
    """[(x, y, inner_radius, outer_radius), ...] for every tube."""
    out: List[Tuple[float, float, float, float]] = []
    if "tube_rings" in spec:
        for ring in spec["tube_rings"]:
            t_ir = float(ring["inner_radius"])
            t_or = t_ir + float(ring["wall"])
            n = int(ring["n"])
            r = float(ring["pitch_radius"])
            a0 = float(ring.get("start_angle_deg", 0.0))
            for i in range(n):
                a = math.radians(a0 + 360.0 * i / n)
                out.append((r * math.cos(a), r * math.sin(a), t_ir, t_or))
    else:
        t_ir = float(spec["tube_inner_radius"])
        t_or = t_ir + float(spec["tube_wall"])
        positions = spec.get("tube_positions")
        if positions is not None:
            for r, th in positions:
                a = math.radians(th)
                out.append((r * math.cos(a), r * math.sin(a), t_ir, t_or))
        else:
            n = int(spec["n_tubes"])
            r = float(spec["tube_pitch_radius"])
            for i in range(n):
                a = 2 * math.pi * i / n
                out.append((r * math.cos(a), r * math.sin(a), t_ir, t_or))
    return out


# ═════════════════════════════════════════════════════════════════════════════
#  IHX  — structure (steel) + tube-side fluid + shell-side fluid
# ═════════════════════════════════════════════════════════════════════════════
def ihx_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    import cadquery as cq
    from components_premade.components_premade_ihx import create_ihx

    L = _ihx_z_layout(spec)
    z_lp_top, z_up_bot, z_up_top = L["z_lp_top"], L["z_up_bot"], L["z_up_top"]

    lp_ir = float(spec["lower_plenum_inner_radius"]); lp_wall = float(spec["lower_plenum_wall"])
    lp_dr = float(spec["lower_plenum_dome_radius"])
    up_ir = float(spec["upper_plenum_inner_radius"]); up_wall = float(spec["upper_plenum_wall"])
    up_dr = float(spec["upper_plenum_dome_radius"]); up_or = up_ir + up_wall
    overshoot = min(lp_wall, up_wall) / 2.0

    structure = create_ihx(spec)
    structure = structure.val() if hasattr(structure, "val") else structure

    def cyl(r, z0, z1, x=0.0, y=0.0):
        h = z1 - z0
        return (cq.Workplane("XY").workplane(offset=z0 + h / 2.0)
                .center(x, y).cylinder(h, r).val())

    def hemi(r, z_eq, upper):
        s = cq.Workplane("XY").workplane(offset=z_eq).sphere(r)
        b = r * 4
        cut = (cq.Workplane("XY").workplane(offset=z_eq - r).box(b, b, r * 2) if upper
               else cq.Workplane("XY").workplane(offset=z_eq + r).box(b, b, r * 2))
        return s.cut(cut).val()

    # ── Tube-side (secondary): tight interiors, then minus steel ──────────────
    parts = [
        cyl(lp_ir, 0.0, z_lp_top - lp_wall),
        hemi(lp_dr - lp_wall, z_eq=0.0, upper=False),
        cyl(up_ir, z_up_bot + up_wall, z_up_top),
        hemi(up_dr - up_wall, z_eq=z_up_top, upper=True),
    ]
    for x, y, t_ir, _ in _ihx_ring_positions(spec):
        parts.append(cyl(t_ir, z_lp_top - lp_wall, z_up_bot + up_wall, x, y))

    cp_ir = float(spec["central_pipe_inner_radius"])
    cp_bend = float(spec["central_pipe_bend_radius"])
    cp_z = float(spec["central_pipe_z_offset"]); cp_horiz = float(spec["central_pipe_horiz_len"])
    z_cp_bend = z_up_bot + cp_z
    z_cp_horiz = z_cp_bend + cp_bend
    z_cp_bot = z_lp_top - overshoot
    x_cp_far = cp_bend + up_or + cp_horiz
    cp_path = (cq.Workplane("XZ").moveTo(0, z_cp_bot).lineTo(0, z_cp_bend)
               .radiusArc((cp_bend, z_cp_horiz), cp_bend).lineTo(x_cp_far, z_cp_horiz)
               .wire().val())
    parts.append(cq.Workplane("XY").workplane(offset=z_cp_bot).circle(cp_ir)
                 .sweep(cq.Workplane("XY").newObject([cp_path]), isFrenet=True).val())

    rs_ir = float(spec["riser_inner_radius"]); rs_wall = float(spec["riser_wall"])
    rs_h = float(spec["riser_height"]); rs_or = rs_ir + rs_wall
    z_clip = z_up_top + math.sqrt(up_dr * up_dr - rs_or * rs_or)
    z_rs_low = z_clip - overshoot
    z_rs_bot = z_up_top + up_dr
    z_cap_top = z_rs_low + rs_h + (z_rs_bot - z_rs_low)
    parts.append(cyl(rs_ir, z_up_top, z_cap_top - rs_wall))

    lat_ir = float(spec["lateral_pipe_inner_radius"]); lat_len = float(spec["lateral_pipe_length"])
    lat_z = float(spec["lateral_pipe_z_offset"])
    parts.append(cq.Workplane("YZ").workplane(offset=rs_ir).center(0, z_rs_bot + lat_z)
                 .circle(lat_ir).extrude(rs_or - rs_ir + lat_len).val())

    secondary = cq.Workplane().newObject([parts[0]])
    for p in parts[1:]:
        secondary = secondary.union(cq.Workplane().newObject([p]))
    secondary = secondary.cut(cq.Workplane().newObject([structure])).val()

    # ── Shell-side (primary): bundle-shell bore between tube sheets, minus rest ─
    bs_ir = float(spec.get("bundle_shell_inner_radius", min(lp_ir, up_ir)))
    h = z_up_bot - z_lp_top
    region = cq.Workplane("XY").workplane(offset=z_lp_top + h / 2.0).cylinder(h, bs_ir).val()
    primary = (cq.Workplane().newObject([region])
               .cut(cq.Workplane().newObject([structure]))
               .cut(cq.Workplane().newObject([secondary])).val())

    radius = max(lp_ir + lp_wall, lp_dr, up_or, up_dr)
    if "bundle_shell_wall" in spec:
        radius = max(radius, bs_ir + float(spec["bundle_shell_wall"]))

    return {
        "zones": [
            Zone("structure", "solid", structure.Volume()),
            Zone("tube_side", "fluid", secondary.Volume()),
            Zone("shell_side", "fluid", primary.Volume()),
        ],
        "cylinder": {"radius": radius, "z_bottom": -lp_dr, "height": (z_up_top + up_dr) - (-lp_dr)},
    }


# ═════════════════════════════════════════════════════════════════════════════
#  Reactor core — one solid zone (cylinder or n-sided prism)
# ═════════════════════════════════════════════════════════════════════════════
def reactor_core_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    from components_premade.components_premade_core import create_reactor_core

    solid = create_reactor_core(
        radius=float(spec["radius"]), height=float(spec["height"]),
        z_bottom=float(spec.get("z_bottom", 0.0)), n_sides=spec.get("n_sides"),
    )
    solid = solid.val() if hasattr(solid, "val") else solid
    z0 = float(spec.get("z_bottom", 0.0))
    return {
        "zones": [Zone("core", "solid", solid.Volume())],
        "cylinder": {"radius": float(spec["radius"]), "z_bottom": z0, "height": float(spec["height"])},
    }


# ═════════════════════════════════════════════════════════════════════════════
#  Diagrid — solid shell + the closed interior cavity (a fluid zone)
# ═════════════════════════════════════════════════════════════════════════════
def diagrid_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    from components_premade.components_premade_diagrid import create_diagrid

    diameter = float(spec["diameter"]); height = float(spec["height"])
    z0 = float(spec.get("z_bottom", 0.0))
    wall = spec.get("wall_t")
    ws = float(wall) if wall is not None else float(spec["wall_t_side"])
    wt = float(wall) if wall is not None else float(spec["wall_t_top"])
    wb = float(wall) if wall is not None else float(spec["wall_t_bottom"])

    shell = create_diagrid(
        diameter=diameter, height=height, z_bottom=z0,
        wall_t_side=ws, wall_t_top=wt, wall_t_bottom=wb,
    )
    shell = shell.val() if hasattr(shell, "val") else shell

    r_inner = diameter / 2.0 - ws
    cavity_h = height - wt - wb
    cavity_vol = math.pi * r_inner * r_inner * cavity_h  # closed interior (no bosses)

    return {
        "zones": [
            Zone("shell", "solid", shell.Volume()),
            Zone("cavity", "fluid", cavity_vol),
        ],
        "cylinder": {"radius": diameter / 2.0, "z_bottom": z0, "height": height},
    }


# ═════════════════════════════════════════════════════════════════════════════
#  Registry  (extend like component_anchors / PREMADE_BUILDERS)
# ═════════════════════════════════════════════════════════════════════════════
MATERIAL_ZONES: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "ihx": ihx_zones,
    "reactor_core": reactor_core_zones,
    "diagrid": diagrid_zones,
    # ── To add: primary_pump, redan, strongback, reactor_top_plate,
    #    above_core_structure, reactor_vessel ─────────────────────────────────
    # Template — copy, build the component, declare its zones + envelope:
    #
    #   def primary_pump_zones(spec):
    #       from components_premade.components_premade_primary_pump import create_primary_pump
    #       solid = create_primary_pump(barrel_radius=spec["barrel_radius"], ...)
    #       # steel = solid.Volume(); barrel/nozzle bores = fluid zones (build masks)
    #       return {"zones": [Zone("structure","solid",...), Zone("bore","fluid",...)],
    #               "cylinder": {"radius": ..., "z_bottom": ..., "height": ...}}
    #
    # The single decision each new component needs: which internal cavities are
    # tracked as fluid here vs. left to the surrounding pool at assembly level.
}