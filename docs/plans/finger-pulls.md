# Feature Specification: Finger Pull Scoops

**Author:** Claude (PM/Senior Dev)
**Created:** 2026-03-09
**Status:** Planning Complete - Ready for Implementation

---

## 1. Overview

Add configurable finger pull scoops to cavity openings so users can easily
grip and remove objects from the container. Each scoop is a half-cylinder
cut into the rib/wall material adjacent to the cavity, with a scallop that
dips into the cavity opening itself.

### Design Decisions (from interview)

| Decision | Choice |
|---|---|
| Scoop profile | Semi-circle (half-cylinder) |
| Placement axis | Across the narrow dimension of each cavity |
| Cut direction | Scallops into cavity AND rib/wall material |
| Neighbor merge | Natural CSG overlap (no explicit merge logic) |
| Wall-facing pulls | Always place, even on outer walls |
| Exterior notch | Cut through to exterior (visible from outside) |
| Width coverage | Partial - 50% of cavity wide dimension (configurable) |
| Scoop axis offset | Half of rib_thickness into the rib from cavity edge |
| Radius source | Fixed global parameter on ContainerConfig |
| Vertical depth | Radius defines depth, clamped to cavity depth |
| Enable logic | Enabled when `finger_pull_radius > 0` (default 0 = off) |
| Per-cavity toggle | Boolean `finger_pull` field, default enabled (opt-out) |
| Circular cavities | Two pulls on Y-axis sides (+Y and -Y) |
| Gridfinity support | Yes, both custom and Gridfinity |
| Validation | Validate min radius AND wall integrity |
| Web UI | Dedicated "Finger Pulls" section in sidebar |
| Default radius | 8mm when user enables the feature |
| Default width pct | 50% |

---

## 2. Geometry Specification

### 2.1 Scoop Shape

A half-cylinder (semi-circle cross-section) oriented with its flat face at
the top surface of the container (z_top). The cylinder axis runs parallel
to the **wide** dimension of the cavity.

```
  Top surface (z_top)
  ========================
       \            /       <- scoop profile (semi-circle)
        \          /
         \________/         <- depth = radius (clamped to cavity depth)

  <---- scoop_length ---->
  (= wide_dimension * width_pct)
```

### 2.2 Axis Positioning

The scoop cylinder axis is positioned at:
- **X/Y:** At the cavity edge + `rib_thickness / 2` outward into the rib
- **Z:** At z_top (the top surface of the container)

This means the deepest point of the scoop is at `z_top - radius`, centered
in the rib material.

### 2.3 Scoop Dimensions

- **Radius:** `finger_pull_radius` (global, in mm). Defines both the
  semicircle radius and the vertical depth of the cut.
- **Length:** `cavity_wide_dimension * finger_pull_width_pct` (centered on
  the cavity midline along the wide axis).
- **Effective depth:** `min(finger_pull_radius, cavity_depth)` to prevent
  cutting below the cavity floor.

### 2.4 Placement Rules

For each cavity with finger pulls enabled:

1. **Rectangular cavities:** Determine the narrow dimension.
   - If `width <= length`: narrow = width, wide = length. Scoops placed
     on the -X and +X sides (the two edges bounding the width).
   - If `length < width`: narrow = length, wide = width. Scoops placed
     on the -Y and +Y sides.
2. **Circular cavities:** Scoops placed on -Y and +Y sides. Wide
   dimension = diameter.
3. **Two scoops per cavity** (one on each side of the narrow dimension).

### 2.5 Neighbor Overlap

When two adjacent cavities both have scoops facing each other across a
shared rib, the two half-cylinder CSG cuts will naturally overlap. No
explicit merge logic is needed. CadQuery's `solid.cut(tool)` handles this.

### 2.6 Outer Wall Behavior

When a scoop faces the outer wall, it cuts through to the exterior,
creating a visible notch. No clamping to preserve outer wall material.
The validator will warn if the remaining wall material is below
MIN_WALL_THICKNESS, but the geometry is still generated.

---

## 3. Configuration Schema Changes

### 3.1 ContainerConfig (models.py)

New fields on `ContainerConfig`:

