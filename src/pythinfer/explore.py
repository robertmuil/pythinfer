"""Provide functionality to explore a graph and compare two graphs.

Provides TUI for easy filtering and browsing.

For comparisons, compute intersection, differences, and browse interactively.
"""
import curses
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph, Node
from rdflib.namespace import NamespaceManager

_KEY_ESCAPE = 27
_DEFAULT_FILTERS_FILE = ".current.filters"


@dataclass
class CompareResult:
    """Result of comparing two RDF graphs."""

    left_path: Path
    right_path: Path
    left_count: int
    right_count: int
    only_left: Graph
    only_right: Graph
    both: Graph
    union: Graph


def load_graph(path: str | Path) -> Graph:
    """Load an RDF file and return it as a Graph."""
    g = Graph()
    g.parse(str(path))
    return g


def format_triples(graph: Graph) -> list[str]:
    """Format triples as readable strings using the graph's namespace prefixes."""
    lines: list[str] = []
    nm = graph.namespace_manager
    for s, p, o in sorted(graph, key=lambda t: str(t)):  # noqa: PLW0108 - lambda needed to avoid ty/pylance Buffer issue
        s_str = _shorten(s, nm)
        p_str = _shorten(p, nm)
        o_str = _shorten(o, nm)
        lines.append(f"{s_str}  {p_str}  {o_str} .")
    return lines


def _shorten(term: Node, nm: NamespaceManager) -> str:
    try:
        prefix, _ns, local = nm.compute_qname(str(term), generate=False)
    except Exception:  # noqa: BLE001
        return str(term)
    else:
        return f"{prefix}:{local}"


def _bind_namespaces(target: Graph, *sources: Graph) -> None:
    """Copy namespace bindings from source graphs into target."""
    for src in sources:
        for prefix, ns in src.namespaces():
            target.bind(prefix, ns, override=False)


def compare_graphs(left_path: str | Path, right_path: str | Path) -> CompareResult:
    """Compare two RDF graphs and return structured results."""
    left_path = Path(left_path)
    right_path = Path(right_path)

    left = load_graph(left_path)
    right = load_graph(right_path)

    only_left = left - right
    only_right = right - left
    both = left * right  # Graph intersection
    union = left + right

    # Propagate namespace bindings to all result graphs
    for g in (only_left, only_right, both, union):
        _bind_namespaces(g, left, right)

    return CompareResult(
        left_path=left_path,
        right_path=right_path,
        left_count=len(left),
        right_count=len(right),
        only_left=only_left,
        only_right=only_right,
        both=both,
        union=union,
    )


def build_comparison_views(
    result: CompareResult,
) -> dict[str, tuple[str, list[str]]]:
    """Build the formatted views dict used by the interactive TUI."""
    left_name = result.left_path.name
    right_name = result.right_path.name
    views = {
        "left": (
            f"Only in LEFT ({left_name}): {len(result.only_left)} triples",
            result.only_left,
        ),
        "right": (
            f"Only in RIGHT ({right_name}): {len(result.only_right)} triples",
            result.only_right,
        ),
        "both": (f"Intersection (both): {len(result.both)} triples", result.both),
        "union": (f"Union (all): {len(result.union)} triples", result.union),
    }
    formatted: dict[str, tuple[str, list[str]]] = {}
    for key, (title, graph) in views.items():
        formatted[key] = (title, format_triples(graph))
    return formatted


def build_explore_views(
    graph: Graph,
    label: str = "Graph",
) -> dict[str, tuple[str, list[str]]]:
    """Build a single-view dict for exploring one graph in the TUI."""
    return {
        "both": (f"{label}: {len(graph)} triples", format_triples(graph)),
    }


