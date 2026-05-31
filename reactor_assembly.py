"""
Tier-3: reactor-level assembly.

Builds the full pool-type SFR geometry by adding each component's
cq.Assembly (with named, colored sub-parts) as a named child of a root
cq.Assembly.  No inter-component boolean operations are performed — spatial
relationships are encoded as positioning parameters (center_coords,
rotation_angles) passed to each component spec, following the Paramak model.

Usage
-----
    from reactor_assembly import build_reactor_assembly

    specs = [
        {
            "name": "rpv",
            "obj_type": "reactor_vessel",
            "inner_d": 4.72,
            "wall_t": 0.04,
            "straight_h": 5.5,
            "bottom_head_type": "ellipsoidal",
            "bottom_head_params": {"head_depth": 1.0},
        },
        {
            "name": "diagrid",
            "obj_type": "diagrid",
            "diameter": 4.66,
            "thickness": 1.05,
            "z_bottom": -0.46,
        },
        # ... more components
    ]

    reactor = build_reactor_assembly(specs)
    reactor.save("reactor.step")

Spec keys
---------
Required for every component:
    name        str   — unique name used as the Assembly child name
    obj_type    str   — one of the keys in _ASSEMBLY_BUILDERS

Optional positioning (applied before adding to the root assembly):
    center_coords     (x, y, z)       — translate component centroid to this point
    center_coords_pol (r, theta_deg, z) — polar form; converted to Cartesian
    rotation_angles   (roll, pitch, yaw) in degrees

All other keys are forwarded to the component builder unchanged.
"""

from __future__ import annotations

import math
from typing import Any

import cadquery as cq

from components_premade import build_premade_assembly


def _polar_to_cartesian(r: float, theta_deg: float, z: float) -> tuple[float, float, float]:
    theta = math.radians(theta_deg)
    return (r * math.cos(theta), r * math.sin(theta), z)


def _apply_loc(
    assy: cq.Assembly,
    center_coords: tuple[float, float, float] | None,
    rotation_angles: tuple[float, float, float],
) -> cq.Assembly:
    """Wrap assy in a positioned parent Assembly (translate + RPY rotation)."""
    roll, pitch, yaw = rotation_angles
    x, y, z = center_coords or (0.0, 0.0, 0.0)

    loc = cq.Location(cq.Vector(x, y, z))
    if any(a != 0.0 for a in rotation_angles):
        loc = (
            loc
            * cq.Location(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), yaw)
            * cq.Location(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), pitch)
            * cq.Location(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), roll)
        )

    wrapper = cq.Assembly(loc=loc)
    wrapper.add(assy)
    return wrapper


def build_reactor_assembly(
    component_specs: list[dict[str, Any]],
    name: str = "reactor",
) -> cq.Assembly:
    """
    Build a root cq.Assembly from a list of component specs.

    Each spec produces a named child assembly.  The child assembly itself
    contains the component's own named sub-parts (vessel_body, barrel, …).

    Parameters
    ----------
    component_specs : list[dict]
        Each dict must have:
          - ``name``     : str  — unique child name in the root assembly
          - ``obj_type`` : str  — component type key
        Plus all parameters required by that component's builder.
        Optional: ``center_coords``, ``center_coords_pol``, ``rotation_angles``.

    name : str
        Name of the root assembly (appears in STEP file).

    Returns
    -------
    cq.Assembly
        Root assembly ready for ``show()``, ``save()``, or ``toCompound()``.
    """
    root = cq.Assembly(name=name)

    for spec in component_specs:
        spec = dict(spec)  # shallow copy so we don't mutate caller's dict

        child_name      = spec.pop("name")
        center_coords   = spec.pop("center_coords",     None)
        center_coords_pol = spec.pop("center_coords_pol", None)
        rotation_angles = spec.pop("rotation_angles",   (0.0, 0.0, 0.0))

        if center_coords_pol is not None:
            r, theta, z = center_coords_pol
            center_coords = _polar_to_cartesian(r, theta, z)

        child_assy = build_premade_assembly(spec)

        if center_coords is not None or any(a != 0.0 for a in rotation_angles):
            child_assy = _apply_loc(child_assy, center_coords, rotation_angles)     #type: ignore

        root.add(child_assy, name=child_name)

    return root


def save_reactor(
    reactor: cq.Assembly,
    path: str = "reactor.step",
) -> None:
    """Export the reactor assembly to a STEP file."""
    import os
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    reactor.save(path)
    print(f"Saved: {path}")


# ── Demo ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from ocp_vscode import show

    specs = [
        {
            "name":    "rpv",
            "obj_type": "reactor_vessel",
            "inner_d":   4.72,
            "wall_t":    0.04,
            "straight_h": 5.5,
            "bottom_head_type":   "ellipsoidal",
            "bottom_head_params": {"head_depth": 1.0},
        },
        {
            "name":     "diagrid",
            "obj_type": "diagrid",
            "diameter":  4.660,
            "thickness": 1.050,
            "z_bottom":  -0.460,
        },
    ]

    reactor = build_reactor_assembly(specs)
    show(reactor)
