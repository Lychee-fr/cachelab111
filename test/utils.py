import os
from pathlib import Path
import signal
import subprocess


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


def format_table(data):
    column_widths = [max(len(str(item)) for item in col) for col in zip(*data)]
    table_str = ""
    for i, row in enumerate(data):
        table_str += (
            " | ".join(
                f"{str(item).ljust(width)}" for item, width in zip(row, column_widths)
            )
            + "\n"
        )
        if i == 0:
            table_str += "-+-".join("-" * width for width in column_widths) + "\n"

    table_str = table_str.strip()

    return table_str
