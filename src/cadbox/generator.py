"""CadQuery CAD generation module for cadbox.

Takes a ContainerConfig and PackingResult and produces a CadQuery solid
representing the parametric container with all cavity pockets cut in.

All dimensions are in millimetres unless otherwise noted.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Union

import cadquery as cq

from cadquery import selectors

from .models import CavityShape, ContainerConfig, PackingResult, PlacedCavity

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_EPSILON = 1e-4  # small clearance used when clamping fillet radii


def _safe_fillet_radius(radius: float, *dimensions: float) -> float:
    """Clamp *radius* to at most half the smallest *dimension* minus epsilon.

    CadQuery raises a hard error when a fillet radius equals or exceeds half
    the shortest edge it acts on.  This guard prevents that.

    Args:
        radius:     Requested fillet radius (mm).
        *dimensions: One or more edge/span lengths to clamp against.

    Returns:
        A safe fillet radius guaranteed to be less than ``min(dims) / 2``.
    """
    if not dimensions:
        return radius
    max_allowed = min(dimensions) / 2.0 - _EPSILON
    return max(0.0, min(radius, max_allowed))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate(config: ContainerConfig, packing: PackingResult) -> cq.Workplane:
    """Generate a CadQuery solid for the container described by *config*.

    The workflow is:
    1. Build the outer box (centered on XY, floor on Z=0).
    2. Fillet vertical edges for aesthetics.
    3. Hollow out the interior by cutting a slightly smaller inner box.
    4. Cut each cavity pocket from the top face.

    Args:
        config:  Full container specification (outer dimensions, wall
                 thicknesses, fillet radius, …).
        packing: Placement result from :func:`cadbox.packer.pack_cavities`,
                 containing the resolved position of every cavity.

    Returns:
        A :class:`cadquery.Workplane` containing the finished solid.
    """
    w = config.width
    l = config.length
    h = config.height
    t_wall = config.outer_wall
    t_floor = config.floor_thickness
    r_outer = config.fillet_radius

    # ------------------------------------------------------------------
    # Step 1: Outer box – centred on XY, floor flush with Z=0
    # ------------------------------------------------------------------
    result = (
        cq.Workplane("XY")
        .box(w, l, h, centered=(True, True, False))
    )

    # ------------------------------------------------------------------
    # Step 2: Fillet outer edges
    # ------------------------------------------------------------------
    # 2a: Vertical (Z-parallel) edges
    if r_outer > 0:
        r_outer_safe = _safe_fillet_radius(r_outer, w, l)
        if r_outer_safe > 0:
            result = result.edges("|Z").fillet(r_outer_safe)

    # 2b: Lower (bottom) horizontal edges – edges on the Z=0 face
    r_lower = config.outer_fillet_lower
    if r_lower > 0:
        r_lower_safe = _safe_fillet_radius(r_lower, w, l, h)
        if r_lower_safe > 0:
            result = result.faces("<Z").edges().fillet(r_lower_safe)

    # 2c: Upper (top) horizontal edges – edges on the Z=h face
    r_upper = config.outer_fillet_upper
    if r_upper > 0:
        r_upper_safe = _safe_fillet_radius(r_upper, w, l, h)
        if r_upper_safe > 0:
            result = result.faces(">Z").edges().fillet(r_upper_safe)

    # ------------------------------------------------------------------
    # Step 3: Compute inner dimensions (used for coordinate conversion)
    #
    # No interior void is cut here — the cavity pockets cut in Step 4
    # define the interior geometry.  Material left between pockets forms
    # the ribs, outer walls remain solid by virtue of the packer placing
    # cavities within (w - 2*t_wall) × (l - 2*t_wall).
    # ------------------------------------------------------------------
    inner_w = w - 2 * t_wall
    inner_l = l - 2 * t_wall

    # ------------------------------------------------------------------
    # Step 4: Cut cavity pockets from the top face
    #
    # PlacedCavity coordinates use bottom-left origin (0,0 = inner
    # floor corner).  CadQuery's box is centred on XY, so we convert:
    #   cx_cad = placement.x - inner_w/2
    #   cy_cad = placement.y - inner_l/2
    # ------------------------------------------------------------------
    for placement in packing.placements:
        adjusted = PlacedCavity(
            x=placement.x - inner_w / 2,
            y=placement.y - inner_l / 2,
            spec=placement.spec,
        )
        result = _cut_cavity(result, adjusted, config.fillet_radius, config.cavity_fillet_top)

    return result


def _cut_cavity(
    solid: cq.Workplane,
    placement: PlacedCavity,
    fillet_radius: float,
    cavity_fillet_top_default: float = 0.0,
) -> cq.Workplane:
    """Cut a single cavity pocket into *solid* at the position given by *placement*.

    Args:
        solid:                    The workplane/solid to cut into.
        placement:                Cavity position and geometry (coords in CadQuery XY-centred space).
        fillet_radius:            Requested corner fillet radius for rectangular cavities.
        cavity_fillet_top_default: Container-level default fillet for cavity top edges.

    Returns:
        The modified solid with the cavity pocket removed.
    """
    spec = placement.spec
    depth = spec.depth
    cx = placement.x
    cy = placement.y

    # Resolve effective cavity top fillet: per-cavity override > container default
    r_top = spec.fillet_top if spec.fillet_top is not None else cavity_fillet_top_default

    # Build the cut tool as a standalone solid, then subtract it.
    # This avoids CadQuery workplane state issues when chaining multiple
    # cutBlind operations on a progressively modified solid.
    z_top = solid.val().BoundingBox().zmax

    # Extra height so the tool punches cleanly through the top surface.
    # This ensures crisp opening edges that can be filleted on the solid.
    overshoot = max(r_top, 0.1)

    # Clamp the pocket fillet to at most half the depth (the vertical edge)
    # and half the smallest lateral dimension.
    if spec.shape == CavityShape.circle:
        radius = spec.diameter / 2.0  # type: ignore[operator]
        r_pocket = _safe_fillet_radius(fillet_radius, depth, spec.diameter)
        tool = (
            cq.Workplane("XY")
            .center(cx, cy)
            .circle(radius)
            .extrude(depth + overshoot)
        )
        # Fillet the bottom ring of the pocket (edges on the Z=0 face of tool)
        if r_pocket > 0:
            tool = tool.faces("<Z").edges().fillet(r_pocket)
        tool = tool.translate((0, 0, z_top - depth))
        hw, hl = radius, radius

    elif spec.shape == CavityShape.rect:
        cav_w = spec.width   # type: ignore[assignment]
        cav_l = spec.length  # type: ignore[assignment]

        # XY corner fillet for rectangular cavities
        r_corner = _safe_fillet_radius(fillet_radius, cav_w, cav_l)
        # Pocket bottom fillet (vertical-to-floor transition)
        r_pocket = _safe_fillet_radius(fillet_radius, depth, cav_w, cav_l)

        if r_corner > 0:
            tool = (
                cq.Workplane("XY")
                .center(cx, cy)
                .sketch()
                .rect(cav_w, cav_l)
                .vertices()
                .fillet(r_corner)
                .finalize()
                .extrude(depth + overshoot)
            )
        else:
            tool = (
                cq.Workplane("XY")
                .center(cx, cy)
                .rect(cav_w, cav_l)
                .extrude(depth + overshoot)
            )
        # Fillet the bottom edges of the pocket
        if r_pocket > 0:
            tool = tool.faces("<Z").edges().fillet(r_pocket)
        tool = tool.translate((0, 0, z_top - depth))
        hw, hl = cav_w / 2, cav_l / 2
    else:
        return solid

    result = solid.cut(tool)

    # Apply cavity top fillet on the solid after cutting.
    # Select edges at the cavity opening using a BoxSelector centred on the
    # cavity position at z_top.
    if r_top > 0:
        r_top_safe = _safe_fillet_radius(r_top, depth, 2 * hw, 2 * hl)
        if r_top_safe > 0:
            tol = 0.5
            sel = selectors.BoxSelector(
                (cx - hw - tol, cy - hl - tol, z_top - tol),
                (cx + hw + tol, cy + hl + tol, z_top + tol),
            )
            try:
                result = result.edges(sel).fillet(r_top_safe)
            except Exception:
                pass  # skip if geometry cannot support the fillet

    return result


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def export_step(solid: cq.Workplane, path: Union[str, Path]) -> None:
    """Export *solid* to STEP format.

    Args:
        solid: CadQuery workplane holding the finished solid.
        path:  Destination file path (``*.step`` or ``*.stp``).
    """
    cq.exporters.export(solid, str(path), exportType="STEP")


def export_stl(solid: cq.Workplane, path: Union[str, Path]) -> None:
    """Export *solid* to binary STL format (useful for web preview / slicers).

    Args:
        solid: CadQuery workplane holding the finished solid.
        path:  Destination file path (``*.stl``).
    """
    cq.exporters.export(solid, str(path), exportType="STL")


def generate_and_export(
    config: ContainerConfig,
    packing: PackingResult,
    output_path: Union[str, Path],
) -> cq.Workplane:
    """Generate the container solid and export it based on the file extension.

    Supported extensions (case-insensitive):
    - ``.step`` / ``.stp`` → STEP format
    - ``.stl``             → STL format

    Args:
        config:      Full container specification.
        packing:     Bin-packing result produced by
                     :func:`cadbox.packer.pack_cavities`.
        output_path: Destination file path; the extension determines the
                     export format.

    Returns:
        The generated :class:`cadquery.Workplane` (the solid before export),
        allowing the caller to render a preview or perform further operations.

    Raises:
        ValueError: If the file extension is not recognised.
    """
    output_path = Path(output_path)
    solid = generate(config, packing)

    suffix = output_path.suffix.lower()
    if suffix in (".step", ".stp"):
        export_step(solid, output_path)
    elif suffix == ".stl":
        export_stl(solid, output_path)
    else:
        raise ValueError(
            f"Unsupported export format '{suffix}'. "
            "Supported extensions: .step, .stp, .stl"
        )

    return solid
