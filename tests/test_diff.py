import unittest
from poing_ai.core.git import annotate_diff, split_batches, split_diff_by_file

SAMPLE_DIFF = """diff --git a/test.gd b/test.gd
index 1234567..89abcdef 100644
--- a/test.gd
+++ b/test.gd
@@ -10,4 +10,5 @@
 var a := 1
-var b = 2
+var b := 2
+var c := 3
 var d := 4
"""


class TestDiff(unittest.TestCase):
    def test_annotate_diff(self):
        annotated, valid_lines = annotate_diff(SAMPLE_DIFF)
        self.assertIn("[test.gd L11] +var b := 2", annotated)
        self.assertIn("[test.gd L12] +var c := 3", annotated)
        self.assertIn(("test.gd", 11), valid_lines)
        self.assertIn(("test.gd", 12), valid_lines)

    def test_split_diff_by_file(self):
        multi_diff = SAMPLE_DIFF + "\ndiff --git a/other.gd b/other.gd\n+var x := 10\n"
        blocks = split_diff_by_file(multi_diff)
        self.assertEqual(len(blocks), 2)
        self.assertIn("test.gd", blocks[0])
        self.assertIn("other.gd", blocks[1])

    def test_split_batches(self):
        blocks = ["block1" * 10, "block2" * 10, "block3" * 10]
        batches = split_batches(blocks, max_chars=100)
        self.assertGreaterEqual(len(batches), 1)


if __name__ == "__main__":
    unittest.main()
