"""pythinfer CLI entry point."""

from pathlib import Path

import typer
from rdflib import ConjunctiveGraph

from .inout import Project
from .merge import merge_graphs

app = typer.Typer()


@app.command()
def merge(
    config: Path = Path("example_projects/eg1-ancestors/ancestors.yaml"),
    output: Path | None = None,
    *,
    exclude_external: bool = True,
) -> ConjunctiveGraph:
    """Merge graphs as specified in the config file and export."""
    typer.echo(f"Merging RDF graphs using config: {config}")
    cfg = Project.from_yaml(config)
    if output is None:
        output = cfg.paths_data[0].parent / "_merged.ttl"
    typer.secho(f"Project loaded: {cfg}", fg=typer.colors.GREEN)
    external, internal, data = merge_graphs(cfg)
    typer.secho(
        f"Merged graph lengths: external={len(external)}, internal={len(internal)}, "
        f"data={len(data)}",
        fg=typer.colors.GREEN,
    )

    # filtered_graph = export_filtered_triples(
    #     (external, internal, data),
    #     exclude_external=exclude_external,
    # )
    filtered_graph = external + internal + data  # Placeholder
    filtered_graph.serialize(destination=output, format="longturtle", canon=True)
    typer.echo(f"Exported {len(filtered_graph)} triples to '{output}'")

    return filtered_graph


@app.command()
def infer(
    config: Path = Path("example_projects/eg1-ancestors/ancestors.yaml"),
    backend: str = "default",
) -> None:
    """Run inference backends on merged graph."""
    typer.echo(f"Running inference using config: {config} and backend: {backend}")
    cfg = Project.from_yaml(config)
    merged_graphs = merge_graphs(cfg)
    # inferred_graphs = run_inference_backend(merged_graphs, backend=backend)
    # typer.echo(f"Inference complete. Graphs: {list(inferred_graphs.keys())}")
    raise NotImplementedError("Inference backend not implemented yet.")


if __name__ == "__main__":
    app()