def _prompt_input(stdscr: curses.window, prompt: str) -> str:
    """Prompt the user for text input at the bottom of the screen.

    Returns the entered text, or empty string if cancelled with Escape.
    """
    height, width = stdscr.getmaxyx()
    stdscr.addstr(height - 1, 0, prompt, curses.A_BOLD)
    stdscr.clrtoeol()
    stdscr.refresh()
    curses.curs_set(1)
    curses.echo()

    buf: list[str] = []
    while True:
        ch = stdscr.getch()
        if ch in (curses.KEY_ENTER, ord("\n"), ord("\r")):
            break
        if ch == _KEY_ESCAPE:
            buf.clear()
            break
        if ch in (curses.KEY_BACKSPACE, 127, ord("\b")):
            if buf:
                buf.pop()
        elif 0 <= ch < 256:  # noqa: PLR2004
            buf.append(chr(ch))
        # Redraw input
        text = "".join(buf)
        stdscr.move(height - 1, 0)
        stdscr.clrtoeol()
        stdscr.addnstr(height - 1, 0, f"{prompt}{text}", width - 1, curses.A_BOLD)
        stdscr.refresh()

    curses.noecho()
    curses.curs_set(0)
    return "".join(buf)


@dataclass
class _Filter:
    """A single regex filter."""

    pattern: re.Pattern[str]
    source_text: str  # original user input, for display


@dataclass
class _FilterState:
    """Manages an ordered list of active filters."""

    filters: list[_Filter] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return len(self.filters) > 0

    @property
    def multi(self) -> bool:
        return len(self.filters) > 1

    def apply(self, lines: list[str]) -> list[str]:
        """Apply all filters in order, returning matched lines."""
        result = lines
        for f in self.filters:
            result = [line for line in result if f.pattern.search(line)]
        return result

    def combined_pattern(self) -> re.Pattern[str] | None:
        """Build a combined pattern for highlighting all filter matches."""
        if not self.filters:
            return None
        combined = "|".join(
            f"(?:{f.pattern.pattern})" for f in self.filters
        )
        # Use the flags of the first filter as a reasonable default
        return re.compile(combined, self.filters[0].pattern.flags)

    def summary(self, total: int, matched: int) -> str:
        """Format a summary string for the header."""
        if not self.filters:
            return ""
        parts = "/".join(f.source_text for f in self.filters)
        return f" [/{parts}/ {matched}/{total} matched]"

    def set_single(self, filt: _Filter) -> None:
        """Replace all filters with a single one."""
        self.filters = [filt]

    def add(self, filt: _Filter) -> None:
        """Append a filter to the list."""
        self.filters.append(filt)

    def clear(self) -> None:
        self.filters.clear()

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.filters):
            self.filters.pop(index)

    def swap(self, i: int, j: int) -> None:
        """Swap two filters by index."""
        if 0 <= i < len(self.filters) and 0 <= j < len(self.filters):
            self.filters[i], self.filters[j] = (
                self.filters[j],
                self.filters[i],
            )

    def save(self, path: Path) -> None:
        """Save filter patterns to a text file, one per line."""
        path.write_text(
            "\n".join(f.source_text for f in self.filters) + "\n",
        )

    def load(self, path: Path) -> None:
        """Load filter patterns from a text file, one per line."""
        self.clear()
        for raw_line in path.read_text().splitlines():
            text = raw_line.strip()
            if text:
                filt = _compile_filter(text)
                if filt is not None:
                    self.filters.append(filt)


def _compile_filter(text: str) -> _Filter | None:
    """Compile user text into a Filter, or None on invalid regex."""
    try:
        # Smart-case: case-insensitive unless pattern has uppercase
        flags = 0 if text != text.lower() else re.IGNORECASE
        return _Filter(pattern=re.compile(text, flags), source_text=text)
    except re.error:
        return None


def _addstr_highlighted(  # noqa: PLR0913
    stdscr: curses.window,
    row: int,
    col: int,
    text: str,
    max_len: int,
    pattern: re.Pattern[str] | None,
    attr: int,
) -> None:
    """Write text to the screen, highlighting regex matches with attr."""
    text = text[:max_len]
    if pattern is None:
        stdscr.addnstr(row, col, text, max_len)
        return
    pos = 0
    cur_col = col
    for m in pattern.finditer(text):
        # Text before match
        if m.start() > pos:
            segment = text[pos:m.start()]
            stdscr.addstr(row, cur_col, segment)
            cur_col += len(segment)
        # Matched text
        matched = m.group()
        stdscr.addstr(row, cur_col, matched, attr)
        cur_col += len(matched)
        pos = m.end()
    # Remaining text after last match
    if pos < len(text):
        stdscr.addstr(row, cur_col, text[pos:])


