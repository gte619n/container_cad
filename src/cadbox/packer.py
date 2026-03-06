"""Bin-packing module for cadbox.

Arranges cavities inside a container using the ``rectpack`` library.
All public dimensions are in millimetres; internally the packer works in
integer units of 0.01 mm to avoid floating-point rounding issues.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import rectpack

from .models import (
    CavityRef,
    CavitySpec,
    ContainerConfig,
    Layout,
    PackingResult,
    PlacedCavity,
)

# Scale factor: 1 mm -> 100 integer units (0.01 mm resolution)
_SCALE = 100


def _to_int(mm: float) -> int:
    """Convert millimetres to integer packer units (round to nearest 0.01 mm)."""
    return round(mm * _SCALE)


def _to_mm(units: int) -> float:
    """Convert integer packer units back to millimetres."""
    return units / _SCALE


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class PackingError(Exception):
    """Raised when cavities cannot be packed into the container.

    Attributes:
        message:    Human-readable description of the failure.
        suggestion: Minimum container dimensions (width x length) that would
                    fit all cavities, formatted as a string.
    """

    def __init__(self, message: str, suggestion: str) -> None:
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion


# ---------------------------------------------------------------------------
# Internal helper types
# ---------------------------------------------------------------------------


class _CavityItem(NamedTuple):
    """A single cavity ready for packing, with its padded bounding box."""

    spec: CavitySpec
    padded_w: int  # integer packer units
    padded_l: int  # integer packer units


# ---------------------------------------------------------------------------
# Expansion helpers
# ---------------------------------------------------------------------------


def _expand_cavities(config: ContainerConfig) -> list[CavitySpec]:
    """Resolve all CavityRef entries and expand count/grid repetitions.

    Returns a flat list of individual :class:`CavitySpec` instances – one per
    physical cavity to be placed.
    """
    specs: list[CavitySpec] = []

    for entry in config.cavities:
        # Resolve references to concrete specs
        if isinstance(entry, CavityRef):
            spec = config.resolve_cavity(entry)
        else:
            spec = entry

        if spec.grid is not None:
            cols, rows = spec.grid
            total = cols * rows
        else:
            total = spec.count

        # Strip count/grid from the individual spec so each placement is
        # unambiguously a single cavity.
        single = CavitySpec(
            shape=spec.shape,
            width=spec.width,
            length=spec.length,
            diameter=spec.diameter,
            depth=spec.depth,
            fillet_top=spec.fillet_top,
            count=1,
            grid=None,
        )
        specs.extend([single] * total)

    return specs


def _build_items(specs: list[CavitySpec], rib_thickness: float) -> list[_CavityItem]:
    """Build padded bounding boxes for every cavity spec.

    Each rectangle is enlarged by ``rib_thickness`` on both its width and
    length axes.  This guarantees a gap of at least ``rib_thickness`` between
    adjacent cavity walls once the padding is removed at placement time.
    """
    items: list[_CavityItem] = []
    for spec in specs:
        pw = _to_int(spec.footprint_width + rib_thickness)
        pl = _to_int(spec.footprint_length + rib_thickness)
        items.append(_CavityItem(spec=spec, padded_w=pw, padded_l=pl))
    return items


# ---------------------------------------------------------------------------
# Core packing logic
# ---------------------------------------------------------------------------


def _run_rectpack(
    items: list[_CavityItem],
    bin_w: int,
    bin_l: int,
) -> list[tuple[int, int, _CavityItem]] | None:
    """Attempt to pack *items* into a single bin of size ``bin_w`` x ``bin_l``.

    Returns a list of ``(x, y, item)`` tuples where ``(x, y)`` is the
    bottom-left corner of each padded rectangle in integer packer units, or
    ``None`` if not all items could be packed.

    Rotation is disabled so cavities keep their user-specified orientation.
    """
    packer = rectpack.newPacker(
        mode=rectpack.PackingMode.Offline,
        bin_algo=rectpack.PackingBin.BFF,
        pack_algo=rectpack.MaxRectsBssf,
        rotation=False,
    )

    # Add the single bin
    packer.add_bin(bin_w, bin_l)

    # Add all rectangles with a numeric rid for retrieval
    for idx, item in enumerate(items):
        packer.add_rect(item.padded_w, item.padded_l, rid=idx)

    packer.pack()

    packed_bins = packer.rect_list()
    if len(packed_bins) != len(items):
        return None

    # Build a lookup: rid -> (x, y) bottom-left corner
    placements: dict[int, tuple[int, int]] = {}
    for b, x, y, w, h, rid in packed_bins:  # noqa: B007  (b unused)
        placements[rid] = (x, y)

    if len(placements) != len(items):
        return None

    result: list[tuple[int, int, _CavityItem]] = []
    for idx, item in enumerate(items):
        x, y = placements[idx]
        result.append((x, y, item))

    return result


# ---------------------------------------------------------------------------
# Coordinate conversion
# ---------------------------------------------------------------------------


def _to_container_coords(
    x_bl: int,
    y_bl: int,
    padded_w: int,
    padded_l: int,
) -> tuple[float, float]:
    """Convert a rectpack bottom-left position to inner-floor coordinates.

    The returned ``(x, y)`` is the *centre* of the cavity footprint in
    container coordinate space where ``(0, 0)`` is the **bottom-left corner**
    of the inner floor.

    Each padded rectangle already includes ``rib_thickness`` of padding, so
    edge cavities naturally sit ``rib_thickness / 2`` from the bin boundary
    (which corresponds to the inner wall).  No additional offset is needed.
    """
    cx_mm = _to_mm(x_bl + padded_w / 2)
    cy_mm = _to_mm(y_bl + padded_l / 2)

    return cx_mm, cy_mm


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def estimate_minimum_container(
    cavities: list[CavitySpec],
    outer_wall: float,
    rib_thickness: float,
) -> tuple[float, float]:
    """Estimate the minimum outer container dimensions that can hold *cavities*.

    Uses an iterative approach: starts from the square root of the total
    padded area and grows in 5 mm steps until rectpack succeeds.

    Args:
        cavities:       Flat list of individual cavity specs (already expanded).
        outer_wall:     Wall thickness added on each side (mm).
        rib_thickness:  Minimum gap between cavities / cavities and walls (mm).

    Returns:
        ``(min_width, min_length)`` in millimetres (outer dimensions).
    """
    if not cavities:
        # Degenerate case: only walls needed
        return (2 * outer_wall + 1.0, 2 * outer_wall + 1.0)

    items = _build_items(cavities, rib_thickness)

    # Sum of padded widths and max padded length give a good rectangular start
    total_padded_w = sum(_to_mm(i.padded_w) for i in items)
    max_padded_w = _to_mm(max(i.padded_w for i in items))
    max_padded_l = _to_mm(max(i.padded_l for i in items))

    # Try rectangular bins: start from (sum_of_widths, max_length) and grow
    start_w = max(max_padded_w, 1.0)
    start_l = max(max_padded_l, 1.0)

    step = 1.0  # mm growth per iteration
    max_iter = 500

    # Strategy: grow width from minimum, keep length at max needed
    w = start_w
    for _ in range(max_iter):
        bin_w = _to_int(w)
        bin_l = _to_int(start_l)
        if bin_w > 0 and bin_l > 0:
            result = _run_rectpack(items, bin_w, bin_l)
            if result is not None:
                return (w + 2 * outer_wall, start_l + 2 * outer_wall)
        w += step

    # Fallback: return a generous estimate
    fallback_w = w + 2 * outer_wall
    fallback_l = start_l + 2 * outer_wall
    return (fallback_w, fallback_l)


def _center_placements(
    placements: list[PlacedCavity],
    inner_w: float,
    inner_l: float,
) -> list[PlacedCavity]:
    """Shift all placements so their bounding box is centred in the container."""
    if not placements:
        return placements

    min_x = min(p.x - p.spec.footprint_width / 2 for p in placements)
    max_x = max(p.x + p.spec.footprint_width / 2 for p in placements)
    min_y = min(p.y - p.spec.footprint_length / 2 for p in placements)
    max_y = max(p.y + p.spec.footprint_length / 2 for p in placements)

    dx = (inner_w - (max_x + min_x)) / 2
    dy = (inner_l - (max_y + min_y)) / 2

    return [PlacedCavity(x=p.x + dx, y=p.y + dy, spec=p.spec) for p in placements]


def _even_placements(
    placements: list[PlacedCavity],
    inner_w: float,
    inner_l: float,
    rib_thickness: float,
) -> list[PlacedCavity]:
    """Redistribute placements with equal spacing between columns/rows and walls.

    Groups cavities into columns (X-axis) and rows (Y-axis) based on the
    packed arrangement, then spreads them evenly across the container.
    """
    if not placements:
        return placements

    result = list(placements)

    # --- Redistribute along X (columns) ---
    result = _redistribute_axis(result, inner_w, rib_thickness, axis="x")

    # --- Redistribute along Y (rows) ---
    result = _redistribute_axis(result, inner_l, rib_thickness, axis="y")

    return result


def _redistribute_axis(
    placements: list[PlacedCavity],
    inner_span: float,
    rib_thickness: float,
    axis: str,
) -> list[PlacedCavity]:
    """Redistribute placements evenly along one axis.

    Groups cavities into lanes (columns for X, rows for Y) based on
    overlapping ranges, then spaces lanes evenly.
    """

    def _pos(p: PlacedCavity) -> float:
        return p.x if axis == "x" else p.y

    def _half_extent(p: PlacedCavity) -> float:
        return (p.spec.footprint_width if axis == "x" else p.spec.footprint_length) / 2

    # Sort by position on this axis
    sorted_indices = sorted(range(len(placements)), key=lambda i: _pos(placements[i]))

    # Group into lanes: cavities whose ranges overlap are in the same lane
    lanes: list[list[int]] = []
    current_lane: list[int] = [sorted_indices[0]]
    lane_max_edge = _pos(placements[sorted_indices[0]]) + _half_extent(placements[sorted_indices[0]])

    for idx in sorted_indices[1:]:
        p = placements[idx]
        left_edge = _pos(p) - _half_extent(p)
        if left_edge > lane_max_edge + rib_thickness / 2:
            lanes.append(current_lane)
            current_lane = [idx]
            lane_max_edge = _pos(p) + _half_extent(p)
        else:
            current_lane.append(idx)
            lane_max_edge = max(lane_max_edge, _pos(p) + _half_extent(p))
    lanes.append(current_lane)

    # Compute each lane's width (max footprint extent in this axis)
    lane_widths = []
    for lane in lanes:
        max_footprint = max(2 * _half_extent(placements[i]) for i in lane)
        lane_widths.append(max_footprint)

    # Distribute: total gap = inner_span - sum(lane_widths)
    # Number of gaps = N_lanes + 1 (wall-to-lane and lane-to-wall)
    total_lane_width = sum(lane_widths)
    n_gaps = len(lanes) + 1
    gap = max((inner_span - total_lane_width) / n_gaps, rib_thickness / 2)

    # Compute new lane centre positions
    lane_centers = []
    cursor = gap
    for lw in lane_widths:
        lane_centers.append(cursor + lw / 2)
        cursor += lw + gap

    # Compute the offset for each lane relative to its original centre
    result = list(placements)
    for lane, new_center in zip(lanes, lane_centers):
        # Original lane centre = average of cavity positions in this lane
        old_center = sum(_pos(placements[i]) for i in lane) / len(lane)
        delta = new_center - old_center
        for i in lane:
            p = result[i]
            if axis == "x":
                result[i] = PlacedCavity(x=p.x + delta, y=p.y, spec=p.spec)
            else:
                result[i] = PlacedCavity(x=p.x, y=p.y + delta, spec=p.spec)

    return result


def pack_cavities(config: ContainerConfig) -> PackingResult:
    """Pack all cavities defined in *config* into the container floor.

    Algorithm
    ---------
    1. Compute inner usable dimensions (outer minus walls on both sides).
    2. Expand and resolve all cavity entries to a flat list of
       :class:`CavitySpec` objects.
    3. Build padded bounding rectangles for each cavity.
    4. Shrink the effective bin by ``rib_thickness / 2`` on each side so that
       the outermost cavities maintain a half-rib gap against the inner walls.
    5. Run :func:`_run_rectpack` with rotation disabled.
    6. Convert positions to container-centre coordinates.
    7. Return a :class:`PackingResult`.

    Raises:
        PackingError: If the cavities cannot be fitted into the container.
    """
    # --- 1. Inner dimensions ---
    inner_w = config.width - 2 * config.outer_wall
    inner_l = config.length - 2 * config.outer_wall

    # --- 2. Expand cavities ---
    specs = _expand_cavities(config)

    if not specs:
        return PackingResult(
            placements=[],
            container_width=inner_w,
            container_length=inner_l,
            utilization=0.0,
        )

    # --- 3. Padded items ---
    items = _build_items(specs, config.rib_thickness)

    # --- 4. Bin size ---
    # The bin matches the inner dimensions exactly.  Each cavity's padded
    # bounding box already includes rib_thickness, so edge cavities end up
    # rib_thickness/2 from the inner wall and adjacent cavities have a full
    # rib_thickness gap between them.
    bin_w = _to_int(inner_w)
    bin_l = _to_int(inner_l)

    if bin_w <= 0 or bin_l <= 0:
        min_w, min_l = estimate_minimum_container(specs, config.outer_wall, config.rib_thickness)
        raise PackingError(
            message="Container inner dimensions are too small to hold any cavities.",
            suggestion=f"{min_w:.1f} mm × {min_l:.1f} mm (outer)",
        )

    # --- 5. Pack ---
    packed = _run_rectpack(items, bin_w, bin_l)

    if packed is None:
        min_w, min_l = estimate_minimum_container(specs, config.outer_wall, config.rib_thickness)
        raise PackingError(
            message=(
                f"Could not fit {len(specs)} cavit{'y' if len(specs) == 1 else 'ies'} "
                f"into the container ({config.width:.1f} mm × {config.length:.1f} mm outer, "
                f"{inner_w:.1f} mm × {inner_l:.1f} mm inner)."
            ),
            suggestion=f"{min_w:.1f} mm × {min_l:.1f} mm (outer)",
        )

    # --- 6. Convert to container coordinates ---
    placements: list[PlacedCavity] = []
    for x_bl, y_bl, item in packed:
        cx, cy = _to_container_coords(x_bl, y_bl, item.padded_w, item.padded_l)
        placements.append(PlacedCavity(x=cx, y=cy, spec=item.spec))

    # --- 7. Apply layout strategy ---
    if config.layout == Layout.centered:
        placements = _center_placements(placements, inner_w, inner_l)
    elif config.layout == Layout.even:
        placements = _even_placements(placements, inner_w, inner_l, config.rib_thickness)

    # --- 8. Utilization ---
    inner_area = inner_w * inner_l
    cavity_area = sum(
        p.spec.footprint_width * p.spec.footprint_length for p in placements
    )
    utilization = min(cavity_area / inner_area, 1.0) if inner_area > 0 else 0.0

    return PackingResult(
        placements=placements,
        container_width=inner_w,
        container_length=inner_l,
        utilization=utilization,
    )
