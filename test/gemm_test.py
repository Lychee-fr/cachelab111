"""Local correctness and performance evaluation for Part B."""

import argparse
from pathlib import Path
import sys

from grading import perf_rate, weighted_speedup
from utils import (
    EvaluationError,
    check_environment,
    format_table,
    read_results_file,
    run_command,
)


def output_results(results: list, baselines: list):
    table = [["case", "status", "miss_cache", "miss_reg", "latency", "speedup"]]
    for case, miss_cache, miss_reg, latency, speedup in results:
        if latency > 0:
            table.append([case, "OK", miss_cache, miss_reg, latency, f"{speedup:.4f}"])
        else:
            table.append([case, "ERROR", "N/A", "N/A", "N/A", "0.0000"])
    speedups = [result[-1] for result in results]
    weighted = weighted_speedup(speedups)
    rate = perf_rate(speedups)
    print(format_table(table))
    print(f"Weighted Speedup: {weighted:.4f}")
    print(f"Part B performance score: {100 * rate:.2f} / 100")

    # Keep the existing numeric layout for .overall_results consumers.
    # A failed case has -1 for its three unavailable measurements.
    output = []
    for result, baseline in zip(results, baselines):
        output.extend(result[1:4])
        output.append(baseline)
    output.append(weighted)
    return output


def test_gemm_case(case: str) -> tuple:
    Path(".csim_results").unlink(missing_ok=True)
    run_command(["make", case])
    try:
        with open(f"gemm_traces/{case}.trace") as trace:
            miss_reg = sum(1 for _ in trace)
    except OSError as error:
        raise EvaluationError(f"Cannot read trace for {case}: {error}") from error
    miss_cache = read_results_file()[1]
    latency = 15 * miss_cache + miss_reg
    if latency <= 0:
        raise EvaluationError(f"Empty or invalid trace for {case}")
    return case, miss_cache, miss_reg, latency


def test_gemm(baseline_only=False):
    check_environment()
    # Part B uses csim-ref and must also work before Part A is implemented.
    run_command(["make", "-j", "printTrace"], timeout=120)
    baselines = []
    results = []
    for index in range(4):
        case = f"case{index}_baseline"
        # Baseline/infrastructure failures invalidate the evaluation itself.
        result = test_gemm_case(case)
        baselines.append(result[-1])
        if baseline_only:
            results.append((*result, 1.0))

    if not baseline_only:
        for index, baseline in enumerate(baselines):
            case = f"case{index}"
            try:
                result = test_gemm_case(case)
            except EvaluationError as error:
                print(f"{case}: ERROR (speedup = 0)\n{error}")
                results.append((case, -1, -1, -1, 0.0))
            else:
                results.append((*result, baseline / result[-1]))

    return output_results(results, baselines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true", help="evaluate only the baselines")
    args = parser.parse_args()
    try:
        test_gemm(baseline_only=args.baseline)
    except EvaluationError as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
