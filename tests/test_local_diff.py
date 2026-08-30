import unittest
from unittest.mock import MagicMock, patch

from poing_ai.core.git import get_git_diff


class TestLocalDiff(unittest.TestCase):
    @patch("subprocess.run")
    def test_get_git_diff_staged(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "diff --git a/test.py b/test.py\n+print('hello')\n"
        mock_run.return_value = mock_proc

        diff = get_git_diff(staged=True)
        self.assertIn("diff --git", diff)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd, ["git", "diff", "--cached"])

    @patch("subprocess.run")
    def test_get_git_diff_diff_target(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "diff --git a/test.py b/test.py\n"
        mock_run.return_value = mock_proc

        diff = get_git_diff(diff_target="HEAD~1")
        self.assertIn("diff --git", diff)
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd, ["git", "diff", "HEAD~1"])

    @patch("subprocess.run")
    def test_get_git_diff_files_filter(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "diff --git a/src/main.py b/src/main.py\n"
        mock_run.return_value = mock_proc

        diff = get_git_diff(files=["src/main.py"])
        self.assertIn("diff --git", diff)
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd, ["git", "diff", "HEAD", "--", "src/main.py"])

    @patch("subprocess.run")
    def test_get_git_diff_local_fallback(self, mock_run):
        # 1st call (git diff HEAD) is empty, 2nd call (git diff master...HEAD) returns diff
        mock_proc1 = MagicMock(returncode=0, stdout="")
        mock_proc2 = MagicMock(returncode=0, stdout="diff --git a/app.py b/app.py\n")
        mock_run.side_effect = [mock_proc1, mock_proc2]

        diff = get_git_diff(base_ref="master", local=True)
        self.assertIn("diff --git", diff)
        self.assertEqual(mock_run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
