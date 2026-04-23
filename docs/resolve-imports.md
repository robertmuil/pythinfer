# resolve-imports

The `resolve-imports` command automates the retrieval of external ontologies referenced via `owl:imports` statements in the RDF data of a project. It downloads the imported content to local files and adds them to the project's `reference` list, removing the need for network access during subsequent processing.

## Motivation

OWL ontologies declare dependencies on external vocabularies using
`owl:imports`:

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .

<http://example.org/my-ontology> owl:imports
    <http://purl.org/dc/terms/> ,
    <http://www.w3.org/ns/prov> .
```

Resolving these URLs at merge, inference, or query time introduces problems:

- **Network dependency** -- processing fails without connectivity.
- **Latency** -- remote servers may be slow or rate-limited.
- **Reproducibility** -- remote content can change between runs.

`resolve-imports` solves these by fetching once and caching locally.

## Usage

```bash
# Resolve imports for the current project (discovers pythinfer.yaml)
pythinfer resolve-imports

# Specify a project file
pythinfer -p myproject.yaml resolve-imports

# Use a custom download directory (default: imports/ next to project file)
pythinfer resolve-imports --download-dir /path/to/cache
```

## How it works

1. **Scan** -- All files listed in the project's `focus` and `reference` fields are parsed. Every `owl:imports` object URL is collected.

2. **Download** -- Each URL is fetched using `curl`, which inherits the system's proxy configuration, SSL trust store, and redirect handling. An `Accept` header requests RDF formats (Turtle, RDF/XML, etc.) so vocabulary servers return machine-readable content. The downloaded graph is serialized as Turtle to a local file in the download directory. URLs whose local file already exists are skipped, so re-running the command is cheap. Delete a cached file to force a re-download.

3. **Closure** -- Downloaded files are themselves scanned for further `owl:imports` statements. This continues until the full transitive closure is resolved. A URL that has already been resolved is never visited again, so circular import chains terminate naturally.

4. **Update project** -- The local file paths are appended to the `reference` key in the project YAML file. The update is done by modifying only the `reference` key, preserving any other keys in the file (in case the project file is a superset config shared with other tools).

5. **Save mapping** -- A `url-mapping.yaml` file is written to the download directory, mapping each import URL to its local file path. This is updated on every run.

## File naming

Downloaded files are named by sanitizing the source URL:

| URL | Local file |
|-----|-----------|
| `http://purl.org/dc/terms/` | `imports/purl.org_dc_terms.ttl` |
| `http://www.w3.org/ns/prov` | `imports/www.w3.org_ns_prov.ttl` |
| `http://www.w3.org/2004/02/skos/core` | `imports/www.w3.org_2004_02_skos_core.ttl` |

The scheme is: `{netloc}_{path_slug}.ttl`, where non-alphanumeric characters in the path are replaced with underscores.

## Download directory

By default, downloads are saved to an `imports/` directory next to the project file. You can override this with `--download-dir`. The directory is created if it does not exist.

Consider adding the download directory to version control so that collaborators do not need to re-download the same ontologies, and to track changes to them over time.

## Error handling

If a URL cannot be fetched (network error, 404, unparseable content), a warning is logged and that import is skipped. All other imports are still resolved. Re-run the command after fixing the issue to pick up the failed import.

## Example

Given a project with this data file:

```turtle
@prefix owl: <http://www.w3.org/2002/07/owl#> .

<http://example.org/my-ontology> owl:imports
    <http://purl.org/dc/terms/> ,
    <http://www.w3.org/ns/prov> .
```

Running `pythinfer resolve-imports` will:

1. Download `http://purl.org/dc/terms/` to `imports/purl.org_dc_terms.ttl`
2. Download `http://www.w3.org/ns/prov` to `imports/www.w3.org_ns_prov.ttl`
3. Scan both downloaded files for further `owl:imports` and resolve those too
4. Add both files to the project's `reference` list in `pythinfer.yaml`

The project file is updated from:

```yaml
name: my-project
focus:
  - data.ttl
```

to:

```yaml
name: my-project
focus:
  - data.ttl
reference:
  - imports/purl.org_dc_terms.ttl
  - imports/www.w3.org_ns_prov.ttl
```
