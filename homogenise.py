"""
Homogenise any premade component into an equivalent cylinder that conserves the
number of atoms of every nuclide.

Three-way separation of concerns
────────────────────────────────
  materials.py                what a material IS        (composition library)
  component_material_zones.py what ZONES a component has (per-component, by obj_type)
  spec["materials"]           which material fills each zone (assignment, by zone name)

The atom-conservation core (``material_number_densities``, ``homogenise_volumes``)
is pure Python — no CadQuery. Only the per-component zone functions touch the CAD
kernel, and only when ``homogenise`` actually builds a component.

Core identity. For each material m with total volume V_m and per-nuclide number
density n_m,i, and a target cylinder of volume V_cyl::

        n_hom,i  =  ( Σ_m  V_m · n_m,i ) / V_cyl

so V_cyl · n_hom,i equals the original total for every nuclide. V_cyl is free
(atoms are conserved for any size); the default is the component's own bounding
cylinder, declared alongside its zones.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, Optional

from component_material_zones import MATERIAL_ZONES

N_A = 6.02214076e23  # Avogadro, atoms / mol
_LEN_TO_CM = {"mm": 0.1, "cm": 1.0, "m": 100.0}


def _len_to_cm(unit: str) -> float:
    try:
        return _LEN_TO_CM[unit]
    except KeyError:
        raise ValueError(f"length_unit must be one of {list(_LEN_TO_CM)}, got {unit!r}")


# ─────────────────────────────────────────────────────────────────────────────
# MATERIALS  (pure python)
# ─────────────────────────────────────────────────────────────────────────────
def material_number_densities(mat: Dict[str, Any]) -> Dict[str, float]:
    """
    Per-nuclide number densities in atoms/b·cm. Two accepted forms::

        {"kind": "number_density", "nuclides": {"Fe56": 5.9e-2, ...}}   # atoms/b·cm
        {"kind": "mass_density", "density": 0.85,
         "nuclides": {"Na23": {"ao": 1.0, "M": 22.99}}}                 # g/cm³ + frac
    """
    kind = mat.get("kind", "number_density")
    nucs = mat["nuclides"]
    if kind == "number_density":
        return {k: float(v) for k, v in nucs.items()}
    if kind == "mass_density":
        rho = float(mat["density"])
        ao = {k: float(v["ao"]) for k, v in nucs.items()}
        molar = {k: float(v["M"]) for k, v in nucs.items()}
        tot = sum(ao.values())
        if tot <= 0:
            raise ValueError("atom fractions sum to zero")
        ao = {k: v / tot for k, v in ao.items()}
        m_avg = sum(ao[k] * molar[k] for k in ao)
        n_tot = rho * N_A / m_avg
        return {k: ao[k] * n_tot * 1e-24 for k in ao}
    raise ValueError(f"unknown material kind {kind!r}")


# ─────────────────────────────────────────────────────────────────────────────
# ATOM-CONSERVING HOMOGENISATION  (pure python)
# ─────────────────────────────────────────────────────────────────────────────
def homogenise_volumes(
    volume_by_material_cm3: Dict[str, float],
    materials: Dict[str, Dict[str, Any]],
    cylinder_volume_cm3: float,
) -> Dict[str, Any]:
    if cylinder_volume_cm3 <= 0:
        raise ValueError("cylinder volume must be positive")
    n_hom: Dict[str, float] = defaultdict(float)
    source_atoms: Dict[str, float] = defaultdict(float)
    for mat_name, vol in volume_by_material_cm3.items():
        if vol <= 0:
            continue
        if mat_name not in materials:
            raise KeyError(f"material {mat_name!r} used by geometry but absent from library")
        for nuc, n in material_number_densities(materials[mat_name]).items():
            n_hom[nuc] += vol * n / cylinder_volume_cm3
            source_atoms[nuc] += vol * n * 1e24
    balance: Dict[str, Dict[str, float]] = {}
    for nuc, nd in n_hom.items():
        cyl_atoms = nd * cylinder_volume_cm3 * 1e24
        src = source_atoms[nuc]
        balance[nuc] = {
            "number_density_bcm": nd,
            "source_atoms": src,
            "cylinder_atoms": cyl_atoms,
            "rel_error": abs(cyl_atoms - src) / src if src else 0.0,
        }
    return {"number_densities": dict(n_hom), "balance": balance}


def cylinder_volume_cm3(cyl: Dict[str, Any], length_unit: str) -> float:
    f = _len_to_cm(length_unit)
    return math.pi * (float(cyl["radius"]) * f) ** 2 * (float(cyl["height"]) * f)


# ─────────────────────────────────────────────────────────────────────────────
# GENERIC DRIVER — dispatch by obj_type through the zone registry
# ─────────────────────────────────────────────────────────────────────────────
def homogenise(
    spec: Dict[str, Any],
    materials: Dict[str, Dict[str, Any]],
    length_unit: str = "mm",
    cylinder: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the component named by ``spec["obj_type"]``, measure each declared zone,
    assign materials from ``spec["materials"]`` (zone name -> material name), and
    return the homogenised cylinder with conserved per-nuclide densities.
    """
    obj_type = spec.get("obj_type")
    if obj_type not in MATERIAL_ZONES:
        raise KeyError(
            f"no material-zone declaration for obj_type {obj_type!r}. "
            f"Known: {sorted(MATERIAL_ZONES)}. Add one in component_material_zones.py."
        )
    if "materials" not in spec:
        raise KeyError("spec is missing the 'materials' assignment block (zone -> material)")

    model = MATERIAL_ZONES[obj_type](spec)
    zones = model["zones"]
    assign = spec["materials"]

    declared = {z.name for z in zones}
    used = set(assign)
    missing = declared - used
    unknown = used - declared
    if missing:
        raise KeyError(
            f"{obj_type}: zones {sorted(missing)} have no material assigned. "
            f"Declared zones: {sorted(declared)}."
        )
    if unknown:
        raise KeyError(
            f"{obj_type}: spec['materials'] names {sorted(unknown)} are not zones of "
            f"this component. Valid zone names: {sorted(declared)}."
        )

    f3 = _len_to_cm(length_unit) ** 3
    by_material: Dict[str, float] = defaultdict(float)
    for z in zones:
        by_material[assign[z.name]] += z.volume * f3

    cyl = dict(cylinder) if cylinder is not None else dict(model["cylinder"])
    cyl.setdefault("length_unit", length_unit)
    v_cyl = cylinder_volume_cm3(cyl, length_unit)
    cyl["volume_cm3"] = v_cyl

    hom = homogenise_volumes(dict(by_material), materials, v_cyl)
    return {
        "obj_type": obj_type,
        "cylinder": cyl,
        "number_densities": hom["number_densities"],
        "balance": hom["balance"],
        "zones_cm3": {z.name: (z.role, z.volume * f3) for z in zones},
        "by_material_cm3": dict(by_material),
    }


