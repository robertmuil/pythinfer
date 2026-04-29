"""Interactive SPARQL query TUI built on prompt_toolkit.

Provides vim keybindings, SPARQL syntax highlighting, and autocompletion.
Falls back to the curses-based TUI (query_tui.py) when prompt_toolkit
is not installed.
"""

from __future__ import annotations
from prompt_toolkit.enums import EditingMode

from pathlib import Path

from prompt_toolkit import Application
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import vi_navigation_mode
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import (
    Float,
    FloatContainer,
    HSplit,
    Window,
)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.widgets import Frame, TextArea
from pygments.lexers import (
    # These are dynamically generated namespaces so static checkers can't find them
    SparqlLexer,  # pyright: ignore[reportAttributeAccessIssue] # ty:ignore[unresolved-import]
)
from rdflib import Dataset
from rdflib.namespace import NamespaceManager
from rdflib.query import Result

_DEFAULT_QUERY = """\
SELECT ?s ?p ?o
WHERE {
    ?s ?p ?o .
}
LIMIT 20"""


# ---------------------------------------------------------------------------
# SPARQL autocompletion
# ---------------------------------------------------------------------------

# Common SPARQL keywords
_SPARQL_KEYWORDS = [
    "ASK",
    "BASE",
    "BIND",
    "CONSTRUCT",
    "DESCRIBE",
    "DISTINCT",
    "FILTER",
    "FROM",
    "GRAPH",
    "GROUP BY",
    "HAVING",
    "INSERT",
    "LIMIT",
    "MINUS",
    "OFFSET",
    "OPTIONAL",
    "ORDER BY",
    "PREFIX",
    "REDUCED",
    "SELECT",
    "SERVICE",
    "UNION",
    "VALUES",
    "WHERE",
    "DELETE",
    "ASC",
    "DESC",
    "AS",
    "IN",
    "NOT",
    "EXISTS",
    "BOUND",
    "COALESCE",
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "GROUP_CONCAT",
    "SAMPLE",
    "STR",
    "LANG",
    "LANGMATCHES",
    "DATATYPE",
    "IRI",
    "URI",
    "BNODE",
    "RAND",
    "ABS",
    "CEIL",
    "FLOOR",
    "ROUND",
    "CONCAT",
    "STRLEN",
    "UCASE",
    "LCASE",
    "CONTAINS",
    "STRSTARTS",
    "STRENDS",
    "SUBSTR",
    "REPLACE",
    "REGEX",
    "IF",
    "STRLANG",
    "STRDT",
    "isIRI",
    "isURI",
    "isBLANK",
    "isLITERAL",
    "isNUMERIC",
    "YEAR",
    "MONTH",
    "DAY",
    "HOURS",
    "MINUTES",
    "SECONDS",
    "TIMEZONE",
    "NOW",
    "UUID",
    "STRUUID",
    "MD5",
    "SHA1",
    "SHA256",
    "SHA384",
    "SHA512",
    "ENCODE_FOR_URI",
]


class SparqlCompleter(Completer):
    """Complete SPARQL keywords and known namespace prefixes."""

    def __init__(self, namespace_manager: NamespaceManager) -> None:
        self._prefixes: list[str] = []
        self._prefix_uris: dict[str, str] = {}
        for prefix, ns in namespace_manager.namespaces():
            p = str(prefix)
            if p:
                self._prefixes.append(f"{p}:")
                self._prefix_uris[p] = str(ns)

    def get_completions(
        self, document: Document, complete_event: object,
    ) -> list[Completion]:
        word = document.get_word_before_cursor(WORD=True)
        if not word:
            return []

        word_upper = word.upper()
        results: list[Completion] = []

        # SPARQL keywords (case-insensitive match)
        for kw in _SPARQL_KEYWORDS:
            if kw.startswith(word_upper):
                results.append(Completion(kw, start_position=-len(word)))

        # Prefix completions
        for p in self._prefixes:
            if p.lower().startswith(word.lower()):
                results.append(Completion(p, start_position=-len(word)))

        return results


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------


def _format_result(
    result: Result, namespace_manager: NamespaceManager,
) -> tuple[str, str]:
    """Format a query result as (frozen_header, scrollable_data)."""
    if result.type == "SELECT":
        return _format_select(result, namespace_manager)
    if result.type in ("CONSTRUCT", "DESCRIBE"):
        return "", _format_construct(result, namespace_manager)
    if result.type == "ASK":
        return "", str(result.askAnswer)
    return "", f"(unknown result type: {result.type})"


def _format_select(
    result: Result, namespace_manager: NamespaceManager,
) -> tuple[str, str]:
    if not result.vars:
        return "", "(no variables in result)"

    headers = [str(v) for v in result.vars]
    rows: list[list[str]] = []
    for binding in result.bindings:
        row = []
        for var in result.vars:
            val = binding.get(var)
            row.append(val.n3(namespace_manager) if val is not None else "")
        rows.append(row)

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    sep = " | "
    header_line = sep.join(h.ljust(w) for h, w in zip(headers, col_widths))
    divider = "-+-".join("-" * w for w in col_widths)
    data_lines = [
        sep.join(c.ljust(w) for c, w in zip(row, col_widths))
        for row in rows
    ]
    count = f"({len(rows)} row{'s' if len(rows) != 1 else ''})"
    frozen = "\n".join([header_line, divider])
    data = "\n".join([*data_lines, count])
    return frozen, data


