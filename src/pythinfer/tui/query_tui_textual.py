"""Interactive SPARQL query TUI built on Textual.

Provides a split-pane interface with a SPARQL query editor and a results
table with frozen column headers, horizontal scrolling, and no line
wrapping.  Uses textual-textarea for the editor (VS Code-like bindings,
undo/redo, Pygments-based SPARQL syntax highlighting).
"""

from __future__ import annotations

from pathlib import Path

import tree_sitter_sparql as _ts_sparql  # type: ignore[import-untyped]
from rdflib import Dataset
from rdflib.query import Result
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    OptionList,
    TextArea,
)
from textual_textarea import TextEditor
from tree_sitter import Language as TSLanguage  # type: ignore[import-untyped]

_SPARQL_LANGUAGE = TSLanguage(_ts_sparql.language())

_SPARQL_HIGHLIGHTS = """
(comment) @comment
(var) @variable
(pn_prefix) @type
(pn_local) @tag
(rdf_literal) @string
(integer) @number
(decimal) @number
(double) @number
(boolean_literal) @constant.builtin

["SELECT" "DISTINCT" "REDUCED" "AS" "WHERE"
 "CONSTRUCT" "DESCRIBE" "ASK"
 "FROM" "NAMED" "GRAPH"
 "GROUP" "BY" "ORDER" "ASC" "DESC"
 "HAVING" "LIMIT" "OFFSET"
 "OPTIONAL" "UNION" "MINUS" "FILTER"
 "BIND" "VALUES" "SERVICE"
 "INSERT" "DELETE" "BASE" "PREFIX"
 "IN" "NOT" "EXISTS"
 "a"] @keyword

["BOUND" "BNODE" "IF" "COALESCE" "NOW" "RAND"
 "STRUUID" "UUID" "ABS" "CEIL" "FLOOR" "ROUND"
 "CONCAT" "STRLEN" "UCASE" "LCASE" "CONTAINS"
 "STRSTARTS" "STRENDS" "STRBEFORE" "STRAFTER"
 "STRDT" "STRLANG" "STR" "LANG" "LANGMATCHES"
 "DATATYPE" "IRI" "URI" "ENCODE_FOR_URI" "REGEX" "REPLACE"
 "YEAR" "MONTH" "DAY" "HOURS" "MINUTES" "SECONDS"
 "TIMEZONE" "TZ" "MD5" "SHA1" "SHA256" "SHA384" "SHA512"
 "COUNT" "SUM" "AVG" "MIN" "MAX" "GROUP_CONCAT" "SAMPLE"
 "isIRI" "isURI" "isBLANK" "isLITERAL" "isNUMERIC"
 "sameTerm"] @function.builtin
"""

_DEFAULT_QUERY = """\
SELECT ?s ?p ?o
WHERE {
    ?s ?p ?o .
}
LIMIT 20"""


# ---------------------------------------------------------------------------
# File picker modal
# ---------------------------------------------------------------------------


class _FilePickerScreen(ModalScreen[Path | None]):
    """Modal dialog to pick a .rq file."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, files: list[Path], base_dir: Path) -> None:
        super().__init__()
        self._files = files
        self._base_dir = base_dir

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker"):
            yield Label("Select a .rq file:")
            yield OptionList(
                *[
                    self._label_for(f)
                    for f in self._files
                ],
                id="file-list",
            )

    def _label_for(self, f: Path) -> str:
        try:
            return str(f.relative_to(self._base_dir))
        except ValueError:
            return str(f)

    @on(OptionList.OptionSelected, "#file-list")
    def _on_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self._files[event.option_index])

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Save dialog modal
# ---------------------------------------------------------------------------


class _SaveDialog(ModalScreen[str | None]):
    """Modal dialog to enter a filename for saving."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, default: str) -> None:
        super().__init__()
        self._default = default

    def compose(self) -> ComposeResult:
        with Vertical(id="save-dialog"):
            yield Label("Filename:")
            yield TextArea(self._default, id="save-input")

    @on(TextArea.Changed, "#save-input")
    def _on_change(self, event: TextArea.Changed) -> None:
        # Submit on Enter (single-line: newline means submit)
        if "\n" in event.text_area.text:
            name = event.text_area.text.strip()
            if name:
                self.dismiss(name)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Main TUI App
# ---------------------------------------------------------------------------


