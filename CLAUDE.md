# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**cadbox** is a Python CLI tool that generates parametric CAD container boxes with inset cavities for 3D printing. It uses CadQuery (OCCT kernel) to produce STEP files importable into Bambu Studio and Fusion 360.

## Build & Run Commands

```bash
# Setup (requires Python 3.10-3.13, NOT 3.14 — CadQuery lacks wheels)
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Generate a container from JSON config
cadbox generate examples/simple_config.json -o output.step -v
cadbox examples/simple_config.json -o output.step    # shorthand

# Validate config without generating
cadbox generate examples/simple_config.json --validate-only

# Generate with browser preview
cadbox generate examples/simple_config.json -o output.step --preview

# Preview existing file
cadbox preview output.stl

# Run tests
pytest
pytest tests/test_models.py -v         # single file
pytest -k "test_packer" -v             # by name pattern
```

## Architecture

```
src/cadbox/
├── models.py        # Pydantic v2 data models (ContainerConfig, CavitySpec, etc.)
├── config.py        # JSON config loader with error handling
├── validator.py     # FDM printability validation (0.4mm nozzle constraints)
├── packer.py        # Bin-packing via rectpack (integer-scaled coordinates)
├── generator.py     # CadQuery solid modeling (box shell + cavity cutting)
├── cli.py           # Click CLI entry point
└── preview/
    └── server.py    # Embedded Three.js STL viewer over localhost HTTP
```

**Data flow:** JSON config → `config.py` parses → `validator.py` checks printability → `packer.py` arranges cavities (rectpack) → `validator.py` checks placement gaps → `generator.py` builds CadQuery solid → STEP/STL export

## Key Design Decisions

- **Coordinate systems**: Packer outputs bottom-left origin coords (0,0 = inner floor corner). Generator converts to CadQuery XY-centered coords by subtracting `inner_w/2, inner_l/2`.
- **Integer scaling**: Packer multiplies all dimensions by 100 (0.01mm resolution) for rectpack's integer-only API, converts back on output.
- **Cavity padding**: Each cavity's bounding box is enlarged by `rib_thickness` before packing. This guarantees minimum rib gap between adjacent cavities.
- **Fixed orientation**: Bin-packer does not rotate rectangles (user controls orientation).
- **CavitySpec vs CavityRef**: Cavities can be inline specs or references to named templates. `ContainerConfig.resolve_cavity()` expands refs. `count` and `grid` are expanded to individual placements in the packer.
- **Discriminated union**: `CavityEntry = Union[CavitySpec, CavityRef]` uses Pydantic's `union_mode="left_to_right"` — CavitySpec is tried first (has `shape` field), CavityRef second (has `template` field).

## Finger Pulls

Configurable finger pull scoops on cavity edges for grip access. Controlled by:
- `finger_pull_radius` (float, default 0 = disabled): Scoop radius in mm. Also defines vertical depth (clamped to cavity depth).
- `finger_pull_width_pct` (float, default 0.5): Scoop length as fraction of cavity's wide dimension.
- Per-cavity `finger_pull` (Optional[bool]): Override global. None = follow global, False = disable.

Scoops are half-cylinders placed on both sides of the cavity's narrow dimension, offset `rib_thickness/2` into the rib. They scallop into both the cavity opening and the rib/wall, cutting through to exterior on outer walls. Circular cavities get scoops on +Y/-Y. Adjacent scoops merge naturally via CSG overlap.

## Validation Constants (0.4mm nozzle)

Defined in `validator.py`: MIN_WALL=1.2mm, MIN_RIB=1.2mm, MIN_FLOOR=0.8mm, MIN_FILLET=0.5mm, MIN_CAVITY=2.0mm, MIN_FINGER_PULL_RADIUS=3.0mm. Post-packing validation uses 0.01mm float tolerance.

## Dependencies

- **cadquery** (OCCT kernel) — requires conda-forge OR Python ≤3.13 for pip wheels. Python 3.14 does NOT work.
- **rectpack** — rectangle bin-packing algorithms
- **pydantic** v2 — config validation
- **click** — CLI framework
- Preview uses Three.js r158 from CDN (no Python deps)
