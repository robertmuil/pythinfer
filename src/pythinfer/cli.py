"""pythinfer CLI entry point."""
import logging
import sys
from collections.abc import Sequence
from contextvars import ContextVar
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer
from rdflib import Dataset, IdentifiedNode, URIRef
from rdflib.namespace import NamespaceManager
from rdflib.query import Result
from rich import print as rich_print
from rich.table import Table

from pythinfer.api import Project
from pythinfer.infer import load_cache, run_inference_backend
from pythinfer.merge import merge_graphs
from pythinfer.resolve_imports import resolve_imports as _resolve_imports
from pythinfer.rdflibplus import DatasetView, graph_lengths

ProjectOption = Annotated[
    Path | None,
    typer.Option(
        "--project",
        "-p",
        help="Path to project configuration file (pythinfer.yaml)",
    ),
]

VerboseOption = Annotated[
    bool,
    typer.Option(
        "--verbose",
        "-v",
        help="Enable verbose (DEBUG) logging output",
    ),
]

ExtraExportFormatOption = Annotated[
    list[str] | None,
    typer.Option(
        "--extra-export-format",
        "-x",
        help="Export to additional format (e.g., 'ttl', 'jsonld', 'xml'). "
        "Can be specified multiple times.",
    ),
]


def get_version() -> str:
    """Get the version of pythinfer from package metadata."""
    return version("pythinfer")


def version_callback(*, show_version: bool) -> None:
    """Handle --version flag."""
    if show_version:
        typer.echo(f"pythinfer {get_version()}")
        raise typer.Exit


app = typer.Typer()
logger = logging.getLogger(__name__)

# Context variable to store the project path (thread-safe alternative to global)
_project_path_var: ContextVar[Path | None] = ContextVar("project_path", default=None)


# These are just convenience templates for consistent output formatting
# Output diagnostics to stderr to leave stdout for pipe output (e.g., query results)
def echo_success(msg: str) -> None:  # noqa: D103 - self-explanatory function
    typer.secho(msg, fg=typer.colors.GREEN, err=True)

def echo_neutral(msg: str) -> None:  # noqa: D103 - self-explanatory function
    typer.secho(msg, err=True)

def echo_warning(msg: str) -> None:  # noqa: D103 - self-explanatory function
    typer.secho(msg, fg=typer.colors.YELLOW, err=True)

def echo_important(msg: str, *, bold: bool = False) -> None:  # noqa: D103 - self-explanatory function
    typer.secho(msg, fg=typer.colors.CYAN, bold=bold, err=True)


def echo_dataset_lengths(ds: Dataset, external_gids: Sequence[IdentifiedNode]) -> None:
    """Pretty printing of a the length of a Dataset and its constituent graphs."""
    # Calculate lengths by category
    ext_len = sum(len(ds.graph(gid)) for gid in external_gids)
    internal_len = len(ds) - ext_len

    echo_neutral(
        "Graph Types:"
        f"\n\t   TOTAL: {len(ds): 4d}"
        f"\n\texternal: {ext_len: 4d}"
        f"\n\tinternal: {internal_len: 4d}",
    )
    echo_important("Named Graphs:")
    echo_important(f"{'Graph':60s} Length", bold=True)
    for gid, length in graph_lengths(ds).items():
        echo_important(f"{gid.n3():60s} {length: 4d}")