class QueryApp(App[None], inherit_bindings=False):
    """Interactive SPARQL query TUI."""

    CSS = """
    #query-area {
        height: 1fr;
    }
    #results-area {
        height: 1fr;
    }
    #results-table {
        height: 1fr;
    }
    #results-text {
        height: 1fr;
    }
    #file-picker, #save-dialog {
        width: 60;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("ctrl+e", "execute", "Execute", priority=True),
        Binding("ctrl+l", "load", "Load", priority=True),
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("f6", "focus_next", "Next pane"),
    ]

    def __init__(
        self,
        ds: Dataset,
        num_triples: int,
        project_dir: Path,
    ) -> None:
        super().__init__()
        self._ds = ds
        self._num_triples = num_triples
        self._project_dir = project_dir
        self._current_file: Path | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield TextEditor(
            text=_DEFAULT_QUERY,
            id="query-area",
        )
        with Vertical(id="results-area"):
            yield DataTable(id="results-table")
            yield TextArea(
                "(press Ctrl+E to execute query)",
                read_only=True,
                id="results-text",
            )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.display = False
        self.title = "pythinfer query"
        self.sub_title = "[unsaved]"

        # Register SPARQL language for syntax highlighting
        editor = self.query_one("#query-area", TextEditor)
        editor.text_input.register_language(
            "sparql", _SPARQL_LANGUAGE, _SPARQL_HIGHLIGHTS,
        )
        editor.language = "sparql"

    # -- Actions ------------------------------------------------------------

    def action_execute(self) -> None:
        query_area = self.query_one("#query-area", TextEditor)
        query_text = query_area.text.strip()
        if not query_text:
            self._show_text("(empty query)")
            return
        try:
            result = self._ds.query(query_text)
            self._display_result(result)
        except Exception as e:  # noqa: BLE001
            self._show_text(f"Error: {e}")

    def action_load(self) -> None:
        files = sorted(self._project_dir.rglob("*.rq"))
        if not files:
            self._show_text("(no .rq files found)")
            return

        def _on_pick(path: Path | None) -> None:
            if path is not None:
                query_area = self.query_one("#query-area", TextEditor)
                query_area.text = path.read_text()
                self._current_file = path
                self.sub_title = f"[{path.name}]"
                self._show_text(f"Loaded: {path.name}")

        self.push_screen(
            _FilePickerScreen(files, self._project_dir),
            callback=_on_pick,
        )

    def action_save(self) -> None:
        default = (
            self._current_file.name if self._current_file else "query.rq"
        )

        def _on_save(name: str | None) -> None:
            if name:
                query_area = self.query_one("#query-area", TextEditor)
                path = self._project_dir / name
                path.write_text(query_area.text + "\n")
                self._current_file = path
                self.sub_title = f"[{path.name}]"
                self._show_text(f"Saved: {path}")

        self.push_screen(_SaveDialog(default), callback=_on_save)

    # -- Result display -----------------------------------------------------

    def _display_result(self, result: Result) -> None:
        if result.type == "SELECT":
            self._display_select(result)
        elif result.type in ("CONSTRUCT", "DESCRIBE"):
            self._display_construct(result)
        elif result.type == "ASK":
            self._show_text(str(result.askAnswer))
        else:
            self._show_text(f"(unknown result type: {result.type})")

    def _display_select(self, result: Result) -> None:
        table = self.query_one("#results-table", DataTable)
        text_area = self.query_one("#results-text", TextArea)
        ns = self._ds.namespace_manager

        if not result.vars:
            self._show_text("(no variables in result)")
            return

        # Show table, hide text
        table.display = True
        text_area.display = False

        table.clear(columns=True)
        for var in result.vars:
            table.add_column(str(var), key=str(var))

        row_count = 0
        for binding in result.bindings:
            row = []
            for var in result.vars:
                val = binding.get(var)
                row.append(val.n3(ns) if val is not None else "")
            table.add_row(*row)
            row_count += 1

        self.sub_title = (
            f"{self.sub_title.split('│')[0].strip()}"
            f"  │  {row_count} row{'s' if row_count != 1 else ''}"
        )

    def _display_construct(self, result: Result) -> None:
        ns = self._ds.namespace_manager
        if not result.graph or len(result.graph) == 0:
            self._show_text("(no triples returned)")
            return
        for prefix, namespace in ns.namespaces():
            result.graph.bind(prefix, namespace)
        self._show_text(result.graph.serialize(format="turtle"))

    def _show_text(self, text: str) -> None:
        """Show plain text in the results area, hiding the table."""
        table = self.query_one("#results-table", DataTable)
        text_area = self.query_one("#results-text", TextArea)
        table.display = False
        text_area.display = True
        text_area.load_text(text)


def interactive_query_textual(
    ds: Dataset,
    num_triples: int,
    project_dir: Path,
) -> None:
    """Launch the Textual-based interactive query TUI."""
    app = QueryApp(ds, num_triples, project_dir)
    app.run()
