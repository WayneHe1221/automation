import contextlib
import io
import types
import unittest

from run_all import execute_tasks


class RunnerTests(unittest.TestCase):
    def test_false_result_and_exception_are_failures(self):
        tasks = [
            ("ok", types.SimpleNamespace(main=lambda: True)),
            ("reported_failure", types.SimpleNamespace(main=lambda: False)),
            ("exception", types.SimpleNamespace(main=lambda: 1 / 0)),
            ("missing_main", types.SimpleNamespace()),
        ]

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            failures = execute_tasks(tasks)

        self.assertEqual(failures, 3)


if __name__ == "__main__":
    unittest.main()
