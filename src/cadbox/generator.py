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

from .models import (
    BoxType,
    CavityShape,
    ContainerConfig,
    PackingResult,
    PlacedCavity,
    StackingMode,
)

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


# ---------------------------------------------------------------------------
# Stacking features
# ---------------------------------------------------------------------------


def _add_stacking_receiver(
    result: cq.Workplane, config: ContainerConfig
) -> cq.Workplane:
    """Add a raised rim to the top of the box for receiving a stacker above.

    The rim sits on the top face, aligned with the inner wall surface.
    It creates a channel that the stacker's bottom step drops into.
    """
    w = config.width
    l = config.length
    h = config.height
    ow = config.outer_wall
    sd = config.stacking_shelf_depth
    sh = config.stacking_shelf_height
    cl = config.stacking_clearance
    chamfer = config.stacking_chamfer
    r = config.fillet_radius

    # Rim outer edge sits at the inner wall surface (flush with inner wall)
    rim_outer_w = w - 2 * ow
    rim_outer_l = l - 2 * ow
    rim_inner_w = rim_outer_w - 2 * sd
    rim_inner_l = rim_outer_l - 2 * sd

    if rim_inner_w <= 0 or rim_inner_l <= 0:
        return result  # no room for a rim

    # Build the rim as outer - inner cutout
    r_outer = _safe_fillet_radius(r, rim_outer_w, rim_outer_l)
    if r_outer > 0:
        outer = (
            cq.Workplane("XY")
            .sketch().rect(rim_outer_w, rim_outer_l).vertices().fillet(r_outer)
            .finalize().extrude(sh)
        )
    else:
        outer = cq.Workplane("XY").rect(rim_outer_w, rim_outer_l).extrude(sh)

    r_inner = _safe_fillet_radius(r, rim_inner_w, rim_inner_l)
    if r_inner > 0:
        inner = (
            cq.Workplane("XY")
            .sketch().rect(rim_inner_w, rim_inner_l).vertices().fillet(r_inner)
            .finalize().extrude(sh)
        )
    else:
        inner = cq.Workplane("XY").rect(rim_inner_w, rim_inner_l).extrude(sh)

    rim = outer.cut(inner).translate((0, 0, h))

    # Lead-in chamfer on the inner top edge of the rim
    if chamfer > 0:
        c = _safe_fillet_radius(chamfer, sd, sh)
        if c > 0:
            try:
                rim = rim.faces(">Z").edges().chamfer(c)
            except Exception:
                pass

    return result.union(rim)


def _add_stacking_stacker(
    result: cq.Workplane, config: ContainerConfig
) -> cq.Workplane:
    """Cut a step from the bottom perimeter so the box sits in a receiver rim.

    Removes a ring of material from the bottom outer edge, creating a step
    that nests inside the receiver's rim. The step is chamfered at 45 degrees
    for lead-in and support-free printing.
    """
    w = config.width
    l = config.length
    sd = config.stacking_shelf_depth
    sh = config.stacking_shelf_height
    cl = config.stacking_clearance
    chamfer = config.stacking_chamfer
    r = config.fillet_radius

    # Cut a ring from the bottom: outer dimensions = box, inner = box - 2*sd
    step_inner_w = w - 2 * sd + 2 * cl
    step_inner_l = l - 2 * sd + 2 * cl

    if step_inner_w <= 0 or step_inner_l <= 0:
        return result

    r_outer = _safe_fillet_radius(r, w, l)
    if r_outer > 0:
        outer = (
            cq.Workplane("XY")
            .sketch().rect(w, l).vertices().fillet(r_outer)
            .finalize().extrude(sh)
        )
    else:
        outer = cq.Workplane("XY").rect(w, l).extrude(sh)

    r_inner = _safe_fillet_radius(r, step_inner_w, step_inner_l)
    if r_inner > 0:
        inner = (
            cq.Workplane("XY")
            .sketch().rect(step_inner_w, step_inner_l).vertices().fillet(r_inner)
            .finalize().extrude(sh)
        )
    else:
        inner = cq.Workplane("XY").rect(step_inner_w, step_inner_l).extrude(sh)

    ring = outer.cut(inner)
    result = result.cut(ring)

    # Add 45-degree chamfer on the outer step edge for lead-in (support-free)
    if chamfer > 0:
        c = _safe_fillet_radius(chamfer, sd, sh)
        if c > 0:
            try:
                # Select the bottom outer horizontal edges exposed by the cut
                sel = selectors.BoxSelector(
                    (-w / 2 - 0.5, -l / 2 - 0.5, -0.1),
                    (w / 2 + 0.5, l / 2 + 0.5, sh + 0.1),
                )
                result = result.edges(sel).edges("|Z").chamfer(c)
            except Exception:
                pass

    return result


