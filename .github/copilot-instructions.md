## pythinfer — Copilot instructions

- Names and locations to check first (start here):
  - `README.md` — high-level design notes are here.
  - `example_projects/` — example project configurations and data.
  - `pythinfer/` — main package code.

- Coding patterns to follow (explicit, project-specific):
  - use uv for all Python and dependency management. Avoid altering pyproject.toml directly, especially for adding or removing dependencies.
  - prefer executing python in terminal rather than through MCP
  - when testing functionality, preserve the tests in the test suite rather than just in throw-away scripts.
  - for exploration scripts that should not be preserved in the test suite, place them in the package `scripts/` folder, NOT in /tmp, and give them a clear name and purpose.