def _render_filter_manager(  # noqa: PLR0913
    stdscr: curses.window,
    height: int,
    width: int,
    filters: _FilterState,
    cursor: int,
    cursor_attr: int,
) -> None:
    """Render the filter list manager view."""
    header = f" Active Filters: {len(filters.filters)} "
    stdscr.addstr(0, 0, header[:width - 1], curses.A_REVERSE)

    nav = "  / +filter  d delete  J/K move  S save  L load  Esc/f back  q quit"
    if len(nav) < width:
        stdscr.addstr(1, 0, nav[:width - 1], curses.A_DIM)

    content_start = 3
    for i, f in enumerate(filters.filters):
        row = content_start + i
        if row >= height - 1:
            break
        line = f"  {i + 1}. /{f.source_text}/"
        attr = cursor_attr if i == cursor else 0
        stdscr.addnstr(row, 0, line[:width - 1], width - 1, attr)


def _list_filter_files(directory: Path) -> list[Path]:
    """Return sorted .filters files in the given directory."""
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.filters"))


def _render_file_picker(  # noqa: PLR0913
    stdscr: curses.window,
    height: int,
    width: int,
    files: list[Path],
    cursor: int,
    scroll: int,
    cursor_attr: int,
) -> None:
    """Render a file picker view."""
    header = f" Load Filters: {len(files)} file(s) "
    stdscr.addstr(0, 0, header[:width - 1], curses.A_REVERSE)

    nav = "  Enter select  Esc cancel  j/k scroll  q quit"
    if len(nav) < width:
        stdscr.addstr(1, 0, nav[:width - 1], curses.A_DIM)

    content_start = 3
    content_height = height - content_start - 1

    if not files:
        stdscr.addstr(content_start, 2, "(no .filters files found)")
        return

    for i, path in enumerate(
        files[scroll : scroll + content_height],
    ):
        row = content_start + i
        idx = scroll + i
        if row < height - 1:
            line = f"  {path.name}"
            attr = cursor_attr if idx == cursor else 0
            stdscr.addnstr(row, 0, line[:width - 1], width - 1, attr)


def _unbind_namespace(graph: Graph, prefix: str) -> bool:
    """Remove a namespace binding from a graph's store.

    Uses Memory store internals since rdflib has no public unbind API.
    Returns True if the binding was removed.
    """
    store = graph.store
    try:
        ns_dict: dict[str, object] = getattr(store, "_Memory__namespace")  # noqa: B009
        pfx_dict: dict[object, str] = getattr(store, "_Memory__prefix")  # noqa: B009
    except AttributeError:
        return False
    uri = ns_dict.pop(prefix, None)
    if uri is not None:
        pfx_dict.pop(uri, None)
        graph.namespace_manager.reset()
        return True
    return False


def _render_namespace_view(  # noqa: PLR0913
    stdscr: curses.window,
    height: int,
    width: int,
    namespaces: list[tuple[str, str]],
    cursor: int,
    scroll: int,
    cursor_attr: int,
) -> None:
    """Render the namespace listing with cursor highlight."""
    header = f" Namespaces: {len(namespaces)} bindings "
    stdscr.addstr(0, 0, header[:width - 1], curses.A_REVERSE)

    nav = "  a add  e edit  d delete  n/Esc back  j/k scroll  q quit"
    if len(nav) < width:
        stdscr.addstr(1, 0, nav[:width - 1], curses.A_DIM)

    content_start = 3
    content_height = height - content_start - 1

    if not namespaces:
        stdscr.addstr(content_start, 2, "(no namespace bindings)")
        return

    max_prefix = max(len(p) for p, _ in namespaces)

    for i, (prefix, uri) in enumerate(
        namespaces[scroll : scroll + content_height],
    ):
        row = content_start + i
        idx = scroll + i
        if row < height - 1:
            line = f"  {prefix:<{max_prefix}}  \u2192  {uri}"
            attr = cursor_attr if idx == cursor else 0
            stdscr.addnstr(row, 0, line[:width - 1], width - 1, attr)

    if len(namespaces) > content_height:
        end = min(scroll + content_height, len(namespaces))
        pos_info = f" [{scroll + 1}-{end}/{len(namespaces)}] "
        if len(pos_info) < width:
            stdscr.addstr(height - 1, 0, pos_info[:width - 1], curses.A_DIM)