# ---------------------------------------------------------------------------
# Gridfinity bin construction
# ---------------------------------------------------------------------------

# Gridfinity standard constants
_GF_PITCH = 42.0       # grid pitch (mm)
_GF_CLEARANCE = 0.5    # total clearance per grid unit (mm)
_GF_CORNER_R = 3.75    # top corner radius (mm)
_GF_WALL = 0.95        # wall thickness (mm)
_GF_BASE_HEIGHT = 4.75  # base profile height (mm)
_GF_LIP_HEIGHT = 4.4   # stacking lip height (mm)

# Base profile: [x_outward, z_upward] from innermost bottom corner
_GF_BASE_PROFILE = [
    (0, 0),        # inner bottom corner
    (0.8, 0.8),    # 45-degree chamfer
    (0.8, 2.6),    # vertical wall (1.8mm)
    (2.95, 4.75),  # 45-degree chamfer to full width
]

# Stacking lip profile: [x_outward, z_upward] from inner tip
_GF_LIP_PROFILE = [
    (0, 0),        # inner tip
    (0.7, 0.7),    # 45-degree lower chamfer
    (0.7, 2.5),    # vertical wall (1.8mm)
    (2.6, 4.4),    # 45-degree upper chamfer
]


def _gridfinity_base_solid(w: float, l: float, r: float) -> cq.Workplane:
    """Build the gridfinity stepped base profile as a lofted solid.

    Uses three cross-sections at key Z levels to approximate the
    multi-segment profile: bottom (smallest), mid (after first chamfer),
    and top (full width).
    """
    # At each Z-level, compute the inset from the full outer edge
    # Z=0:    inset = 2.95mm (smallest footprint)
    # Z=0.8:  inset = 2.15mm (after first 45-deg chamfer)
    # Z=2.6:  inset = 2.15mm (vertical wall, same as Z=0.8)
    # Z=4.75: inset = 0mm (full width)

    levels = [
        (0, 2.95),
        (0.8, 2.15),
        (2.6, 2.15),
        (_GF_BASE_HEIGHT, 0.0),
    ]

    sections = []
    for z, inset in levels:
        sw = w - 2 * inset
        sl = l - 2 * inset
        sr = max(r - inset, 0.35)
        if sw <= 0 or sl <= 0:
            continue
        wp = cq.Workplane("XY", origin=(0, 0, z))
        section = wp.sketch().rect(sw, sl).vertices().fillet(sr).finalize()
        sections.append(section)

    if len(sections) < 2:
        # Fallback: simple box
        return (
            cq.Workplane("XY")
            .sketch().rect(w, l).vertices().fillet(r).finalize()
            .extrude(_GF_BASE_HEIGHT)
        )

    # Loft between all sections
    result = sections[0]
    for s in sections[1:]:
        result = result.add(s)
    return result.loft()


def _gridfinity_lip_solid(w: float, l: float, r: float, z_base: float) -> cq.Workplane:
    """Build the gridfinity stacking lip as a lofted solid at the top of the bin.

    The lip profile tapers outward from the bin wall, using 45-degree
    chamfers for support-free printing.
    """
    levels = [
        (0, 2.6),      # inner tip (most inset)
        (0.7, 1.9),    # after lower 45-deg chamfer
        (2.5, 1.9),    # vertical wall
        (_GF_LIP_HEIGHT, 0.0),  # full width at top
    ]

    sections = []
    for dz, inset in levels:
        sw = w - 2 * inset
        sl = l - 2 * inset
        sr = max(r - inset, 0.35)
        if sw <= 0 or sl <= 0:
            continue
        wp = cq.Workplane("XY", origin=(0, 0, z_base + dz))
        section = wp.sketch().rect(sw, sl).vertices().fillet(sr).finalize()
        sections.append(section)

    if len(sections) < 2:
        return cq.Workplane("XY")  # empty

    result = sections[0]
    for s in sections[1:]:
        result = result.add(s)
    return result.loft()


