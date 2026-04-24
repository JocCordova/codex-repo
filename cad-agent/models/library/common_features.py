from __future__ import annotations

import cadquery as cq


def center_counterbore(
    wp: cq.Workplane,
    through_diameter: float,
    counterbore_diameter: float,
    counterbore_depth: float,
) -> cq.Workplane:
    return (
        wp.faces(">Z")
        .workplane()
        .center(0, 0)
        .cboreHole(through_diameter, counterbore_diameter, counterbore_depth)
    )
