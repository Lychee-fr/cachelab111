"""Local reference comparison for Part A."""

import argparse
from pathlib import Path
import sys

from utils import (
    EvaluationError,
    check_environment,
    format_score,
    format_table,
    print_section,
    read_results_file,
    run_command,
)


def output_results(results: list):
    total_ok = sum(1 for status, *_ in results if status == "OK")
    score = 100 * total_ok / len(results)
    table = [["Trace", "s,E,b", "Reference (h/m/e)", "Yours (h/m/e)", "Status"]]
    for status, trace_file, parameters, reference, handin in results:
        table.append([
            Path(trace_file).name,
            ",".join(map(str, parameters)),
            "/".join(map(str, reference)),
            "/".join(map(str, handin)) if isinstance(handin, tuple) else handin,
            status,
        ])
    print("h/m/e = hits / misses / evictions\n")
    print(format_table(table, ["left", "center", "right", "right", "center"], status_column=4))
    print()
    print(format_score(
        [f"Score: {score:.2f} / 100    Passed cases: {total_ok} / {len(results)}"],
        full_score=total_ok == len(results),
    ))
    return total_ok, score


def run_csim(executable, s, E, b, trace_file):
    Path(".csim_results").unlink(missing_ok=True)
    run_command([
        f"./{executable}", "-s", str(s), "-E", str(E), "-b", str(b), "-t", trace_file,
    ])
    return read_results_file()


def test_csim():
    print_section("Part A - Cache Simulator")
    check_environment()
    # Part A can be evaluated even if gemm.cpp does not compile yet.
    run_command(["make", "-j", "csim"], timeout=120)
    trace_files = [
        "traces/yi2.trace", "traces/yi.trace", "traces/dave.trace",
        "traces/trans.trace", "traces/long.trace",
    ]
    results = []
    for s, E, b in [(5, 1, 5), (2, 4, 3), (4, 2, 4), (1, 1, 1)]:
        for trace_file in trace_files:
            # Reference failures are fatal, not student wrong answers.
            ref_results = run_csim("csim-ref", s, E, b, trace_file)
            try:
                handin_results = run_csim("csim", s, E, b, trace_file)
            except EvaluationError as error:
                print(f"{trace_file} ({s}, {E}, {b}): ERROR\n{error}")
                handin_results = "ERROR"
            status = "OK" if ref_results == handin_results else "ERROR"
            results.append((status, trace_file, (s, E, b), ref_results, handin_results))
    return output_results(results)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        test_csim()
    except EvaluationError as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