# ─────────────────────────────────────────────────────────────────────────────
# OPTIONAL: OpenMC adapter
# ─────────────────────────────────────────────────────────────────────────────
def to_openmc(result: Dict[str, Any], name: str = "homogenised"):
    import openmc
    mat = openmc.Material(name=name)
    total = 0.0
    for nuc, nd in result["number_densities"].items():
        mat.add_nuclide(nuc, nd, "ao")
        total += nd
    mat.set_density("atom/b-cm", total)
    cyl = result["cylinder"]
    f = _len_to_cm(cyl.get("length_unit", "mm"))
    r = cyl["radius"] * f
    z0 = cyl["z_bottom"] * f
    z1 = (cyl["z_bottom"] + cyl["height"]) * f
    region = -openmc.ZCylinder(r=r) & +openmc.ZPlane(z0=z0) & -openmc.ZPlane(z0=z1)
    return mat, region


# ─────────────────────────────────────────────────────────────────────────────
# Self-test (pure math — no CadQuery)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    materials = {
        "ss316": {"kind": "number_density",
                  "nuclides": {"Fe56": 5.9e-2, "Cr52": 1.6e-2, "Ni58": 8.0e-3}},
        "na": {"kind": "mass_density", "density": 0.85,
               "nuclides": {"Na23": {"ao": 1.0, "M": 22.99}}},
    }
    hom = homogenise_volumes({"ss316": 1234.0, "na": 8765.0}, materials, 50000.0)
    worst = max(b["rel_error"] for b in hom["balance"].values())
    for nuc, b in hom["balance"].items():
        print(f"  {nuc:6s} n_hom={b['number_density_bcm']:.4e}  rel_err={b['rel_error']:.2e}")
    print(f"worst relative atom error: {worst:.2e}")
    assert worst < 1e-12

    print("\nUsage (needs CadQuery + the components package):")
    print("  from materials import MATERIALS")
    print("  result = homogenise(ihx_spec, MATERIALS)   # ihx_spec['obj_type']=='ihx'")