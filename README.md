# ZeroLevelProduct V9

Parametric 3D CAD library for pool-type sodium-cooled fast reactor (SFR) components, developed as part of an MSc thesis at ETHZ–EPFL.

Built on top of [CadQuery](https://cadquery.readthedocs.io/), the library provides a dictionary-driven interface to construct, assemble, and visualise reactor geometry from high-level parameter specifications.

---

## Project structure

```
ZeroLevelProduct_V9/
├── assemble.py                        # Assembly of multiple 3D objects into a cq.Assembly
├── build_3D_solid.py                  # Unified builder: extrude, revolve, sweep, premade
├── components_3D_primitives.py        # Low-level geometric primitives
├── profile_built_in_2D_sketch.py      # Built-in 2D sketch profiles
├── profile_from_straight_connections.py  # 2D profiles from point sequences
├── utils.py                           # Geometry helpers (rotate, move, extrude, sweep…)
├── components_premade/                # Package of domain-specific reactor components
│   ├── __init__.py                    # Public API: build_premade_component(), PREMADE_BUILDERS
│   ├── components_premade_reactor_vessel.py
│   ├── components_premade_top_plate.py
│   ├── components_premade_ihx.py
│   ├── components_premade_core.py
│   ├── components_premade_strongback.py
│   ├── components_premade_primary_pump.py
│   ├── components_premade_diagrid.py
│   └── components_premade_above_core_structure.py
├── pyproject.toml
└── requirements.txt
```

---

## Available premade components

| Key | Description |
|---|---|
| `reactor_vessel` | Cylindrical reactor vessel with configurable head geometry |
| `reactor_top_plate` | Flat top plate with optional hole groups |
| `ihx` | Intermediate heat exchanger (shell + tube bundle) |
| `reactor_core` | Hexagonal or circular core barrel |
| `strongback` | Flanged strongback support structure |
| `primary_pump` | Primary sodium pump with elbow nozzle |
| `diagrid` | Hollow diagrid with lateral pump nozzle bosses |
| `above_core_structure` | Above-core structure with flow holes and counterbores |

---

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Install the package in editable mode

```bash
pip install -e .
```

This registers the package in the virtual environment so all modules can be imported by name. Editable mode means source changes take effect immediately without reinstalling.

---

## Usage

```python
from build_3D_solid import build_solid
from assemble import assemble_objects

obj_spec = {
    "obj_type": "diagrid",
    "diameter": 2.4,
    "thickness": 0.3,
    "z_bottom": 0.0,
    "wall_t_side": 0.030,
}

solid = build_solid(obj_spec)
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `cadquery` | 3D solid modelling kernel |
| `ocp_vscode` | In-editor 3D viewer for CadQuery |
| `Shapely` | 2D geometry operations |
| `numpy` | Numerical utilities |
| `python-dotenv` | Environment variable management |

---

## License

MIT — see [LICENSE](LICENSE).
