"""Input/output utilities for pythinfer package.

This module contains I/O operations: dataset export, query loading, etc.

The Project data model and project management functions (discovery, loading,
creation) live in pythinfer.project. They are re-exported here for backward
compatibility.
"""
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from rdflib import Dataset

from pythinfer.rdflibplus import reduce

logger = logging.getLogger(__name__)


def export_dataset(
    dataset: Dataset,
    output_file: Path,
    formats: list[str] | None = None,
) -> None:
    """Export a Dataset or Graph to file(s) in specified format(s).

    Exports to one or more formats. For each format, the output file path stem
    is used with the appropriate file extension determined by the format.

    For non-quad-aware formats, the Dataset is merged into a single Graph before export,
    while trig/trix/nquads formats natively support multiple named graphs.

    Args:
        dataset: The Dataset or Graph object to export
        output_file: Path template for output files (determines base name and directory)
        formats: List of export formats (default: ["trig"]).
                Examples: ["trig"], ["ttl"], ["ttl", "xml", "n3"], etc.

    """
    # Determine file extension based on format
    format_to_ext = {
        "ttl": "ttl",
        "turtle": "ttl",
        "xml": "rdf",
        "rdfxml": "rdf",
        "n3": "n3",
        "nt": "nt",
        "nq": "nquads",
        "nquads": "nquads",
        "ntriples": "nt",
        "trig": "trig",
        "trix": "trix",
        "jsonld": "json-ld",
        "json-ld": "json-ld",
    }

    exts = [format_to_ext.get(f.lower(), f.lower()) for f in (formats or ["trig"])]

    combined_graph = None
    for ext in exts:
        fmt_output_file = output_file.with_suffix(f".{ext}")

        if ext in ("trig", "trix", "nquads"):
            # For quad-aware formats (trig etc.) use Dataset directly...
            dataset.serialize(destination=str(fmt_output_file), format=ext, canon=True)
        else:
            # ...otherwise reduce Dataset first into a single Graph (only do it once)
            if combined_graph is None:
                combined_graph = reduce(dataset)
            _fmt = ext if (ext != "rdf") else "xml"
            combined_graph.serialize(
                destination=str(fmt_output_file), format=_fmt, canon=True
            )

        logger.info("Exported %d triples to %s", len(dataset), fmt_output_file)


@dataclass
class Query:
    """Represents a query string more meaningfully than str."""

    source: Path
    content: str  # Should use Template or t-string

    def __len__(self) -> int:
        """Return the length of the query string."""
        return len(self.content)

    def __str__(self) -> str:
        """Return the query contents."""
        return self.content

    @property
    def name(self) -> str:
        """Return the stem of the source path as the 'name' of the query."""
        return self.source.stem


def load_sparql_inference_queries(query_files: Sequence[Path]) -> list[Query]:
    """Load SPARQL inference queries from files.

    Returns:
        list[str]: List of SPARQL queries

    """
    queries: list[Query] = []
    for query_file in query_files:
        with query_file.open() as f:
            q = Query(source=query_file, content=f.read())
            queries.append(q)
    return queries

