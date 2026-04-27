"""Provide functionality to explore and compare two RDF graphs.

Compute intersection, differences, and browse interactively.
"""
import curses
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, Node
from rdflib.namespace import NamespaceManager

_KEY_ESCAPE = 27


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


def build_interactive_views(
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


def _prompt_search(stdscr: curses.window) -> str:
    """Prompt the user for a search pattern at the bottom of the screen."""
    return _prompt_input(stdscr, "/")


def _filter_lines(
    lines: list[str], pattern: re.Pattern[str] | None,
) -> list[str]:
    """Return lines matching the compiled regex, or all lines if no pattern."""
    if pattern is None:
        return lines
    return [line for line in lines if pattern.search(line)]


def _addstr_highlighted(
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
    search_pattern: re.Pattern[str] | None = None

    # Namespace mode state
    ns_mode = False
    ns_cursor = 0
    ns_scroll = 0

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
                            lambda g, p=prefix, u=uri: g.bind(p, u, override=True),
                        )
                        _rebuild_views()
            elif key == ord("e") and namespaces:
                old_prefix, old_uri = namespaces[ns_cursor]
                new_prefix = _prompt_input(stdscr, f"Prefix [{old_prefix}]: ")
                new_uri = _prompt_input(stdscr, f"URI [{old_uri}]: ")
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

        title, all_lines = views[current]
        lines = _filter_lines(all_lines, search_pattern)

        # Header
        header = f" {title} "
        if search_pattern is not None:
            header += (
                f" [/{search_pattern.pattern}/ "
                f"{len(lines)}/{len(all_lines)} matched]"
            )
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
        nav_parts.extend(["/ search", "Esc clear", "q quit", "j/k scroll"])
        nav = "  " + "  ".join(nav_parts)
        if len(nav) < width:
            stdscr.addstr(1, 0, nav[:width - 1], curses.A_DIM)

        # Content area
        content_start = 3
        content_height = height - content_start - 1

        if not lines:
            msg = "(no matches)" if search_pattern else "(no triples)"
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
                        search_pattern, highlight_attr,
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
            text = _prompt_search(stdscr)
            if text:
                try:
                    # Smart-case: case-insensitive unless pattern has uppercase
                    flags = 0 if text != text.lower() else re.IGNORECASE
                    search_pattern = re.compile(text, flags)
                except re.error:
                    search_pattern = None
            else:
                search_pattern = None
            scroll = 0
        elif key == _KEY_ESCAPE:  # Escape — clear search
            search_pattern = None
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
