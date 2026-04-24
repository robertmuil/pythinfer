"""Provide functionality to explore and compare two RDF graphs.

Compute intersection, differences, and browse interactively.
"""
import curses
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


def interactive(stdscr: curses.window, views: dict[str, tuple[str, list[str]]]) -> None:
    """Curses-based interactive triple browser."""
    curses.use_default_colors()
    curses.curs_set(0)
    stdscr.clear()

    current = "both"
    scroll = 0

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        title, lines = views[current]

        # Header
        header = f" {title} "
        stdscr.addstr(0, 0, header[:width - 1], curses.A_REVERSE)

        nav = "  ↑ both  ↓ union  ← left-only  → right-only  q quit  j/k scroll"
        if len(nav) < width:
            stdscr.addstr(1, 0, nav[:width - 1], curses.A_DIM)

        # Content area
        content_start = 3
        content_height = height - content_start - 1

        if not lines:
            stdscr.addstr(content_start, 2, "(no triples)")
        else:
            # Clamp scroll
            max_scroll = max(0, len(lines) - content_height)
            scroll = max(0, min(scroll, max_scroll))

            for i, line in enumerate(lines[scroll : scroll + content_height]):
                row = content_start + i
                if row < height - 1:
                    stdscr.addnstr(row, 1, line, width - 2)

            # Scroll indicator
            if len(lines) > content_height:
                pos_info = f" [{scroll + 1}-{min(scroll + content_height, len(lines))}/{len(lines)}] "
                if len(pos_info) < width:
                    stdscr.addstr(height - 1, 0, pos_info[:width - 1], curses.A_DIM)

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q") or key == ord("Q"):
            break
        if key == curses.KEY_UP:
            current = "both"
            scroll = 0
        elif key == curses.KEY_DOWN:
            current = "union"
            scroll = 0
        elif key == curses.KEY_LEFT:
            current = "left"
            scroll = 0
        elif key == curses.KEY_RIGHT:
            current = "right"
            scroll = 0
        elif key == ord("j") or key == curses.KEY_NPAGE:
            scroll += max(1, content_height // 2)
        elif key == ord("k") or key == curses.KEY_PPAGE:
            scroll -= max(1, content_height // 2)
