"""Input/output utilities for pythinfer package."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Project:
    """Represents a pythinfer project configuration.

    Attributes:
        name: Name of the project.
        path_self: Path to the project config file itself.
        paths_data: List of paths to data files. [Must be > 1]
        paths_vocab_int: List of paths to internal vocabulary files. [Optional]
        paths_vocab_ext: List of paths to external vocabulary files. [Optional]

    """

    name: str
    path_self: Path
    paths_data: list[Path]
    paths_vocab_int: list[Path]
    paths_vocab_ext: list[Path]
    owl_backend: str | None = None
    paths_sparql_inference: list[Path] | None = None

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
            path_self=_config_path,
            paths_vocab_ext=[Path(p) for p in cfg.get("external_vocabs", [])],
            paths_vocab_int=[Path(p) for p in cfg.get("internal_vocabs", [])],
            paths_data=[Path(p) for p in cfg["data"]],
        )


PROJECT_FILE_NAME = "pythinfer.yaml"
MAX_DISCOVERY_SEARCH_DEPTH = 10


def discover_project(start_path: Path, _current_depth: int = 0) -> Path:
    """Discover a pythinfer project by searching for a config file.

    Will recursively search parent directories until a config file is found or:
    1. The root directory is reached.
    2. A maximum search depth is reached (to avoid infinite recursion).
    3. The `$HOME` directory is reached.

    Args:
        start_path: Path to start searching from.
        _current_depth: Current search depth (used internally).

    Returns:
        Path to the discovered project config file

    Raises:
        FileNotFoundError if search reaches limit without discovering a project.

    """
    current_path = start_path.resolve()
    config_path = current_path / PROJECT_FILE_NAME

    # Positive case: config file found
    if config_path.exists():
        return config_path

    # Negative cases: check search limits
    msg = f"Search limit hit before finding project config (`{PROJECT_FILE_NAME}`)"
    if current_path.parent == current_path:
        raise FileNotFoundError(msg + ": reached root directory")
    if _current_depth >= MAX_DISCOVERY_SEARCH_DEPTH:
        raise FileNotFoundError(
            msg + f": reached maximum search depth ({_current_depth})"
        )
    home_path = Path.home().resolve()
    if current_path == home_path:
        raise FileNotFoundError(msg + ": reached `$HOME` directory")

    # Recurse to parent directory
    return discover_project(current_path.parent, _current_depth + 1)


def load_project(config_path: Path | None) -> Project:
    """Load a pythinfer project specification from a YAML file.

    The config file can either be specified directly, or discovered by searching.

    Args:
        config_path: Path to the config file, or None to trigger discovery.

    """
    _config_path = config_path or discover_project(Path.cwd())
    return Project.from_yaml(_config_path)


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
