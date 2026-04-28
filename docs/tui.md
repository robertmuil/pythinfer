# TUI — Interactive Triple Browser

The `explore` and `compare` commands launch an interactive curses-based TUI for browsing RDF triples.

## Launching

```bash
# Browse the project's inferred dataset
pythinfer explore

# Browse a single RDF file
pythinfer explore data.ttl

# Compare two files
pythinfer compare left.ttl right.ttl
```

## Main View

Triples are displayed one per line in `subject  predicate  object .` format, shortened using namespace prefixes.

### Keybindings

| Key | Action |
| --- | ------ |
| `j` | Scroll down one line |
| `k` | Scroll up one line |
| `PageDown` | Scroll down half a page |
| `PageUp` | Scroll up half a page |
| `/` | Add a filter (enter regex, smart-case). Empty input clears all filters. |
| `c` | Clear all filters |
| `Esc` | Clear all filters |
| `f` | Open filter manager |
| `n` | Open namespace editor |
| `q` / `Q` | Quit |

### Compare-only keys

When using `compare`, arrow keys switch between views:

| Key | View |
| --- | ------ |
| `↑` | Intersection (triples in both files) |
| `↓` | Union (all triples) |
| `←` | Only in left file |
| `→` | Only in right file |

## Filters

Filters are regex patterns applied in sequence — each filter narrows the output of the previous one. Matches are highlighted in the triple display.

- **Smart-case**: patterns are case-insensitive unless they contain an uppercase letter.
- **Persistence**: filters are automatically saved to `.current.filters` in the working directory and restored on next launch.
- Pressing `/` with empty input clears all filters.

Note that complex regex filters are likely better expressed as SPARQL queries, so if the filters list gets complex or is taking a long time to filter, it may be worth switching to SPARQL for more efficient querying.

## Filter Manager (`f`)

| Key | Action |
| --- | ------ |
| `/` | Add a new filter |
| `d` | Delete selected filter |
| `J` | Move selected filter down |
| `K` | Move selected filter up |
| `S` | Save filters to a named `.filters` file |
| `L` | Load filters from a file picker |
| `f` / `Esc` | Return to main view |
| `q` | Quit |

### Saving and Loading

- `S` prompts for a filename (`.filters` extension added automatically).
- `L` opens a file picker listing all `*.filters` files in the working directory.

## Namespace Editor (`n`)

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