def interactive(
    stdscr: curses.window,
    views: dict[str, tuple[str, list[str]]],
    graphs: dict[str, Graph] | None = None,
) -> None:
    """Curses-based interactive triple browser.

    When *graphs* is provided (mapping view-key → Graph), the ``n`` key
    opens a namespace editor that lets the user add, edit, and delete
    prefix bindings.  Changes are reflected immediately in the triple
    display.
    """
    curses.use_default_colors()
    curses.curs_set(0)
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    highlight_attr = curses.color_pair(1) | curses.A_BOLD
    cursor_attr = curses.color_pair(2) | curses.A_BOLD
    stdscr.clear()

    current = "both"
    scroll = 0
    filter_state = _FilterState()

    # Namespace mode state
    ns_mode = False
    ns_cursor = 0
    ns_scroll = 0

    # Filter manager mode state
    fm_mode = False
    fm_cursor = 0

    # File picker mode state
    fp_mode = False
    fp_cursor = 0
    fp_scroll = 0
    fp_files: list[Path] = []

    # Directory for saving/loading filters (beside the project file or cwd)
    filters_dir = Path.cwd()

    # Auto-load default filters if the file exists
    default_filters_path = filters_dir / _DEFAULT_FILTERS_FILE
    if default_filters_path.is_file():
        filter_state.load(default_filters_path)

    def _auto_save_filters() -> None:
        """Persist current filters to .current.filters automatically."""
        if filter_state.active:
            filter_state.save(default_filters_path)
        elif default_filters_path.is_file():
            default_filters_path.unlink()

    def _get_namespaces() -> list[tuple[str, str]]:
        if graphs is None:
            return []
        graph = next(iter(graphs.values()))
        return sorted(
            ((str(p), str(ns)) for p, ns in graph.namespace_manager.namespaces()),
            key=lambda x: x[0],
        )

    def _rebuild_views() -> None:
        """Regenerate formatted triple lines from graphs after namespace edits."""
        if graphs is None:
            return
        for key, graph in graphs.items():
            if key in views:
                old_title = views[key][0]
                views[key] = (old_title, format_triples(graph))

    def _apply_to_all_graphs(
        fn: Callable[[Graph], object],
    ) -> None:
        if graphs is None:
            return
        for graph in graphs.values():
            fn(graph)

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        if ns_mode:
            namespaces = _get_namespaces()
            content_height = height - 4

            # Clamp cursor
            if namespaces:
                ns_cursor = max(0, min(ns_cursor, len(namespaces) - 1))
                # Auto-scroll to keep cursor visible
                if ns_cursor < ns_scroll:
                    ns_scroll = ns_cursor
                elif ns_cursor >= ns_scroll + content_height:
                    ns_scroll = ns_cursor - content_height + 1
                max_ns_scroll = max(0, len(namespaces) - content_height)
                ns_scroll = max(0, min(ns_scroll, max_ns_scroll))

            _render_namespace_view(
                stdscr, height, width,
                namespaces, ns_cursor, ns_scroll, cursor_attr,
            )
            stdscr.refresh()
            key = stdscr.getch()

            if key == ord("n") or key == _KEY_ESCAPE:  # back to triples
                ns_mode = False
            elif key == ord("q") or key == ord("Q"):
                break
            elif key == ord("j") or key == curses.KEY_DOWN:
                ns_cursor += 1
            elif key == ord("k") or key == curses.KEY_UP:
                ns_cursor = max(0, ns_cursor - 1)
            elif key == curses.KEY_NPAGE:
                ns_cursor += max(1, (height - 4) // 2)
            elif key == curses.KEY_PPAGE:
                ns_cursor -= max(1, (height - 4) // 2)
                ns_cursor = max(0, ns_cursor)
            elif key == ord("a"):
                prefix = _prompt_input(stdscr, "Prefix: ")
                if prefix:
                    uri = _prompt_input(stdscr, "URI: ")
                    if uri:
                        _apply_to_all_graphs(
                            lambda g, p=prefix, u=uri: g.bind(
                                p, u, override=True,
                            ),
                        )
                        _rebuild_views()
            elif key == ord("e") and namespaces:
                old_prefix, old_uri = namespaces[ns_cursor]
                new_prefix = _prompt_input(
                    stdscr, f"Prefix [{old_prefix}]: ",
                )
                new_uri = _prompt_input(
                    stdscr, f"URI [{old_uri}]: ",
                )
                final_prefix = new_prefix or old_prefix
                final_uri = new_uri or old_uri
                if final_prefix != old_prefix or final_uri != old_uri:
                    if final_prefix != old_prefix:
                        _apply_to_all_graphs(
                            lambda g, p=old_prefix: _unbind_namespace(g, p),
                        )
                    _apply_to_all_graphs(
                        lambda g, p=final_prefix, u=final_uri: g.bind(
                            p, u, override=True,
                        ),
                    )
                    _rebuild_views()
            elif key == ord("d") and namespaces:
                prefix, _uri = namespaces[ns_cursor]
                _apply_to_all_graphs(
                    lambda g, p=prefix: _unbind_namespace(g, p),
                )
                _rebuild_views()
                if ns_cursor >= len(_get_namespaces()):
                    ns_cursor = max(0, len(_get_namespaces()) - 1)
            continue

        if fm_mode:
            _render_filter_manager(
                stdscr, height, width,
                filter_state, fm_cursor, cursor_attr,
            )
            stdscr.refresh()
            key = stdscr.getch()

            if key == ord("f") or key == _KEY_ESCAPE:
                fm_mode = False
            elif key == ord("q") or key == ord("Q"):
                break
            elif key == ord("/"):
                text = _prompt_input(stdscr, "/")
                if text:
                    filt = _compile_filter(text)
                    if filt is not None:
                        filter_state.add(filt)
                        _auto_save_filters()
            elif key == ord("j") or key == curses.KEY_DOWN:
                fm_cursor = min(
                    fm_cursor + 1, len(filter_state.filters) - 1,
                )
            elif key == ord("k") or key == curses.KEY_UP:
                fm_cursor = max(0, fm_cursor - 1)
            elif key == ord("d") and filter_state.filters:
                filter_state.remove(fm_cursor)
                if fm_cursor >= len(filter_state.filters):
                    fm_cursor = max(0, len(filter_state.filters) - 1)
                _auto_save_filters()
                scroll = 0
            elif key == ord("J") and filter_state.filters:
                if fm_cursor < len(filter_state.filters) - 1:
                    filter_state.swap(fm_cursor, fm_cursor + 1)
                    fm_cursor += 1
                    _auto_save_filters()
            elif key == ord("K") and filter_state.filters and fm_cursor > 0:
                filter_state.swap(fm_cursor, fm_cursor - 1)
                fm_cursor -= 1
                _auto_save_filters()
            elif key == ord("S") and filter_state.active:
                name = _prompt_input(stdscr, "Save as (.filters): ")
                if name:
                    if not name.endswith(".filters"):
                        name += ".filters"
                    filter_state.save(filters_dir / name)
            elif key == ord("L"):
                fp_files = _list_filter_files(filters_dir)
                fp_mode = True
                fp_cursor = 0
                fp_scroll = 0
                fm_mode = False
            continue

        if fp_mode:
            content_height = height - 4
            if fp_files:
                fp_cursor = max(0, min(fp_cursor, len(fp_files) - 1))
                if fp_cursor < fp_scroll:
                    fp_scroll = fp_cursor
                elif fp_cursor >= fp_scroll + content_height:
                    fp_scroll = fp_cursor - content_height + 1

            _render_file_picker(
                stdscr, height, width,
                fp_files, fp_cursor, fp_scroll, cursor_attr,
            )
            stdscr.refresh()
            key = stdscr.getch()

            if key == _KEY_ESCAPE:
                fp_mode = False
            elif key == ord("q") or key == ord("Q"):
                break
            elif key == ord("j") or key == curses.KEY_DOWN:
                fp_cursor += 1
            elif key == ord("k") or key == curses.KEY_UP:
                fp_cursor = max(0, fp_cursor - 1)
            elif (
                key in (curses.KEY_ENTER, ord("\n"), ord("\r"))
                and fp_files
            ):
                filter_state.load(fp_files[fp_cursor])
                _auto_save_filters()
                fp_mode = False
                scroll = 0
            continue

        title, all_lines = views[current]
        lines = filter_state.apply(all_lines) if filter_state.active else all_lines
        highlight_pattern = filter_state.combined_pattern()

        # Header
        header = f" {title} "
        header += filter_state.summary(len(all_lines), len(lines))
        stdscr.addstr(0, 0, header[:width - 1], curses.A_REVERSE)

        nav_parts: list[str] = []
        view_keys = views.keys()
        if "both" in view_keys:
            nav_parts.append("↑ both")
        if "union" in view_keys:
            nav_parts.append("↓ union")
        if "left" in view_keys:
            nav_parts.append("← left-only")
        if "right" in view_keys:
            nav_parts.append("→ right-only")
        if graphs is not None:
            nav_parts.append("n namespaces")
        nav_parts.append("/ +filter  f filters  c clear")
        nav_parts.extend(["q quit", "j/k scroll"])
        nav = "  " + "  ".join(nav_parts)
        if len(nav) < width:
            stdscr.addstr(1, 0, nav[:width - 1], curses.A_DIM)

        # Content area
        content_start = 3
        content_height = height - content_start - 1

        if not lines:
            msg = "(no matches)" if filter_state.active else "(no triples)"
            stdscr.addstr(content_start, 2, msg)
        else:
            # Clamp scroll
            max_scroll = max(0, len(lines) - content_height)
            scroll = max(0, min(scroll, max_scroll))

            for i, line in enumerate(lines[scroll : scroll + content_height]):
                row = content_start + i
                if row < height - 1:
                    _addstr_highlighted(
                        stdscr, row, 1, line, width - 2,
                        highlight_pattern, highlight_attr,
                    )

            # Scroll indicator
            if len(lines) > content_height:
                end = min(scroll + content_height, len(lines))
                pos_info = f" [{scroll + 1}-{end}/{len(lines)}] "
                if len(pos_info) < width:
                    stdscr.addstr(
                        height - 1, 0,
                        pos_info[:width - 1], curses.A_DIM,
                    )

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == ord("Q"):
            break
        if key == ord("n") and graphs is not None:
            ns_mode = True
            ns_cursor = 0
            ns_scroll = 0
        elif key == ord("/"):
            text = _prompt_input(stdscr, "/")
            if text:
                filt = _compile_filter(text)
                if filt is not None:
                    filter_state.add(filt)
                    _auto_save_filters()
            else:
                # Empty / clears all filters
                filter_state.clear()
                _auto_save_filters()
            scroll = 0
        elif key == ord("f"):
            fm_mode = True
            fm_cursor = 0
        elif key == ord("c") or key == _KEY_ESCAPE:
            filter_state.clear()
            _auto_save_filters()
            scroll = 0
        elif key == curses.KEY_UP:
            if "both" in views:
                current = "both"
                scroll = 0
        elif key == curses.KEY_DOWN:
            if "union" in views:
                current = "union"
                scroll = 0
        elif key == curses.KEY_LEFT:
            if "left" in views:
                current = "left"
                scroll = 0
        elif key == curses.KEY_RIGHT:
            if "right" in views:
                current = "right"
            scroll = 0
        elif key == ord("j") or key == curses.KEY_NPAGE:
            scroll += max(1, content_height // 2)
        elif key == ord("k") or key == curses.KEY_PPAGE:
            scroll -= max(1, content_height // 2)
