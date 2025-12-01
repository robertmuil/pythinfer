"""pythinfer CLI entry point."""

import logging
from collections.abc import Sequence
from pathlib import Path

import typer
from rdflib import Dataset, IdentifiedNode, URIRef
from rdflib.query import Result

from pythinfer.infer import run_inference_backend
from pythinfer.inout import create_project, load_project
from pythinfer.merge import (
    merge_graphs,
)
from pythinfer.rdflibplus import DatasetView, graph_lengths

app = typer.Typer()
logger = logging.getLogger(__name__)


def echo_success(msg: str) -> None:  # noqa: D103 - self-explanatory function
    typer.secho(msg, fg=typer.colors.GREEN)


echo_neutral = typer.echo


def echo_dataset_lengths(ds: Dataset, external_gids: Sequence[IdentifiedNode]) -> None:
    """Pretty printing of a the length of a Dataset and its constituent graphs."""
    # Calculate lengths by category
    ext_len = sum(len(ds.graph(gid)) for gid in external_gids)
    internal_len = len(ds) - ext_len

    typer.secho(
        "Graph Types:"
        f"\n\t   TOTAL: {len(ds): 4d}"
        f"\n\texternal: {ext_len: 4d}"
        f"\n\tinternal: {internal_len: 4d}",
        fg=typer.colors.YELLOW,
    )
    typer.secho("Named Graphs:", fg=typer.colors.YELLOW)
    typer.secho(f"{'Graph':60s} Length", fg=typer.colors.YELLOW, bold=True)
    for gid, length in graph_lengths(ds).items():
        typer.secho(f"{gid.n3():60s} {length: 4d}", fg=typer.colors.YELLOW)


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
    echo_success(f"✓ Created Project named '{project.name}' at: `{project.path_self}`")


@app.command()
def merge(
    config: Path | None = None,
    output: Path | None = None,
    *,
    export_external: bool = False,
) -> None:
    """Merge graphs as specified in the config file and save.

    Args:
        config: path to the project configuration file
        output: path for data to be saved to (defaults to `derived/merged.trig`)
        export_external: whether to include external graphs in output

    """
    project = load_project(config)
    ds, external_graph_ids = merge_graphs(
        project, output=output or True, export_external=export_external
    )
    echo_success(f"Merged graphs from `{project.path_self}`")
    echo_dataset_lengths(ds, external_graph_ids)


@app.command()
def infer(
    config: Path | None = None,
    backend: str = "owlrl",
    output: Path | None = None,
    *,
    include_unwanted_triples: bool = False,
    export_full: bool = False,
    export_external: bool = False,
) -> tuple[Dataset, list[IdentifiedNode]]:
    """Run inference backends on merged graph.

    Args:
        config: path to Project defining the inputs
        backend: OWL inference engine to use
        output: output path for final inferences (None for project-based default)
        include_unwanted_triples: include all valid inferences, even banal and unhelpful
        export_full: export full file with inputs as well as inferences
        export_external: when exporting, include external graphs and inferences

    """
    project = load_project(config)
    ds, external_graph_ids = merge_graphs(
        project, output=True, export_external=export_external
    )
    project.owl_backend = backend
    echo_neutral(
        f"Running inference using config: {project.path_self} and backend: {backend}"
    )

    # Run inference and get updated external graph IDs (includes inference graphs)
    all_external_ids = run_inference_backend(
        ds,
        external_graph_ids,
        project,
        output,
        include_unwanted_triples=include_unwanted_triples,
        export_full=export_full,
        export_external=export_external,
    )
    echo_success(f"Inference complete. {len(ds)} total triples in dataset")
    echo_dataset_lengths(ds, all_external_ids)

    return ds, all_external_ids


@app.command()
def query(
    query: Path, project: Path | None = None, graph: list[str] | None = None
) -> Result:
    """Perform a query, from given path, against the latest inferred file.

    TODO: don't call the infer CLI command
    TODO: move functionality to module and keep this just CLI

    Args:
        query: Path to the query file to execute
        project: Path to project file (defaults to project selection process)
        graph: IRI for graph to include (can be specified multiple times)

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
    elif result.type in ("CONSTRUCT", "DESCRIBE"):
        typer.secho(f"{len(result.graph)} triples", fg="green")
        typer.secho(result.graph.serialize(format="turtle"), fg="yellow")
    else:
        typer.echo(result.serialize().decode())

    return result


if __name__ == "__main__":
    app()
