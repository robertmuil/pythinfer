"""Interactive TUI for loading, editing, saving, and executing SPARQL queries.

Provides a curses-based interface with a query editor pane and a results pane.
"""

import contextlib
import curses
import textwrap
from pathlib import Path

from rdflib import Dataset
from rdflib.namespace import NamespaceManager
from rdflib.query import Result

_KEY_ESCAPE = 27

_DEFAULT_QUERY = textwrap.dedent("""\
    SELECT ?s ?p ?o
    WHERE {
        ?s ?p ?o .
    }
    LIMIT 20
""")


def _list_query_files(directory: Path) -> list[Path]:
    """Return sorted .rq files in the given directory (recursive)."""
    if not directory.is_dir():
        return []
    return sorted(directory.rglob("*.rq"))


def _prompt_input(stdscr: curses.window, prompt: str, default: str = "") -> str:
    """Prompt for text input at the bottom of the screen."""
    height, width = stdscr.getmaxyx()
    buf: list[str] = list(default)
    stdscr.move(height - 1, 0)
    stdscr.clrtoeol()
    text = "".join(buf)
    stdscr.addnstr(height - 1, 0, f"{prompt}{text}", width - 1, curses.A_BOLD)
    stdscr.refresh()
    curses.curs_set(1)
    curses.echo()

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
        text = "".join(buf)
        stdscr.move(height - 1, 0)
        stdscr.clrtoeol()
        stdscr.addnstr(height - 1, 0, f"{prompt}{text}", width - 1, curses.A_BOLD)
        stdscr.refresh()

    curses.noecho()
    curses.curs_set(0)
    return "".join(buf)


