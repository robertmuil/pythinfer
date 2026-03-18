"""Public Python API for pythinfer.

Provides the `Project` class — a `ProjectSpec` with operational methods
for loading, merging, reasoning, and querying RDF data.

This module sits at the top of the internal import tree so it can safely
import from all other modules without circular dependencies.
"""

import logging
from pathlib import Path

from rdflib import Dataset

from pythinfer.infer import load_cache, run_inference_backend
from pythinfer.merge import merge_graphs
from pythinfer.project import ProjectSpec, create_project, discover_project

logger = logging.getLogger(__name__)


class Project(ProjectSpec):
    """A pythinfer project with operational merge and infer methods.

    Inherits all configuration, serialisation, and discovery from `ProjectSpec`
    and adds the ability to execute merge and inference pipelines.

    Usage::

        from pythinfer import Project

        project = Project.discover()
        ds = project.infer()
        result = ds.query("SELECT * WHERE { GRAPH ?g { ?s ?p ?o } } LIMIT 10")
    """

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Project":
        """Load a project from a config file, discovering one if not specified.

        If no config file is found or specified, a new project is created in the current
        working directory by scanning for RDF files.

        Args:
            config_path: Path to the project configuration file, or None to
                discover the nearest pythinfer.yaml.

        Returns:
            Loaded Project instance.

        """
        if config_path:
            return cls.from_yaml(config_path)

        try:
            path = discover_project(Path.cwd())
            return cls.from_yaml(path)
        except FileNotFoundError:
            logger.info(
                "No existing project found, creating new project in current directory",
            )
            spec = create_project(Path.cwd())
            return cls.from_yaml(spec.path_self)

    @classmethod
    def create(
        cls,
        scan_directory: Path | None = None,
        output_path: Path | None = None,
        *,
        force: bool = False,
    ) -> "Project":
        """Create a new project by scanning a directory for RDF files.

        Args:
            scan_directory: Directory to scan (default: current directory).
            output_path: Where to write pythinfer.yaml (default: in scan_directory).
            force: Overwrite an existing project file if present.

        Returns:
            The newly created Project instance.

        """
        spec = create_project(scan_directory, output_path, force=force)
        return cls.from_yaml(spec.path_self)

    def merge(
        self,
        *,
        output: Path | bool = True,
        extra_export_formats: list[str] | None = None,
    ) -> Dataset:
        """Merge source files as specified in the project configuration.

        Loads all focus and reference files into a single Dataset with named
        graphs for provenance, and optionally persists to disk.

        Args:
            output: False to skip persistence, True for project default path,
                or an explicit Path.
            extra_export_formats: Additional export formats beyond trig
                (e.g., ``["ttl", "jsonld"]``).

        Returns:
            rdflib.Dataset containing all source triples with named graphs.

        """
        ds, _ = merge_graphs(
            self,
            output=output,
            extra_export_formats=extra_export_formats,
        )
        return ds

    def infer(  # noqa: PLR0913 - comfortable we need these arguments
        self,
        *,
        backend: str | None = None,
        output: Path | None = None,
        include_unwanted_triples: bool = False,
        export_full: bool = True,
        no_cache: bool = False,
        extra_export_formats: list[str] | None = None,
    ) -> Dataset:
        """Perform merging and inference on the project data.

        If a valid cached result exists and ``no_cache`` is False, the cached
        dataset is returned directly.  Otherwise the full pipeline runs:
        merge -> OWL-RL / SPARQL inference -> export and cache.

        Args:
            backend: Inference engine to use (default: project config, typically
                ``"owlrl"``).  Overrides ``self.owl_backend`` for this run.
            output: Path for the export file(s), or None for the
                project default.
            include_unwanted_triples: Keep all valid inferences, including
                unhelpful ones that are normally filtered.
            export_full: Write a combined file with all inputs and inferences
                (used for caching and diagnostics).
            no_cache: Skip cache and re-run the full pipeline.  Automatically
                set when ``extra_export_formats`` is provided.
            extra_export_formats: Additional export formats beyond trig
                (e.g., ``["ttl", "jsonld"]``).

        Returns:
            rdflib.Dataset containing merged source data and inferred triples.

        """
        # Extra export formats require a fresh run to actually produce exports
        if extra_export_formats and not no_cache:
            no_cache = True

        ds = None if no_cache else load_cache(self)
        if ds is not None:
            return ds

        ds, external_graph_ids = merge_graphs(
            self,
            output=True,
            extra_export_formats=extra_export_formats,
        )

        if backend is not None:
            self.owl_backend = backend

        run_inference_backend(
            ds,
            external_graph_ids,
            self,
            output,
            include_unwanted_triples=include_unwanted_triples,
            export_full=export_full,
            extra_export_formats=extra_export_formats,
        )

        return ds
