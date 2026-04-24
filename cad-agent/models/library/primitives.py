from __future__ import annotations

import cadquery as cq


def rounded_block(length: float, width: float, height: float, fillet: float) -> cq.Workplane:
    solid = cq.Workplane("XY").box(length, width, height)
    if fillet > 0:
        solid = solid.edges("|Z").fillet(fillet)
    return solid
