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

...
