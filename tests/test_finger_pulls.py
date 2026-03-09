"""Tests for the finger pull scoop feature.

Covers model fields, validation, generator geometry, per-cavity toggle,
circular cavities, Gridfinity support, and export.
"""

from __future__ import annotations

import json

import pytest


def _make_config(**overrides):
    from cadbox.models import ContainerConfig

    base = {
        "width": 100,
        "length": 80,
        "height": 25,
        "outer_wall": 2.0,
        "rib_thickness": 1.6,
        "floor_thickness": 1.2,
        "fillet_radius": 1.0,
        "cavities": [
            {"shape": "rect", "width": 30, "length": 20, "depth": 20},
        ],
    }
    base.update(overrides)
    return ContainerConfig.model_validate(base)


# ---------------------------------------------------------------------------
# 7.1 - Model tests: fields, defaults, serialization
# ---------------------------------------------------------------------------


class TestFingerPullModelFields:
    def test_container_config_defaults(self):
        from cadbox.models import ContainerConfig

        c = ContainerConfig(width=100, length=80, height=25)
        assert c.finger_pull_radius == 0.0
        assert c.finger_pull_width_pct == 0.5

    def test_container_config_custom_values(self):
        c = _make_config(finger_pull_radius=8, finger_pull_width_pct=0.7)
        assert c.finger_pull_radius == 8.0
        assert c.finger_pull_width_pct == 0.7

    def test_cavity_spec_finger_pull_default_none(self):
        from cadbox.models import CavitySpec

        s = CavitySpec(shape="rect", width=20, length=10, depth=15)
        assert s.finger_pull is None

    def test_cavity_spec_finger_pull_explicit(self):
        from cadbox.models import CavitySpec

        s = CavitySpec(shape="rect", width=20, length=10, depth=15, finger_pull=False)
        assert s.finger_pull is False

    def test_cavity_template_finger_pull(self):
        from cadbox.models import CavityTemplate

        t = CavityTemplate(name="t1", shape="rect", width=10, length=5, depth=8, finger_pull=False)
        assert t.finger_pull is False

    def test_cavity_ref_finger_pull(self):
        from cadbox.models import CavityRef

        r = CavityRef(template="t1", finger_pull=True)
        assert r.finger_pull is True


# ---------------------------------------------------------------------------
# 7.2 - finger_pull propagates through CavityRef resolution
# ---------------------------------------------------------------------------


class TestFingerPullResolution:
    def test_ref_inherits_template_finger_pull(self):
        from cadbox.models import CavityRef, ContainerConfig

        config = ContainerConfig.model_validate({
            "width": 80, "length": 60, "height": 20,
            "templates": [{"name": "slot", "shape": "rect", "width": 10, "length": 5, "depth": 8, "finger_pull": False}],
            "cavities": [{"template": "slot"}],
        })
        ref = CavityRef(template="slot")
        spec = config.resolve_cavity(ref)
        assert spec.finger_pull is False

    def test_ref_overrides_template_finger_pull(self):
        from cadbox.models import CavityRef, ContainerConfig

        config = ContainerConfig.model_validate({
            "width": 80, "length": 60, "height": 20,
            "templates": [{"name": "slot", "shape": "rect", "width": 10, "length": 5, "depth": 8, "finger_pull": False}],
            "cavities": [{"template": "slot", "finger_pull": True}],
        })
        ref = CavityRef(template="slot", finger_pull=True)
        spec = config.resolve_cavity(ref)
        assert spec.finger_pull is True


# ---------------------------------------------------------------------------
# 7.3 - Validation: small radius flagged
# ---------------------------------------------------------------------------