def _format_select_result(
    result: Result, namespace_manager: NamespaceManager,
) -> tuple[list[str], list[str]]:
    """Format a SELECT result as (frozen_header_lines, scrollable_data_lines)."""
    if not result.vars:
        return [], ["(no variables in result)"]

    headers = [str(v) for v in result.vars]
    rows: list[list[str]] = []
    for binding in result.bindings:
        row = []
        for var in result.vars:
            val = binding.get(var)
            row.append(val.n3(namespace_manager) if val is not None else "")
        rows.append(row)

    # Compute column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    # Build lines
    sep = " | "
    header_line = sep.join(h.ljust(w) for h, w in zip(headers, col_widths))

    frozen = [header_line]
    data: list[str] = []
    for row in rows:
        data.append(sep.join(c.ljust(w) for c, w in zip(row, col_widths)))
    data.append(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")
    return frozen, data


def _format_construct_result(
    result: Result, namespace_manager: NamespaceManager,
) -> list[str]:
    """Format a CONSTRUCT/DESCRIBE result as lines of text."""
    if not result.graph or len(result.graph) == 0:
        return ["(no triples returned)"]
    for prefix, namespace in namespace_manager.namespaces():
        result.graph.bind(prefix, namespace)
    return result.graph.serialize(format="turtle").splitlines()


def _format_ask_result(result: Result) -> list[str]:
    return [str(result.askAnswer)]


def _format_result(
    result: Result, namespace_manager: NamespaceManager,
) -> tuple[list[str], list[str]]:
    """Format any query result as (frozen_header_lines, scrollable_lines)."""
    if result.type == "SELECT":
        return _format_select_result(result, namespace_manager)
    if result.type in ("CONSTRUCT", "DESCRIBE"):
        return [], _format_construct_result(result, namespace_manager)
    if result.type == "ASK":
        return [], _format_ask_result(result)
    return [], [f"(unknown result type: {result.type})"]


def _render_editor(  # noqa: PLR0913
    stdscr: curses.window,
    editor_lines: list[str],
    cursor_row: int,
    cursor_col: int,
    scroll: int,
    top: int,
    height: int,
    width: int,
    *,
    active: bool,
) -> None:
    """Render the query editor pane."""
    attr = curses.A_REVERSE if active else curses.A_DIM
    header = " QUERY (Tab:switch  Enter:newline  Ctrl-E:execute) "
    stdscr.addnstr(top, 0, header.ljust(width), width - 1, attr)

    for i in range(height):
        row = top + 1 + i
        line_idx = scroll + i
        if row >= stdscr.getmaxyx()[0] - 1:
            break
        stdscr.move(row, 0)
        stdscr.clrtoeol()
        if line_idx < len(editor_lines):
            line = editor_lines[line_idx]
            # Show line number
            gutter = f"{line_idx + 1:3d} "
            stdscr.addnstr(row, 0, gutter, width - 1, curses.A_DIM)
            stdscr.addnstr(row, len(gutter), line[:width - len(gutter) - 1],
                           width - len(gutter) - 1)


def _render_results(  # noqa: PLR0913
    stdscr: curses.window,
    frozen_lines: list[str],
    result_lines: list[str],
    result_scroll: int,
    top: int,
    height: int,
    width: int,
    status: str,
    *,
    active: bool,
    frozen_attr: int = curses.A_BOLD,
) -> None:
    """Render the results pane with frozen header lines that don't scroll."""
    attr = curses.A_REVERSE if active else curses.A_DIM
    header = f" RESULTS: {status} "
    stdscr.addnstr(top, 0, header.ljust(width), width - 1, attr)

    # Render frozen header lines (column headers)
    frozen_rows = 0
    for i, line in enumerate(frozen_lines):
        row = top + 1 + i
        if row >= stdscr.getmaxyx()[0] - 1:
            break
        stdscr.move(row, 0)
        stdscr.clrtoeol()
        stdscr.addnstr(row, 1, line[:width - 2], width - 2, frozen_attr)
        frozen_rows += 1

    # Render scrollable data lines below the frozen header
    scroll_height = height - frozen_rows
    for i in range(scroll_height):
        row = top + 1 + frozen_rows + i
        line_idx = result_scroll + i
        if row >= stdscr.getmaxyx()[0] - 1:
            break
        stdscr.move(row, 0)
        stdscr.clrtoeol()
        if line_idx < len(result_lines):
            stdscr.addnstr(row, 1, result_lines[line_idx][:width - 2],
                           width - 2)

    if len(result_lines) > scroll_height:
        end = min(result_scroll + scroll_height, len(result_lines))
        pos = f" [{result_scroll + 1}-{end}/{len(result_lines)}] "
        bot = top + height + 1
        if bot < stdscr.getmaxyx()[0] and len(pos) < width:
            stdscr.addnstr(bot, 0, pos, width - 1, curses.A_DIM)


def _render_file_picker(  # noqa: PLR0913
    stdscr: curses.window,
    height: int,
    width: int,
    files: list[Path],
    cursor: int,
    scroll: int,
    cursor_attr: int,
    base_dir: Path,
) -> None:
    """Render a file picker for .rq files."""
    header = f" Load Query: {len(files)} file(s) "
    stdscr.addnstr(0, 0, header.ljust(width), width - 1, curses.A_REVERSE)

    nav = "  Enter select  Esc cancel  j/k scroll  q quit"
    if len(nav) < width:
        stdscr.addnstr(1, 0, nav[:width - 1], width - 1, curses.A_DIM)

    content_start = 3
    content_height = height - content_start - 1

    if not files:
        stdscr.addnstr(content_start, 2, "(no .rq files found)", width - 3)
        return

    for i, path in enumerate(files[scroll:scroll + content_height]):
        row = content_start + i
        idx = scroll + i
        if row < height - 1:
            try:
                rel = path.relative_to(base_dir)
            except ValueError:
                rel = path
            line = f"  {rel}"
            attr = cursor_attr if idx == cursor else 0
            stdscr.addnstr(row, 0, line[:width - 1], width - 1, attr)


def interactive_query(
    stdscr: curses.window,
    ds: Dataset,
    num_triples: int,
    project_dir: Path,
) -> None:
    """Curses-based interactive SPARQL query editor and executor."""
    curses.use_default_colors()
    curses.curs_set(1)
    # Allow Ctrl-C to be read as key code 3 instead of raising KeyboardInterrupt
    curses.raw()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_RED, -1)
    curses.init_pair(4, curses.COLOR_CYAN, -1)
    cursor_attr = curses.color_pair(2) | curses.A_BOLD
    col_header_attr = curses.color_pair(4) | curses.A_BOLD

    # Editor state
    editor_lines: list[str] = _DEFAULT_QUERY.splitlines()
    cursor_row = 0
    cursor_col = 0
    editor_scroll = 0
    current_file: Path | None = None

    # Results state
    result_frozen: list[str] = []
    result_lines: list[str] = ["(press F5 or Ctrl-E to execute query)"]
    result_status = "ready"
    result_scroll = 0

    # Focus: True = editor, False = results
    editor_focus = True

    # File picker state
    fp_mode = False
    fp_cursor = 0
    fp_scroll = 0
    fp_files: list[Path] = []

    def _execute_query() -> None:
        nonlocal result_frozen, result_lines, result_status, result_scroll
        query_text = "\n".join(editor_lines)
        if not query_text.strip():
            result_frozen = []
            result_lines = ["(empty query)"]
            result_status = "empty"
            return
        try:
            result = ds.query(query_text)
            result_frozen, result_lines = _format_result(
                result, ds.namespace_manager,
            )
            result_status = f"{result.type} — {num_triples} triples queried"
            result_scroll = 0
        except Exception as e:  # noqa: BLE001
            result_frozen = []
            result_lines = [f"Error: {e}"]
            result_status = "error"
            result_scroll = 0

    def _clamp_cursor() -> None:
        nonlocal cursor_row, cursor_col
        cursor_row = max(0, min(cursor_row, len(editor_lines) - 1))
        line_len = len(editor_lines[cursor_row]) if editor_lines else 0
        cursor_col = max(0, min(cursor_col, line_len))

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

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
                fp_files, fp_cursor, fp_scroll, cursor_attr, project_dir,
            )
            stdscr.refresh()
            key = stdscr.getch()

            if key == _KEY_ESCAPE:
                fp_mode = False
            elif key == ord("q") or key == ord("Q"):
                return
            elif key == ord("j") or key == curses.KEY_DOWN:
                fp_cursor += 1
            elif key == ord("k") or key == curses.KEY_UP:
                fp_cursor = max(0, fp_cursor - 1)
            elif key in (curses.KEY_ENTER, ord("\n"), ord("\r")) and fp_files:
                path = fp_files[fp_cursor]
                editor_lines = path.read_text().splitlines() or [""]
                current_file = path
                cursor_row = 0
                cursor_col = 0
                editor_scroll = 0
                result_frozen = []
                result_lines = [f"Loaded: {path.name}"]
                result_status = f"loaded {path.name}"
                fp_mode = False
            continue

        # Layout: split screen between editor and results
        # Top bar
        file_label = f" [{current_file.name}]" if current_file else " [unsaved]"
        top_bar = (
            f" pythinfer query{file_label}  |"
            "  L:load  S:save  Ctrl-E:exec"
            "  Tab:switch  Ctrl-C:quit "
        )
        stdscr.addnstr(0, 0, top_bar.ljust(width), width - 1, curses.A_REVERSE)

        # Split remaining height
        usable = height - 2  # top bar + bottom status
        editor_height = max(usable // 2, 5)
        results_height = usable - editor_height - 1  # -1 for results header

        editor_top = 1
        results_top = editor_top + editor_height + 1

        # Scroll editor to keep cursor visible
        if cursor_row < editor_scroll:
            editor_scroll = cursor_row
        elif cursor_row >= editor_scroll + editor_height:
            editor_scroll = cursor_row - editor_height + 1

        _render_editor(
            stdscr, editor_lines, cursor_row, cursor_col,
            editor_scroll, editor_top, editor_height, width,
            active=editor_focus,
        )

        _render_results(
            stdscr, result_frozen, result_lines, result_scroll,
            results_top, results_height, width, result_status,
            active=not editor_focus,
            frozen_attr=col_header_attr,
        )

        # Bottom status
        pos_info = f" Ln {cursor_row + 1}, Col {cursor_col + 1} "
        if height > 2:
            stdscr.addnstr(height - 1, 0, pos_info, width - 1, curses.A_DIM)

        # Position cursor in editor if focused
        if editor_focus:
            gutter_width = 4
            screen_row = editor_top + 1 + (cursor_row - editor_scroll)
            screen_col = gutter_width + cursor_col
            if 0 <= screen_row < height and 0 <= screen_col < width:
                with contextlib.suppress(curses.error):
                    stdscr.move(screen_row, screen_col)
            curses.curs_set(1)
        else:
            curses.curs_set(0)

        stdscr.refresh()
        key = stdscr.getch()

        # Global keys
        if key == 3:  # Ctrl-C
            return

        if key == ord("\t"):  # Tab: switch focus
            editor_focus = not editor_focus
            continue

        # Ctrl-L: load
        if key == 12:
            fp_files = _list_query_files(project_dir)
            fp_mode = True
            fp_cursor = 0
            fp_scroll = 0
            continue

        # Ctrl-S: save
        if key == 19:
            if current_file:
                default_name = current_file.name
            else:
                default_name = "query.rq"
            name = _prompt_input(stdscr, "Save as: ", default_name)
            if name:
                path = project_dir / name
                path.write_text("\n".join(editor_lines) + "\n")
                current_file = path
                result_frozen = []
                result_lines = [f"Saved: {path}"]
                result_status = f"saved {path.name}"
            continue

        if editor_focus:
            # Editor key handling
            if key == 5:  # Ctrl-E
                _execute_query()
            elif key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
                # Plain Enter: newline in editor
                line = editor_lines[cursor_row]
                editor_lines[cursor_row] = line[:cursor_col]
                editor_lines.insert(cursor_row + 1, line[cursor_col:])
                cursor_row += 1
                cursor_col = 0
            elif key in (curses.KEY_BACKSPACE, 127, ord("\b")):
                if cursor_col > 0:
                    line = editor_lines[cursor_row]
                    editor_lines[cursor_row] = (
                        line[:cursor_col - 1] + line[cursor_col:]
                    )
                    cursor_col -= 1
                elif cursor_row > 0:
                    # Join with previous line
                    prev = editor_lines[cursor_row - 1]
                    editor_lines[cursor_row - 1] = prev + editor_lines[cursor_row]
                    editor_lines.pop(cursor_row)
                    cursor_row -= 1
                    cursor_col = len(prev)
            elif key == curses.KEY_DC:  # Delete key
                line = editor_lines[cursor_row]
                if cursor_col < len(line):
                    editor_lines[cursor_row] = (
                        line[:cursor_col] + line[cursor_col + 1:]
                    )
                elif cursor_row < len(editor_lines) - 1:
                    editor_lines[cursor_row] = line + editor_lines[cursor_row + 1]
                    editor_lines.pop(cursor_row + 1)
            elif key == curses.KEY_LEFT:
                if cursor_col > 0:
                    cursor_col -= 1
                elif cursor_row > 0:
                    cursor_row -= 1
                    cursor_col = len(editor_lines[cursor_row])
            elif key == curses.KEY_RIGHT:
                if cursor_col < len(editor_lines[cursor_row]):
                    cursor_col += 1
                elif cursor_row < len(editor_lines) - 1:
                    cursor_row += 1
                    cursor_col = 0
            elif key == curses.KEY_UP:
                if cursor_row > 0:
                    cursor_row -= 1
                    _clamp_cursor()
            elif key == curses.KEY_DOWN:
                if cursor_row < len(editor_lines) - 1:
                    cursor_row += 1
                    _clamp_cursor()
            elif key == curses.KEY_HOME:
                cursor_col = 0
            elif key == curses.KEY_END:
                cursor_col = len(editor_lines[cursor_row])
            elif key == curses.KEY_PPAGE:
                cursor_row = max(0, cursor_row - editor_height)
                _clamp_cursor()
            elif key == curses.KEY_NPAGE:
                cursor_row = min(
                    len(editor_lines) - 1, cursor_row + editor_height,
                )
                _clamp_cursor()
            elif 0 <= key < 256:  # noqa: PLR2004
                ch = chr(key)
                line = editor_lines[cursor_row]
                editor_lines[cursor_row] = (
                    line[:cursor_col] + ch + line[cursor_col:]
                )
                cursor_col += 1
        else:
            # Results pane key handling
            scroll_area = results_height - len(result_frozen)
            if key == ord("j") or key == curses.KEY_DOWN:
                result_scroll += 1
                max_scroll = max(0, len(result_lines) - scroll_area)
                result_scroll = min(result_scroll, max_scroll)
            elif key == ord("k") or key == curses.KEY_UP:
                result_scroll = max(0, result_scroll - 1)
            elif key == curses.KEY_NPAGE or key == ord("J"):
                result_scroll += max(1, scroll_area // 2)
                max_scroll = max(0, len(result_lines) - scroll_area)
                result_scroll = min(result_scroll, max_scroll)
            elif key == curses.KEY_PPAGE or key == ord("K"):
                result_scroll -= max(1, scroll_area // 2)
                result_scroll = max(0, result_scroll)
            # L: load file (also works from results pane)
            elif key == ord("L"):
                fp_files = _list_query_files(project_dir)
                fp_mode = True
                fp_cursor = 0
                fp_scroll = 0
            # S: save (also works from results pane)
            elif key == ord("S"):
                if current_file:
                    default_name = current_file.name
                else:
                    default_name = "query.rq"
                name = _prompt_input(stdscr, "Save as: ", default_name)
                if name:
                    path = project_dir / name
                    path.write_text("\n".join(editor_lines) + "\n")
                    current_file = path
                    result_frozen = []
                    result_lines = [f"Saved: {path}"]
                    result_status = f"saved {path.name}"