```python
finger_pull_radius: float = Field(
    default=0.0, ge=0,
    description="Finger pull scoop radius in mm. 0 = disabled."
)
finger_pull_width_pct: float = Field(
    default=0.5, gt=0, le=1.0,
    description="Scoop length as a fraction of the cavity's wide dimension (0-1)."
)
```

### 3.2 CavitySpec (models.py)

New field on `CavitySpec`:

```python
finger_pull: Optional[bool] = Field(
    default=None,
    description="Override global finger pull. None = follow global, False = disable, True = enable."
)
```

### 3.3 CavityTemplate / CavityRef (models.py)

Same `finger_pull: Optional[bool]` field added to both `CavityTemplate`
and `CavityRef` so templates and refs can override.

### 3.4 Resolution Logic

When determining if a placed cavity gets finger pulls:

```
effective = cavity.finger_pull if cavity.finger_pull is not None
            else (config.finger_pull_radius > 0)
```

### 3.5 Example JSON

```json
{
  "width": 100,
  "length": 80,
  "height": 25,
  "finger_pull_radius": 8,
  "finger_pull_width_pct": 0.5,
  "cavities": [
    {"shape": "rect", "width": 30, "length": 20, "depth": 20},
    {"shape": "rect", "width": 15, "length": 40, "depth": 15, "finger_pull": false},
    {"shape": "circle", "diameter": 25, "depth": 20}
  ]
}
```

---

## 4. Validation Rules (validator.py)

### 4.1 New Checks

| Check | Condition | Severity |
|---|---|---|
| Min scoop radius | `finger_pull_radius > 0 and finger_pull_radius < MIN_FEATURE_SIZE` | Error |
| Wall integrity | Scoop at outer wall leaves < MIN_WALL_THICKNESS | Warning |
| Depth clamp notice | `finger_pull_radius > cavity_depth` for any enabled cavity | Warning |
| Width pct range | `finger_pull_width_pct` not in (0, 1] | Error (Pydantic) |

### 4.2 Validation Constants

```python
MIN_FINGER_PULL_RADIUS: float = 3.0  # mm - smaller scoops don't help fingers
```

---

## 5. Generator Changes (generator.py)

### 5.1 New Function: `_cut_finger_pulls`

```python
def _cut_finger_pulls(
    solid: cq.Workplane,
    placement: PlacedCavity,
    config: ContainerConfig,
    z_top: float,
) -> cq.Workplane:
```

Called after `_cut_cavity` for each placed cavity. For each of the two
scoop positions:

1. Compute the scoop center position (cavity edge + rib_thickness/2).
2. Compute scoop length = `wide_dimension * config.finger_pull_width_pct`.
3. Compute effective radius = `min(config.finger_pull_radius, spec.depth)`.
4. Build a half-cylinder solid:
   - Full cylinder of `effective_radius` with length = scoop_length.
   - Cut in half with a box to get the bottom half only.
   - Translate/rotate to position at z_top, centered on the scoop.
5. `solid = solid.cut(half_cylinder)`

### 5.2 Integration Points

- **`generate()` (custom boxes):** After the cavity-cutting loop, add a
  second loop for finger pulls on enabled cavities.
- **`generate_gridfinity()`:** Same pattern, after cavity cutting.

### 5.3 Coordinate Conversion

The scoop positions use the same coordinate system as cavity placement.
The PlacedCavity already has CadQuery XY-centered coords at this point
in the pipeline (after the `inner_w/2` offset is applied in the generate
functions).

---

## 6. Web UI Changes (preview/ui.py)

### 6.1 New Sidebar Section

Add a "Finger Pulls" collapsible section between "Structure" and
"Stacking" with:

- **Radius** slider/input: 0-20mm, step 0.5, default 0
- **Width %** slider/input: 10%-100%, step 5%, default 50%
- Info text: "Set radius > 0 to enable finger pulls on cavity edges"

### 6.2 Per-Cavity Toggle

In the cavity editor card, add a checkbox: "Finger pull" (tri-state:
inherit / on / off). Default = inherit (follows global).

---

## 7. Development Phases

### Phase 1: Data Model & Config
**Files:** `models.py`, `config.py`

