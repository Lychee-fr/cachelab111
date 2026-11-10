import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys


class EvaluationError(RuntimeError):
    """A build, test process, or result file could not be evaluated."""


def run_command(command, timeout=30):
    """Run locally and stop the whole process group if a test hangs."""
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            start_new_session=True,
        )
    except OSError as error:
        raise EvaluationError(f"Cannot run {command[0]}: {error}") from error
    try:
        output, _ = process.communicate(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        output, _ = process.communicate()
        if isinstance(error, KeyboardInterrupt):
            raise
        raise EvaluationError(
            f"{' '.join(command)} timed out after {timeout}s.\n{output}"
        ) from None
    if process.returncode != 0:
        raise EvaluationError(
            f"{' '.join(command)} exited with status {process.returncode}.\n{output}"
        )
    return output


def check_environment():
    if not Path("Makefile").is_file() or not Path("simulator.h").is_file():
        raise EvaluationError("Run this command from the CacheLab project root.")
    if not Path("csim-ref").is_file() or not os.access("csim-ref", os.X_OK):
        raise EvaluationError(
            "Missing executable ./csim-ref. Restore the supplied Linux x86-64 "
            "reference binary and its executable permission."
        )


def read_results_file():
    try:
        return parse_results_file(Path(".csim_results").read_text())
    except (OSError, ValueError) as error:
        raise EvaluationError(f"Invalid .csim_results: {error}") from error


def parse_csim_output(text) -> tuple:
    "hits:15 misses:1 evictions:0"
    return tuple(
        map(
            lambda x: int(x.split(":")[1]),
            text.strip().split(" "),
        )
    )


def parse_results_file(text) -> tuple:
    "15 1 0"
    result = tuple(map(int, text.split()))
    if len(result) != 3 or any(value < 0 for value in result):
        raise ValueError("expected three nonnegative integers")
    return result


def _styled(text, style):
    if (sys.stdout.isatty() and os.environ.get("TERM") != "dumb"
            and "NO_COLOR" not in os.environ):
        return f"\033[{style}m{text}\033[0m"
    return text


def _unicode_output():
    try:
        "┏─│╭".encode(sys.stdout.encoding or "utf-8")
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def _report_width():
    return min(100, shutil.get_terminal_size((80, 24)).columns)


def print_section(title):
    rule = "━" if _unicode_output() else "="
    label = f" {title} "
    print(_styled(rule * 2 + label + rule * max(2, _report_width() - len(label) - 2), "1;36"))
    print(flush=True)


def format_table(data, alignments=None, status_column=None):
    """Render compact, aligned tables without third-party dependencies."""
    widths = [max(len(str(item)) for item in col) for col in zip(*data)]
    alignments = alignments or ["left"] * len(widths)
    alignment_codes = {"left": "<", "center": "^", "right": ">"}
    if _unicode_output():
        top, middle, bottom = "┏┳┓━", "┡╇┩━", "└┴┘─"
        header_vertical, vertical = "┃", "│"
    else:
        top = middle = bottom = "+++-"
        header_vertical = vertical = "|"

    def border(chars):
        left, cross, right, horizontal = chars
        return _styled(left + cross.join(horizontal * (width + 2) for width in widths) + right, "2")

    lines = [border(top)]
    for index, row in enumerate(data):
        cells = []
        for column, (item, width, alignment) in enumerate(zip(row, widths, alignments)):
            text = f"{str(item):{alignment_codes[alignment]}{width}}"
            if index == 0:
                text = _styled(text, "1")
            elif column == status_column:
                text = _styled(text, "1;32" if item == "OK" else "1;31")
            elif column == 0:
                text = _styled(text, "36")
            cells.append(f" {text} ")
        edge = header_vertical if index == 0 else vertical
        lines.append(edge + edge.join(cells) + edge)
        if index == 0:
            lines.append(border(middle))
    lines.append(border(bottom))
    return "\n".join(lines)


def format_score(lines, full_score):
    """Keep each part's existing score in a separate summary panel."""
    width = max(_report_width(), max(map(len, lines)) + 4)
    if _unicode_output():
        top_left, top_right, bottom_left, bottom_right, horizontal, vertical = "╭╮╰╯─│"
    else:
        top_left = top_right = bottom_left = bottom_right = "+"
        horizontal, vertical = "-", "|"
    style = "32" if full_score else "33"
    edge = _styled(vertical, style)
    output = [_styled(top_left + horizontal * (width - 2) + top_right, style)]
    for line in lines:
        output.append(edge + " " + _styled(line.ljust(width - 4), "1") + " " + edge)
    output.append(_styled(bottom_left + horizontal * (width - 2) + bottom_right, style))
    return "\n".join(output)
