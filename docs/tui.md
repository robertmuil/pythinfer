# TUI

Text user interfaces (TUIs) are included in `pythinfer` for interactive exploration of RDF data.

To provide maximum compatibility, `curses` is used to provide the basic functionality. If a user has `prompt_toolkit` installed, it will be used to enhance the user experience with features like better input handling and file pickers, and if `Textual` is installed, it will be used for even further improvements like mouse handling.

## Common Features

### Column Widths

Wherever columns are presented with dynamic content (for instance in the the results pane of the query editor), their widths are determined according to the following principles:

1. **Equitable Distribution**: Every column can use up to a fair share of available space, where fair share is simply the window width divided by the number of columns.
1. **Only use necessary space**: if a column doesn't need its fair share, it only uses what is required for the longest value in that column, and the remaining space is redistributed among the other columns.
1. **Minimum Width**: Each column has a minimum width of 3 characters to ensure readability.

#### Overflow Handling

When a column's content exceeds its allocated width, the content is **clipped in the middle** — the beginning and end of the value are preserved and the middle is replaced with `..`. For example, `http://example.org/very/long/uri` at width 12 becomes `http:..g/uri` and `eg:VeryBigClass` at width 10 becomes `eg:..Class`. This keeps both the prefix and the local name visible, which is typically the most useful information.

#### Scope

- **Triple browser** (`explore`, `compare`): column widths are recalculated on every render, so resizing the terminal immediately adjusts the layout.
- **Query editor** (curses and prompt_toolkit): column widths are calculated once when the query is executed. Resize the terminal and re-execute the query to reformat.
- **Textual query editor**: uses Textual's built-in `DataTable` widget which provides horizontal scrolling, so no clipping is applied.

### Namespace Editing

TODO: document cross-interface

## Interactive Triple Browser

The `explore` and `compare` commands launch an interactive curses-based TUI for browsing RDF triples.

### Launching

```bash
# Browse the project's inferred dataset
pythinfer explore

# Browse a single RDF file
pythinfer explore data.ttl

# Compare two files
pythinfer compare left.ttl right.ttl
```

### Main View

Triples are displayed one per line in `subject  predicate  object .` format, shortened using namespace prefixes.

#### Keybindings

| Key | Action |
| --- | ------ |
| `j` | Scroll down one line |
| `k` | Scroll up one line |
| `J` / `PageDown` | Scroll down half a page |
| `K` / `PageUp` | Scroll up half a page |
| `/` | Add a filter (enter regex, smart-case). Empty input clears all filters. |
| `c` | Clear all filters |
| `Esc` | Clear all filters |
| `f` | Open filter manager |
| `n` | Open namespace editor |
| `q` / `Q` | Quit |

#### Compare-only keys

When using `compare`, arrow keys switch between views:

| Key | View |
| --- | ------ |
| `↑` | Intersection (triples in both files) |
| `↓` | Union (all triples) |
| `←` | Only in left file |
| `→` | Only in right file |

### Filters

Filters are regex patterns applied in sequence — each filter narrows the output of the previous one. Matches are highlighted in the triple display.

- **Smart-case**: patterns are case-insensitive unless they contain an uppercase letter.
- **Field prefixes**: prefix a filter with `s=`, `p=`, or `o=` to restrict matching to the subject, predicate, or object field respectively. For example, `s=foaf:Person` only matches subjects.
- **Persistence**: filters are automatically saved to `.current.filters` in the working directory and restored on next launch.
- Pressing `/` with empty input clears all filters.

Note that complex regex filters are likely better expressed as SPARQL queries, so if the filters list gets complex or is taking a long time to filter, it may be worth switching to SPARQL for more efficient querying.

### Filter Manager (`f`)

| Key | Action |
| --- | ------ |
| `/` | Add a new filter |
| `e` | Edit selected filter |
| `d` | Delete selected filter |
| `J` | Move selected filter down |
| `K` | Move selected filter up |
| `S` | Save filters to a named `.filters` file |
| `L` | Load filters from a file picker |
| `Enter` / `f` / `Esc` | Return to main view |
| `q` | Quit |

#### Saving and Loading

- `S` prompts for a filename (`.filters` extension added automatically).
- `L` opens a file picker listing all `*.filters` files in the working directory.

### Namespace Editor (`n`)

View and edit the prefix→URI bindings used to shorten URIs in the display.

| Key | Action |
| --- | ------ |
| `a` | Add a new prefix binding |
| `e` | Edit the selected binding (prefix and/or URI) |
| `d` | Delete the selected binding |
| `j` / `k` | Move cursor |
| `PageDown` / `PageUp` | Scroll half-page |
| `n` / `Esc` | Return to main view |
| `q` | Quit |

Changes take effect immediately — the triple display is re-rendered with updated prefix shortenings.

## Query Editor

The `query` command, when run without a query argument, launches an interactive TUI for writing, loading, saving, and executing SPARQL queries against the project's inferred dataset.

### Launching

```bash
# Launch with auto-detected backend (Textual → prompt-toolkit → curses)
pythinfer query

# Force a specific backend
pythinfer query --tui textual
pythinfer query --tui prompt-toolkit
pythinfer query --tui curses

# Query specific graphs
pythinfer query --graph "http://example.org/my-graph"
```

### Backends

Three backends are available, each requiring different dependencies. By default (`--tui auto`), the best available backend is selected automatically.

