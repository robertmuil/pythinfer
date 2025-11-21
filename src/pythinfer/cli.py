"""pythinfer CLI entry point."""

import logging
from pathlib import Path

import typer

from pythinfer.inout import Project, discover_project
from pythinfer.merge import (
    CategorisedDataset,
    GraphCategory,
    graph_lengths,
    merge_graphs,
    run_inference_backend,
)

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
) -> CategorisedDataset:
    """Merge graphs as specified in the config file and export."""
    config_path = config or discover_project(Path.cwd())
    typer.echo(f"Merging RDF graphs using config: {config_path}")
    cfg = Project.from_yaml(config_path)
    if output is None:
        output = config_path.parent / "derived" / "merged.trig"
        output.parent.mkdir(parents=True, exist_ok=True)
    typer.secho(f"Project loaded: {cfg}", fg=typer.colors.GREEN)
    cd = merge_graphs(cfg)

    # Calculate lengths by category
    ext_len = sum(
        len(cd.ds.graph(gid)) for gid in cd.category.get(GraphCategory.EXT_VOCAB, [])
    )
    int_len = sum(
        len(cd.ds.graph(gid)) for gid in cd.category.get(GraphCategory.INT_VOCAB, [])
    )
    data_len = sum(
        len(cd.ds.graph(gid)) for gid in cd.category.get(GraphCategory.DATA, [])
    )

    typer.secho(
        "Merged graph lengths:"
        f"\n\texternal: {ext_len: 4d}"
        f"\n\tinternal: {int_len: 4d}"
        f"\n\tdata:     {data_len: 4d}"
        f"\n\tmerged:   {len(cd.ds): 4d}",
        fg=typer.colors.GREEN,
    )

    filtered_graph = cd.ds
    if exclude_external:
        filtered_graph = cd.final
    filtered_graph.serialize(destination=output, format="trig", canon=True)
    typer.echo(f"Exported {len(filtered_graph)} triples to '{output}'")

    return cd


@app.command()
def infer(
    config: Path | None = None,
    backend: str = "owlrl",
    output: Path | None = None,
) -> CategorisedDataset:
    """Run inference backends on merged graph."""
    config_path = config or discover_project(Path.cwd())
    typer.echo(f"Running inference using config: {config_path} and backend: {backend}")
    cd = merge(config_path)

    run_inference_backend(cd, backend=backend)
    typer.secho(
        f"Inference complete. {len(cd.ds)} total triples in dataset",
        fg=typer.colors.GREEN,
    )

    if output is None:
        output = config_path.parent / "derived" / f"inferred_{backend}.trig"
        output.parent.mkdir(parents=True, exist_ok=True)

    cd.final.serialize(destination=output, format="trig")
    typer.echo(
        f"Exported {len(cd.final)} inferred triples to '{output}'",
    )

    # Calculate lengths by category
    ext_len = sum(
        len(cd.ds.graph(gid)) for gid in cd.category.get(GraphCategory.EXT_VOCAB, [])
    )
    int_len = sum(
        len(cd.ds.graph(gid)) for gid in cd.category.get(GraphCategory.INT_VOCAB, [])
    )
    data_len = sum(
        len(cd.ds.graph(gid)) for gid in cd.category.get(GraphCategory.DATA, [])
    )
    ext_inf_len = sum(
        len(cd.ds.graph(gid))
        for gid in cd.category.get(GraphCategory.INF_EXT_VOCAB, [])
    )
    full_inf_len = sum(
        len(cd.ds.graph(gid)) for gid in cd.category.get(GraphCategory.INF_FULL, [])
    )

    typer.secho(
        "Merged graph category breakdown:"
        f"\n\texternal: {ext_len: 4d}"
        f"\n\tinternal: {int_len: 4d}"
        f"\n\tdata:     {data_len: 4d}"
        f"\n\tinferred_external: {ext_inf_len: 4d}"
        f"\n\tinferred_full:     {full_inf_len: 4d}",
        fg=typer.colors.GREEN,
    )
    typer.secho("Named graph categories:", fg=typer.colors.YELLOW)
    typer.secho(f"{'Graph':60s} Length", fg=typer.colors.YELLOW, bold=True)
    for gid, length in graph_lengths(cd.ds).items():
        typer.secho(f"{gid.n3():60s} {length: 4d}", fg=typer.colors.YELLOW)

    return cd


if __name__ == "__main__":
    app()
