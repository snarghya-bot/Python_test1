import unittest
from scancode import human

class TestHumanReadableSize(unittest.TestCase):
    """
    Each method = one test case.
    Method names MUST start with 'test_' — that's how unittest finds them.
    """

    # --- Byte range ---------------------------------------------------------

    def test_zero_bytes(self):
        self.assertEqual(human(0), "0 B")

    def test_single_byte(self):
        self.assertEqual(human(1), "1 B")

    def test_just_under_one_kb(self):
        # 1023 bytes should still show as B, not KB
        self.assertEqual(human(1023), "1023 B")

    # --- Kilobyte range -----------------------------------------------------

    def test_exactly_one_kb(self):
        # 1024 bytes = 1.0 KB
        self.assertEqual(human(1024), "1.0 KB")

    def test_one_and_a_half_kb(self):
        self.assertEqual(human(1536), "1.5 KB")

    def test_just_under_one_mb(self):
        # 1023 * 1024 bytes should show as KB, not MB
        result = human(1023 * 1024)
        self.assertIn("KB", result)

    # --- Megabyte range -----------------------------------------------------

    def test_exactly_one_mb(self):
        self.assertEqual(human(1024 ** 2), "1.0 MB")

    def test_typical_pdf_size(self):
        # 2.5 MB — a common PDF size
        self.assertEqual(human(int(2.5 * 1024 ** 2)), "2.5 MB")

    # --- Gigabyte range -----------------------------------------------------

    def test_exactly_one_gb(self):
        self.assertEqual(human(1024 ** 3), "1.0 GB")

    # --- Terabyte range -----------------------------------------------------

    def test_exactly_one_tb(self):
        self.assertEqual(human(1024 ** 4), "1.0 TB")

    # --- Output format checks -----------------------------------------------

    def test_output_is_a_string(self):
        # human() must always return a string
        self.assertIsInstance(human(500), str)

    def test_output_contains_unit(self):
        # result should contain one of the known units
        result = human(999999)
        self.assertTrue(
            any(unit in result for unit in ["B", "KB", "MB", "GB", "TB"]),
            msg=f"No unit found in output: '{result}'"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)  # verbosity=2 prints each test name