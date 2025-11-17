"""pythinfer CLI entry point."""

from pathlib import Path

import typer

from pythinfer.inout import Project
from pythinfer.merge import (
    CategorisedDataset,
    GraphCategory,
    graph_lengths,
    merge_graphs,
    run_inference_backend,
)

app = typer.Typer()


@app.command()
def merge(
    config: Path = Path("example_projects/eg1-ancestors/ancestors.yaml"),
    output: Path | None = None,
    *,
    exclude_external: bool = False,
) -> CategorisedDataset:
    """Merge graphs as specified in the config file and export."""
    typer.echo(f"Merging RDF graphs using config: {config}")
    cfg = Project.from_yaml(config)
    if output is None:
        output = cfg.paths_data[0].parent / "_merged.trig"
    typer.secho(f"Project loaded: {cfg}", fg=typer.colors.GREEN)
    cd = merge_graphs(cfg)

    # Calculate lengths by category
    ext_len = sum(
        len(cd.ds.graph(gid))
        for gid, cat in cd.category.items()
        if cat == GraphCategory.EXT_VOCAB
    )
    int_len = sum(
        len(cd.ds.graph(gid))
        for gid, cat in cd.category.items()
        if cat == GraphCategory.INT_VOCAB
    )
    data_len = sum(
        len(cd.ds.graph(gid))
        for gid, cat in cd.category.items()
        if cat == GraphCategory.DATA
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
    config: Path = Path("example_projects/eg1-ancestors/ancestors.yaml"),
    backend: str = "owlrl",
    output: Path | None = None,
) -> CategorisedDataset:
    """Run inference backends on merged graph."""
    typer.echo(f"Running inference using config: {config} and backend: {backend}")
    cd = merge(config)

    run_inference_backend(cd, backend=backend)
    typer.secho(
        f"Inference complete. {len(cd.ds)} total triples in dataset",
        fg=typer.colors.GREEN,
    )

    if output is None:
        output = config.parent / f"_inferred_{backend}.trig"

    cd.final.serialize(destination=output, format="trig")
    typer.echo(
        f"Exported {len(cd.final)} inferred triples to '{output}'",
    )

    # Calculate lengths by category
    ext_len = sum(
        len(cd.ds.graph(gid))
        for gid, cat in cd.category.items()
        if cat.value == "external_vocab"
    )
    int_len = sum(
        len(cd.ds.graph(gid))
        for gid, cat in cd.category.items()
        if cat.value == "internal_vocab"
    )
    data_len = sum(
        len(cd.ds.graph(gid)) for gid, cat in cd.category.items() if cat.value == "data"
    )
    ext_inf_len = sum(
        len(cd.ds.graph(gid))
        for gid, cat in cd.category.items()
        if cat.value == "external_inferences"
    )
    full_inf_len = sum(
        len(cd.ds.graph(gid))
        for gid, cat in cd.category.items()
        if cat.value == "full_inferences"
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
    # table_data = [[gid, length] for gid, length in graph_lengths(cd.ds).items()]
    typer.secho(f"{'Graph':60s} Length", fg=typer.colors.YELLOW, bold=True)
    for gid, length in graph_lengths(cd.ds).items():
        typer.secho(f"{gid.n3():60s} {length: 4d}", fg=typer.colors.YELLOW)

    return cd


if __name__ == "__main__":
    app()
