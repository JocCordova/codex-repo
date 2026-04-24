from __future__ import annotations

import cadquery as cq


def _required(params: dict[str, float], key: str) -> float:
    if key not in params:
        raise KeyError(f"Missing required dimension: {key}")
    return float(params[key])


def build_part(params: dict[str, float]) -> cq.Workplane:
    """Build a screw-mount cable clip for FDM printing."""
    base_length = _required(params, "base_length_mm")
    base_width = _required(params, "base_width_mm")
    base_thickness = _required(params, "base_thickness_mm")
    clip_depth = _required(params, "clip_depth_mm")
    clip_inner_width = _required(params, "clip_inner_width_mm")
    wall_thickness = _required(params, "wall_thickness_mm")
    cable_diameter = _required(params, "cable_diameter_mm")
    screw_hole_dia = _required(params, "screw_hole_diameter_mm")
    screw_head_dia = _required(params, "screw_head_clearance_diameter_mm")
    screw_head_depth = _required(params, "screw_head_clearance_depth_mm")
    fillet_radius = float(params.get("fillet_radius_mm", 1.0))

    clip_outer_width = clip_inner_width + 2.0 * wall_thickness
    clip_height = cable_diameter + wall_thickness

    part = cq.Workplane("XY").box(base_length, base_width, base_thickness)

    clip = (
        cq.Workplane("XY")
        .box(clip_outer_width, clip_depth, clip_height)
        .faces(">Z")
        .workplane()
        .center(0, 0)
        .hole(cable_diameter)
    )

    clip = clip.translate((0.0, 0.0, (base_thickness + clip_height) / 2.0))
    part = part.union(clip)

    part = (
        part.faces(">Z")
        .workplane()
        .center(0, 0)
        .cboreHole(screw_hole_dia, screw_head_dia, screw_head_depth)
    )

    if fillet_radius > 0:
        part = part.edges("|Z").fillet(fillet_radius)

    return part
