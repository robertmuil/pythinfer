"""pythinfer CLI entry point."""

from pathlib import Path

import typer

from .inout import Project
from .merge import MergedGraph, merge_graphs, run_inference_backend

app = typer.Typer()


@app.command()
def merge(
    config: Path = Path("example_projects/eg1-ancestors/ancestors.yaml"),
    output: Path | None = None,
    *,
    exclude_external: bool = True,
) -> MergedGraph:
    """Merge graphs as specified in the config file and export."""
    typer.echo(f"Merging RDF graphs using config: {config}")
    cfg = Project.from_yaml(config)
    if output is None:
        output = cfg.paths_data[0].parent / "_merged.ttl"
    typer.secho(f"Project loaded: {cfg}", fg=typer.colors.GREEN)
    merged = merge_graphs(cfg)
    typer.secho(
        "Merged graph lengths:"
        f"\n\texternal: {len(merged.vocab_external): 4d}"
        f"\n\tinternal: {len(merged.vocab_internal): 4d}"
        f"\n\tdata:     {len(merged.data): 4d}"
        f"\n\tmerged:   {len(merged.merged): 4d}",
        fg=typer.colors.GREEN,
    )

    # filtered_graph = export_filtered_triples(
    #     (external, internal, data),
    #     exclude_external=exclude_external,
    # )
    filtered_graph = (
        merged.vocab_external + merged.vocab_internal + merged.data
    )  # Placeholder
    filtered_graph.serialize(destination=output, format="longturtle", canon=True)
    typer.echo(f"Exported {len(filtered_graph)} triples to '{output}'")

    return merged


@app.command()
def infer(
    config: Path = Path("example_projects/eg1-ancestors/ancestors.yaml"),
    backend: str = "owlrl",
    output: Path | None = None,
) -> None:
    """Run inference backends on merged graph."""
    typer.echo(f"Running inference using config: {config} and backend: {backend}")
    mg = merge(config)

    try:
        run_inference_backend(mg, backend=backend)
        if mg.full_inferences is not None:
            assert mg.vocab_external_inferences is not None  # noqa: S101
            typer.secho(
                f"Inference complete. {len(mg.full_inferences)} inferred triples"
                f" ({len(mg.vocab_external_inferences)} external inferred triples).",
                fg=typer.colors.GREEN,
            )

            if output is None:
                output = config.parent / f"_inferred_{backend}.trig"

            mg.final.serialize(
                destination=output,
                format="trig",
                # canon=True,
            )
            typer.echo(
                f"Exported {len(mg.final)} inferred triples to '{output}'",
            )
    except ValueError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