def _format_construct(
    result: Result, namespace_manager: NamespaceManager,
) -> str:
    if not result.graph or len(result.graph) == 0:
        return "(no triples returned)"
    for prefix, namespace in namespace_manager.namespaces():
        result.graph.bind(prefix, namespace)
    return result.graph.serialize(format="turtle")


# ---------------------------------------------------------------------------
# File picker (simple prompt_toolkit dialog)
# ---------------------------------------------------------------------------


def _pick_file(
    files: list[Path], base_dir: Path,
) -> Path | None:
    """Simple file picker using prompt_toolkit."""
    if not files:
        return None

    from prompt_toolkit.shortcuts import radiolist_dialog

    choices = []
    for f in files:
        try:
            label = str(f.relative_to(base_dir))
        except ValueError:
            label = str(f)
        choices.append((f, label))

    return radiolist_dialog(
        title="Load Query",
        text="Select a .rq file:",
        values=choices,
    ).run()


# ---------------------------------------------------------------------------
# Main TUI application
# ---------------------------------------------------------------------------


def interactive_query_pt(
    ds: Dataset,
    num_triples: int,
    project_dir: Path,
) -> None:
    """Launch the prompt_toolkit-based interactive query TUI."""
    completer = SparqlCompleter(ds.namespace_manager)

    # Query editor with SPARQL highlighting and vim bindings
    query_area = TextArea(
        text=_DEFAULT_QUERY,
        multiline=True,
        scrollbar=True,
        wrap_lines=False,
        lexer=PygmentsLexer(SparqlLexer),
        completer=completer,
        focusable=True,
        focus_on_click=True,
    )

    # Results: frozen column header + scrollable data
    result_header_control = FormattedTextControl(text="")
    result_header_window = Window(
        content=result_header_control,
        height=0,
        wrap_lines=False,
        style="bold",
    )

    result_data_area = TextArea(
        text="(press Ctrl-E to execute query)",
        multiline=True,
        scrollbar=True,
        wrap_lines=False,
        read_only=True,
        focusable=True,
        focus_on_click=True,
    )

    # Track current file
    current_file: list[Path | None] = [None]  # mutable container

    # Status bar
    def _get_status_text() -> str:
        file_label = (
            f"[{current_file[0].name}]"
            if current_file[0]
            else "[unsaved]"
        )
        return (
            f" pythinfer query {file_label}"
            "  │  Ctrl-E:exec  Ctrl-L:load"
            "  Ctrl-S:save  Tab:switch  Ctrl-C:quit"
        )

    status_bar = FormattedTextControl(
        lambda: _get_status_text(),
    )

    # Layout
    results_container = HSplit([
        result_header_window,
        result_data_area,
    ])

    body = HSplit([
        Window(content=status_bar, height=1, style="reverse"),
        Frame(query_area, title="Query"),
        Frame(results_container, title="Results"),
    ])

    layout = Layout(
        FloatContainer(
            content=body,
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(max_height=12, scroll_offset=1),
                ),
            ],
        ),
        focused_element=query_area,
    )

    # Key bindings
    kb = KeyBindings()

    def _set_result(frozen: str, data: str) -> None:
        """Update the result panes with frozen header and scrollable data."""
        if frozen:
            result_header_control.text = frozen
            result_header_window.height = frozen.count("\n") + 1
        else:
            result_header_control.text = ""
            result_header_window.height = 0
        result_data_area.text = data

    @kb.add("c-e")
    def _execute(event: object) -> None:
        query_text = query_area.text.strip()
        if not query_text:
            _set_result("", "(empty query)")
            return
        try:
            result = ds.query(query_text)
            frozen, data = _format_result(
                result, ds.namespace_manager,
            )
            _set_result(frozen, data)
        except Exception as e:  # noqa: BLE001
            _set_result("", f"Error: {e}")

    @kb.add("tab")
    def _focus_next(event: object) -> None:
        event.app.layout.focus_next()  # type: ignore[union-attr]

    @kb.add("s-tab")
    def _focus_prev(event: object) -> None:
        event.app.layout.focus_previous()  # type: ignore[union-attr]

    @kb.add("c-c")
    def _quit(event: object) -> None:
        event.app.exit()  # type: ignore[union-attr]

    @kb.add("q", filter=vi_navigation_mode)
    def _quit_q(event: object) -> None:
        event.app.exit()  # type: ignore[union-attr]

    @kb.add("c-l")
    async def _load(event: object) -> None:
        files = sorted(project_dir.rglob("*.rq"))
        if not files:
            _set_result("", "(no .rq files found)")
            return
        path = await run_in_terminal(
            lambda: _pick_file(files, project_dir),
            in_executor=True,
        )
        if path is not None:
            query_area.text = path.read_text()
            current_file[0] = path
            _set_result("", f"Loaded: {path.name}")

    @kb.add("c-s")
    async def _save(event: object) -> None:
        from prompt_toolkit.shortcuts import input_dialog

        default = (
            current_file[0].name if current_file[0] else "query.rq"
        )
        name = await run_in_terminal(
            lambda: input_dialog(
                title="Save Query",
                text="Filename:",
                default=default,
            ).run(),
            in_executor=True,
        )
        if name:
            path = project_dir / name
            path.write_text(query_area.text + "\n")
            current_file[0] = path
            _set_result("", f"Saved: {path}")

    app: Application[None] = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        mouse_support=True,
        editing_mode=EditingMode.VI,
    )
    app.run()
