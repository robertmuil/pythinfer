"""Resolve owl:imports statements by downloading and caching imported ontologies."""

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from rdflib import OWL, Graph

from pythinfer.project import ProjectSpec

logger = logging.getLogger(__name__)


def _sanitize_url_to_filename(url: str) -> str:
    """Convert a URL into a safe, readable filename.

    Example: http://purl.org/dc/terms/ -> purl.org_dc_terms.ttl
    """
    parsed = urlparse(url)
    slug = parsed.netloc + parsed.path
    slug = slug.strip("/")
    slug = re.sub(r"[^\w.-]", "_", slug)
    slug = re.sub(r"_+", "_", slug)
    return f"{slug}.ttl"


def _collect_import_urls(filepath: Path) -> set[str]:
    """Parse an RDF file and return all owl:imports URLs."""
    g = Graph()
    g.parse(filepath)
    return {str(obj) for obj in g.objects(predicate=OWL.imports)}


def resolve_imports(
    project: ProjectSpec,
    download_dir: Path | None = None,
) -> dict[str, Path]:
    """Resolve owl:imports statements from project files, downloading to local cache.

    Scans all focus and reference files for owl:imports, downloads each imported
    ontology, saves it locally, and recursively resolves imports from downloaded
    files (full import closure).

    Args:
        project: Project specification whose files to scan.
        download_dir: Directory for downloaded files.
            Defaults to ``<project_dir>/imports/``.

    Returns:
        Mapping of import URL to local file path for all resolved imports.

    """
    if download_dir is None:
        download_dir = project.path_self.parent / "imports"

    resolved: dict[str, Path] = {}
    pending: set[str] = set()

    # Collect initial import URLs from all project files
    for filepath in project.focus + project.reference:
        pending |= _collect_import_urls(filepath)

    # Filter out URLs that already have local files in the download dir
    existing_files = {p.stem: p for p in download_dir.glob("*.ttl")} if download_dir.exists() else {}

    while pending:
        url = pending.pop()
        if url in resolved:
            continue

        local_filename = _sanitize_url_to_filename(url)
        local_path = download_dir / local_filename

        if local_path.exists():
            logger.info("Already cached: %s -> %s", url, local_path)
            resolved[url] = local_path
            # Still need to check this file for further imports
            pending |= _collect_import_urls(local_path) - set(resolved)
            continue

        logger.info("Downloading: %s", url)
        try:
            g = Graph()
            g.parse(url)
        except Exception:
            logger.warning("Failed to download: %s", url)
            continue

        download_dir.mkdir(parents=True, exist_ok=True)
        g.serialize(destination=str(local_path), format="turtle")
        logger.info("Saved: %s -> %s", url, local_path)
        resolved[url] = local_path

        # Check downloaded content for further imports (closure)
        further_imports = {str(obj) for obj in g.objects(predicate=OWL.imports)}
        pending |= further_imports - set(resolved)

    return resolved
