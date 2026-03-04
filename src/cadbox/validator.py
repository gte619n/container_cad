"""Printability validator for cadbox – enforces FDM constraints for a 0.4 mm nozzle.

All dimensions are in millimetres unless otherwise noted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .models import CavityShape, CavitySpec, ContainerConfig, PackingResult, PlacedCavity

# ---------------------------------------------------------------------------
# FDM constants (0.4 mm nozzle)
# ---------------------------------------------------------------------------

NOZZLE_DIAMETER: float = 0.4
MIN_WALL_THICKNESS: float = 1.2   # 3× nozzle
MIN_RIB_THICKNESS: float = 1.2    # 3× nozzle
MIN_FLOOR_THICKNESS: float = 0.8  # 2× nozzle
MIN_FEATURE_SIZE: float = 1.8     # smallest printable feature
MIN_FILLET_RADIUS: float = 0.5
MIN_CAVITY_DIMENSION: float = 2.0  # smallest printable hole/opening
_TOLERANCE: float = 0.01  # mm – float-comparison tolerance for placement checks


# ---------------------------------------------------------------------------
# Validation primitives
# ---------------------------------------------------------------------------


@dataclass
class ValidationError:
    """A single printability constraint violation."""

    message: str
    field: str
    value: float
    minimum: float

    def __str__(self) -> str:
        return (
            f"{self.field}: {self.message} "
            f"(got {self.value:.3f} mm, minimum {self.minimum:.3f} mm)"
        )


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class CadboxValidationError(ValueError):
    """Raised by :func:`validate_all` when one or more validation errors exist."""

    def __init__(self, errors: list[ValidationError]) -> None:
        self.errors = errors
        super().__init__(str(self))

    def __str__(self) -> str:
        lines = [f"cadbox validation failed with {len(self.errors)} error(s):"]
        for i, err in enumerate(self.errors, start=1):
            lines.append(f"  {i}. {err}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-spec cavity helpers
# ---------------------------------------------------------------------------


def _resolved_spec(config: ContainerConfig, cavity_index: int) -> CavitySpec:
    """Return the concrete CavitySpec for the *i*-th cavity entry."""
    from .models import CavityRef  # local to avoid circular import issues

    entry = config.cavities[cavity_index]
    if isinstance(entry, CavityRef):
        return config.resolve_cavity(entry)
    return entry  # type: ignore[return-value]


def _iter_resolved_specs(config: ContainerConfig):
    """Yield (index, CavitySpec) for every cavity entry in config."""
    from .models import CavityRef

    for i, entry in enumerate(config.cavities):
        if isinstance(entry, CavityRef):
            yield i, config.resolve_cavity(entry)
        else:
            yield i, entry  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Main validators
# ---------------------------------------------------------------------------


def validate_container(config: ContainerConfig) -> list[ValidationError]:
    """Validate container-level and cavity-level printability constraints.

    Does *not* require a packing result – only the raw config is needed.

    Args:
        config: The container configuration to validate.

    Returns:
        A (possibly empty) list of :class:`ValidationError` instances.
    """
    errors: list[ValidationError] = []

    # -- structural thickness checks ----------------------------------------

    if config.outer_wall < MIN_WALL_THICKNESS:
        errors.append(
            ValidationError(
                message="outer wall is too thin for reliable FDM extrusion",
                field="outer_wall",
                value=config.outer_wall,
                minimum=MIN_WALL_THICKNESS,
            )
        )

    if config.rib_thickness < MIN_RIB_THICKNESS:
        errors.append(
            ValidationError(
                message="rib thickness is too thin for reliable FDM extrusion",
                field="rib_thickness",
                value=config.rib_thickness,
                minimum=MIN_RIB_THICKNESS,
            )
        )

    if config.floor_thickness < MIN_FLOOR_THICKNESS:
        errors.append(
            ValidationError(
                message="floor thickness is too thin for reliable FDM extrusion",
                field="floor_thickness",
                value=config.floor_thickness,
                minimum=MIN_FLOOR_THICKNESS,
            )
        )

    if config.fillet_radius < MIN_FILLET_RADIUS:
        errors.append(
            ValidationError(
                message="fillet radius is smaller than the minimum printable radius",
                field="fillet_radius",
                value=config.fillet_radius,
                minimum=MIN_FILLET_RADIUS,
            )
        )

    # -- inner space check --------------------------------------------------

    inner_width = config.width - 2.0 * config.outer_wall
    inner_length = config.length - 2.0 * config.outer_wall

    if inner_width <= 0:
        errors.append(
            ValidationError(
                message="outer walls consume the entire container width – no inner space",
                field="width",
                value=config.width,
                minimum=2.0 * config.outer_wall + MIN_CAVITY_DIMENSION,
            )
        )

    if inner_length <= 0:
        errors.append(
            ValidationError(
                message="outer walls consume the entire container length – no inner space",
                field="length",
                value=config.length,
                minimum=2.0 * config.outer_wall + MIN_CAVITY_DIMENSION,
            )
        )

    # -- per-cavity checks --------------------------------------------------

    for idx, spec in _iter_resolved_specs(config):
        field_prefix = f"cavities[{idx}]"

        # depth must not exceed container interior
        max_depth = config.height - config.floor_thickness
        if spec.depth > max_depth:
            errors.append(
                ValidationError(
                    message=(
                        "cavity depth exceeds container height minus floor thickness"
                    ),
                    field=f"{field_prefix}.depth",
                    value=spec.depth,
                    minimum=0.0,  # no hard minimum; surfaced as max violation
                )
            )
            # Override minimum with the actual allowed maximum for clarity
            # Replace the last entry with a properly described one
            errors[-1] = ValidationError(
                message=(
                    f"cavity depth ({spec.depth:.3f} mm) exceeds "
                    f"max allowed depth = height ({config.height:.3f}) "
                    f"- floor_thickness ({config.floor_thickness:.3f}) "
                    f"= {max_depth:.3f} mm"
                ),
                field=f"{field_prefix}.depth",
                value=spec.depth,
                minimum=max_depth,  # used as the "required" bound (value must be ≤)
            )

        if spec.shape == CavityShape.circle:
            if spec.diameter is not None and spec.diameter < MIN_CAVITY_DIMENSION:
                errors.append(
                    ValidationError(
                        message="circular cavity diameter is below minimum printable dimension",
                        field=f"{field_prefix}.diameter",
                        value=spec.diameter,
                        minimum=MIN_CAVITY_DIMENSION,
                    )
                )

        elif spec.shape == CavityShape.rect:
            if spec.width is not None and spec.width < MIN_CAVITY_DIMENSION:
                errors.append(
                    ValidationError(
                        message="rectangular cavity width is below minimum printable dimension",
                        field=f"{field_prefix}.width",
                        value=spec.width,
                        minimum=MIN_CAVITY_DIMENSION,
                    )
                )
            if spec.length is not None and spec.length < MIN_CAVITY_DIMENSION:
                errors.append(
                    ValidationError(
                        message="rectangular cavity length is below minimum printable dimension",
                        field=f"{field_prefix}.length",
                        value=spec.length,
                        minimum=MIN_CAVITY_DIMENSION,
                    )
                )

    return errors


def validate_placement(
    config: ContainerConfig, result: PackingResult
) -> list[ValidationError]:
    """Validate post-packing spatial constraints.

    Checks that:
    - The gap between every pair of placed cavities is >= ``rib_thickness``.
    - No cavity overlaps the container inner wall (gap >= 0).

    The gap between two axis-aligned bounding boxes is the minimum separating
    distance along either axis.  For circles, the bounding box of the circle
    is used (i.e. a square of side = diameter), which is conservative.

    Args:
        config: The container configuration (needed for wall/rib thresholds).
        result: The packing result with placed cavity positions.

    Returns:
        A (possibly empty) list of :class:`ValidationError` instances.
    """
    errors: list[ValidationError] = []
    placements = result.placements

    # Helper: axis-aligned bounding-box half-extents for a placed cavity
    def _half_extents(p: PlacedCavity) -> tuple[float, float]:
        return p.spec.footprint_width / 2.0, p.spec.footprint_length / 2.0

    # -- cavity vs. container inner wall ------------------------------------
    # Inner space coordinates: x in [0, container_width], y in [0, container_length]
    # PlacedCavity (x, y) is the centre within that space.

    for i, placed in enumerate(placements):
        hw, hl = _half_extents(placed)
        field = f"placements[{i}]"

        # distance from left/right inner wall
        gap_x_left = placed.x - hw
        gap_x_right = result.container_width - (placed.x + hw)
        # distance from bottom/top inner wall
        gap_y_bottom = placed.y - hl
        gap_y_top = result.container_length - (placed.y + hl)

        for gap, direction in (
            (gap_x_left, "left"),
            (gap_x_right, "right"),
            (gap_y_bottom, "bottom"),
            (gap_y_top, "top"),
        ):
            if gap < -_TOLERANCE:
                errors.append(
                    ValidationError(
                        message=(
                            f"cavity overlaps the container {direction} inner wall "
                            f"(gap = {gap:.3f} mm)"
                        ),
                        field=field,
                        value=gap,
                        minimum=0.0,
                    )
                )

    # -- cavity-to-cavity rib gap -------------------------------------------

    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            a = placements[i]
            b = placements[j]
            hw_a, hl_a = _half_extents(a)
            hw_b, hl_b = _half_extents(b)

            # Separating distance along each axis between the two AABBs
            # Positive value = gap; negative = overlap
            gap_x = abs(a.x - b.x) - hw_a - hw_b
            gap_y = abs(a.y - b.y) - hl_a - hl_b

            # The actual gap between AABBs is the min-separating axis gap.
            # If either axis already separates them completely, use the smaller.
            if gap_x >= 0 and gap_y >= 0:
                # Non-overlapping in both axes; AABB gap is min of the two
                gap = min(gap_x, gap_y)
            elif gap_x >= 0:
                gap = gap_x  # separated only on X
            elif gap_y >= 0:
                gap = gap_y  # separated only on Y
            else:
                # Overlapping on both axes – record zero as the effective gap
                gap = min(gap_x, gap_y)

            if gap < config.rib_thickness - _TOLERANCE:
                errors.append(
                    ValidationError(
                        message=(
                            f"gap between placements[{i}] and placements[{j}] "
                            f"({gap:.3f} mm) is less than rib_thickness"
                        ),
                        field=f"placements[{i}]-placements[{j}]",
                        value=gap,
                        minimum=config.rib_thickness,
                    )
                )

    return errors


def validate_all(
    config: ContainerConfig,
    result: Optional[PackingResult] = None,
) -> list[ValidationError]:
    """Run all applicable validation passes and raise on failure.

    Runs :func:`validate_container` unconditionally; also runs
    :func:`validate_placement` when *result* is provided.

    Args:
        config: The container configuration to validate.
        result: Optional packing result for post-packing spatial checks.

    Returns:
        The combined list of :class:`ValidationError` instances (empty = valid).

    Raises:
        CadboxValidationError: If any validation errors are found.  The
            exception carries the full ``errors`` list and formats them
            in its ``__str__`` representation.
    """
    errors: list[ValidationError] = validate_container(config)

    if result is not None:
        errors.extend(validate_placement(config, result))

    if errors:
        raise CadboxValidationError(errors)

    return errors
