"""
Same pump assembly, but with the left/right nozzle symmetry fixed.
 
Previous bug: the left elbow was built via `mirror('YZ')` then rotated +90°
about Z. The mirror flipped the elbow's handedness (a right-hand bend
became a left-hand bend in the local frame), and the subsequent rotation
then mapped that flipped frame to world coords in a slightly-off way.
 
Fix: don't mirror at all. Build the elbow once (right-hand bend, inlet
along +Y, curves toward +X). Place the right nozzle with one rotation,
and place the left nozzle with a DIFFERENT rotation that takes the same
unmirrored elbow to the +X-curving-toward-+Y... wait, that's wrong too.
 
The clean approach: build the elbow once, place the right copy by rotating
the local +Y axis to point along world +X. For the left copy, we want a
mirror image — but we achieve it by mirroring AFTER placement, not before.
So place the right elbow first, then mirror the world-frame result across
the YZ plane to produce the left copy.
 
Because mirroring is the LAST operation, the final positions of the two
nozzles are exact mirror images of each other — no compounded transform
errors.
 
Implementation note: calling .mirror("YZ") on a swept OCCT solid produces
a shape with REVERSED face orientation, which causes .union() to hang
indefinitely. Fix: construct the left elbow by reflecting the path wire
analytically (mirror_x=True in _elbow_path_wire) and sweeping a fresh
solid. Result is geometrically identical to the mirrored solid but with
correct outward normals.
"""
 
from __future__ import annotations
import math
import cadquery as cq
 
from profile_built_in_2D_sketch import build_2D_sketch
from utils import sweep_profile
 
 
# ──────────────────────────────────────────────────────────────────────
# Elbow centerline + sweep
# ──────────────────────────────────────────────────────────────────────
def _elbow_path_wire(
    R_bend: float, arc_deg: float, L_inlet: float, L_leg: float,
    overshoot: float = 0.0,
    mirror_x: bool = False,
) -> cq.Wire:
    arc_rad = math.radians(arc_deg)
    sx = -1.0 if mirror_x else 1.0  # reflects arc into -X half-plane
 
    P_arc_start = (0.0, L_inlet, 0.0)
    P_arc_end   = (sx * R_bend * (1.0 - math.cos(arc_rad)),
                   L_inlet + R_bend * math.sin(arc_rad),
                   0.0)
    tan_end     = (sx * math.sin(arc_rad), math.cos(arc_rad), 0.0)
 
    leg_total = L_leg + overshoot
    P_end     = (P_arc_end[0] + leg_total * tan_end[0],
                 P_arc_end[1] + leg_total * tan_end[1],
                 0.0)
 
    half      = arc_rad / 2.0
    P_arc_mid = (sx * R_bend * (1.0 - math.cos(half)),
                 L_inlet + R_bend * math.sin(half),
                 0.0)
 
    edges = [
        cq.Edge.makeLine(cq.Vector(0.0, 0.0, 0.0),
                         cq.Vector(*P_arc_start)),
        cq.Edge.makeThreePointArc(cq.Vector(*P_arc_start),
                                  cq.Vector(*P_arc_mid),
                                  cq.Vector(*P_arc_end)),
    ]
    if leg_total > 0:
        edges.append(cq.Edge.makeLine(cq.Vector(*P_arc_end),
                                      cq.Vector(*P_end)))
 
    return cq.Wire.assembleEdges(edges)
 
 
def _build_elbow_outer_inner(
    r_pipe: float, wall_t: float,
    R_bend: float, arc_deg: float,
    L_inlet: float, L_leg: float,
    inner_overshoot: float,
    mirror_x: bool = False,
):
    outer_path = _elbow_path_wire(R_bend, arc_deg, L_inlet, L_leg,
                                  overshoot=0.0,            mirror_x=mirror_x)
    inner_path = _elbow_path_wire(R_bend, arc_deg, L_inlet, L_leg,
                                  overshoot=inner_overshoot, mirror_x=mirror_x)
 
    profile_outer = build_2D_sketch({"obj_type": "circle", "radius": r_pipe},          sketch_plane="XY")
    profile_inner = build_2D_sketch({"obj_type": "circle", "radius": r_pipe - wall_t}, sketch_plane="XY")
 
    outer = sweep_profile(profile_outer, outer_path, isFrenet=True)
    inner = sweep_profile(profile_inner, inner_path, isFrenet=True)
    return outer, inner
 
 
