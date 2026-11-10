"""Maintainer regressions; all compiled fixtures live in temporary copies."""

from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import gemm_test
from grading import perf_rate, speedups_from_results, weighted_speedup
from utils import EvaluationError, run_command


ROOT = Path(__file__).resolve().parents[1]
BASELINES = [
    (3, 20, 65),
    (4792, 8448, 80328),
    (36032, 66560, 607040),
    (36869, 60507, 613542),
]


class GradingTests(unittest.TestCase):
    def test_score_boundaries_and_case0_weight(self):
        for speedup, expected in [(0, 0), (1, 0), (4.5, 0.5), (8, 1), (20, 1)]:
            with self.subTest(speedup=speedup):
                self.assertAlmostEqual(perf_rate([999, speedup, speedup, speedup]), expected)
        self.assertAlmostEqual(weighted_speedup([0, 20, 1, 5]), 8.3)
        self.assertEqual(perf_rate([0, 20, 1, 5]), 1)

    def test_failed_case_preserves_other_cases_and_partial_credit(self):
        def evaluate(case):
            if case.endswith("_baseline"):
                return case, 0, 1000, 1000
            if case == "case1":
                raise EvaluationError("Incorrect result")
            return case, 0, 100, 100

        output = io.StringIO()
        with patch.object(gemm_test, "check_environment"), \
                patch.object(gemm_test, "run_command"), \
                patch.object(gemm_test, "test_gemm_case", side_effect=evaluate) as cases, \
                redirect_stdout(output):
            results = gemm_test.test_gemm()
        self.assertEqual(cases.call_count, 8)
        self.assertEqual(len(results), 17)
        self.assertEqual(results[4:8], [-1, -1, -1, 1000])
        self.assertEqual(speedups_from_results(results), [10, 0, 10, 10])
        self.assertEqual(results[-1], 7)
        self.assertIn("Part B performance score: 85.71 / 100", output.getvalue())
        self.assertNotIn("Part B performance contribution:", output.getvalue())

    def test_timeout_kills_children_holding_output_pipe(self):
        # Killing only the parent would leave communicate() waiting for the child.
        script = (
            "import subprocess, sys, time; "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(5)']); "
            "time.sleep(5)"
        )
        start = time.monotonic()
        with self.assertRaisesRegex(EvaluationError, "timed out"):
            run_command([sys.executable, "-c", script], timeout=0.2)
        self.assertLess(time.monotonic() - start, 3)


class LocalEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cachelab local test ")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        for source in ROOT.iterdir():
            if source.is_file() and (
                source.suffix in {".c", ".cpp", ".h"}
                or source.name in {"Makefile", "csim-ref"}
            ):
                shutil.copy2(source, self.work / source.name)
        for directory in ("test", "traces"):
            shutil.copytree(
                ROOT / directory, self.work / directory,
                ignore=shutil.ignore_patterns("__pycache__"),
            )

    def evaluate(self, script, *args, success=True):
        result = subprocess.run(
            [sys.executable, f"test/{script}", *args], cwd=self.work,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=120,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result.stdout

    def inject_case(self, index, code):
        path = self.work / "gemm.cpp"
        source = path.read_text()
        marker = (
            f"void gemm_case{index}(ptr_reg A, ptr_reg B, ptr_reg C, ptr_reg buffer)\n{{"
        )
        self.assertEqual(source.count(marker), 1)
        path.write_text(source.replace(marker, marker + "\n" + code, 1))

    def run_register_fixture(self, body):
        source = self.work / "register_fixture.cpp"
        source.write_text('#include "common.h"\n#include <utility>\n' + body)
        build = subprocess.run(
            ["g++", "-Wall", "-O0", "-std=c++23", str(source), "-o", "register_fixture"],
            cwd=self.work, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        result = subprocess.run(
            ["./register_fixture"], cwd=self.work, capture_output=True,
            text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_register_subtraction_accepts_integer_operands(self):
        self.run_register_fixture('''
int main() {
    reg a = 7;
    reg b = 2;
    return (a - 2 == 5 && 2 - a == -5 && a - b == 5) ? 0 : 1;
}
''')

    def test_move_assignment_releases_registers_and_handles_self_move(self):
        self.run_register_fixture('''
int main() {
    for (int i = 0; i < 100; ++i) {
        reg a = 0;
        {
            reg b = i;
            a = std::move(b);
            if (get_current_reg_count() != 1 || a != i) return 1;
            try { b.check_valid(); return 2; }
            catch (const InactiveRegisterException &) {}
        }
        a = std::move(a);
        if (a != i || get_current_reg_count() != 1) return 3;
    }
    if (get_current_reg_count() != 0) return 4;
    int data[4] = {};
    {
        ptr_reg p(data);
        for (int i = 0; i < 100; ++i) {
            p = ptr_reg(data + i % 4);
            if (get_current_reg_count() != 1 || p.ptr_ != data + i % 4) return 5;
        }
    }
    if (get_current_reg_count() != 0) return 6;
    {
        reg full[36];
        if (get_current_reg_count() != 36) return 7;
        try { reg extra; return 8; }
        catch (const OutOfRegistersException &) {}
    }
    return get_current_reg_count() != 0;
}
''')

    def raw_results(self):
        lines = (self.work / ".overall_results").read_text().splitlines()
        self.assertEqual(len(lines), 2)
        return [list(map(float, line.split())) for line in lines]

    def test_clean_template_runs_without_credentials(self):
        output = self.evaluate("overall_test.py")
        part_a, part_b = self.raw_results()
        self.assertEqual(part_a, [0, 0])
        expected = [value for row in BASELINES for value in (*row, row[-1])] + [1]
        self.assertEqual(part_b, expected)
        self.assertTrue(output.rstrip().endswith("Part B performance score: 0.00 / 100"))
        for removed in (
            "Part B performance contribution:", "Part A:", "Part B performance:",
            "Automatic subtotal:", "Report/style points", "Raw results saved",
        ):
            self.assertNotIn(removed, output)
        for filename in (".access_key", ".last_submit_time", ".autograder_result"):
            self.assertFalse((self.work / filename).exists())

    def test_baseline_option_and_existing_legacy_files(self):
        for filename in (".access_key", ".last_submit_time"):
            (self.work / filename).write_text("unused legacy value")
        output = self.evaluate("gemm_test.py", "--baseline")
        rows = [line.split("|") for line in output.splitlines() if "_baseline" in line]
        self.assertEqual(len(rows), 4)
        for row, expected in zip(rows, BASELINES):
            self.assertEqual(tuple(int(value) for value in row[2:5]), expected)
        for filename in (".access_key", ".last_submit_time"):
            self.assertEqual((self.work / filename).read_text(), "unused legacy value")

    def test_part_b_ignores_broken_part_a(self):
        (self.work / "csim.c").write_text("#error Part A is unfinished\n")
        output = self.evaluate("gemm_test.py")
        self.assertIn("Weighted Speedup: 1.0000", output)
        self.assertFalse((self.work / "csim").exists())

    def test_memory_assignment_shares_register_pool_with_baseline(self):
        # Assignment-only student code must not change which register pool the
        # baseline's memory constructors allocate from in another source file.
        path = self.work / "gemm.cpp"
        source = path.read_text()
        source = source.replace(
            "reg tmpa = A[i * n + k];", "reg tmpa; tmpa = A[i * n + k];"
        ).replace(
            "reg tmpb = B[k * p + j];", "reg tmpb; tmpb = B[k * p + j];"
        )
        path.write_text(source)
        self.evaluate("overall_test.py")
        _, results = self.raw_results()
        expected = [value for row in BASELINES for value in (*row, row[-1])] + [1]
        self.assertEqual(results, expected)

    def test_part_a_ignores_broken_part_b(self):
        (self.work / "gemm.cpp").write_text("#error Part B is unfinished\n")
        output = self.evaluate("csim_test.py")
        self.assertIn("Score: 0.00", output)
        self.assertFalse((self.work / "printTrace").exists())

    def test_part_a_accepts_cpp_filename(self):
        (self.work / "csim.c").rename(self.work / "csim.cpp")
        self.assertIn("Score: 0.00", self.evaluate("csim_test.py"))

    def test_actions_part_a_uses_cpp_and_ignores_broken_part_b(self):
        (self.work / "csim.c").rename(self.work / "csim.cpp")
        (self.work / "gemm.cpp").write_text("#error Part B is unfinished\n")
        summary = self.work / "summary.md"
        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
            output = self.evaluate("actions_test.py", "--part", "A")
        self.assertIn("Score: 0.00", output)
        self.assertIn("Score: 0.00 / 100", summary.read_text())
        self.assertFalse((self.work / "printTrace").exists())

    def test_actions_part_b_ignores_broken_part_a_and_continues_after_wrong_case(self):
        (self.work / "csim.c").write_text("#error Part A is unfinished\n")
        self.inject_case(1, "return;")
        summary = self.work / "summary.md"
        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
            output = self.evaluate("actions_test.py", "--part", "B")
        self.assertIn("Weighted Speedup: 0.7000", output)
        self.assertIn("Performance score: 0.00 / 100", summary.read_text())
        self.assertIn("| case1 | ERROR | 0.0000 |", summary.read_text())
        self.assertIn("| case3 | OK | 1.0000 |", summary.read_text())
        self.assertFalse((self.work / "csim").exists())

    def test_reference_as_correct_part_a_fixture_scores_full_marks(self):
        # An oracle executable is sufficient to test score aggregation; no solution
        # source is added to the public template.
        shutil.copyfile(self.work / "csim-ref", self.work / "csim")
        (self.work / "csim").chmod(0o755)
        (self.work / "csim").touch()
        output = self.evaluate("csim_test.py")
        self.assertIn("Score: 100.00", output)
        self.assertEqual(sum(line.startswith("OK ") for line in output.splitlines()), 20)

    def test_wrong_answers_and_register_overflow_continue(self):
        self.inject_case(0, "return;")
        self.inject_case(1, "return;")
        self.inject_case(2, "reg too_many_registers[37];")
        output = self.evaluate("overall_test.py")
        _, results = self.raw_results()
        for index in range(3):
            self.assertEqual(results[4 * index:4 * index + 3], [-1, -1, -1])
            self.assertEqual(results[4 * index + 3], BASELINES[index][-1])
        self.assertEqual(results[12:16], [36869, 60507, 613542, 613542])
        self.assertAlmostEqual(results[-1], 0.4)
        self.assertIn("Incorrect result", output)
        self.assertIn("no more available registers", output)

    def test_illegal_source_rejected_and_stale_overall_result_removed(self):
        (self.work / ".overall_results").write_text("old score")
        self.inject_case(1, "int illegal_variable = 0; (void)illegal_variable;")
        output = self.evaluate("overall_test.py", success=False)
        self.assertIn("You use something illegal", output)
        self.assertNotIn("Automatic subtotal:", output)
        self.assertFalse((self.work / ".overall_results").exists())

    def test_missing_reference_is_an_environment_error(self):
        (self.work / "csim-ref").unlink()
        output = self.evaluate("gemm_test.py", success=False)
        self.assertIn("Missing executable ./csim-ref", output)
        self.assertNotIn("Part B performance score:", output)

    def test_reference_runtime_failure_is_fatal(self):
        (self.work / "csim-ref").write_text("#!/bin/sh\nexit 7\n")
        output = self.evaluate("gemm_test.py", success=False)
        self.assertIn("Evaluation failed:", output)
        self.assertIn("case0_baseline", output)
        self.assertNotIn("Part B performance score:", output)

    def test_missing_student_summary_does_not_reuse_reference_summary(self):
        (self.work / "csim.c").write_text("int main(void) { return 0; }\n")
        (self.work / ".csim_results").write_text("15 1 0\n")
        output = self.evaluate("csim_test.py")
        self.assertIn("Invalid .csim_results:", output)
        self.assertIn("Score: 0.00", output)
        self.assertFalse(any(line.startswith("OK ") for line in output.splitlines()))

    def test_removed_flags_are_rejected_before_running_tests(self):
        for script, flag in [
            ("csim_test.py", "--no_linux"),
            ("gemm_test.py", "--ignore_submit"),
            ("overall_test.py", "--ignore_submit"),
        ]:
            with self.subTest(script=script):
                output = self.evaluate(script, flag, success=False)
                self.assertIn("unrecognized arguments", output)
        self.assertFalse((self.work / "csim").exists())
        self.assertFalse((self.work / "printTrace").exists())


if __name__ == "__main__":
    unittest.main()
