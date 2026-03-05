"""Data models for cadbox - parametric CAD container generator.

All dimensions are in millimetres unless otherwise noted.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Optional, Union

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class CavityShape(str, Enum):
    """Supported cross-section shapes for a cavity."""

    rect = "rect"
    circle = "circle"


# ---------------------------------------------------------------------------
# Core cavity types
# ---------------------------------------------------------------------------


class CavitySpec(BaseModel):
    """A single cavity definition with full geometric parameters.

    Rectangular cavities require ``width`` and ``length``.
    Circular cavities require ``diameter``.
    Exactly one of ``count`` or ``grid`` may be set (not both).
    """

    shape: CavityShape
    width: Optional[float] = Field(default=None, description="Rect only – X dimension (mm)")
    length: Optional[float] = Field(default=None, description="Rect only – Y dimension (mm)")
    diameter: Optional[float] = Field(default=None, description="Circle only – diameter (mm)")
    depth: float = Field(..., description="Cavity depth from top surface (mm)")
    fillet_top: Optional[float] = Field(
        default=None,
        ge=0,
        description="Fillet radius for the cavity top opening edge (mm). Overrides container-level cavity_fillet_top.",
    )
    count: int = Field(default=1, ge=1, description="Repeat this cavity N times for the packer")
    grid: Optional[tuple[int, int]] = Field(
        default=None,
        description="Arrange copies in a grid: (cols, rows).  Mutually exclusive with count > 1.",
    )

    @model_validator(mode="after")
    def _validate_geometry(self) -> "CavitySpec":
        if self.shape == CavityShape.rect:
            if self.width is None or self.length is None:
                raise ValueError("Rectangular cavity requires both 'width' and 'length'.")
        elif self.shape == CavityShape.circle:
            if self.diameter is None:
                raise ValueError("Circular cavity requires 'diameter'.")

        if self.grid is not None and self.count != 1:
            raise ValueError("'grid' and 'count' are mutually exclusive; set only one.")

        return self

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def footprint_width(self) -> float:
        """Footprint extent along the X axis (mm)."""
        if self.shape == CavityShape.circle:
            return self.diameter  # type: ignore[return-value]
        return self.width  # type: ignore[return-value]

    @property
    def footprint_length(self) -> float:
        """Footprint extent along the Y axis (mm)."""
        if self.shape == CavityShape.circle:
            return self.diameter  # type: ignore[return-value]
        return self.length  # type: ignore[return-value]


class CavityTemplate(BaseModel):
    """A named, reusable cavity preset.

    Identical to :class:`CavitySpec` but without *count* / *grid* so that
    repetition is controlled at the point of reference.
    """

    name: str = Field(..., description="Unique identifier used by CavityRef")
    shape: CavityShape
    width: Optional[float] = Field(default=None, description="Rect only – X dimension (mm)")
    length: Optional[float] = Field(default=None, description="Rect only – Y dimension (mm)")
    diameter: Optional[float] = Field(default=None, description="Circle only – diameter (mm)")
    depth: float = Field(..., description="Default cavity depth (mm)")
    fillet_top: Optional[float] = Field(
        default=None,
        ge=0,
        description="Fillet radius for the cavity top opening edge (mm). Overrides container-level cavity_fillet_top.",
    )

    @model_validator(mode="after")
    def _validate_geometry(self) -> "CavityTemplate":
        if self.shape == CavityShape.rect:
            if self.width is None or self.length is None:
                raise ValueError("Rectangular template requires both 'width' and 'length'.")
        elif self.shape == CavityShape.circle:
            if self.diameter is None:
                raise ValueError("Circular template requires 'diameter'.")
        return self


class CavityRef(BaseModel):
    """A reference to a :class:`CavityTemplate` by name.

    Optional overrides let a single template be reused at different depths
    or with different repetition counts.
    """

    template: str = Field(..., description="Name of the CavityTemplate to reference")
    depth: Optional[float] = Field(
        default=None, description="Override template depth (mm); None keeps template default"
    )
    fillet_top: Optional[float] = Field(
        default=None,
        ge=0,
        description="Override cavity top fillet radius (mm); None keeps template/container default.",
    )
    count: int = Field(default=1, ge=1, description="Repeat this cavity N times for the packer")
    grid: Optional[tuple[int, int]] = Field(
        default=None,
        description="Arrange copies in a grid: (cols, rows).  Mutually exclusive with count > 1.",
    )

    @model_validator(mode="after")
    def _validate_repetition(self) -> "CavityRef":
        if self.grid is not None and self.count != 1:
            raise ValueError("'grid' and 'count' are mutually exclusive; set only one.")
        return self


# ---------------------------------------------------------------------------
# Discriminated union helper
# ---------------------------------------------------------------------------

# Tag-based discrimination is not possible here because CavitySpec and
# CavityRef share no common literal field.  Pydantic v2 will attempt
# CavitySpec first (it has the richer schema) and fall back to CavityRef.
CavityEntry = Annotated[
    Union[CavitySpec, CavityRef],
    Field(union_mode="left_to_right"),
]


# ---------------------------------------------------------------------------
# Top-level container config
# ---------------------------------------------------------------------------


class ContainerConfig(BaseModel):
    """Full specification for generating a parametric container.

    Dimensions describe the *outer* envelope of the box.  Cavities may be
    given as :class:`CavitySpec` literals or :class:`CavityRef` lookups that
    resolve against ``templates``.
    """

    width: float = Field(..., gt=0, description="Outer width (X) in mm")
    length: float = Field(..., gt=0, description="Outer length (Y) in mm")
    height: float = Field(..., gt=0, description="Outer height (Z) in mm")
    outer_wall: float = Field(default=2.0, gt=0, description="Wall thickness (mm)")
    rib_thickness: float = Field(default=1.6, gt=0, description="Internal rib thickness (mm)")
    floor_thickness: float = Field(default=1.2, gt=0, description="Floor thickness (mm)")
    fillet_radius: float = Field(
        default=1.0, ge=0, description="Corner fillet radius for rectangular cavities (mm)"
    )
    outer_fillet_upper: float = Field(
        default=0.0, ge=0, description="Fillet radius for outer upper (top) horizontal edges (mm)"
    )
    outer_fillet_lower: float = Field(
        default=0.0, ge=0, description="Fillet radius for outer lower (bottom) horizontal edges (mm)"
    )
    cavity_fillet_top: float = Field(
        default=0.0, ge=0, description="Default fillet radius for cavity top opening edges (mm)"
    )
    templates: list[CavityTemplate] = Field(
        default_factory=list, description="Named cavity presets available for CavityRef lookups"
    )
    cavities: list[CavityEntry] = Field(  # type: ignore[valid-type]
        default_factory=list, description="Ordered list of cavity specs or template references"
    )

    @model_validator(mode="after")
    def _resolve_refs(self) -> "ContainerConfig":
        """Validate that every CavityRef names an existing template."""
        template_map: dict[str, CavityTemplate] = {t.name: t for t in self.templates}
        for entry in self.cavities:
            if isinstance(entry, CavityRef):
                if entry.template not in template_map:
                    raise ValueError(
                        f"CavityRef references unknown template '{entry.template}'. "
                        f"Available: {list(template_map.keys())}"
                    )
        return self

    def resolve_cavity(self, ref: CavityRef) -> CavitySpec:
        """Resolve a :class:`CavityRef` to a concrete :class:`CavitySpec`.

        Args:
            ref: The reference to resolve.

        Returns:
            A :class:`CavitySpec` with fields taken from the named template,
            overridden by any non-``None`` values on the ref.

        Raises:
            KeyError: If the referenced template does not exist.
        """
        template_map: dict[str, CavityTemplate] = {t.name: t for t in self.templates}
        tmpl = template_map[ref.template]
        return CavitySpec(
            shape=tmpl.shape,
            width=tmpl.width,
            length=tmpl.length,
            diameter=tmpl.diameter,
            depth=ref.depth if ref.depth is not None else tmpl.depth,
            fillet_top=ref.fillet_top if ref.fillet_top is not None else tmpl.fillet_top,
            count=ref.count,
            grid=ref.grid,
        )


# ---------------------------------------------------------------------------
# Packer output models
# ---------------------------------------------------------------------------


class PlacedCavity(BaseModel):
    """A cavity that has been assigned a position by the bin packer.

    Coordinates are in container space (origin = bottom-left of the inner
    floor), measured to the *centre* of the cavity footprint.
    """

    x: float = Field(..., description="Centre X position within the container (mm)")
    y: float = Field(..., description="Centre Y position within the container (mm)")
    spec: CavitySpec = Field(..., description="Fully resolved cavity geometry")


class PackingResult(BaseModel):
    """Complete output produced by the bin packer.

    ``utilization`` is the ratio of cavity floor area to total inner floor
    area (0 – 1).  Values near 1 indicate a very dense layout.
    """

    placements: list[PlacedCavity] = Field(
        default_factory=list, description="All cavities with their assigned positions"
    )
    container_width: float = Field(..., gt=0, description="Inner usable width (mm)")
    container_length: float = Field(..., gt=0, description="Inner usable length (mm)")
    utilization: float = Field(
        ..., ge=0, le=1, description="Fraction of inner floor area occupied by cavities (0–1)"
    )