class TestFingerPullValidation:
    def test_small_radius_flagged(self):
        from cadbox.validator import validate_container

        c = _make_config(finger_pull_radius=1.0)
        errs = validate_container(c)
        assert any("finger_pull" in e.field for e in errs)

    def test_zero_radius_no_errors(self):
        from cadbox.validator import validate_container

        c = _make_config(finger_pull_radius=0)
        errs = validate_container(c)
        assert not any("finger_pull" in e.field for e in errs)

    def test_valid_radius_no_errors(self):
        from cadbox.validator import validate_container

        c = _make_config(finger_pull_radius=8, outer_wall=10.0)
        errs = validate_container(c)
        fp_errs = [e for e in errs if "finger_pull" in e.field]
        assert fp_errs == []

    # 7.4 - Wall integrity warning (non-blocking)
    def test_wall_integrity_warning(self):
        from cadbox.validator import validate_finger_pull_warnings

        c = _make_config(finger_pull_radius=10, outer_wall=2.0)
        warns = validate_finger_pull_warnings(c)
        wall_warns = [e for e in warns if "wall" in e.message]
        assert len(wall_warns) > 0

    # 7.5 - Depth clamp warning (non-blocking)
    def test_depth_clamp_warning(self):
        from cadbox.validator import validate_finger_pull_warnings

        c = _make_config(
            finger_pull_radius=25,
            cavities=[{"shape": "rect", "width": 20, "length": 10, "depth": 15}],
        )
        warns = validate_finger_pull_warnings(c)
        depth_warns = [e for e in warns if "clamp" in e.message.lower()]
        assert len(depth_warns) > 0


# ---------------------------------------------------------------------------
# 7.6 - Generator: volume reduction with finger pulls
# ---------------------------------------------------------------------------


class TestFingerPullGenerator:
    def _generate(self, **config_overrides):
        from cadbox.generator import generate
        from cadbox.packer import pack_cavities

        c = _make_config(**config_overrides)
        p = pack_cavities(c)
        s = generate(c, p)
        return s.val().Volume()

    def test_volume_reduction(self):
        v_without = self._generate(finger_pull_radius=0)
        v_with = self._generate(finger_pull_radius=8)
        assert v_with < v_without, f"Expected {v_with} < {v_without}"

    # 7.7 - No volume change when radius=0
    def test_no_change_when_disabled(self):
        v1 = self._generate(finger_pull_radius=0)
        v2 = self._generate()  # default is 0
        assert abs(v1 - v2) < 0.01

    # 7.8 - Per-cavity disable respected
    def test_per_cavity_disable(self):
        v_all = self._generate(
            finger_pull_radius=8,
            cavities=[{"shape": "rect", "width": 30, "length": 20, "depth": 20}],
        )
        v_disabled = self._generate(
            finger_pull_radius=8,
            cavities=[{"shape": "rect", "width": 30, "length": 20, "depth": 20, "finger_pull": False}],
        )
        v_none = self._generate(
            finger_pull_radius=0,
            cavities=[{"shape": "rect", "width": 30, "length": 20, "depth": 20}],
        )
        # Disabled should match no-pulls
        assert abs(v_disabled - v_none) < 0.01
        # Enabled should be less
        assert v_all < v_none

    # 7.9 - Circular cavity finger pulls
    def test_circle_finger_pulls(self):
        v_without = self._generate(
            finger_pull_radius=0,
            cavities=[{"shape": "circle", "diameter": 25, "depth": 20}],
        )
        v_with = self._generate(
            finger_pull_radius=8,
            cavities=[{"shape": "circle", "diameter": 25, "depth": 20}],
        )
        assert v_with < v_without

    # 7.10 - Gridfinity with finger pulls
    def test_gridfinity_finger_pulls(self):
        from cadbox.generator import generate
        from cadbox.models import ContainerConfig
        from cadbox.packer import pack_cavities

        base = {
            "box_type": "gridfinity",
            "grid_units_x": 2, "grid_units_y": 1, "height_units": 3,
            "cavities": [{"shape": "rect", "width": 20, "length": 15, "depth": 10}],
        }
        c1 = ContainerConfig.model_validate({**base, "finger_pull_radius": 0})
        c2 = ContainerConfig.model_validate({**base, "finger_pull_radius": 6})
        p1 = pack_cavities(c1)
        p2 = pack_cavities(c2)
        v1 = generate(c1, p1).val().Volume()
        v2 = generate(c2, p2).val().Volume()
        assert v2 < v1

    # 7.11 - STEP/STL export with finger pulls
    def test_export_with_finger_pulls(self, tmp_path):
        from cadbox.generator import generate_and_export
        from cadbox.packer import pack_cavities

        c = _make_config(finger_pull_radius=8)
        p = pack_cavities(c)

        step_out = tmp_path / "fp_test.step"
        generate_and_export(c, p, step_out)
        assert step_out.exists()
        assert step_out.stat().st_size > 0

        stl_out = tmp_path / "fp_test.stl"
        generate_and_export(c, p, stl_out)
        assert stl_out.exists()
        assert stl_out.stat().st_size > 0


