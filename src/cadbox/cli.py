"""Click-based CLI for cadbox - parametric CAD container generator."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from cadbox.config import ConfigError, load_config
from cadbox.validator import CadboxValidationError, validate_all


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_error(msg: str) -> None:
    click.echo(click.style("Error: ", fg="red", bold=True) + msg, err=True)


def _print_warning(msg: str) -> None:
    click.echo(click.style("Warning: ", fg="yellow", bold=True) + msg, err=True)


def _print_success(msg: str) -> None:
    click.echo(click.style(msg, fg="green"))


def _print_info(msg: str) -> None:
    click.echo(msg)


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """cadbox - parametric FDM-printable container generator."""
    # When invoked without a subcommand, show help.
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# generate command  (also the "default" when a file path is given directly)
# ---------------------------------------------------------------------------


@main.command("generate")
@click.argument("config_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "-o", "--output",
    default="output.step",
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Output STEP file path.",
)
@click.option(
    "--preview/--no-preview",
    default=False,
    show_default=True,
    help="Launch 3-D preview in the browser after generation.",
)
@click.option(
    "--validate-only",
    is_flag=True,
    default=False,
    help="Run validation only; do not generate geometry.",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    default=False,
    help="Print detailed info about packing and generation.",
)
def generate(
    config_file: Path,
    output: Path,
    preview: bool,
    validate_only: bool,
    verbose: bool,
) -> None:
    """Generate a container from CONFIG_FILE (JSON) and write a STEP file."""

    # ------------------------------------------------------------------
    # Step a: Load config
    # ------------------------------------------------------------------
    try:
        config = load_config(config_file)
    except ConfigError as exc:
        _print_error(str(exc))
        sys.exit(1)

    if verbose:
        _print_info(
            f"Loaded config: {config.width} x {config.length} x {config.height} mm, "
            f"{len(config.cavities)} cavity spec(s)"
        )

    # ------------------------------------------------------------------
    # Step b: Pre-packing validation
    # ------------------------------------------------------------------
    try:
        validate_all(config)
    except CadboxValidationError as exc:
        _print_error("Validation failed:")
        for err in exc.errors:
            click.echo(click.style(f"  • {err}", fg="red"), err=True)
        sys.exit(1)

    if validate_only:
        _print_success("Validation passed.")
        return

    # ------------------------------------------------------------------
    # Step c: Pack cavities
    # ------------------------------------------------------------------
    from cadbox import packer
    from cadbox.packer import PackingError

    try:
        packing_result = packer.pack_cavities(config)
    except PackingError as exc:
        _print_error(f"Packing failed: {exc}")
        click.echo(
            click.style(
                "Suggestion: reduce cavity count, shrink cavity dimensions, "
                "or increase container size.",
                fg="yellow",
            )
        )
        sys.exit(1)

    if verbose:
        _print_info(
            f"Packing complete: {len(packing_result.placements)} cavities placed, "
            f"utilization {packing_result.utilization * 100:.1f}%"
        )

    # ------------------------------------------------------------------
    # Step d: Post-packing validation
    # ------------------------------------------------------------------
    try:
        validate_all(config, packing_result)
    except CadboxValidationError as exc:
        _print_warning("Post-packing validation issues:")
        for err in exc.errors:
            click.echo(click.style(f"  • {err}", fg="yellow"), err=True)

    # ------------------------------------------------------------------
    # Step e: Generate and export
    # ------------------------------------------------------------------
    from cadbox import generator

    try:
        solid = generator.generate_and_export(config, packing_result, output)
    except Exception as exc:  # noqa: BLE001
        _print_error(f"Generation failed: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step f: Print summary
    # ------------------------------------------------------------------
    _print_success(f"Generated: {output}")
    _print_info(
        f"  Dimensions : {config.width} x {config.length} x {config.height} mm"
    )
    _print_info(f"  Cavities   : {len(packing_result.placements)} placed")
    _print_info(f"  Utilization: {packing_result.utilization * 100:.1f}%")

    # ------------------------------------------------------------------
    # Step g: Optional preview
    # ------------------------------------------------------------------
    if preview:
        _launch_preview_for_solid(solid, output)


def _launch_preview_for_solid(solid: "cq.Workplane", step_path: Path) -> None:
    """Export the solid to a temporary STL and launch the preview server."""
    from cadbox.generator import export_stl
    from cadbox.preview.server import launch_preview

    stl_path = step_path.with_suffix(".stl")
    export_stl(solid, stl_path)
    _print_info(f"  Preview STL: {stl_path}")

    try:
        launch_preview(stl_path)
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# preview command
# ---------------------------------------------------------------------------


@main.command("preview")
@click.argument(
    "model_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--port",
    default=8123,
    show_default=True,
    type=int,
    help="Local port for the preview HTTP server.",
)
def preview_cmd(model_file: Path, port: int) -> None:
    """Launch a 3-D preview for an existing STEP or STL file."""
    from cadbox.preview.server import launch_preview

    try:
        launch_preview(model_file, port=port)
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# Allow  `cadbox <config.json>`  as a shortcut for  `cadbox generate`
# ---------------------------------------------------------------------------


@main.result_callback()
def _after_group(result, **kwargs):  # noqa: ANN001, ANN201
    pass


# Make bare `cadbox somefile.json` work by routing through generate when
# the argument looks like a file path (not a known subcommand).
_original_main_invoke = main.invoke


def _patched_invoke(ctx: click.Context) -> None:  # type: ignore[override]
    # If invoked without a recognised subcommand and the first arg looks like
    # a file path, silently rewrite to `generate`.
    args = ctx.protected_args + ctx.args
    known = {cmd.name for cmd in main.commands.values()}  # type: ignore[attr-defined]
    if args and args[0] not in known:
        ctx.protected_args = ["generate"]
    _original_main_invoke(ctx)


main.invoke = _patched_invoke  # type: ignore[method-assign]
