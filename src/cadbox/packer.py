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
    rib_half: float,
) -> tuple[float, float]:
    """Convert a rectpack bottom-left position to inner-floor coordinates.

    The returned ``(x, y)`` is the *centre* of the cavity footprint in
    container coordinate space where ``(0, 0)`` is the **bottom-left corner**
    of the inner floor.

    The effective bin is inset by ``rib_half`` (half the rib thickness) from
    the inner walls so that outermost cavities maintain a half-rib gap.

    Within the effective bin, the padded rectangle's centre is:

        cavity_centre_in_bin = (x_bl + padded_w/2, y_bl + padded_l/2)

    Shifting back to inner-floor space adds the rib_half offset.
    """
    cx_mm = rib_half + _to_mm(x_bl + padded_w / 2)
    cy_mm = rib_half + _to_mm(y_bl + padded_l / 2)

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

    # Total padded area gives a lower bound
    total_area = sum(i.padded_w * i.padded_l for i in items)
    side = max(
        _to_mm(max(i.padded_w for i in items)),
        _to_mm(max(i.padded_l for i in items)),
        math.sqrt(_to_mm(total_area)),
    )

    # Wall padding that must be subtracted from outer size to get bin size
    wall_padding_mm = 2 * outer_wall + rib_thickness  # rib_thickness for the half-rib at edges

    step = 5.0  # mm growth per iteration
    max_iter = 200

    for _ in range(max_iter):
        inner_w = side
        inner_l = side
        bin_w = _to_int(inner_w - rib_thickness)
        bin_l = _to_int(inner_l - rib_thickness)
        if bin_w > 0 and bin_l > 0:
            result = _run_rectpack(items, bin_w, bin_l)
            if result is not None:
                outer_w = inner_w + wall_padding_mm - rib_thickness
                outer_l = inner_l + wall_padding_mm - rib_thickness
                return (outer_w, outer_l)
        side += step

    # Fallback: return a generous estimate
    fallback = side + wall_padding_mm
    return (fallback, fallback)


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

    # --- 4. Effective bin size ---
    # We shrink by rib_thickness on the total span (rib_thickness/2 each side)
    # to keep edge cavities a full half-rib away from the inner wall.
    eff_w = inner_w - config.rib_thickness
    eff_l = inner_l - config.rib_thickness

    bin_w = _to_int(eff_w)
    bin_l = _to_int(eff_l)

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
    rib_half = config.rib_thickness / 2.0
    placements: list[PlacedCavity] = []
    for x_bl, y_bl, item in packed:
        cx, cy = _to_container_coords(x_bl, y_bl, item.padded_w, item.padded_l, rib_half)
        placements.append(PlacedCavity(x=cx, y=cy, spec=item.spec))

    # --- 7. Utilization ---
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