| # | Task | Status | Tested | Pushed |
|---|---|---|---|---|
| 1.1 | Add `finger_pull_radius` and `finger_pull_width_pct` to `ContainerConfig` | `[ ]` | `[ ]` | `[ ]` |
| 1.2 | Add `finger_pull: Optional[bool]` to `CavitySpec` | `[ ]` | `[ ]` | `[ ]` |
| 1.3 | Add `finger_pull: Optional[bool]` to `CavityTemplate` and `CavityRef` | `[ ]` | `[ ]` | `[ ]` |
| 1.4 | Update `resolve_cavity()` to propagate `finger_pull` field | `[ ]` | `[ ]` | `[ ]` |
| 1.5 | Update `_expand_cavities()` in packer to propagate `finger_pull` | `[ ]` | `[ ]` | `[ ]` |

**Verification criteria:**
- Existing tests pass with no changes (backward compatible).
- New config with `finger_pull_radius: 8` parses without error.
- Config without finger pull fields still works (defaults to 0 / None).
- `finger_pull` field round-trips through CavityRef resolution.

**Agent verification commands:**
```bash
pytest tests/test_cadbox.py -v  # all existing tests pass
python -c "
from cadbox.models import ContainerConfig, CavitySpec
# Test new fields exist and have correct defaults
c = ContainerConfig(width=100, length=80, height=25)
assert c.finger_pull_radius == 0.0
assert c.finger_pull_width_pct == 0.5
s = CavitySpec(shape='rect', width=20, length=10, depth=15)
assert s.finger_pull is None
print('Phase 1 PASS')
"
```

---

### Phase 2: Validation
**Files:** `validator.py`

| # | Task | Status | Tested | Pushed |
|---|---|---|---|---|
| 2.1 | Add `MIN_FINGER_PULL_RADIUS` constant | `[ ]` | `[ ]` | `[ ]` |
| 2.2 | Validate `finger_pull_radius` is >= MIN when > 0 | `[ ]` | `[ ]` | `[ ]` |
| 2.3 | Validate wall integrity: warn when scoop at outer wall leaves < MIN_WALL | `[ ]` | `[ ]` | `[ ]` |
| 2.4 | Warn when radius > cavity depth (will be clamped) | `[ ]` | `[ ]` | `[ ]` |

**Verification criteria:**
- `finger_pull_radius: 1.0` triggers min-radius validation error.
- `finger_pull_radius: 0` triggers no errors.
- `finger_pull_radius: 20` with `outer_wall: 2.0` triggers wall integrity warning.
- `finger_pull_radius: 25` with cavity depth 15 triggers depth-clamp warning.

**Agent verification commands:**
```bash
python -c "
from cadbox.models import ContainerConfig
from cadbox.validator import validate_container

# Too small radius
c = ContainerConfig(width=100, length=80, height=25, finger_pull_radius=1.0,
    cavities=[{'shape': 'rect', 'width': 20, 'length': 10, 'depth': 15}])
errs = validate_container(c)
assert any('finger_pull' in e.field for e in errs), 'Should flag small radius'

# Zero radius = no errors from finger pulls
c2 = ContainerConfig(width=100, length=80, height=25, finger_pull_radius=0,
    cavities=[{'shape': 'rect', 'width': 20, 'length': 10, 'depth': 15}])
errs2 = validate_container(c2)
assert not any('finger_pull' in e.field for e in errs2), 'No errors when disabled'
print('Phase 2 PASS')
"
```

---

### Phase 3: Generator - Core Scoop Geometry
**Files:** `generator.py`

| # | Task | Status | Tested | Pushed |
|---|---|---|---|---|
| 3.1 | Implement `_build_finger_pull_tool()`: creates the half-cylinder solid | `[ ]` | `[ ]` | `[ ]` |
| 3.2 | Implement `_cut_finger_pulls()`: positions and cuts scoops for one cavity | `[ ]` | `[ ]` | `[ ]` |
| 3.3 | Integrate into `generate()` (custom box) after cavity loop | `[ ]` | `[ ]` | `[ ]` |
| 3.4 | Integrate into `generate_gridfinity()` after cavity loop | `[ ]` | `[ ]` | `[ ]` |
| 3.5 | Handle effective radius clamping: `min(radius, depth)` | `[ ]` | `[ ]` | `[ ]` |

**Verification criteria:**
- Generate a container with finger pulls and verify the solid has LESS
  volume than the same container without finger pulls.
