"""Run a local grader and publish its score in a GitHub Actions job summary."""

import argparse
import os
from pathlib import Path
import sys

from csim_test import test_csim
from gemm_test import test_gemm
from grading import perf_rate, speedups_from_results
from utils import EvaluationError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part", choices=("A", "B"), required=True)
    args = parser.parse_args(argv)
    summary = f"## Part {args.part}\n\n"
    status = 0
    try:
        if args.part == "A":
            passed, score = test_csim()
            summary += f"**Score: {score:.2f} / 100**\n\nPassed test cases: {passed} / 20.\n"
        else:
            results = test_gemm()
            speedups = speedups_from_results(results)
            score = 100 * perf_rate(speedups)
            summary += (
                f"**Performance score: {score:.2f} / 100**\n\n"
                f"Weighted speedup: {results[-1]:.4f}.\n\n"
                "| Case | Status | Speedup |\n| --- | --- | --- |\n"
            )
            for index, speedup in enumerate(speedups):
                case_status = "OK" if results[4 * index + 2] > 0 else "ERROR"
                summary += f"| case{index} | {case_status} | {speedup:.4f} |\n"
            summary += "\ncase0 is for practice and does not contribute to the score.\n"
        summary += (
            "\nA successful workflow means grading completed, not that all cases "
            "passed or full marks were earned.\n"
        )
    except EvaluationError as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        summary += "**Evaluation failed. No score was produced.**\n"
        status = 1
    summary += "\nSee the evaluation step's log for the full report and diagnostics.\n"
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        Path(summary_path).write_text(summary, encoding="utf-8")
    return status


if __name__ == "__main__":
    sys.exit(main())
