"""
Assemble multiple 3D objects into one cq.Assembly.

Takes a list of object specifications, builds each one using build_solid(),
and assembles them together.
"""

import re
from typing import Any, Dict, List, cast
import cadquery as cq
from ocp_vscode import show
import hashlib
import warnings

from utils import insert_into


def _color_from_id(obj_id: str) -> cq.Color:
    """Deterministic pleasant color from obj_id string."""
    h = int(hashlib.md5(obj_id.encode()).hexdigest(), 16)
    r = ((h >> 16) & 0xFF) / 255
    g = ((h >> 8)  & 0xFF) / 255
    b = (h         & 0xFF) / 255
    r = 0.3 + r * 0.6
    g = 0.3 + g * 0.6
    b = 0.3 + b * 0.6
    return cq.Color(r, g, b)  


def _patch_step_names(
    step_path: str,
    obj_ids: List[str],
    subnames_per_obj: Dict[str, List[str]] | None = None,
) -> None:
    """
    Replace generic OCCT PRODUCT names in a STEP file with obj_id names.

    CadQuery's STEP exporter uses the OCCT writer, which generates names like:
        'Open CASCADE STEP translator X.Y 1.N'           — top-level component N
        'Open CASCADE STEP translator X.Y 1.N.1.K'       — Kth child of comp N
        'Open CASCADE STEP translator X.Y 1.N.1.K.M'     — deeper nesting

    Naming strategy:
      • Top-level part N → obj_ids[N-1]      (e.g. "rpv", "ihx_1", "pump_1")
      • First-level child K of component N:
          - If obj_ids[N-1] has subnames in subnames_per_obj, use
            "{parent_obj_id}_{subnames_per_obj[parent][K-1]}"
            (e.g. "ihx_1_tube_bundle", "ihx_2_tube_bundle", ...) so multiple
            instances of the same compound type (e.g. three IHX) get
            distinguishable per-instance sub-part names.
          - Otherwise, the sub-part inherits the parent name.
      • Deeper levels: inherit the parent's resolved name (clean Onshape view)

    Args:
        step_path:          path to the already-exported STEP file.
        obj_ids:            list of obj_id strings, in assembly order.
        subnames_per_obj:   for components that expose sub-parts via a sidecar
                            attribute (e.g. `_ihx_subnames`), this dict maps
                            obj_id → list of sub-part names. Used to give
                            meaningful, instance-prefixed names to compound
                            children.
    """
    subnames_per_obj = subnames_per_obj or {}

    with open(step_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Capture: group(1) = N (top-level index), group(2) = K (first child) or None,
    # group(3) = trailing dotted suffix or None.
    pattern = re.compile(
        r"'Open CASCADE STEP translator [\d.]+ 1\.(\d+)(?:\.\d+\.(\d+))?(\.[\d.]+)?'"
    )

    def replace_match(match: re.Match) -> str:
        n = int(match.group(1)) - 1   # top-level (0-based)
        if not (0 <= n < len(obj_ids)):
            return match.group(0)

        parent_name = obj_ids[n]
        k_str = match.group(2)
        if k_str is None:
            # Top-level part name itself
            return f"'{parent_name}'"

        # First-level child of a compound component
        k = int(k_str) - 1
        subnames = subnames_per_obj.get(parent_name, [])
        if 0 <= k < len(subnames):
            # Prefix sub-part with parent obj_id so 3 IHX produce names like
            # ihx_1_tube_bundle, ihx_2_tube_bundle, ihx_3_tube_bundle.
            return f"'{parent_name}_{subnames[k]}'"
        else:
            # No subname available — inherit parent's name
            return f"'{parent_name}'"

    content = pattern.sub(replace_match, content)

    with open(step_path, "w", encoding="utf-8") as f:
        f.write(content)


def validate_solids(resolved_dicts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Build each solid from its spec and run OCCT geometry validity checks.

    Called automatically at the start of assemble_objects() — issues are
    printed as warnings but never block the export.

    Checks performed per component:
      • BUILD_FAILED   — build_solid() raised an exception
      • NULL_SHAPE     — build_solid() returned None
      • ZERO_VOLUME    — resulting solid has volume < 1e-9 (collapsed geometry)
    """
    from build_3D_solid import build_solid

    issues = []

    for spec in resolved_dicts:
        obj_id = spec.get("obj_id", "<unknown>")

        try:
            spec_copy = spec.copy()
            operation = spec_copy.pop("operation", "primitive")
            spec_copy.pop("insert_into",      None)
            spec_copy.pop("material",         None)
            spec_copy.pop("material_tag",     None)
            spec_copy.pop("manual_placement", None)

            if "profile" in spec_copy:
                solid, _ = build_solid(operation, **spec_copy)
            elif "obj_type" in spec_copy:
                profile = spec_copy.copy()
                _obj_id           = profile.pop("obj_id", None)
                rotation_angles   = profile.pop("rotation_angles", (0, 0, 0))
                center_coords     = profile.pop("center_coords", None)
                center_coords_pol = profile.pop("center_coords_pol", None)
                solid, _ = build_solid(operation, profile,
                                       obj_id=_obj_id,
                                       rotation_angles=rotation_angles,
                                       center_coords=center_coords,
                                       center_coords_pol=center_coords_pol)
            else:
                solid, _ = build_solid(operation, **spec_copy)

        except Exception as e:
            issues.append({"obj_id": obj_id, "problem": "BUILD_FAILED", "detail": str(e)})
            continue

        if solid is None:
            issues.append({"obj_id": obj_id, "problem": "NULL_SHAPE",
                           "detail": "build_solid returned None"})
            continue

        try:
            vol = solid.val().Volume()  # type: ignore
            if vol < 1e-9:
                issues.append({"obj_id": obj_id, "problem": "ZERO_VOLUME",
                               "detail": f"Volume = {vol:.2e} (collapsed geometry)"})
        except Exception as e:
            issues.append({"obj_id": obj_id, "problem": "VOLUME_CHECK_FAILED",
                           "detail": str(e)})

    return issues


def assemble_objects(object_specs: List[Dict[str, Any]], export_path: str | None = None) -> cq.Assembly:
    """
    Build a list of objects and assemble them.

    Runs geometry validation automatically before building the assembly
    (via validate_solids). Any issues found are printed as warnings —
    they never block the export.

    STEP export: part names (obj_id) are written into the exported STEP
    file. Components that expose a `_ihx_subnames` sidecar attribute on
    their Workplane (e.g. the IHX, whose internal Compound contains 7
    sub-components) get those sub-names propagated as well, PREFIXED with
    the parent obj_id so that multiple instances of the same compound
    type are distinguishable: "ihx_1_tube_bundle", "ihx_2_tube_bundle",
    "ihx_3_tube_bundle", etc.
    """
    from build_3D_solid import build_solid

    issues = validate_solids(object_specs)
    for issue in issues:
        warnings.warn(
            f"[GEOMETRY] [{issue['problem']}] {issue['obj_id']}: {issue['detail']}",
            stacklevel=2,
        )

    assembly = cq.Assembly()
    objects: Dict[str, cq.Workplane] = {}
    subnames_per_obj: Dict[str, List[str]] = {}

    print(f"Building {len(object_specs)}-component assembly:")
    for spec in object_specs:
        print(f"  {spec.get('obj_type', spec.get('operation', '?'))}  [{spec.get('obj_id', '')}]")
        spec_copy = spec.copy()
        operation = spec_copy.pop("operation")
        spec_copy.pop("insert_into",  None)
        spec_copy.pop("material",     None)
        spec_copy.pop("material_tag", None)

        if "profile" in spec_copy:
            solid, obj_id = build_solid(operation, **spec_copy)
        elif "obj_type" in spec_copy:
            profile = spec_copy.copy()
            obj_id            = profile.pop("obj_id", None)
            rotation_angles   = profile.pop("rotation_angles", (0, 0, 0))
            center_coords     = profile.pop("center_coords", None)
            center_coords_pol = profile.pop("center_coords_pol", None)
            solid, obj_id = build_solid(operation, profile,
                                        obj_id=obj_id,
                                        rotation_angles=rotation_angles,
                                        center_coords=center_coords,
                                        center_coords_pol=center_coords_pol)
        else:
            solid, obj_id = build_solid(operation, **spec_copy)

        # Pick up sidecar with sub-component names if the builder attached one.
        sub = getattr(solid, "_ihx_subnames", None)
        if sub:
            subnames_per_obj[obj_id] = sub

        objects[obj_id] = solid

    # ── insert_into pass ───────────────────────────────────────────────
    for spec in object_specs:
        target_id = spec.get("insert_into")
        if target_id is None:
            continue
        insert_id = spec.get("obj_id")
        if insert_id is None:
            raise ValueError("insert_into: spec is missing 'obj_id'")
        target_ids = [target_id] if isinstance(target_id, str) else target_id
        for tid in target_ids:
            if tid not in objects:
                raise ValueError(f"insert_into: target '{tid}' not found in assembly")
            objects[tid] = insert_into(objects[tid], objects[insert_id])

    # ── Overlap detection ──────────────────────────────────────────────
    intentional_pairs = set()
    for spec in object_specs:
        obj_id = spec.get("obj_id")
        if obj_id is None:
            continue
        # insert_into pairs
        for tid in ([spec["insert_into"]] if isinstance(spec.get("insert_into"), str)
                    else spec.get("insert_into") or []):
            intentional_pairs.add((obj_id, tid))
            intentional_pairs.add((tid, obj_id))
        # interfaces_with pairs — designed touching interfaces (e.g. IHX
        # walls against top-plate hole edges, pump barrel against redan hole)
        for tid in spec.get("interfaces_with", []):
            intentional_pairs.add((obj_id, tid))
            intentional_pairs.add((tid, obj_id))

    overlap_shapes: list[tuple[str, cq.Workplane]] = []
    solid_list = list(objects.items())
    for i in range(len(solid_list)):
        id_i, wp_i = solid_list[i]
        for j in range(i + 1, len(solid_list)):
            id_j, wp_j = solid_list[j]
            if (id_i, id_j) in intentional_pairs:
                continue
            try:
                inter = wp_i.val().intersect(wp_j.val())  # type: ignore
                if not inter.isNull() and inter.Volume() > 1e-4:
                    warnings.warn(
                        f"Overlap detected between '{id_i}' and '{id_j}' "
                        f"(volume ≈ {inter.Volume():.5f} mm³). ",
                        stacklevel=2,
                    )
                    overlap_shapes.append((
                        f"OVERLAP_{id_i}__{id_j}",
                        cq.Workplane().newObject([inter]),
                    ))
            except Exception:
                pass

    # ── Assemble with deterministic per-component colors ──────────────
    colors = {spec["obj_id"]: spec.get("color") for spec in object_specs if "obj_id" in spec}
    for obj_id, solid in objects.items():
        color_spec = colors.get(obj_id)
        if color_spec is not None:
            if not isinstance(color_spec, (tuple, list)) or len(color_spec) not in (3, 4):
                raise ValueError(
                    f"'{obj_id}' color must be (r, g, b) or (r, g, b, a) with values "
                    f"in 0.0–1.0, got: {color_spec}"
                )
            color = cq.Color(*color_spec)
        else:
            color = _color_from_id(obj_id)
        assembly.add(solid, name=obj_id, color=color)

    assembly._specs = object_specs  # type: ignore

    # ── STEP export (overlap shapes excluded) ──────────────────────────
    if export_path is not None:
        import os
        parent = os.path.dirname(export_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        cq.exporters.export(assembly.toCompound(), export_path)
        _patch_step_names(
            export_path,
            list(objects.keys()),
            subnames_per_obj=subnames_per_obj,
        )
        print(f"Assembly exported to: {export_path}")

    # ── Add overlap solids for viewer only (after STEP export) ─────────
    for overlap_name, overlap_wp in overlap_shapes:
        assembly.add(overlap_wp, name=overlap_name, color=cq.Color(1, 0, 0, 1))

    return assembly


def apply_boolean_operations(assembly: cq.Assembly, operations: List[Dict[str, Any]]) -> cq.Assembly:
    """
    Apply Boolean operations between solids in an assembly.
    """
    objects = {child.name: child.obj for child in assembly.children}

    for op_spec in operations:
        operation = op_spec["operation"].lower()
        obj1_id   = op_spec["obj1"]
        obj2_id   = op_spec["obj2"]
        keep_obj2 = op_spec.get("keep_obj2", True)

        if obj1_id not in objects or obj2_id not in objects:
            raise ValueError(f"Objects not found in assembly: obj1='{obj1_id}', obj2='{obj2_id}'")

        obj1 = cast(cq.Workplane, objects[obj1_id])
        obj2 = cast(cq.Workplane, objects[obj2_id])

        if operation == "union":
            result = obj1.union(obj2)
        elif operation == "cut":
            result = obj1.cut(obj2)
        elif operation == "intersect":
            result = obj1.intersect(obj2)
        else:
            raise ValueError(f"Unknown operation: '{operation}'. Use 'union', 'cut', or 'intersect'")

        objects[obj1_id] = result
        if not keep_obj2:
            del objects[obj2_id]

    new_assembly = cq.Assembly()
    for obj_id, obj in objects.items():
        original = next((c for c in assembly.children if c.name == obj_id), None)
        color = original.color if original is not None else _color_from_id(obj_id)
        new_assembly.add(obj, name=obj_id, color=color)

    new_assembly._specs = getattr(assembly, "_specs", [])  # type: ignore

    return new_assembly