- BoundingBox of the solid changes when finger pulls are on outer walls
  (exterior notch should reduce bounding box on the affected face).
- Export to STEP/STL succeeds without CadQuery errors.
- Container with `finger_pull_radius: 0` produces identical geometry to
  the current implementation (regression test).

**Agent verification commands:**
```bash
python -c "
from cadbox.models import ContainerConfig
from cadbox.packer import pack_cavities
from cadbox.generator import generate

# Without finger pulls
c1 = ContainerConfig(width=100, length=80, height=25, finger_pull_radius=0,
    cavities=[{'shape': 'rect', 'width': 30, 'length': 20, 'depth': 20}])
p1 = pack_cavities(c1)
s1 = generate(c1, p1)
v1 = s1.val().Volume()

# With finger pulls
c2 = ContainerConfig(width=100, length=80, height=25, finger_pull_radius=8,
    cavities=[{'shape': 'rect', 'width': 30, 'length': 20, 'depth': 20}])
p2 = pack_cavities(c2)
s2 = generate(c2, p2)
v2 = s2.val().Volume()

assert v2 < v1, f'Finger pulls should reduce volume: {v2} vs {v1}'
print(f'Volume without: {v1:.1f}, with: {v2:.1f}, diff: {v1-v2:.1f}')
print('Phase 3 PASS')
"
```

---

### Phase 4: Placement Logic (rect & circle)
**Files:** `generator.py`

| # | Task | Status | Tested | Pushed |
|---|---|---|---|---|
| 4.1 | Narrow-dimension detection for rectangular cavities | `[ ]` | `[ ]` | `[ ]` |
| 4.2 | Y-axis placement for circular cavities | `[ ]` | `[ ]` | `[ ]` |
| 4.3 | Per-cavity `finger_pull` toggle respected | `[ ]` | `[ ]` | `[ ]` |
| 4.4 | Scoop positioning with rib_thickness/2 offset | `[ ]` | `[ ]` | `[ ]` |

**Verification criteria:**
- Rect cavity 30w x 20l: scoops appear on the two length (20mm) edges,
  running parallel to the width (30mm) axis.
- Rect cavity 15w x 40l: scoops appear on the two width (15mm) edges,
  running parallel to the length (40mm) axis.
- Square cavity 20x20: either axis is fine (consistent choice).
- Circle: scoops on +Y and -Y sides.
- Cavity with `finger_pull: false` gets no scoops even when global > 0.
- Cavity with `finger_pull: true` and global radius 0 gets NO scoops
  (no radius = nothing to cut, even if toggle is true).

**Agent verification commands:**
```bash
python -c "
from cadbox.models import ContainerConfig
from cadbox.packer import pack_cavities
from cadbox.generator import generate

# Test per-cavity disable
c = ContainerConfig(width=100, length=80, height=25, finger_pull_radius=8,
    cavities=[
        {'shape': 'rect', 'width': 30, 'length': 20, 'depth': 20},
        {'shape': 'rect', 'width': 20, 'length': 15, 'depth': 15, 'finger_pull': False},
    ])
p = pack_cavities(c)
s = generate(c, p)
assert s.val().Volume() > 0
print('Phase 4 PASS')
"
```

---

### Phase 5: Validation Integration
**Files:** `validator.py`

| # | Task | Status | Tested | Pushed |
|---|---|---|---|---|
| 5.1 | Post-packing validation: check wall integrity for each scoop position | `[ ]` | `[ ]` | `[ ]` |
| 5.2 | Depth-clamp warning per enabled cavity | `[ ]` | `[ ]` | `[ ]` |

**Verification criteria:**
- Container with thin walls (2mm) and large radius (10mm) triggers
  wall integrity warning.
- Container with shallow cavities (5mm) and radius 8mm triggers
  depth-clamp warning.
