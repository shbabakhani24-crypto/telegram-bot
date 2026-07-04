import unittest
from unittest.mock import patch

import scanner


class ScannerTests(unittest.TestCase):
    def test_scan_reports_data_fetch_errors(self):
        with patch.object(scanner, "get_data", side_effect=RuntimeError("API blocked")):
            result = scanner.scan()

        self.assertIn("Unable to fetch market data", result)
        self.assertNotIn("No setups found", result)


if __name__ == "__main__":
    unittest.main()
