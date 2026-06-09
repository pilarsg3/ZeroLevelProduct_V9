"""
Central material library — compositions only, no geometry.

Every component spec references these by name in its ``materials`` block; this
file is the single source of truth for *what* each material is. Two accepted
forms per material:

    "number_density"  ->  nuclide: atoms/b·cm           (the simple, preferred form)
    "mass_density"    ->  density (g/cm³) + nuclide: {ao: atom_frac, M: molar_mass}

Number densities are what neutronics workflows usually carry, so prefer that
form when you have it; mass_density is a convenience for quick coolant entries.
"""

MATERIALS = {
    # Structural steel (placeholder densities — replace with your own)
    "ss316": {
        "kind": "number_density",
        "nuclides": {
            "Fe56": 5.90e-2,
            "Cr52": 1.60e-2,
            "Ni58": 8.00e-3,
            "Mo98": 1.20e-3,
        },
    },
    "ss304": {
        "kind": "number_density",
        "nuclides": {
            "Fe56": 6.00e-2,
            "Cr52": 1.70e-2,
            "Ni58": 7.00e-3,
        },
    },

    # Coolants by mass density + atom fractions
    "na_primary": {
        "kind": "mass_density",
        "density": 0.83,  # g/cm³ at the primary-side temperature
        "nuclides": {"Na23": {"ao": 1.0, "M": 22.99}},
    },
    "na_secondary": {
        "kind": "mass_density",
        "density": 0.85,  # g/cm³ at the secondary-side temperature
        "nuclides": {"Na23": {"ao": 1.0, "M": 22.99}},
    },
}