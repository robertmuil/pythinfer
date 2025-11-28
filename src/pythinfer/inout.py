"""Input/output utilities for pythinfer package."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from rdflib import Dataset, Graph

from pythinfer.rdflibplus import DatasetView

logger = logging.getLogger(__name__)


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

    def to_yaml(self) -> str:
        """Serialize project configuration to a YAML string."""
        cfg_dict: dict[str, object] = {
            "name": self.name,
            "data": [str(p) for p in self.paths_data],
        }
        if self.paths_vocab_int:
            cfg_dict["internal_vocabs"] = [str(p) for p in self.paths_vocab_int]
        if self.paths_vocab_ext:
            cfg_dict["external_vocabs"] = [str(p) for p in self.paths_vocab_ext]
        return yaml.dump(cfg_dict)

    def to_yaml_file(self, output_path: Path) -> None:
        """Write project configuration to a YAML file."""
        with output_path.open("w") as f:
            f.write(self.to_yaml())


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
            msg + f": reached maximum search depth ({_current_depth})",
        )
    home_path = Path.home().resolve()
    if current_path == home_path:
        raise FileNotFoundError(msg + ": reached `$HOME` directory")

    # Recurse to parent directory
    return discover_project(current_path.parent, _current_depth + 1)


def load_project(config_path: Path | None) -> Project:
    """Load a pythinfer project specification from a YAML file.

    The config file can either be specified directly, or discovered by searching.
    If neither yield a result, a new project will be created.

    Args:
        config_path: Path to the config file, or None to trigger discovery.

    """
    try:
        _config_path = config_path or discover_project(Path.cwd())
        project = Project.from_yaml(_config_path)
    except FileNotFoundError:
        logger.info(
            "⚠  No existing project found, creating new project in current directory",
        )
        project = create_project(Path.cwd())
    return project


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
    output_path: Path | None = None,
    *,
    force: bool = False,
) -> Project:
    """Create a new Project specification by scanning directory for RDF files.

    Scans the specified directory (or current working directory) for RDF files
    (with .ttl or .rdf extensions) and creates a new Project specification listing them.

    This Project specification will be saved as `output_path` which defaults to
    `pythinfer.yaml` in the scan_directory.

    Subsidiary files such as SPARQL inference scripts are also sought and added to the
    Project specification.

    Args:
        scan_directory: Directory to scan for RDF files. If None, uses current working
            directory.
        output_path: Path where the project file should be created.
        force: Overwrite existing project file if it exists.

    Returns:
        Project specification object.

    Side Effects:
        Creates a new project configuration file at the specified output path.
        May also create backup files if overwriting existing files.

    Raises:
        FileExistsError: If the output_path already exists.
        FileNotFoundError: If no RDF files are found in the scan_directory or any of
            its subdirectories.

    """
    _scan_dir = scan_directory or Path.cwd()
    _output_path = Path(output_path or _scan_dir / PROJECT_FILE_NAME)

    # Cowardly refuse to overwrite existing project file
    if _output_path.exists():
        if not force:
            msg = f"Refusing to overwrite existing project file at `{_output_path}`"
            raise FileExistsError(msg)
        # Store backup of existing file with incrementing .bak suffix
        for i in range(100):
            backup_path = _output_path.with_suffix(f".bak{i}.yaml")
            if not backup_path.exists():
                break
        else:
            msg = "Too many backup files exist, cannot create new backup."
            raise FileExistsError(msg)
        _output_path.rename(backup_path)
        logger.warning("⚠ Existing project file exists, backed up to `%s`", backup_path)

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

    if not rdf_files:
        msg = f"No RDF files found in directory `{_scan_dir}` to create project."
        raise FileNotFoundError(msg)

    # Sort for consistent output
    rdf_files.sort()

    # Create project configuration
    project_config = Project(
        name=_scan_dir.name,
        path_self=_output_path,
        paths_data=rdf_files,
        paths_vocab_ext=[],
        paths_vocab_int=[],
    )

    project_config.to_yaml_file(_output_path)

    logger.info("✅ Created new project file at `%s`", _output_path)

    return project_config