def configure_logging(*, verbose: bool) -> None:
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
    *,
    project: ProjectOption = None,
    verbose: VerboseOption = False,
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show version and exit",
            callback=version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Global options for pythinfer CLI."""
    _project_path_var.set(project)
    configure_logging(verbose=verbose)


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
    project = Project.create(scan_directory=directory, output_path=output, force=force)
    echo_success(f"✓ Created Project named '{project.name}' at: `{project.path_self}`")


@app.command()
def resolve_imports(
    download_dir: Path | None = None,
) -> None:
    """Resolve owl:imports statements and download imported ontologies.

    Scans project data files for owl:imports, downloads the referenced
    ontologies to local files, and adds them to the project's reference list.
    Resolves the full import closure (imports of imports).

    Args:
        download_dir: Directory to save downloaded files
                       (default: imports/ next to the project file).

    """
    import yaml

    project = Project.load(_project_path_var.get())
    resolved = _resolve_imports(project, download_dir=download_dir)

    if not resolved:
        echo_neutral("No owl:imports found to resolve.")
        return

    # Update the YAML file directly to preserve extra keys
    with project.path_self.open() as f:
        raw = yaml.safe_load(f)

    project_dir = project.path_self.parent
    existing_refs = [str(r) for r in raw.get("reference", [])]
    for local_path in resolved.values():
        try:
            rel = str(local_path.relative_to(project_dir))
        except ValueError:
            rel = str(local_path)
        if rel not in existing_refs:
            existing_refs.append(rel)
    raw["reference"] = existing_refs

    with project.path_self.open("w") as f:
        yaml.dump(raw, f)

    echo_success(
        f"Resolved {len(resolved)} import(s), "
        f"project updated: `{project.path_self}`"
    )
    for url, path in sorted(resolved.items()):
        echo_neutral(f"  {url} -> {path}")


@app.command()
def merge(
    output: Path | None = None,
    *,
    extra_export_format: ExtraExportFormatOption = None,
) -> None:
    """Merge graphs as specified in the config file and save.

    Args:
        output: path for data to be saved to
                 (defaults to `derived/<project_file_stem>/0-merged.trig`)
        extra_export_format: additional export format(s) (besides trig),
                                can be specified multiple times

    """
    project = Project.load(_project_path_var.get())
    ds, external_graph_ids = merge_graphs(
        project,
        output=output or True,
        extra_export_formats=extra_export_format,
    )
    echo_success(f"Merged graphs from `{project.path_self}`")
    echo_dataset_lengths(ds, external_graph_ids)


@app.command()
def infer(
    backend: str = "owlrl",
    output: Path | None = None,
    *,
    include_unwanted_triples: bool = False,
    no_cache: bool = False,
    extra_export_format: ExtraExportFormatOption = None,
) -> tuple[Dataset, list[IdentifiedNode]]:
    """Run inference backends on merged graph.

    Args:
        backend: OWL inference engine to use
        output: output path for final inferences (None for project-based default)
        include_unwanted_triples: include all valid inferences, even unhelpful
        no_cache: skip cache and re-run inference
        extra_export_format: additional export format(s) (besides trig),
                                can be specified multiple times

    """
    project = Project.load(_project_path_var.get())

    # Force no_cache when extra export formats requested, otherwise exports won't happen
    if extra_export_format and not no_cache:
        echo_warning(
            "Warning: --extra-export-format requires fresh export; ignoring cache.",
        )
        no_cache = True

    ds = None if no_cache else load_cache(project)
    if ds:
        echo_success(
            f"Loaded cached dataset from previous inference at `{project.path_self}`"
        )
        if logger.isEnabledFor(logging.DEBUG):
            echo_dataset_lengths(ds, [])
        return ds, []

    ds, external_graph_ids = merge_graphs(
        project,
        output=True,
        extra_export_formats=extra_export_format,
    )
    project.owl_backend = backend
    echo_neutral(
        f"Running inference using config: {project.path_self} and backend: {backend}"
    )
    echo_dataset_lengths(ds, external_graph_ids)

    all_external_ids = run_inference_backend(
        ds,
        external_graph_ids,
        project,
        output,
        include_unwanted_triples=include_unwanted_triples,
        extra_export_formats=extra_export_format,
    )
    echo_success(f"Inference complete. {len(ds)} total triples in dataset")
    echo_dataset_lengths(ds, all_external_ids)

    return ds, all_external_ids


def _display_select_result(
    result: Result,
    namespace_manager: NamespaceManager,
    *,
    output_format: str | None = None,
) -> None:
    echo_success(f"Retrieved {len(result.bindings)} rows")

    if not result.vars:
        msg = "Query returned no variables."
        raise ValueError(msg)

    if not output_format and sys.stdout.isatty():
        # Create a Rich table from query results
        table = Table(show_header=True, header_style="bold yellow")

        # Add columns from result variables
        for var in result.vars:
            table.add_column(str(var))

        # Add rows from bindings
        for binding in result.bindings:
            row = [binding[var].n3(namespace_manager) for var in result.vars]
            table.add_row(*row)

        rich_print(table)
    else:
        fmt = output_format or "csv"
        result_bytes = result.serialize(format=fmt) # pyright: ignore[reportUnknownMemberType]
        typer.echo(result_bytes, nl=False)


def _display_construct_result(
    result: Result, namespace_manager: NamespaceManager,
) -> None:
    echo_success(
        f"Query returned {len(result.graph) if result.graph else 0} triples:"
    )
    if result.graph:
        # Bind all namespaces from the dataset to preserve prefixes
        for prefix, namespace in namespace_manager.namespaces():
            result.graph.bind(prefix, namespace)
        typer.echo(result.graph.serialize(format="turtle"))


def _display_ask_result(result: Result) -> None:
    if not sys.stdout.isatty():
        typer.echo(str(result.askAnswer))
    else:
        typer.secho(
            str(result.askAnswer),
            fg=typer.colors.GREEN if result.askAnswer else typer.colors.RED,
            bold=True
        )


def _display_query_result(
    result: Result,
    namespace_manager: NamespaceManager,
    num_triples: int,
    *,
    output_format: str | None = None,
) -> None:
    """Display query results to the terminal."""
    echo_neutral(f"Executed {result.type} query against {num_triples} triples:")
    if result.type == "SELECT":
        _display_select_result(result, namespace_manager, output_format=output_format)
    elif result.type in ("CONSTRUCT", "DESCRIBE"):
        _display_construct_result(result, namespace_manager)
    elif result.type in ("ASK"):
        _display_ask_result(result)
    else:
        echo_warning(f"Unknown query result type: {result.type}")
        result_bytes = result.serialize() # pyright: ignore[reportUnknownMemberType]
        if not result_bytes:
            echo_important("Query returned no result.", bold=True)
        else:
            typer.echo(result_bytes.decode())


@app.command()
def query(
    query: str,
    graph: list[str] | None = None,
    *,
    no_cache: bool = False,
    output_format: Annotated[
        str | None,
        typer.Option(
            "--output-format",
            "-f",
            help="Output format for SELECT results (e.g., 'csv', 'json', 'xml', 'txt')."
            "If not set, uses a rich table for terminals and csv otherwise.",
        ),
    ] = None,
) -> Result:
    """Perform a query, from given path, against the latest inferred file.

    Args:
        query: path to the query file to execute, or the query string itself
        graph: IRI for graph to include (can be specified multiple times)
        no_cache: whether to skip loading from cache and re-run inference
        output_format: serialization format for SELECT results (csv, json, xml, txt)

    """
    if Path(query).is_file():
        with Path(query).open() as f:
            query_contents = f.read()
    else:
        query_contents = str(query)

    ds, _ = infer(no_cache=no_cache)

    view = ds
    if graph:
        view = DatasetView(ds, [URIRef(g) for g in graph])
        gid_n3s = [gid.n3() for gid in view.included_graph_ids]
        echo_neutral(f"querying only {len(graph)} graphs: {'; '.join(gid_n3s)}")

    result = view.query(query_contents)

    _display_query_result(
        result, ds.namespace_manager, len(view), output_format=output_format,
    )

    return result


if __name__ == "__main__":
    app()