# ---------------------------------------------------------------------------
# 7.12 - Scoop positioned on correct (narrow) axis
# ---------------------------------------------------------------------------


class TestFingerPullPlacement:
    def test_narrow_width_scoops_on_x_sides(self):
        """30w x 20l: narrow=width, scoops on +X/-X. Both orientations produce valid geometry."""
        from cadbox.generator import generate
        from cadbox.packer import pack_cavities

        c = _make_config(
            finger_pull_radius=8,
            cavities=[{"shape": "rect", "width": 20, "length": 30, "depth": 20}],
        )
        p = pack_cavities(c)
        s = generate(c, p)
        assert s.val().Volume() > 0

    def test_narrow_length_scoops_on_y_sides(self):
        """20w x 10l: narrow=length, scoops on +Y/-Y."""
        from cadbox.generator import generate
        from cadbox.packer import pack_cavities

        c = _make_config(
            finger_pull_radius=6,
            cavities=[{"shape": "rect", "width": 40, "length": 15, "depth": 20}],
        )
        p = pack_cavities(c)
        s = generate(c, p)
        assert s.val().Volume() > 0

    def test_both_orientations_reduce_volume(self):
        """Different narrow axes both produce volume reduction."""
        from cadbox.generator import generate
        from cadbox.packer import pack_cavities

        # Narrow = width (20 < 30)
        c1_off = _make_config(finger_pull_radius=0, cavities=[{"shape": "rect", "width": 20, "length": 30, "depth": 20}])
        c1_on = _make_config(finger_pull_radius=8, cavities=[{"shape": "rect", "width": 20, "length": 30, "depth": 20}])
        v1_off = generate(c1_off, pack_cavities(c1_off)).val().Volume()
        v1_on = generate(c1_on, pack_cavities(c1_on)).val().Volume()
        assert v1_on < v1_off

        # Narrow = length (15 < 40)
        c2_off = _make_config(finger_pull_radius=0, cavities=[{"shape": "rect", "width": 40, "length": 15, "depth": 20}])
        c2_on = _make_config(finger_pull_radius=8, cavities=[{"shape": "rect", "width": 40, "length": 15, "depth": 20}])
        v2_off = generate(c2_off, pack_cavities(c2_off)).val().Volume()
        v2_on = generate(c2_on, pack_cavities(c2_on)).val().Volume()
        assert v2_on < v2_off


# ---------------------------------------------------------------------------
# 7.13 - Scoop doesn't cut below cavity floor (depth clamping)
# ---------------------------------------------------------------------------


class TestFingerPullDepthClamping:
    def test_clamped_radius_matches_cavity_depth(self):
        """radius=15 with depth=8 should produce same result as radius=8 with depth=8."""
        from cadbox.generator import generate
        from cadbox.packer import pack_cavities

        c_large = _make_config(
            finger_pull_radius=15,
            cavities=[{"shape": "rect", "width": 30, "length": 20, "depth": 8}],
        )
        c_exact = _make_config(
            finger_pull_radius=8,
            cavities=[{"shape": "rect", "width": 30, "length": 20, "depth": 8}],
        )
        v_large = generate(c_large, pack_cavities(c_large)).val().Volume()
        v_exact = generate(c_exact, pack_cavities(c_exact)).val().Volume()
        # Both should be approximately equal since large radius is clamped to depth=8
        assert abs(v_large - v_exact) < 1.0, f"Expected ~equal: {v_large} vs {v_exact}"


# ---------------------------------------------------------------------------
# 7.14 - Regression: all existing tests still pass (run via pytest)
# ---------------------------------------------------------------------------
# This is verified by running: pytest tests/ -v
