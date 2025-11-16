## pythinfer — Copilot instructions

- Project purpose: a Python package that merges RDF graphs, runs external inference backends, and exports the original triples plus a filtered set of "useful" inferences (see README.md for more information).

- Names and locations to check first (start here):
  - `README.md` — high-level design notes are here.
  - `example_projects/` — example project configurations and data.
  - `pythinfer/` — main package code.

- Coding patterns to follow (explicit, project-specific):
  - use uv for all Python and dependency management. Avoid altering pyproject.toml directly, especially for adding or removing dependencies.
  - Preserve provenance using named graphs (graph URI = source file or category). Do not collapse sources into a single anonymous graph during merging.
  - Treat 'external' vocabulary graphs as ephemeral sources for inference only — mark them so they can be removed from final outputs.
  - Keep backend adapters small, idiomatic, and testable. Prefer a thin wrapper that accepts graphs and returns graphs/changesets.

- Quick checks and tests for PRs:
  - Ensure merging preserves named graph URIs for each input file.
  - Add a tiny fixture: one external vocabulary + one internal ontology + one data file and assert the final exported triples do not include trivial external-only inferences.