def _place_right_nozzle(elbow: cq.Workplane,
                        barrel_radius: float, overshoot: float,
                        nozzle_z: float) -> cq.Workplane:
    """Rotate so local +Y → world +X, translate to right side of barrel."""
    return (elbow
            .rotate((0, 0, 0), (0, 0, 1), -90)
            .translate((barrel_radius - overshoot, 0, nozzle_z)))
 
 
def _place_left_nozzle(elbow: cq.Workplane,
                       barrel_radius: float, overshoot: float,
                       nozzle_z: float) -> cq.Workplane:
    """Rotate so local +Y → world -X, translate to left side of barrel.
    Pair with a mirror_x=True elbow to get true mirror geometry without
    calling .mirror() on a solid (which inverts OCCT face normals)."""
    return (elbow
            .rotate((0, 0, 0), (0, 0, 1), 90)
            .translate((-(barrel_radius - overshoot), 0, nozzle_z)))
 
 
# ──────────────────────────────────────────────────────────────────────
# Pump assembly
# ──────────────────────────────────────────────────────────────────────
def create_primary_pump(
    barrel_radius:  float,
    barrel_wall_t:  float,
    barrel_height:  float,
    nozzle_r_pipe:  float,
    nozzle_wall_t:  float,
    nozzle_L_leg:   float,
    nozzle_R_bend:  float,
    nozzle_arc_deg: float,
    nozzle_L_inlet: float,
    nozzle_z:       float,
    flange_width:   float,
    flange_height:  float,
    flange_depth:   float,
    z_bottom:       float = 0.0,
    flange_z_top:   float | None = None,
) -> cq.Workplane:
 
    if flange_z_top is None:
        flange_z_top = barrel_height - 0.5
 
    overshoot       = barrel_wall_t
    inner_overshoot = nozzle_wall_t * 2
 
    barrel_outer = cq.Workplane("XY").circle(barrel_radius).extrude(barrel_height)
 
    # Right elbow: arc curves toward +X
    elbow_out_R, elbow_in_R = _build_elbow_outer_inner(
        r_pipe=nozzle_r_pipe, wall_t=nozzle_wall_t,
        R_bend=nozzle_R_bend, arc_deg=nozzle_arc_deg,
        L_inlet=nozzle_L_inlet, L_leg=nozzle_L_leg,
        inner_overshoot=inner_overshoot, mirror_x=False,
    )
    # Left elbow: arc curves toward -X (analytically mirrored path, fresh sweep)
    elbow_out_L, elbow_in_L = _build_elbow_outer_inner(
        r_pipe=nozzle_r_pipe, wall_t=nozzle_wall_t,
        R_bend=nozzle_R_bend, arc_deg=nozzle_arc_deg,
        L_inlet=nozzle_L_inlet, L_leg=nozzle_L_leg,
        inner_overshoot=inner_overshoot, mirror_x=True,
    )
 
    j_right_out = _place_right_nozzle(elbow_out_R, barrel_radius, overshoot, nozzle_z)
    j_right_in  = _place_right_nozzle(elbow_in_R,  barrel_radius, overshoot, nozzle_z)
    j_left_out  = _place_left_nozzle( elbow_out_L, barrel_radius, overshoot, nozzle_z)
    j_left_in   = _place_left_nozzle( elbow_in_L,  barrel_radius, overshoot, nozzle_z)
 
    flange = (cq.Workplane("XY")
              .workplane(offset=flange_z_top - flange_height)
              .moveTo(0, barrel_radius + flange_width / 2 - overshoot)
              .rect(flange_depth, flange_width)
              .extrude(flange_height))
 
    barrel_bore = (cq.Workplane("XY")
                   .workplane(offset=barrel_wall_t)
                   .circle(barrel_radius - barrel_wall_t)
                   .extrude(barrel_height - 2 * barrel_wall_t))
 
    # Radial bore punches: j_right_in / j_left_in start exactly at the barrel
    # inner cylindrical surface (x = barrel_inner_radius), making only tangent
    # (zero-area) contact there. These straight punches start from the barrel
    # axis (x = 0) and penetrate through the inner surface, creating a proper
    # 2D curved opening that connects the barrel interior to each nozzle bore.
    nozzle_r_bore    = nozzle_r_pipe - nozzle_wall_t
    bore_punch_right = (
        cq.Workplane("YZ")
        .workplane(offset=0)
        .center(0, nozzle_z)
        .circle(nozzle_r_bore)
        .extrude(barrel_radius + 1.0)
    )
    bore_punch_left = bore_punch_right.mirror("YZ")
 
    # Flange bore: same tangent-contact issue as the nozzles — the flange inner
    # face starts at y = barrel_inner_radius, making zero-area contact with the
    # barrel's inner cylindrical surface. This box cutter starts from the barrel
    # axis (y = 0) and extends in +Y through the barrel wall and INTO the flange,
    # but STOPS short of the flange's outer face by barrel_wall_t. This opens the
    # flange cavity toward the barrel interior only, while leaving a closed outer
    # wall (a blind pocket) — i.e. walls of barrel_wall_t on all four lateral
    # sides AND on the outer end. The inner end stays open to the barrel.
    # Built as an explicit box (not a workplane extrude) to avoid sign ambiguity
    # in the XZ workplane normal direction.
    #
    # Flange outer face is at y = barrel_radius + flange_width - overshoot
    # (overshoot = barrel_wall_t). To leave a barrel_wall_t-thick cap there, the
    # cutter must reach only to (outer_face - barrel_wall_t) =
    # barrel_radius + flange_width - 2 * barrel_wall_t, starting from y = 0.
    _fb_w   = flange_depth  - 2 * barrel_wall_t
    _fb_len = barrel_radius + flange_width - 2 * barrel_wall_t
    _fb_h   = flange_height - 2 * barrel_wall_t
    flange_bore_cutter = (
        cq.Workplane("XY")
        .box(_fb_w, _fb_len, _fb_h)
        .translate((0.0, _fb_len / 2, flange_z_top - flange_height / 2))
    )
 
    barrel       = barrel_outer.cut(barrel_bore).cut(j_right_in).cut(j_left_in).cut(bore_punch_right).cut(bore_punch_left).cut(flange_bore_cutter).clean()
    # Do NOT cut barrel_outer from nozzles. The inlet section starts at
    # barrel_radius - overshoot (inside the barrel wall), giving volumetric
    # overlap needed for reliable OCCT fusion. Cutting barrel_outer would
    # reduce the contact to a coincident face only → invalid/red solid.
    nozzle_right = j_right_out.cut(j_right_in).clean()
    nozzle_left  = j_left_out.cut(j_left_in).clean()
    flange       = flange.cut(flange_bore_cutter).clean()
 
    return barrel.union(nozzle_right).union(nozzle_left).union(flange).clean()
 
 
# ──────────────────────────────────────────────────────────────────────
# Demo
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from ocp_vscode import show
 
    pump = create_primary_pump(
        barrel_radius  = 1.350 / 2,
        barrel_wall_t  = 0.040,
        barrel_height  = 12.000,
        nozzle_r_pipe  = 0.460 / 2,
        nozzle_wall_t  = 0.025,
        nozzle_L_leg   = 0.600,
        nozzle_R_bend  = 0.460,
        nozzle_arc_deg = 105.0,
        nozzle_L_inlet = 0.050,
        nozzle_z       = 0.450,
        flange_width   = 0.548,
        flange_height  = 0.900,
        flange_depth   = 0.500,
    )
    show(pump)
 
 
 
 
 
 
 
 
 
 
 
 