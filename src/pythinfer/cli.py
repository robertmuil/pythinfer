"""pythinfer CLI entry point."""

import logging
from pathlib import Path

import typer
from rdflib import Dataset, IdentifiedNode

from pythinfer.inout import Project, discover_project
from pythinfer.merge import (
    graph_lengths,
    merge_graphs,
    run_inference_backend,
)
from pythinfer.rdflibplus import DatasetView

app = typer.Typer()
logger = logging.getLogger(__name__)


def configure_logging(verbose: bool) -> None:
    """Configure logging level based on verbose flag."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        force=True,  # Reconfigure if already configured
    )


@app.callback()
def main_callback(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose (DEBUG) logging output",
    ),
) -> None:
    """Global options for pythinfer CLI."""
    configure_logging(verbose)


@app.command()
def merge(
    config: Path | None = None,
    output: Path | None = None,
    *,
    exclude_external: bool = False,
) -> tuple[Dataset, list[IdentifiedNode]]:
    """Merge graphs as specified in the config file and export."""
    config_path = config or discover_project(Path.cwd())
    typer.echo(f"Merging RDF graphs using config: {config_path}")
    cfg = Project.from_yaml(config_path)
    if output is None:
        output = config_path.parent / "derived" / "merged.trig"
        output.parent.mkdir(parents=True, exist_ok=True)
    typer.secho(f"Project loaded: {cfg}", fg=typer.colors.GREEN)
    ds, external_graph_ids = merge_graphs(cfg)

    # Calculate lengths by category
    ext_len = sum(len(ds.graph(gid)) for gid in external_graph_ids)
    internal_len = len(ds) - ext_len

    typer.secho(
        "Merged graph lengths:"
        f"\n\texternal: {ext_len: 4d}"
        f"\n\tinternal: {internal_len: 4d}"
        f"\n\tmerged:   {len(ds): 4d}",
        fg=typer.colors.GREEN,
    )

    output_ds = ds
    if exclude_external:
        external_view = DatasetView(ds, external_graph_ids)
        output_ds = external_view.invert()
    output_ds.serialize(destination=output, format="trig", canon=True)
    typer.echo(f"Exported {len(output_ds)} triples to '{output}'")

    return ds, external_graph_ids


@app.command()
def infer(
    config: Path | None = None,
    backend: str = "owlrl",
    output: Path | None = None,
) -> tuple[Dataset, list[IdentifiedNode]]:
    """Run inference backends on merged graph."""
    config_path = config or discover_project(Path.cwd())
    typer.echo(f"Running inference using config: {config_path} and backend: {backend}")
    ds, external_graph_ids = merge(config_path)

    # Run inference and get updated external graph IDs (includes inference graphs)
    all_external_ids = run_inference_backend(ds, external_graph_ids, backend=backend)
    typer.secho(
        f"Inference complete. {len(ds)} total triples in dataset",
        fg=typer.colors.GREEN,
    )

    if output is None:
        output = config_path.parent / "derived" / f"inferred_{backend}.trig"
        output.parent.mkdir(parents=True, exist_ok=True)

    external_view = DatasetView(ds, all_external_ids)
    final_ds = external_view.invert()
    final_ds.serialize(destination=output, format="trig")
    typer.echo(
        f"Exported {len(final_ds)} inferred triples to '{output}'",
    )

    # Calculate lengths by category
    ext_len = sum(len(ds.graph(gid)) for gid in all_external_ids)
    internal_len = len(ds) - ext_len

    typer.secho(
        "Graph breakdown:"
        f"\n\texternal (incl. inferences): {ext_len: 4d}"
        f"\n\tinternal (incl. inferences): {internal_len: 4d}",
        fg=typer.colors.GREEN,
    )
    typer.secho("Named graph breakdown:", fg=typer.colors.YELLOW)
    typer.secho(f"{'Graph':60s} Length", fg=typer.colors.YELLOW, bold=True)
    for gid, length in graph_lengths(ds).items():
        typer.secho(f"{gid.n3():60s} {length: 4d}", fg=typer.colors.YELLOW)

    return ds, all_external_ids


if __name__ == "__main__":
    app()