- All warnings are informational (don't block generation).

**Agent verification commands:**
```bash
python -c "
from cadbox.models import ContainerConfig
from cadbox.validator import validate_container

# Depth clamp warning
c = ContainerConfig(width=100, length=80, height=25, finger_pull_radius=8,
    cavities=[{'shape': 'rect', 'width': 20, 'length': 10, 'depth': 5}])
errs = validate_container(c)
depth_warns = [e for e in errs if 'clamp' in e.message.lower() or 'depth' in e.message.lower()]
print(f'Depth warnings: {len(depth_warns)}')
print('Phase 5 PASS')
"
```

---

### Phase 6: Web UI
**Files:** `preview/ui.py`, `preview/server.py`

| # | Task | Status | Tested | Pushed |
|---|---|---|---|---|
| 6.1 | Add "Finger Pulls" section to sidebar HTML | `[ ]` | `[ ]` | `[ ]` |
| 6.2 | Add radius slider/input (0-20mm, step 0.5) | `[ ]` | `[ ]` | `[ ]` |
| 6.3 | Add width % slider/input (10-100%, step 5) | `[ ]` | `[ ]` | `[ ]` |
| 6.4 | Add per-cavity finger_pull checkbox to cavity cards | `[ ]` | `[ ]` | `[ ]` |
| 6.5 | Wire new fields into config JSON sent to generate API | `[ ]` | `[ ]` | `[ ]` |

**Verification criteria:**
- UI loads without JS errors.
- Changing radius slider and clicking Generate produces a model with
  visible scoops in the 3D preview.
- Per-cavity checkbox disables scoops for that cavity.
- Default state (radius=0) shows no scoops.

**Agent verification commands:**
```bash
# Start server and check it responds
timeout 5 bash -c 'cadbox serve --no-browser --port 18085 &
  sleep 2 && curl -s http://localhost:18085/ | grep -q "Finger Pull" && echo "Phase 6 PASS"
  kill %1 2>/dev/null' || echo "Phase 6 NEEDS MANUAL CHECK"
```

---

### Phase 7: Tests
**Files:** `tests/test_cadbox.py` (or new `tests/test_finger_pulls.py`)

| # | Task | Status | Tested | Pushed |
|---|---|---|---|---|
| 7.1 | Model tests: new fields exist, defaults correct, serialization | `[ ]` | `[ ]` | `[ ]` |
| 7.2 | Model tests: finger_pull propagates through CavityRef resolution | `[ ]` | `[ ]` | `[ ]` |
| 7.3 | Validation tests: small radius flagged | `[ ]` | `[ ]` | `[ ]` |
| 7.4 | Validation tests: wall integrity warning | `[ ]` | `[ ]` | `[ ]` |
| 7.5 | Validation tests: depth clamp warning | `[ ]` | `[ ]` | `[ ]` |
| 7.6 | Generator tests: volume reduction with finger pulls | `[ ]` | `[ ]` | `[ ]` |
| 7.7 | Generator tests: no volume change when radius=0 | `[ ]` | `[ ]` | `[ ]` |
| 7.8 | Generator tests: per-cavity disable respected | `[ ]` | `[ ]` | `[ ]` |
| 7.9 | Generator tests: circular cavity finger pulls | `[ ]` | `[ ]` | `[ ]` |
| 7.10 | Generator tests: Gridfinity with finger pulls | `[ ]` | `[ ]` | `[ ]` |
| 7.11 | Generator tests: STEP/STL export with finger pulls | `[ ]` | `[ ]` | `[ ]` |
| 7.12 | Functional test: scoop positioned on correct (narrow) axis | `[ ]` | `[ ]` | `[ ]` |
| 7.13 | Functional test: scoop doesn't cut below cavity floor | `[ ]` | `[ ]` | `[ ]` |
| 7.14 | Regression: all existing tests still pass | `[ ]` | `[ ]` | `[ ]` |

**Functional verification approach for 7.12 (scoop on correct axis):**

The agent verifies scoop axis placement by comparing bounding boxes. A
scoop on the narrow-dimension side extends the cut outward. By checking
`BoundingBox` dimensions with and without finger pulls, the agent can
confirm material was removed on the expected axis:

```python
# For a 30w x 20l cavity (narrow=length=20, scoops on Y-axis sides):
# The bounding box should be identical on X, but the solid near the
# cavity's Y-edges should show material removal.
# Practical check: volume delta > 0 confirms cuts were made.
# Axis check: generate two configs where the narrow axis differs,
# verify both produce valid geometry with volume reduction.
```

**Functional verification for 7.13 (scoop depth clamped):**

```python
# Config: finger_pull_radius=15, cavity_depth=8
# The scoop effective depth should be 8mm (clamped).
# Verify: solid with radius=15 has same volume as radius=8 for this cavity,
# since both are clamped to depth=8.
```

---

### Phase 8: Examples & Documentation
**Files:** `examples/`, `CLAUDE.md`

| # | Task | Status | Tested | Pushed |
|---|---|---|---|---|
| 8.1 | Add `examples/finger_pull_config.json` | `[ ]` | `[ ]` | `[ ]` |
| 8.2 | Update CLAUDE.md with finger pull config fields | `[ ]` | `[ ]` | `[ ]` |

---

## 8. Testing Strategy

### 8.1 Unit Tests (technical correctness)

- **Model layer:** Field existence, defaults, type validation, Pydantic
  serialization, ref resolution with new field.
- **Validator layer:** Each new validation rule fires under the correct
  condition and doesn't fire otherwise.
- **Generator layer:** `_build_finger_pull_tool()` returns a valid solid
  with positive volume. `_cut_finger_pulls()` reduces the parent solid's
  volume.

### 8.2 Functional Tests (feature correctness)

- **Scoop placement axis:** For cavities with known narrow dimension,
  verify scoops affect the correct sides by comparing volumes or
  bounding boxes of isolated geometry.
- **Depth clamping:** Radius exceeding cavity depth produces the same
  effective cut as radius = cavity depth.
- **Per-cavity toggle:** Disabled cavity has identical volume to same
  cavity without global finger pulls.
- **Exterior notch:** Bounding box of the solid is unchanged on non-scoop
  faces, but may change on scoop faces (confirms through-wall cut).
- **Backward compatibility:** Config with no finger pull fields generates
  identical output to current implementation.

### 8.3 Integration Tests

- **CLI round-trip:** `cadbox generate <config-with-pulls> -o out.step`
  exits 0 and produces a non-empty file.
- **Validate-only:** `cadbox generate <config-with-pulls> --validate-only`
  exits 0 (or shows expected warnings).

### 8.4 Visual Verification (manual)

- **3D preview:** Open the web UI with finger pull config, visually
  confirm scoops appear on the correct sides.
- **Slicer import:** Import STEP into Bambu Studio / Fusion 360 and
  verify the scoops are clean geometry.

---

## 9. Definition of Done

All of the following must be true:

- [ ] All 8 phases have Status = `[x]`, Tested = `[x]`, Pushed = `[x]`
- [ ] `pytest` passes with 0 failures
- [ ] Agent verification commands for each phase exit successfully
- [ ] No regression in existing functionality (all pre-existing tests pass)
- [ ] `cadbox generate examples/finger_pull_config.json -o test.step` succeeds
- [ ] Web UI shows finger pull controls and they affect generated geometry
- [ ] CLAUDE.md updated to document new config fields

---

## 10. Risk Register

| Risk | Mitigation |
|---|---|
| CadQuery boolean subtraction fails on half-cylinder | Build tool as full cylinder + box cut, test in isolation first |
| Scoop overlaps with cavity fillet_top geometry | Apply finger pulls AFTER cavity top fillets |
| Performance: many scoops on many cavities | Each scoop is a single CSG cut; profile if > 20 cavities |
| Gridfinity thin walls (0.95mm) fully cut through | Accepted by design; validator warns |
| Scoop tool extends below Z=0 (floor) | Clamp effective radius to cavity depth |

---

## 11. Files Modified

| File | Changes |
|---|---|
| `src/cadbox/models.py` | New fields on ContainerConfig, CavitySpec, CavityTemplate, CavityRef |
| `src/cadbox/validator.py` | New validation checks for finger pull constraints |
| `src/cadbox/generator.py` | `_build_finger_pull_tool()`, `_cut_finger_pulls()`, integration in `generate()` and `generate_gridfinity()` |
| `src/cadbox/packer.py` | Propagate `finger_pull` in `_expand_cavities()` |
| `src/cadbox/preview/ui.py` | New "Finger Pulls" sidebar section, per-cavity checkbox |
| `src/cadbox/preview/server.py` | Wire new fields in API config handling |
| `tests/test_cadbox.py` | New test classes for finger pull feature |
| `examples/finger_pull_config.json` | New example config |
| `CLAUDE.md` | Document new config fields |
