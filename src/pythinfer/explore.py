"""Provide functionality to explore and compare two RDF graphs.

Compute intersection, differences, and browse interactively.
"""
import curses
import re
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, Node
from rdflib.namespace import NamespaceManager


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


def _prompt_search(stdscr: curses.window) -> str:
    """Prompt the user for a search pattern at the bottom of the screen."""
    height, width = stdscr.getmaxyx()
    prompt = "/"
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
        if ch == 27:  # Escape
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
        stdscr.addnstr(height - 1, 0, f"/{text}", width - 1, curses.A_BOLD)
        stdscr.refresh()

    curses.noecho()
    curses.curs_set(0)
    return "".join(buf)


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


def interactive(stdscr: curses.window, views: dict[str, tuple[str, list[str]]]) -> None:
    """Curses-based interactive triple browser."""
    curses.use_default_colors()
    curses.curs_set(0)
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    highlight_attr = curses.color_pair(1) | curses.A_BOLD
    stdscr.clear()

    current = "both"
    scroll = 0
    search_pattern: re.Pattern[str] | None = None

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

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
        if key == ord("/"):
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
        elif key == 27:  # Escape — clear search
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