def _gridfinity_magnet_holes(
    result: cq.Workplane, config: ContainerConfig
) -> cq.Workplane:
    """Cut magnet holes into the bottom of each grid unit cell."""
    magnet_r = 3.25  # hole radius (6.5mm dia for 6mm magnet)
    magnet_depth = 2.4
    hole_inset = 8.0  # distance from unit cell edge to hole center

    for gx in range(config.grid_units_x):
        for gy in range(config.grid_units_y):
            # Center of this grid unit cell
            cx = (gx + 0.5) * _GF_PITCH - config.width / 2 - _GF_CLEARANCE / 2
            cy = (gy + 0.5) * _GF_PITCH - config.length / 2 - _GF_CLEARANCE / 2
            # Four corner holes per unit cell
            for dx_sign in (-1, 1):
                for dy_sign in (-1, 1):
                    hx = cx + dx_sign * (_GF_PITCH / 2 - hole_inset)
                    hy = cy + dy_sign * (_GF_PITCH / 2 - hole_inset)
                    hole = (
                        cq.Workplane("XY")
                        .center(hx, hy)
                        .circle(magnet_r)
                        .extrude(magnet_depth)
                    )
                    result = result.cut(hole)
    return result


def generate_gridfinity(config: ContainerConfig, packing: PackingResult) -> cq.Workplane:
    """Generate a Gridfinity-compatible bin.

    Builds the bin with the standard base profile, thin walls, stacking
    lip, and optional magnet holes. Cavities are cut from the top.
    """
    w = config.width
    l = config.length
    h = config.height
    r = _GF_CORNER_R

    # -- 1. Base profile (stepped bottom) --
    base = _gridfinity_base_solid(w, l, r)

    # -- 2. Flat floor above base (from 4.75mm to 7.0mm) --
    floor_block = (
        cq.Workplane("XY")
        .sketch().rect(w, l).vertices().fillet(r).finalize()
        .extrude(7.0 - _GF_BASE_HEIGHT)
        .translate((0, 0, _GF_BASE_HEIGHT))
    )

    # -- 3. Walls from base top (7mm) to lip bottom --
    lip_z = h - _GF_LIP_HEIGHT  # where the lip starts
    wall_height = lip_z - 7.0
    if wall_height > 0:
        outer_wall = (
            cq.Workplane("XY")
            .sketch().rect(w, l).vertices().fillet(r).finalize()
            .extrude(wall_height)
            .translate((0, 0, 7.0))
        )
        inner_w = w - 2 * _GF_WALL
        inner_l = l - 2 * _GF_WALL
        r_inner = max(r - _GF_WALL, 0.35)
        inner_cut = (
            cq.Workplane("XY")
            .sketch().rect(inner_w, inner_l).vertices().fillet(r_inner).finalize()
            .extrude(wall_height)
            .translate((0, 0, 7.0))
        )
        walls = outer_wall.cut(inner_cut)
    else:
        walls = None

    # -- 4. Stacking lip --
    lip = _gridfinity_lip_solid(w, l, r, lip_z)

    # -- 5. Assemble --
    result = base.union(floor_block)
    if walls is not None:
        result = result.union(walls)
    result = result.union(lip)

    # -- 6. Magnet holes --
    if config.gridfinity_magnets:
        result = _gridfinity_magnet_holes(result, config)

    # -- 7. Cut cavities from the top --
    inner_w = w - 2 * _GF_WALL
    inner_l = l - 2 * _GF_WALL
    for placement in packing.placements:
        adjusted = PlacedCavity(
            x=placement.x - inner_w / 2,
            y=placement.y - inner_l / 2,
            spec=placement.spec,
        )
        result = _cut_cavity(result, adjusted, config.fillet_radius, config.cavity_fillet_top)

    return result


# ---------------------------------------------------------------------------
# Main generate function
# ---------------------------------------------------------------------------


def generate(config: ContainerConfig, packing: PackingResult) -> cq.Workplane:
    """Generate a CadQuery solid for the container described by *config*.

    Dispatches to :func:`generate_gridfinity` when ``box_type`` is
    ``gridfinity``.  For custom boxes the workflow is:

    1. Build the outer box (centered on XY, floor on Z=0).
    2. Fillet vertical edges for aesthetics.
    3. Cut each cavity pocket from the top face.
    4. Add stacking features (receiver rim / stacker step) if requested.

    Args:
        config:  Full container specification.
        packing: Placement result from :func:`cadbox.packer.pack_cavities`.

    Returns:
        A :class:`cadquery.Workplane` containing the finished solid.
    """
    if config.box_type == BoxType.gridfinity:
        return generate_gridfinity(config, packing)

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

    # ------------------------------------------------------------------
    # Step 5: Stacking features
    # ------------------------------------------------------------------
    if config.stacking in (StackingMode.receiver, StackingMode.both):
        result = _add_stacking_receiver(result, config)
    if config.stacking in (StackingMode.stacker, StackingMode.both):
        result = _add_stacking_stacker(result, config)

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
