"""Input/output utilities for pythinfer package."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from rdflib import Dataset, Graph

logger = logging.getLogger(__name__)

PROJECT_FILE_NAME = "pythinfer.yaml"
MAX_DISCOVERY_SEARCH_DEPTH = 10

MERGED_FILESTEM = "0-merged"
COMBINED_FULL_FILESTEM = "1-combined-full"
INFERRED_WANTED_FILESTEM = "2-inferred-wanted"


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

    have_non_quad_format = any(f not in ("trig", "trix", "nquads") for f in exts)

    # For non-quad formats, we'll need to merge Dataset into a single Graph
    combined_graph = Graph()
    if have_non_quad_format:
        # Iterate over quads - this works with DatasetView naturally
        for s, p, o, _ in dataset.quads():
            combined_graph.add((s, p, o))

    for ext in exts:
        fmt_output_file = output_file.with_suffix(f".{ext}")

        # For quad-aware formats (trig) use Dataset directly, otherwise
        # combine into single Graph first
        if ext in ("trig", "trix", "nquads"):
            dataset.serialize(destination=str(fmt_output_file), format=ext, canon=True)
        else:
            _fmt = ext if (ext != "rdf") else "xml"
            combined_graph.serialize(
                destination=str(fmt_output_file), format=_fmt, canon=True
            )

        logger.info("Exported %d triples to %s", len(dataset), fmt_output_file)


class Project(BaseModel):
    """Represents a pythinfer project configuration.

    Attributes:
        name: Name of the project.
        path_self: Path to the project config file itself.
        paths_data: List of paths to data files. [Must be > 1]
        paths_vocab_int: List of paths to internal vocabulary files. [Optional]
        paths_vocab_ext: List of paths to external vocabulary files. [Optional]

    """

    model_config = ConfigDict(
        extra="forbid",  # This rejects unexpected keys
        arbitrary_types_allowed=True,  # Allows Path objects
    )

    name: str
    path_self: Path
    paths_data: list[Path] = Field(min_length=1)
    paths_vocab_int: list[Path] = Field(default_factory=list)
    paths_vocab_ext: list[Path] = Field(default_factory=list)
    owl_backend: str | None = None
    paths_sparql_inference: list[Path] | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_field_names(cls, data: dict) -> dict:
        """Normalize field names to accept multiple spellings."""
        if not isinstance(data, dict):
            return data

        # Map of alternative spellings to canonical field names
        field_aliases = {
            "data": "paths_data",
            "paths_data": "paths_data",
            "internal-vocabs": "paths_vocab_int",
            "internal_vocabs": "paths_vocab_int",
            "paths_vocab_int": "paths_vocab_int",
            "external-vocabs": "paths_vocab_ext",
            "external_vocabs": "paths_vocab_ext",
            "paths_vocab_ext": "paths_vocab_ext",
            "sparql-inference": "paths_sparql_inference",
            "sparql_inference": "paths_sparql_inference",
            "paths_sparql_inference": "paths_sparql_inference",
            "owl-backend": "owl_backend",
            "owl_backend": "owl_backend",
        }

        normalized = {}
        for key, value in data.items():
            # Use canonical name if it's an alias, otherwise keep original
            canonical_key = field_aliases.get(key, key)
            normalized[canonical_key] = value

        return normalized

    @field_validator(
        "paths_data",
        "paths_vocab_int",
        "paths_vocab_ext",
        "paths_sparql_inference",
        mode="before",
    )
    @classmethod
    def convert_str_to_path(cls, v: list[str] | list[Path] | None) -> list[Path] | None:
        """Convert string paths to Path objects."""
        if v is None:
            return None
        return [Path(p) if isinstance(p, str) else p for p in v]

    @field_validator(
        "paths_data",
        "paths_vocab_int",
        "paths_vocab_ext",
        "paths_sparql_inference",
        mode="after",
    )
    @classmethod
    def resolve_relative_paths(
        cls, v: list[Path] | None, info: ValidationInfo
    ) -> list[Path] | None:
        """Resolve relative paths against the project directory.

        Uses the config_dir from validation context if available.
        """
        if v is None:
            return None

        config_dir = info.context.get("config_dir") if info.context else None
        if not config_dir:
            return v

        resolved_paths: list[Path] = []
        for path in v:
            # Only resolve relative paths; absolute paths stay as-is
            resolved_path = path if path.is_absolute() else config_dir / path
            resolved_paths.append(resolved_path)
        return resolved_paths

    @staticmethod
    def from_yaml(config_path: Path | str) -> "Project":
        """Load project configuration from a YAML file.

        Relative paths in the YAML file are resolved relative to the directory
        containing the project file.
        """
        _config_path = Path(config_path).resolve()
        config_dir = _config_path.parent

        with _config_path.open() as f:
            cfg = yaml.safe_load(f)

        # TODO(robert): handle path patterns.
        # TODO(robert): validate paths exist.

        # Add path_self to the config dict before validation
        cfg["path_self"] = _config_path
        if "name" not in cfg:
            cfg["name"] = _config_path.stem

        # Let Pydantic handle validation and field normalization
        # Pass config_dir through context for path resolution in validators
        return Project.model_validate(cfg, context={"config_dir": config_dir})

    def _path_to_yaml_str(self, path: Path) -> str:
        """Convert a path to a string for YAML serialization.

        If the path is relative to the project file's directory, store it
        relative for better portability. Otherwise, store as absolute path.
        """
        project_dir = self.path_self.parent
        try:
            # Try to make it relative to the project directory
            rel_path = path.relative_to(project_dir)
            return str(rel_path)
        except ValueError:
            # Path is not relative to project_dir, store as-is
            return str(path)

    def to_yaml(self) -> str:
        """Serialize project configuration to a YAML string.

        Paths are stored relative to the project file directory when possible,
        for better portability.
        """
        cfg_dict: dict[str, object] = {
            "name": self.name,
            "data": [self._path_to_yaml_str(p) for p in self.paths_data],
        }
        if self.paths_vocab_int:
            cfg_dict["internal_vocabs"] = [
                self._path_to_yaml_str(p) for p in self.paths_vocab_int
            ]
        if self.paths_vocab_ext:
            cfg_dict["external_vocabs"] = [
                self._path_to_yaml_str(p) for p in self.paths_vocab_ext
            ]
        if self.owl_backend:
            cfg_dict["owl_backend"] = self.owl_backend
        if self.paths_sparql_inference:
            cfg_dict["sparql_inference"] = [
                self._path_to_yaml_str(p) for p in self.paths_sparql_inference
            ]
        return yaml.dump(cfg_dict)

    def to_yaml_file(self, output_path: Path) -> None:
        """Write project configuration to a YAML file."""
        with output_path.open("w") as f:
            f.write(self.to_yaml())

    @property
    def path_output(self) -> Path:
        """Path to the output folder."""
        return self.path_self.parent / "derived"

    @property
    def paths_all_input(self) -> list[Path]:
        """List of all input paths (data + vocabularies)."""
        return self.paths_data + self.paths_vocab_int + self.paths_vocab_ext

    @property
    def paths_all(self) -> list[Path]:
        """List of all paths (input + SPARQL inference) - cache checking."""
        return self.paths_all_input + (self.paths_sparql_inference or [])


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

    # Load SPARQL inference queries from the 'queries' directory
    sparql_query_files: list[Path] = []
    for query_file in _scan_dir.rglob("infer*.rq"):
        rel_path = query_file.relative_to(_scan_dir)
        sparql_query_files.append(rel_path)

    # Sort for consistent output
    sparql_query_files.sort()

    # Create project configuration
    project_config = Project(
        name=_scan_dir.name,
        path_self=_output_path,
        paths_data=rdf_files,
        paths_vocab_ext=[],
        paths_vocab_int=[],
        paths_sparql_inference=sparql_query_files,
    )

    project_config.to_yaml_file(_output_path)

    logger.info("✅ Created new project file at `%s`", _output_path)

    return project_config
