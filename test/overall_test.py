"""Run the Part A and Part B evaluations locally."""

import argparse
from pathlib import Path
import sys

from csim_test import test_csim
from gemm_test import test_gemm
from utils import EvaluationError


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    results_file = Path(".overall_results")
    results_file.unlink(missing_ok=True)
    try:
        results_csim = test_csim()
        results_gemm = test_gemm()
    except EvaluationError as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        return 1

    results_file.write_text(
        " ".join(map(str, results_csim)) + "\n"
        + " ".join(map(str, results_gemm)) + "\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
