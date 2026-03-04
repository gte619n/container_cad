"""Comprehensive pytest test suite for cadbox.

Covers models, config loading, validation, packing, generation, and CLI.
All dimensions are in millimetres.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

SIMPLE_CONFIG_DICT = {
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
    ],
}

SIMPLE_CONFIG_JSON = json.dumps(SIMPLE_CONFIG_DICT)


def _make_config(**overrides):
    """Return a ContainerConfig built from SIMPLE_CONFIG_DICT with overrides."""
    from cadbox.models import ContainerConfig

    data = {**SIMPLE_CONFIG_DICT, **overrides}
    return ContainerConfig.model_validate(data)


# ---------------------------------------------------------------------------
# test_models – CavitySpec, CavityTemplate, CavityRef, ContainerConfig
# ---------------------------------------------------------------------------


class TestCavitySpecValidation:
    """CavitySpec geometry and repetition constraints."""

    def test_rect_requires_width_and_length(self):
        from pydantic import ValidationError as PydanticValidationError

        from cadbox.models import CavitySpec

        with pytest.raises(PydanticValidationError, match="width.*length|width and length"):
            CavitySpec(shape="rect", depth=10)  # missing both

    def test_rect_missing_length_raises(self):
        from pydantic import ValidationError as PydanticValidationError

        from cadbox.models import CavitySpec

        with pytest.raises(PydanticValidationError):
            CavitySpec(shape="rect", width=10, depth=10)  # missing length

    def test_rect_missing_width_raises(self):
        from pydantic import ValidationError as PydanticValidationError

        from cadbox.models import CavitySpec

        with pytest.raises(PydanticValidationError):
            CavitySpec(shape="rect", length=10, depth=10)  # missing width

    def test_circle_requires_diameter(self):
        from pydantic import ValidationError as PydanticValidationError

        from cadbox.models import CavitySpec

        with pytest.raises(PydanticValidationError, match="diameter"):
            CavitySpec(shape="circle", depth=10)

    def test_valid_rect(self):
        from cadbox.models import CavityShape, CavitySpec

        spec = CavitySpec(shape="rect", width=15, length=10, depth=8)
        assert spec.shape == CavityShape.rect
        assert spec.width == 15
        assert spec.length == 10
        assert spec.depth == 8

    def test_valid_circle(self):
        from cadbox.models import CavityShape, CavitySpec

        spec = CavitySpec(shape="circle", diameter=12, depth=5)
        assert spec.shape == CavityShape.circle
        assert spec.diameter == 12

    def test_grid_and_count_mutually_exclusive(self):
        from pydantic import ValidationError as PydanticValidationError

        from cadbox.models import CavitySpec

        with pytest.raises(PydanticValidationError, match="grid.*count|mutually exclusive"):
            CavitySpec(shape="rect", width=10, length=10, depth=5, count=3, grid=(2, 2))

    def test_count_alone_is_valid(self):
        from cadbox.models import CavitySpec

        spec = CavitySpec(shape="rect", width=10, length=10, depth=5, count=4)
        assert spec.count == 4
        assert spec.grid is None

    def test_grid_alone_is_valid(self):
        from cadbox.models import CavitySpec

        spec = CavitySpec(shape="rect", width=10, length=10, depth=5, grid=(2, 3))
        assert spec.grid == (2, 3)
        assert spec.count == 1  # default


class TestCavitySpecFootprint:
    """CavitySpec.footprint_width and footprint_length properties."""

    def test_rect_footprint(self):
        from cadbox.models import CavitySpec

        spec = CavitySpec(shape="rect", width=20, length=15, depth=5)
        assert spec.footprint_width == 20
        assert spec.footprint_length == 15

    def test_circle_footprint_uses_diameter(self):
        from cadbox.models import CavitySpec

        spec = CavitySpec(shape="circle", diameter=18, depth=5)
        assert spec.footprint_width == 18
        assert spec.footprint_length == 18


class TestCavityTemplateValidation:
    """CavityTemplate geometry constraints."""

    def test_rect_template_requires_width_and_length(self):
        from pydantic import ValidationError as PydanticValidationError

        from cadbox.models import CavityTemplate

        with pytest.raises(PydanticValidationError):
            CavityTemplate(name="t1", shape="rect", depth=10)

    def test_circle_template_requires_diameter(self):
        from pydantic import ValidationError as PydanticValidationError

        from cadbox.models import CavityTemplate

        with pytest.raises(PydanticValidationError, match="diameter"):
            CavityTemplate(name="t2", shape="circle", depth=10)

    def test_valid_rect_template(self):
        from cadbox.models import CavityTemplate

        tmpl = CavityTemplate(name="slot", shape="rect", width=10, length=5, depth=8)
        assert tmpl.name == "slot"

    def test_valid_circle_template(self):
        from cadbox.models import CavityTemplate

        tmpl = CavityTemplate(name="hole", shape="circle", diameter=8, depth=6)
        assert tmpl.name == "hole"


class TestCavityRefResolution:
    """CavityRef resolution via ContainerConfig.resolve_cavity()."""

    def _config_with_template(self):
        from cadbox.models import ContainerConfig

        data = {
            "width": 80,
            "length": 60,
            "height": 20,
            "templates": [
                {"name": "slot", "shape": "rect", "width": 10, "length": 5, "depth": 8}
            ],
            "cavities": [
                {"template": "slot"}
            ],
        }
        return ContainerConfig.model_validate(data)

    def test_ref_resolves_to_spec(self):
        from cadbox.models import CavityRef, CavityShape, CavitySpec

        config = self._config_with_template()
        ref = CavityRef(template="slot")
        spec = config.resolve_cavity(ref)
        assert isinstance(spec, CavitySpec)
        assert spec.shape == CavityShape.rect
        assert spec.width == 10
        assert spec.length == 5
        assert spec.depth == 8

    def test_ref_depth_override(self):
        from cadbox.models import CavityRef

        config = self._config_with_template()
        ref = CavityRef(template="slot", depth=15)
        spec = config.resolve_cavity(ref)
        assert spec.depth == 15  # override wins

    def test_ref_count_propagated(self):
        from cadbox.models import CavityRef

        config = self._config_with_template()
        ref = CavityRef(template="slot", count=3)
        spec = config.resolve_cavity(ref)
        assert spec.count == 3

    def test_ref_unknown_template_raises(self):
        from pydantic import ValidationError as PydanticValidationError

        from cadbox.models import ContainerConfig

        data = {
            "width": 80,
            "length": 60,
            "height": 20,
            "templates": [],
            "cavities": [{"template": "nonexistent"}],
        }
        with pytest.raises(PydanticValidationError, match="unknown template|nonexistent"):
            ContainerConfig.model_validate(data)

    def test_ref_key_error_on_missing_template_direct(self):
        """resolve_cavity raises KeyError when template map lacks the name."""
        from cadbox.models import CavityRef, ContainerConfig

        config = ContainerConfig(width=80, length=60, height=20)
        # Bypass model_validator by building ref directly
        ref = CavityRef.model_construct(template="ghost", depth=None, count=1, grid=None)
        with pytest.raises(KeyError):
            config.resolve_cavity(ref)


class TestContainerConfigProperties:
    """ContainerConfig field validation and defaults."""

    def test_width_must_be_positive(self):
        from pydantic import ValidationError as PydanticValidationError

        from cadbox.models import ContainerConfig

        with pytest.raises(PydanticValidationError):
            ContainerConfig(width=0, length=50, height=20)

    def test_minimal_valid_config(self):
        from cadbox.models import ContainerConfig

        cfg = ContainerConfig(width=50, length=40, height=15)
        assert cfg.outer_wall == 2.0
        assert cfg.rib_thickness == 1.6
        assert cfg.floor_thickness == 1.2
        assert cfg.fillet_radius == 1.0
        assert cfg.templates == []
        assert cfg.cavities == []


# ---------------------------------------------------------------------------
# test_config – load_config_from_string / load_config
# ---------------------------------------------------------------------------


class TestLoadConfigFromString:
    """load_config_from_string happy path and error cases."""

    def test_valid_json_parses(self):
        from cadbox.config import load_config_from_string
        from cadbox.models import ContainerConfig

        cfg = load_config_from_string(SIMPLE_CONFIG_JSON)
        assert isinstance(cfg, ContainerConfig)
        assert cfg.width == 100
        assert cfg.length == 80
        assert cfg.height == 25

    def test_cavity_count_correct(self):
        from cadbox.config import load_config_from_string

        cfg = load_config_from_string(SIMPLE_CONFIG_JSON)
        assert len(cfg.cavities) == 2

    def test_invalid_json_raises_config_error(self):
        from cadbox.config import ConfigError, load_config_from_string

        with pytest.raises(ConfigError, match="[Ii]nvalid JSON"):
            load_config_from_string("{not valid json}")

    def test_invalid_schema_raises_config_error(self):
        from cadbox.config import ConfigError, load_config_from_string

        bad = json.dumps({"width": "not_a_number", "length": 50, "height": 20})
        with pytest.raises(ConfigError, match="[Cc]onfig validation"):
            load_config_from_string(bad)

    def test_missing_required_field_raises_config_error(self):
        from cadbox.config import ConfigError, load_config_from_string

        # height is required
        bad = json.dumps({"width": 100, "length": 80})
        with pytest.raises(ConfigError):
            load_config_from_string(bad)

    def test_unknown_cavity_template_ref_raises_config_error(self):
        from cadbox.config import ConfigError, load_config_from_string

        bad = json.dumps(
            {
                "width": 100,
                "length": 80,
                "height": 25,
                "cavities": [{"template": "missing_template"}],
            }
        )
        with pytest.raises(ConfigError):
            load_config_from_string(bad)


class TestLoadConfigFile:
    """load_config file I/O error handling."""

    def test_missing_file_raises_config_error(self, tmp_path):
        from cadbox.config import ConfigError, load_config

        with pytest.raises(ConfigError, match="[Nn]ot found|not found"):
            load_config(tmp_path / "does_not_exist.json")

    def test_valid_file_loads(self, tmp_path):
        from cadbox.config import load_config

        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(SIMPLE_CONFIG_JSON, encoding="utf-8")
        cfg = load_config(cfg_file)
        assert cfg.width == 100

    def test_invalid_json_file_raises_config_error(self, tmp_path):
        from cadbox.config import ConfigError, load_config

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{broken", encoding="utf-8")
        with pytest.raises(ConfigError, match="[Ii]nvalid JSON"):
            load_config(bad_file)


# ---------------------------------------------------------------------------
# test_validator – validate_container
# ---------------------------------------------------------------------------


class TestValidateContainer:
    """validate_container constraint checks."""

    def test_valid_config_returns_no_errors(self):
        from cadbox.validator import validate_container

        cfg = _make_config()
        errors = validate_container(cfg)
        assert errors == []

    def test_thin_outer_wall_flagged(self):
        from cadbox.validator import MIN_WALL_THICKNESS, validate_container

        cfg = _make_config(outer_wall=0.3)  # below MIN_WALL_THICKNESS
        errors = validate_container(cfg)
        fields = [e.field for e in errors]
        assert "outer_wall" in fields

    def test_thin_rib_flagged(self):
        from cadbox.validator import MIN_RIB_THICKNESS, validate_container

        cfg = _make_config(rib_thickness=0.2)
        errors = validate_container(cfg)
        fields = [e.field for e in errors]
        assert "rib_thickness" in fields

    def test_thin_floor_flagged(self):
        from cadbox.validator import MIN_FLOOR_THICKNESS, validate_container

        cfg = _make_config(floor_thickness=0.3)
        errors = validate_container(cfg)
        fields = [e.field for e in errors]
        assert "floor_thickness" in fields

    def test_depth_exceeds_height_flagged(self):
        from cadbox.validator import validate_container
        from cadbox.models import ContainerConfig

        data = {
            "width": 80,
            "length": 60,
            "height": 10,
            "floor_thickness": 1.2,
            "cavities": [
                {"shape": "rect", "width": 20, "length": 15, "depth": 15}  # 15 > 10-1.2=8.8
            ],
        }
        cfg = ContainerConfig.model_validate(data)
        errors = validate_container(cfg)
        depth_errors = [e for e in errors if "depth" in e.field]
        assert depth_errors, "Expected a depth violation error"

    def test_small_circular_cavity_flagged(self):
        from cadbox.validator import MIN_CAVITY_DIMENSION, validate_container
        from cadbox.models import ContainerConfig

        data = {
            "width": 80,
            "length": 60,
            "height": 20,
            "cavities": [
                {"shape": "circle", "diameter": 1.0, "depth": 5}  # below MIN_CAVITY_DIMENSION
            ],
        }
        cfg = ContainerConfig.model_validate(data)
        errors = validate_container(cfg)
        diam_errors = [e for e in errors if "diameter" in e.field]
        assert diam_errors, "Expected a diameter violation error"

    def test_small_rect_cavity_width_flagged(self):
        from cadbox.validator import validate_container
        from cadbox.models import ContainerConfig

        data = {
            "width": 80,
            "length": 60,
            "height": 20,
            "cavities": [
                {"shape": "rect", "width": 1.0, "length": 10, "depth": 5}
            ],
        }
        cfg = ContainerConfig.model_validate(data)
        errors = validate_container(cfg)
        width_errors = [e for e in errors if "width" in e.field and "cavities" in e.field]
        assert width_errors, "Expected a cavity width violation"

    def test_validation_error_str_representation(self):
        from cadbox.validator import ValidationError

        err = ValidationError(
            message="test message",
            field="outer_wall",
            value=0.3,
            minimum=1.2,
        )
        s = str(err)
        assert "outer_wall" in s
        assert "0.300" in s
        assert "1.200" in s

    def test_validate_all_raises_on_errors(self):
        from cadbox.validator import CadboxValidationError, validate_all

        cfg = _make_config(outer_wall=0.1)
        with pytest.raises(CadboxValidationError) as exc_info:
            validate_all(cfg)
        assert exc_info.value.errors

    def test_validate_all_returns_empty_for_valid(self):
        from cadbox.validator import validate_all

        cfg = _make_config()
        errors = validate_all(cfg)
        assert errors == []


# ---------------------------------------------------------------------------
# test_packer – pack_cavities
# ---------------------------------------------------------------------------


class TestPackCavities:
    """pack_cavities placement count, bounds, and error cases."""

    def test_simple_config_returns_correct_placement_count(self):
        from cadbox.packer import pack_cavities

        cfg = _make_config()
        result = pack_cavities(cfg)
        # 1 rect + 1 circle = 2 placements
        assert len(result.placements) == 2

    def test_count_expansion(self):
        from cadbox.config import load_config_from_string
        from cadbox.packer import pack_cavities

        data = {
            "width": 100,
            "length": 80,
            "height": 20,
            "cavities": [
                {"shape": "circle", "diameter": 10, "depth": 8, "count": 3}
            ],
        }
        cfg = load_config_from_string(json.dumps(data))
        result = pack_cavities(cfg)
        assert len(result.placements) == 3

    def test_grid_expansion(self):
        from cadbox.config import load_config_from_string
        from cadbox.packer import pack_cavities

        data = {
            "width": 120,
            "length": 100,
            "height": 20,
            "cavities": [
                {"shape": "rect", "width": 15, "length": 10, "depth": 8, "grid": [3, 2]}
            ],
        }
        cfg = load_config_from_string(json.dumps(data))
        result = pack_cavities(cfg)
        assert len(result.placements) == 6  # 3*2

    def test_empty_cavities_returns_zero_placements(self):
        from cadbox.models import ContainerConfig
        from cadbox.packer import pack_cavities

        cfg = ContainerConfig(width=80, length=60, height=20)
        result = pack_cavities(cfg)
        assert result.placements == []
        assert result.utilization == 0.0

    def test_all_placements_within_bounds(self):
        from cadbox.packer import pack_cavities

        cfg = _make_config()
        result = pack_cavities(cfg)

        for p in result.placements:
            hw = p.spec.footprint_width / 2
            hl = p.spec.footprint_length / 2
            assert p.x - hw >= -0.01, f"Placement x={p.x} extends past left wall"
            assert p.x + hw <= result.container_width + 0.01, "Extends past right wall"
            assert p.y - hl >= -0.01, f"Placement y={p.y} extends past bottom wall"
            assert p.y + hl <= result.container_length + 0.01, "Extends past top wall"

    def test_packing_error_when_cavities_dont_fit(self):
        from cadbox.config import load_config_from_string
        from cadbox.packer import PackingError, pack_cavities

        # Container too small for a large cavity
        data = {
            "width": 10,
            "length": 10,
            "height": 20,
            "outer_wall": 2.0,
            "cavities": [
                {"shape": "rect", "width": 50, "length": 50, "depth": 10}
            ],
        }
        cfg = load_config_from_string(json.dumps(data))
        with pytest.raises(PackingError):
            pack_cavities(cfg)

    def test_packing_error_has_suggestion(self):
        from cadbox.config import load_config_from_string
        from cadbox.packer import PackingError, pack_cavities

        data = {
            "width": 10,
            "length": 10,
            "height": 20,
            "outer_wall": 2.0,
            "cavities": [
                {"shape": "rect", "width": 50, "length": 50, "depth": 10}
            ],
        }
        cfg = load_config_from_string(json.dumps(data))
        with pytest.raises(PackingError) as exc_info:
            pack_cavities(cfg)
        assert exc_info.value.suggestion  # non-empty suggestion string

    def test_utilization_between_zero_and_one(self):
        from cadbox.packer import pack_cavities

        cfg = _make_config()
        result = pack_cavities(cfg)
        assert 0.0 <= result.utilization <= 1.0

    def test_container_dimensions_in_result(self):
        from cadbox.packer import pack_cavities

        cfg = _make_config()
        result = pack_cavities(cfg)
        expected_w = cfg.width - 2 * cfg.outer_wall
        expected_l = cfg.length - 2 * cfg.outer_wall
        assert abs(result.container_width - expected_w) < 0.01
        assert abs(result.container_length - expected_l) < 0.01


# ---------------------------------------------------------------------------
# test_generator – generate() and generate_and_export()
# ---------------------------------------------------------------------------


class TestGenerate:
    """generate() returns a CadQuery Workplane with a valid solid."""

    def _simple_packing(self):
        from cadbox.packer import pack_cavities

        cfg = _make_config()
        return cfg, pack_cavities(cfg)

    def test_generate_returns_workplane(self):
        import cadquery as cq

        from cadbox.generator import generate

        cfg, packing = self._simple_packing()
        result = generate(cfg, packing)
        assert isinstance(result, cq.Workplane)

    def test_generate_solid_has_volume(self):
        from cadbox.generator import generate

        cfg, packing = self._simple_packing()
        result = generate(cfg, packing)
        # CadQuery solids expose volume via .val().Volume()
        volume = result.val().Volume()
        assert volume > 0, "Generated solid must have positive volume"

    def test_generate_empty_cavities(self):
        import cadquery as cq

        from cadbox.generator import generate
        from cadbox.models import ContainerConfig
        from cadbox.packer import pack_cavities

        cfg = ContainerConfig(width=50, length=40, height=15)
        packing = pack_cavities(cfg)
        result = generate(cfg, packing)
        assert isinstance(result, cq.Workplane)


class TestGenerateAndExport:
    """generate_and_export() writes STEP and STL files."""

    def _simple_cfg_and_packing(self):
        from cadbox.packer import pack_cavities

        cfg = _make_config()
        return cfg, pack_cavities(cfg)

    def test_step_file_created_and_nonempty(self, tmp_path):
        from cadbox.generator import generate_and_export

        cfg, packing = self._simple_cfg_and_packing()
        out = tmp_path / "test_output.step"
        generate_and_export(cfg, packing, out)
        assert out.exists(), "STEP file was not created"
        assert out.stat().st_size > 0, "STEP file is empty"

    def test_stl_file_created_and_nonempty(self, tmp_path):
        from cadbox.generator import generate_and_export

        cfg, packing = self._simple_cfg_and_packing()
        out = tmp_path / "test_output.stl"
        generate_and_export(cfg, packing, out)
        assert out.exists(), "STL file was not created"
        assert out.stat().st_size > 0, "STL file is empty"

    def test_stp_extension_also_works(self, tmp_path):
        from cadbox.generator import generate_and_export

        cfg, packing = self._simple_cfg_and_packing()
        out = tmp_path / "test_output.stp"
        generate_and_export(cfg, packing, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_unsupported_extension_raises(self, tmp_path):
        from cadbox.generator import generate_and_export

        cfg, packing = self._simple_cfg_and_packing()
        out = tmp_path / "test_output.obj"
        with pytest.raises(ValueError, match="[Uu]nsupported"):
            generate_and_export(cfg, packing, out)

    def test_returns_workplane(self, tmp_path):
        import cadquery as cq

        from cadbox.generator import generate_and_export

        cfg, packing = self._simple_cfg_and_packing()
        out = tmp_path / "test_output.step"
        result = generate_and_export(cfg, packing, out)
        assert isinstance(result, cq.Workplane)

    def test_step_contains_brep_header(self, tmp_path):
        """STEP files should start with ISO-10303 header."""
        from cadbox.generator import generate_and_export

        cfg, packing = self._simple_cfg_and_packing()
        out = tmp_path / "test_output.step"
        generate_and_export(cfg, packing, out)
        header = out.read_bytes()[:200]
        assert b"ISO-10303" in header or b"STEP" in header or b"step" in header.lower()


# ---------------------------------------------------------------------------
# test_cli – Click CLI via CliRunner
# ---------------------------------------------------------------------------


class TestCLIGenerate:
    """CLI generate command tests via click.testing.CliRunner."""

    @pytest.fixture()
    def simple_cfg_file(self, tmp_path):
        """Write simple_config.json to a temp file and return its path."""
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(SIMPLE_CONFIG_JSON, encoding="utf-8")
        return cfg_file

    def test_generate_succeeds_exit_code_0(self, simple_cfg_file, tmp_path):
        from click.testing import CliRunner

        from cadbox.cli import main

        out_file = tmp_path / "result.step"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["generate", str(simple_cfg_file), "-o", str(out_file)],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"

    def test_generate_creates_step_file(self, simple_cfg_file, tmp_path):
        from click.testing import CliRunner

        from cadbox.cli import main

        out_file = tmp_path / "result.step"
        runner = CliRunner()
        runner.invoke(main, ["generate", str(simple_cfg_file), "-o", str(out_file)])
        assert out_file.exists()
        assert out_file.stat().st_size > 0

    def test_validate_only_succeeds(self, simple_cfg_file):
        from click.testing import CliRunner

        from cadbox.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["generate", str(simple_cfg_file), "--validate-only"],
        )
        assert result.exit_code == 0, f"validate-only failed: {result.output}"
        assert "passed" in result.output.lower() or "Validation" in result.output

    def test_validate_only_no_output_file_needed(self, simple_cfg_file, tmp_path):
        """With --validate-only, no STEP file should be written."""
        from click.testing import CliRunner

        from cadbox.cli import main

        out_file = tmp_path / "should_not_exist.step"
        runner = CliRunner()
        runner.invoke(
            main,
            ["generate", str(simple_cfg_file), "-o", str(out_file), "--validate-only"],
        )
        assert not out_file.exists(), "STEP file was written despite --validate-only"

    def test_missing_config_file_fails_gracefully(self, tmp_path):
        from click.testing import CliRunner

        from cadbox.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["generate", str(tmp_path / "nonexistent.json")],
        )
        # Click's path validation (exists=True) produces exit_code 2 for missing file
        assert result.exit_code != 0, "Should fail on missing config file"

    def test_verbose_flag_produces_extra_output(self, simple_cfg_file, tmp_path):
        from click.testing import CliRunner

        from cadbox.cli import main

        out_file = tmp_path / "result.step"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["generate", str(simple_cfg_file), "-o", str(out_file), "--verbose"],
        )
        assert result.exit_code == 0
        # Verbose output mentions loaded config dimensions
        assert "100" in result.output or "Loaded" in result.output

    def test_invalid_json_config_fails_gracefully(self, tmp_path):
        from click.testing import CliRunner

        from cadbox.cli import main

        bad_cfg = tmp_path / "bad.json"
        bad_cfg.write_text("{broken json", encoding="utf-8")
        out_file = tmp_path / "result.step"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["generate", str(bad_cfg), "-o", str(out_file)],
        )
        assert result.exit_code != 0

    def test_no_subcommand_shows_help(self):
        from click.testing import CliRunner

        from cadbox.cli import main

        runner = CliRunner()
        result = runner.invoke(main, [])
        # Should show help text, exit 0
        assert "cadbox" in result.output.lower() or "Usage" in result.output


class TestCLIHelpOutput:
    """CLI top-level help and subcommand registration."""

    def test_help_flag(self):
        from click.testing import CliRunner

        from cadbox.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "generate" in result.output

    def test_generate_help(self):
        from click.testing import CliRunner

        from cadbox.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output or "-o" in result.output
