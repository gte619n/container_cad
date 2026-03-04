# cadbox

Parametric CAD container generator for 3D printing. Define your container layout in JSON — cadbox packs the cavities, validates FDM printability, and outputs STEP/STL files ready for slicing.

![Python 3.10+](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **JSON-driven**: Define containers, cavities, and templates in a simple config file
- **Auto-packing**: Bin-packing via rectpack arranges cavities with guaranteed rib gaps
- **FDM validation**: Checks wall thickness, rib width, floor thickness, and fillet radii against 0.4mm nozzle constraints
- **Filleted pockets**: Smooth internal corner fillets on all cavity pockets for better printability
- **STEP + STL export**: Import directly into Bambu Studio, Fusion 360, PrusaSlicer, or any CAD/slicer
- **Browser preview**: Built-in Three.js viewer for instant 3D preview over localhost
- **Templates**: Named reusable cavity presets with per-reference overrides
- **Grid layouts**: Arrange cavity copies in rows/columns automatically

## Installation

### Requirements

- **Python 3.10–3.13** (3.14 is NOT supported — CadQuery lacks wheels)
- pip

### Install from source

```bash
git clone git@github.com:gte619n/container_cad.git
cd container_cad

python3.13 -m venv .venv
source .venv/bin/activate

pip install -e .
```

For development (includes pytest):

```bash
pip install -e ".[dev]"
```

### Verify installation

```bash
cadbox --help
```

## Quick Start

### 1. Create a config file

```json
{
  "width": 100,
  "length": 80,
  "height": 25,
  "outer_wall": 2.0,
  "rib_thickness": 1.6,
  "floor_thickness": 1.2,
  "fillet_radius": 1.0,
  "cavities": [
    {"shape": "rect", "width": 30, "length": 20, "depth": 20},
    {"shape": "circle", "diameter": 25, "depth": 20},
    {"shape": "rect", "width": 20, "length": 15, "depth": 15, "count": 2},
    {"shape": "circle", "diameter": 12, "depth": 10, "count": 3}
  ]
}
```

### 2. Generate

```bash
cadbox generate config.json -o container.step -v
```

### 3. Preview in browser

```bash
cadbox generate config.json -o container.step --preview -v
```

Or preview an existing file:

```bash
cadbox preview container.stl
```

## CLI Reference

### `cadbox generate`

Generate a container from a JSON config file.

```
cadbox generate CONFIG_FILE [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output PATH` | `output.step` | Output file path (`.step`, `.stp`, or `.stl`) |
| `--preview / --no-preview` | `--no-preview` | Launch 3D browser preview after generation |
| `--validate-only` | off | Run validation only; skip geometry generation |
| `-v, --verbose` | off | Print packing and generation details |

Shorthand (omit `generate`):

```bash
cadbox config.json -o output.step
```

### `cadbox preview`

Launch the 3D viewer for an existing STEP or STL file.

```
cadbox preview MODEL_FILE [--port 8123]
```

## Config Reference

### Container (top-level)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `width` | float | yes | — | Outer width, X axis (mm) |
| `length` | float | yes | — | Outer length, Y axis (mm) |
| `height` | float | yes | — | Outer height, Z axis (mm) |
| `outer_wall` | float | no | 2.0 | Wall thickness (mm) |
| `rib_thickness` | float | no | 1.6 | Minimum gap between adjacent cavities (mm) |
| `floor_thickness` | float | no | 1.2 | Floor thickness (mm) |
| `fillet_radius` | float | no | 1.0 | Corner fillet radius for outer edges and cavity pockets (mm) |
| `templates` | array | no | [] | Named cavity presets (see below) |
| `cavities` | array | yes | — | List of cavity specs or template references |

### Cavity Spec (inline)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `shape` | `"rect"` or `"circle"` | yes | Cross-section shape |
| `width` | float | rect only | X dimension (mm) |
| `length` | float | rect only | Y dimension (mm) |
| `diameter` | float | circle only | Diameter (mm) |
| `depth` | float | yes | Pocket depth from top surface (mm) |
| `count` | int | no (default 1) | Number of copies to place |
| `grid` | `[cols, rows]` | no | Arrange copies in a grid (mutually exclusive with `count`) |

### Cavity Template

Define reusable presets in the `templates` array:

```json
{
  "templates": [
    {"name": "sd_card", "shape": "rect", "width": 24, "length": 32, "depth": 3},
    {"name": "coin_cell", "shape": "circle", "diameter": 20, "depth": 4}
  ],
  "cavities": [
    {"template": "sd_card", "grid": [3, 2]},
    {"template": "coin_cell", "count": 4},
    {"template": "sd_card", "depth": 10, "count": 1}
  ]
}
```

Template references support overriding `depth`, `count`, and `grid`.

## FDM Validation Constraints

cadbox validates your config against 0.4mm nozzle FDM printing constraints:

| Constraint | Minimum | Description |
|------------|---------|-------------|
| Wall thickness | 1.2 mm | 3x nozzle diameter |
| Rib thickness | 1.2 mm | 3x nozzle diameter |
| Floor thickness | 0.8 mm | 2x nozzle diameter |
| Fillet radius | 0.5 mm | Smallest printable fillet |
| Cavity dimension | 2.0 mm | Smallest printable pocket |

Post-packing validation also checks that rib gaps between placed cavities meet the minimum.

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

**Data flow:**

```
JSON config
  → config.py (parse + validate schema)
  → validator.py (check FDM printability)
  → packer.py (bin-pack cavities via rectpack)
  → validator.py (check placement gaps)
  → generator.py (CadQuery solid modeling)
  → STEP/STL export
```

### Key Design Decisions

- **Solid block with pocket cuts**: The container starts as a solid block. Each cavity is cut from the top as an individual pocket. Material between pockets forms the ribs naturally.
- **Integer-scaled packing**: rectpack requires integers, so all dimensions are multiplied by 100 (0.01mm resolution) and converted back after packing.
- **Padded bounding boxes**: Each cavity is enlarged by `rib_thickness` before packing, guaranteeing minimum rib gaps between adjacent cavities.
- **Pocket fillets**: All cavity pockets get filleted bottom edges for printability. The fillet radius is clamped to avoid OCCT kernel errors.
- **No rotation**: The bin-packer does not rotate rectangles — the user controls cavity orientation.

## Examples

Two example configs are included:

- **`examples/simple_config.json`** — 100x80x25mm box with mixed rect/circle cavities
- **`examples/sample_config.json`** — 200x150x40mm organizer with templates (SD cards, coin cells, batteries, USB dongles)

```bash
# Simple container
cadbox generate examples/simple_config.json -o simple.step --preview -v

# Complex organizer
cadbox generate examples/sample_config.json -o organizer.step --preview -v
```

## Running Tests

```bash
pytest
pytest -v                          # verbose
pytest tests/test_cadbox.py -v     # single file
pytest -k "test_packer" -v         # by name pattern
```

## Dependencies

| Package | Purpose |
|---------|---------|
| [CadQuery](https://cadquery.readthedocs.io/) | OCCT-based solid modeling |
| [rectpack](https://github.com/secnot/rectpack) | Rectangle bin-packing |
| [Pydantic](https://docs.pydantic.dev/) v2 | Config validation |
| [Click](https://click.palletsprojects.com/) | CLI framework |

Preview uses Three.js r158 loaded from CDN (no additional Python dependencies).

## License

MIT
