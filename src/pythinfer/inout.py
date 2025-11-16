"""Input/output utilities for pythinfer package."""

from dataclasses import dataclass
from pathlib import Path

import yaml
from rdflib import Graph


@dataclass
class Project:
    """Represents a pythinfer project configuration.

    Attributes:
        name: Name of the project.
        paths_data: List of paths to data files. [Must be > 1]
        paths_vocab_int: List of paths to internal vocabulary files. [Optional]
        paths_vocab_ext: List of paths to external vocabulary files. [Optional]

    """

    name: str
    paths_data: list[Path]
    paths_vocab_int: list[Path]
    paths_vocab_ext: list[Path]

    @staticmethod
    def from_yaml(config_path: Path | str) -> "Project":
        """Load project configuration from a YAML file."""
        _config_path = Path(config_path)
        with _config_path.open() as f:
            cfg = yaml.safe_load(f)

        # TODO(robert): handle path patterns.
        # TODO(robert): validate paths exist.
        return Project(
            name=cfg.get("name", _config_path.stem),
            paths_vocab_ext=[Path(p) for p in cfg.get("external_vocabs", [])],
            paths_vocab_int=[Path(p) for p in cfg.get("internal_vocabs", [])],
            paths_data=[Path(p) for p in cfg["data"]],
        )


def export_filtered_triples(
    graphs: dict[str, Graph],
    *,
    exclude_external: bool = True,
) -> Graph:
    """Export original triples plus filtered set of useful inferences. Exclude external-only inferences if requested."""
    # Placeholder: In a real implementation, filter out triples from external-only graphs
    merged = Graph()
    for src, g in graphs.items():
        if exclude_external and "external" in src:
            continue
        for triple in g:
            merged.add(triple)
    return merged