| Backend | Dependency | Features |
| ------- | ---------- | -------- |
| **Textual** | `textual`, `textual-textarea`, `tree-sitter-sparql` | Mouse support, syntax highlighting, undo/redo, horizontal scrolling in results |
| **prompt-toolkit** | `prompt-toolkit`, `pygments` | Vim keybindings, syntax highlighting, SPARQL autocompletion, mouse support |
| **curses** | *(stdlib — always available)* | No extra dependencies, line numbers in editor |

Install optional backends via the extras:

```bash
uv pip install pythinfer[tui-textual]   # Textual backend
uv pip install pythinfer[tui-pt]        # prompt-toolkit backend
```

If an explicitly requested backend is not installed, the command fails with an `ImportError` rather than silently falling back.

### Layout

All three backends share the same split-pane layout:

- **Top**: status bar showing the current filename and available shortcuts
- **Upper pane**: SPARQL query editor, pre-populated with a default `SELECT ?s ?p ?o` query
- **Lower pane**: query results (table for SELECT, Turtle text for CONSTRUCT/DESCRIBE, boolean for ASK)

Press `Tab` to switch focus between the editor and results panes.

### Common Keybindings

These keybindings work across all backends (with minor variations noted):

| Key | Action |
| --- | ------ |
| `Ctrl-E` | Execute the current query |
| `Ctrl-L` | Load a `.rq` file from the project directory |
| `Ctrl-S` | Save the current query to a file |
| `Tab` | Switch focus between editor and results panes |
| `Ctrl-C` | Quit (curses and prompt-toolkit) |
| `Ctrl-Q` | Quit (Textual) |

### Result Display

All SPARQL query types are supported:

- **SELECT**: results are displayed as a table with column headers. In the curses and prompt-toolkit backends, column headers are frozen at the top of the results pane while data rows scroll beneath. In Textual, results use a `DataTable` widget with horizontal scrolling.
- **CONSTRUCT / DESCRIBE**: results are serialized as Turtle text, with namespace prefixes inherited from the dataset.
- **ASK**: displays `True` or `False`.

Errors are caught and displayed inline in the results pane.

### File Management

#### Loading

The load function (`Ctrl-L`) recursively scans the project directory for `*.rq` files and presents a file picker:

- **curses**: a full-screen picker navigated with `j`/`k` and `Enter`
- **prompt-toolkit**: a radio-list dialog
- **Textual**: a modal option list

#### Saving

The save function (`Ctrl-S`) prompts for a filename (defaulting to the current file's name, or `query.rq` for unsaved queries). The file is written to the project directory.

### Backend-specific Details

#### Textual Backend

The Textual backend provides the richest experience:

- **Syntax highlighting**: SPARQL keywords, variables, prefixes, literals, and numbers are highlighted using a Tree-sitter grammar.
- **Editor features**: full VS Code-like editing via `textual-textarea` — undo/redo, selection, clipboard support.
- **Results table**: SELECT results use Textual's `DataTable` widget with horizontal scrolling, so column clipping is not applied.
- **Mouse support**: click to position cursor, click pane headers to switch focus.
- **Pane cycling**: `F6` moves focus to the next pane.

| Key | Action |
| --- | ------ |
| `Ctrl-E` | Execute query |
| `Ctrl-L` | Load `.rq` file |
| `Ctrl-Q` | Quit |
| `F6` | Cycle focus to next pane |

#### prompt-toolkit Backend

The prompt-toolkit backend provides vim-style editing and autocompletion:

- **Vim keybindings**: the editor uses vi editing mode by default.
- **Syntax highlighting**: SPARQL highlighting via Pygments' `SparqlLexer`.
- **Autocompletion**: completes SPARQL keywords (case-insensitive) and namespace prefixes from the dataset. A completions menu appears automatically.
- **Frozen headers**: SELECT column headers and a divider line are pinned above the scrollable results.
- **Mouse support**: enabled by default.

| Key | Action |
| --- | ------ |
| `Ctrl-E` | Execute query |
| `Ctrl-L` | Load `.rq` file |
| `Ctrl-S` | Save query |
| `Tab` | Switch focus to next pane |
| `Shift-Tab` | Switch focus to previous pane |
| `Ctrl-C` | Quit |
| `q` (in vi normal mode) | Quit |

#### curses Backend

The curses backend requires no additional dependencies:

- **Line numbers**: the editor gutter displays line numbers.
- **Frozen headers**: SELECT column headers are pinned above the scrollable results data.
- **Scroll position**: a position indicator `[1-20/100]` appears at the bottom of the results pane.
- **Status bar**: shows cursor position (`Ln 3, Col 7`) at the bottom of the screen.

##### Editor Pane Keybindings

| Key | Action |
| --- | ------ |
| `Ctrl-E` | Execute query |
| `Enter` | Insert newline |
| `Backspace` | Delete character (or join lines) |
| `Delete` | Delete forward (or join with next line) |
| `←` `→` `↑` `↓` | Move cursor |
| `Home` | Move to start of line |
| `End` | Move to end of line |
| `PageUp` / `PageDown` | Scroll editor by one page |

##### Results Pane Keybindings

| Key | Action |
| --- | ------ |
| `j` / `↓` | Scroll down one line |
| `k` / `↑` | Scroll up one line |
| `J` / `PageDown` | Scroll down half a page |
| `K` / `PageUp` | Scroll up half a page |
| `L` | Load `.rq` file |
| `S` | Save query |
