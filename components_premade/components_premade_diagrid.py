"""
Parametric diagrid — final version.

Hollow short cylinder with thin walls (default 30 mm on all sides) closed
top and bottom, with lateral bosses for pump-elbow connection. The bores
pierce the lateral wall and open into the interior cavity.

Key changes vs early versions:
  - `wall_t` split into `wall_t_side`, `wall_t_top`, `wall_t_bottom` so the
    plates can be thinner than the lateral wall (or vice versa) without
    blocking the bore.
  - Bore length is computed analytically so the LATERAL edges of the
    bore — not just the centerline — pierce the inner wall, avoiding the
    "vertical strip" rendering artifact.
  - Bosses are inset into the outer wall before being extruded radially
    outward, so the union with the curved wall is gap-free.
  - Validation: raises a clear error if the top/bottom plate would clip
    the bore, or if the boss vertically extends past the disc faces.
"""

from __future__ import annotations
import math
import cadquery as cq


def create_diagrid(
    diameter:               float,
    thickness:              float,
    z_bottom:               float = 0.0,
    wall_t:                 float | None = None,   # legacy alias for all three
    wall_t_side:            float = 0.030,
    wall_t_top:             float = 0.030,
    wall_t_bottom:          float = 0.030,
    open_top:               bool  = False,
    open_bottom:            bool  = False,
    nozzle_boss_angles_deg: list[float] | None = None,
    nozzle_z_abs:           float | None = None,
    nozzle_r_bore:          float = 0.230,
    nozzle_r_boss:          float = 0.301,
    nozzle_boss_height:     float = 0.0775,
) -> cq.Workplane:

    # Legacy support
    if wall_t is not None:
        wall_t_side = wall_t_top = wall_t_bottom = wall_t

    if diameter <= 0 or thickness <= 0:
        raise ValueError("diameter and thickness must be > 0")
    if wall_t_side <= 0:
        raise ValueError("wall_t_side must be > 0")
    if wall_t_top < 0 or wall_t_bottom < 0:
        raise ValueError("wall_t_top and wall_t_bottom must be ≥ 0")

    radius_outer = diameter / 2.0
    radius_inner = radius_outer - wall_t_side
    if radius_inner <= 0:
        raise ValueError(
            f"wall_t_side ({wall_t_side}) is too large for diameter ({diameter})."
        )

    z_top = z_bottom + thickness

    cavity_z_bottom = z_bottom if open_bottom else z_bottom + wall_t_bottom
    cavity_z_top    = z_top    if open_top    else z_top    - wall_t_top
    cavity_height   = cavity_z_top - cavity_z_bottom
    if cavity_height <= 0:
        raise ValueError(
            f"wall_t_top + wall_t_bottom ({wall_t_top + wall_t_bottom}) "
            f"is too large for thickness ({thickness})."
        )

    # Bore obstruction check
    if nozzle_z_abs is not None and nozzle_boss_angles_deg:
        bore_z_low  = nozzle_z_abs - nozzle_r_bore
        bore_z_high = nozzle_z_abs + nozzle_r_bore
        if (not open_top) and bore_z_high > cavity_z_top:
            raise ValueError(
                f"Top plate (Z = [{cavity_z_top:.4f}, {z_top:.4f}]) "
                f"overlaps the bore (Z = [{bore_z_low:.4f}, "
                f"{bore_z_high:.4f}]). Reduce wall_t_top to ≤ "
                f"{(z_top - bore_z_high):.4f} m or move the bore down."
            )
        if (not open_bottom) and bore_z_low < cavity_z_bottom:
            raise ValueError(
                f"Bottom plate (Z = [{z_bottom:.4f}, {cavity_z_bottom:.4f}]) "
                f"overlaps the bore (Z = [{bore_z_low:.4f}, "
                f"{bore_z_high:.4f}]). Reduce wall_t_bottom to ≤ "
                f"{(bore_z_low - z_bottom):.4f} m or move the bore up."
            )

    # ── Shell: hollow body ────────────────────────────────────────────────
    shell = (cq.Workplane("XY")
             .workplane(offset=z_bottom)
             .circle(radius_outer)
             .extrude(thickness))

    cavity = (cq.Workplane("XY")
              .workplane(offset=cavity_z_bottom)
              .circle(radius_inner)
              .extrude(cavity_height))

    shell = shell.cut(cavity)

    # ── Bosses + bores ────────────────────────────────────────────────────
    boss_solids: list[cq.Workplane] = []

    if nozzle_boss_angles_deg and nozzle_z_abs is not None:

        if nozzle_r_boss >= radius_outer:
            raise ValueError(
                f"nozzle_r_boss ({nozzle_r_boss}) must be smaller than "
                f"diagrid outer radius ({radius_outer})."
            )
        if nozzle_r_bore >= radius_inner:
            raise ValueError(
                f"nozzle_r_bore ({nozzle_r_bore}) must be smaller than "
                f"diagrid inner radius ({radius_inner})."
            )

        inset_min  = radius_outer - math.sqrt(radius_outer**2 - nozzle_r_boss**2)
        inset_safe = inset_min + 0.005
        boss_total_height = inset_safe + nozzle_boss_height

        margin = nozzle_r_boss
        if not (z_bottom + margin < nozzle_z_abs < z_top - margin):
            raise ValueError(
                f"nozzle_z_abs={nozzle_z_abs:.4f} m clips the diagrid face. "
                f"Must be in ({z_bottom + margin:.4f}, {z_top - margin:.4f})."
            )

        L_min = (
            (radius_outer + nozzle_boss_height)
            - math.sqrt(radius_inner**2 - nozzle_r_bore**2)
        )
        bore_length = L_min + 0.010

        for theta in nozzle_boss_angles_deg:
            rad = math.radians(theta)

            outward = cq.Vector( math.cos(rad),  math.sin(rad), 0.0)
            inward  = cq.Vector(-math.cos(rad), -math.sin(rad), 0.0)
            tangent = cq.Vector(-math.sin(rad),  math.cos(rad), 0.0)

            base_x = (radius_outer - inset_safe) * math.cos(rad)
            base_y = (radius_outer - inset_safe) * math.sin(rad)
            base_origin = cq.Vector(base_x, base_y, nozzle_z_abs)

            boss_plane = cq.Plane(
                origin=base_origin, xDir=tangent, normal=outward
            )
            boss = (cq.Workplane(boss_plane)
                    .circle(nozzle_r_boss)
                    .extrude(boss_total_height))

            outer_face_origin = cq.Vector(
                (radius_outer + nozzle_boss_height) * math.cos(rad),
                (radius_outer + nozzle_boss_height) * math.sin(rad),
                nozzle_z_abs,
            )
            bore_plane = cq.Plane(
                origin=outer_face_origin, xDir=tangent, normal=inward
            )
            bore = (cq.Workplane(bore_plane)
                    .circle(nozzle_r_bore)
                    .extrude(bore_length))

            # Cut bore through both boss and shell
            boss  = boss.cut(bore)
            shell = shell.cut(bore)
            boss_solids.append(boss.clean())

    # ── Assemble ──────────────────────────────────────────────────────────
    result = shell.clean()
    for b in boss_solids:
        result = result.union(b)
    return result.clean()


if __name__ == "__main__":
    from ocp_vscode import show

    assy = create_diagrid(
        diameter   = 4.660,
        thickness  = 1.050,
        z_bottom   = -0.460,
    )
    show(assy)