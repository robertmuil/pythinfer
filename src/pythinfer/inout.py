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


def create_project(
    scan_directory: Path | None = None,
    output_path: Path | str = PROJECT_FILE_NAME,
) -> Path:
    """Create a new pythinfer.yaml project file by scanning directory for RDF files.

    Scans the specified directory (or current working directory) for RDF files
    (with .ttl or .rdf extensions) and creates a pythinfer.yaml configuration
    file listing them.

    Args:
        scan_directory: Directory to scan for RDF files. If None, uses current working directory.
        output_path: Path where the project file should be created.

    Returns:
        Path to the created project configuration file.

    """
    _scan_dir = (scan_directory or Path.cwd()).resolve()
    _output_path = Path(output_path)

    # Ensure output directory exists
    _output_path.parent.mkdir(parents=True, exist_ok=True)

    # Find all RDF files, excluding the 'derived' directory
    rdf_files: list[Path] = []
    for rdf_ext in ("*.ttl", "*.rdf"):
        # Search recursively but exclude 'derived' directory
        for rdf_file in _scan_dir.rglob(rdf_ext):
            # Skip files in 'derived' directory
            if "derived" in rdf_file.parts:
                continue
            # Store relative paths from scan directory
            rel_path = rdf_file.relative_to(_scan_dir)
            rdf_files.append(rel_path)

    # Sort for consistent output
    rdf_files.sort()

    # Create project configuration
    project_config = {
        "name": _scan_dir.name,
        "data": [str(f) for f in rdf_files],
    }

    # Write to YAML file
    with _output_path.open("w") as f:
        yaml.dump(project_config, f, default_flow_style=False)

    return _output_path
