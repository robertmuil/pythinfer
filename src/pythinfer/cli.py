"""pythinfer CLI entry point."""

import logging
from pathlib import Path

import typer
from rdflib import Dataset, IdentifiedNode, URIRef
from rdflib.query import Result

from pythinfer.infer import run_inference_backend
from pythinfer.inout import Project, create_project, load_project
from pythinfer.merge import (
    merge_graphs,
)
from pythinfer.rdflibplus import DatasetView, graph_lengths

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
def create(
    directory: Path | None = None,
    output: Path | None = None,
    *,
    force: bool = False,
) -> None:
    """Create a new pythinfer project file by scanning for RDF files.

    Scans the specified directory (or current directory) for RDF files
    and generates a pythinfer.yaml configuration file.

    Args:
        directory: Directory to scan for RDF files (default: current directory).
        output: Path to create the project file (default: pythinfer.yaml).
        force: Overwrite existing project file if it exists.

    """
    project = create_project(scan_directory=directory, output_path=output, force=force)
    typer.secho(
        f"✓ Created project file at: `{project.path_self}`",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Project name: {project.path_self.parent.name}")

@app.command()
def merge(
    config: Path | None = None,
    output: Path | None = None,
    *,
    exclude_external: bool = True,
) -> tuple[Dataset, list[IdentifiedNode], Project]:
    """Merge graphs as specified in the config file and export."""
    project = load_project(config)

    if output is None:
        output = project.path_self.parent / "derived" / "merged.trig"
        output.parent.mkdir(parents=True, exist_ok=True)

    typer.echo(f"Merging RDF graphs using project at `{project.path_self}`")
    typer.secho(f"Project loaded: {project}", fg=typer.colors.GREEN)
    ds, external_graph_ids = merge_graphs(project)

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

    return ds, external_graph_ids, project


@app.command()
def infer(
    config: Path | None = None,
    backend: str = "owlrl",
    output: Path | None = None,
    *,
    include_unwanted_triples: bool = False,
    include_external: bool = False,
) -> tuple[Dataset, list[IdentifiedNode]]:
    """Run inference backends on merged graph."""
    ds, external_graph_ids, project = merge(config)
    project.owl_backend = backend
    typer.echo(
        f"Running inference using config: {project.path_self} and backend: {backend}"
    )

    # Run inference and get updated external graph IDs (includes inference graphs)
    all_external_ids = run_inference_backend(
        ds,
        external_graph_ids,
        project,
        include_unwanted_triples=include_unwanted_triples,
    )
    typer.secho(
        f"Inference complete. {len(ds)} total triples in dataset",
        fg=typer.colors.GREEN,
    )

    if output is None:
        output = project.path_self.parent / "derived" / f"inferred_{backend}.trig"
        output.parent.mkdir(parents=True, exist_ok=True)

    final_ds = ds
    if not include_external:
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

@app.command()
def query(
    query: Path, project: Path | None = None, graph: list[str] | None = None
) -> Result:
    """Perform a query, from given path, against the latest inferred file.

    Args:
        query: Path to the query file to execute
        project: Path to project file (defaults to project selection process)

    """
    with query.open() as f:
        query_contents = f.read()

    ds, _ = infer(project)

    view = ds
    if graph:
        view = DatasetView(ds, [URIRef(g) for g in graph])
        gid_n3s = [gid.n3() for gid in view.included_graph_ids]
        typer.secho(f"querying only {len(graph)} graphs: {'; '.join(gid_n3s)}")

    result = view.query(query_contents)

    typer.secho(f"Executed {result.type} query:")
    if result.type == "SELECT":
        typer.secho(f"{len(result.bindings)} rows", fg="green")
        # TODO: turn the bindings into a proper typer table instead of serialize()
        typer.secho(result.serialize(format="csv").decode(), fg="yellow")
    elif result.type == "CONSTRUCT":
        typer.secho(f"{len(result.graph)} triples", fg="green")
        typer.secho(result.graph.serialize(format="turtle"), fg="yellow")
    else:
        typer.echo(result.serialize().decode())

    return result


if __name__ == "__main__":
    app()
