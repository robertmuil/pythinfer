"""Resolve owl:imports statements by downloading and caching imported ontologies."""

import logging
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yaml
from rdflib import OWL, Graph

from pythinfer.project import ProjectSpec

logger = logging.getLogger(__name__)

# RDF content types in preference order for Accept header negotiation
_RDF_ACCEPT = (
    "text/turtle, "
    "application/rdf+xml;q=0.9, "
    "application/n-triples;q=0.8, "
    "application/ld+json;q=0.7, "
    "text/n3;q=0.6, "
    "*/*;q=0.1"
)


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


def _fetch_rdf(url: str) -> Graph:
    """Fetch RDF from a URL using curl for reliable proxy/SSL/redirect handling.

    Uses curl to download, which inherits the system's proxy configuration,
    SSL trust store, and handles redirects. An Accept header requests RDF
    formats so vocabulary servers return machine-readable content.

    For file:// URIs, rdflib is used directly (no curl needed).
    """
    g = Graph()

    if url.startswith("file://"):
        g.parse(url)
        return g

    with tempfile.NamedTemporaryFile(suffix=".rdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(
            [
                "curl", "-fsSL",
                "-H", f"Accept: {_RDF_ACCEPT}",
                "-o", str(tmp_path),
                "-w", "%{content_type}",
                url,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        content_type = result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        tmp_path.unlink(missing_ok=True)
        msg = f"curl failed for {url}"
        raise RuntimeError(msg) from e

    try:
        fmt = None
        if "turtle" in content_type:
            fmt = "turtle"
        elif "rdf+xml" in content_type or "/xml" in content_type:
            fmt = "xml"
        elif "json" in content_type:
            fmt = "json-ld"
        elif "n-triples" in content_type:
            fmt = "nt"
        elif "n3" in content_type:
            fmt = "n3"

        g.parse(tmp_path, format=fmt, publicID=url)
    finally:
        tmp_path.unlink(missing_ok=True)

    return g


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
            g = _fetch_rdf(url)
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

    # Persist URL-to-file mapping
    if resolved:
        mapping_file = download_dir / "url-mapping.yaml"
        mapping = {url: str(path) for url, path in sorted(resolved.items())}
        download_dir.mkdir(parents=True, exist_ok=True)
        with mapping_file.open("w") as f:
            yaml.dump(mapping, f)
        logger.info("Saved URL mapping to %s", mapping_file)

    return resolved
