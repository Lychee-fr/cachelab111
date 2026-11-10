"""Check Actions feedback without changing the local graders' behavior."""

from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import actions_test
from utils import EvaluationError


class ActionsSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cachelab actions test ")
        self.addCleanup(self.temp.cleanup)
        self.summary = Path(self.temp.name) / "summary.md"
        environment = patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(self.summary)})
        environment.start()
        self.addCleanup(environment.stop)

    def run_part(self, part):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = actions_test.main(["--part", part])
        return status, stdout.getvalue(), stderr.getvalue()

    def test_part_a_reports_zero_partial_and_full_scores_without_extra_stdout(self):
        for passed, score in [(0, 0), (13, 65), (20, 100)]:
            with self.subTest(passed=passed):
                def evaluate():
                    print("local report")
                    return passed, score

                with patch.object(actions_test, "test_csim", side_effect=evaluate), \
                        patch.object(actions_test, "test_gemm") as part_b:
                    self.assertEqual(self.run_part("A"), (0, "local report\n", ""))
                part_b.assert_not_called()
                summary = self.summary.read_text()
                self.assertIn(f"Score: {score:.2f} / 100", summary)
                self.assertIn(f"Passed test cases: {passed} / 20", summary)

    def test_part_b_keeps_partial_credit_when_one_case_fails(self):
        # case1 fails; the other three cases have speedup 10, yielding W = 7.
        results = [0, 100, 100, 1000, -1, -1, -1, 1000,
                   0, 100, 100, 1000, 0, 100, 100, 1000, 7]
        with patch.object(actions_test, "test_gemm", return_value=results), \
                patch.object(actions_test, "test_csim") as part_a:
            self.assertEqual(self.run_part("B"), (0, "", ""))
        part_a.assert_not_called()
        summary = self.summary.read_text()
        self.assertIn("Performance score: 85.71 / 100", summary)
        self.assertIn("Weighted speedup: 7.0000", summary)
        self.assertIn("| case1 | ERROR | 0.0000 |", summary)
        self.assertIn("| case3 | OK | 10.0000 |", summary)

    def test_failed_evaluation_replaces_old_score_and_fails_the_job(self):
        for part, grader in [("A", "test_csim"), ("B", "test_gemm")]:
            with self.subTest(part=part):
                self.summary.write_text("Old score: 100.00 / 100\n")
                with patch.object(actions_test, grader, side_effect=EvaluationError("build failed")):
                    status, stdout, stderr = self.run_part(part)
                self.assertEqual(status, 1)
                self.assertEqual(stdout, "")
                self.assertIn("Evaluation failed: build failed", stderr)
                summary = self.summary.read_text()
                self.assertIn("No score was produced", summary)
                self.assertNotIn("100.00", summary)

    def test_without_actions_environment_the_local_report_still_works(self):
        environment = dict(os.environ)
        environment.pop("GITHUB_STEP_SUMMARY", None)
        with patch.dict(os.environ, environment, clear=True), \
                patch.object(actions_test, "test_csim", return_value=(20, 100)):
            self.assertEqual(self.run_part("A"), (0, "", ""))
        self.assertFalse(self.summary.exists())


if __name__ == "__main__":
    unittest.main()
