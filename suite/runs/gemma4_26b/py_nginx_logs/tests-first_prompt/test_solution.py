import unittest
from datetime import datetime, timezone, timedelta
from solution import parse_line, top_error_paths

class TestNginxTriage(unittest.TestCase):

    def test_parse_line_success(self):
        line = '127.0.0.1 - admin [10/Oct/2026:13:55:36 +0500] "GET /api/users?id=5 HTTP/1.1" 502 1234 "-" "curl/8.0"'
        result = parse_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "127.0.0.1")
        # Check timezone awareness and offset
        self.assertEqual(result["time"].year, 2026)
        self.assertEqual(result["time"].tzinfo, timezone(timedelta(hours=5)))
        self.assertEqual(result["method"], "GET")
        self.assertEqual(result["path"], "/api/users")
        self.assertEqual(result["status"], 502)
        self.assertEqual(result["bytes"], 1234)

    def test_parse_line_bytes_dash(self):
        line = '127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET / HTTP/1.1" 200 - "-" "Mozilla"'
        result = parse_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["bytes"], 0)

    def test_parse_line_malformed(self):
        cases = [
            "",                                         # Empty
            "garbage text",                             # Garbage
            '127.0.0.1 - - [bad_date] "GET / HTTP/1.1" 200 123 "-" "-"', # Bad date
            '127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET /" 200 123 "-" "-"', # Bad request format (missing protocol)
            '127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "-" 200 123 "-" "-"',     # Bad request (dash)
            '127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET / HTTP/1.1" ABC 123 "-" "-"', # Non-numeric status
            '127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET / HTTP/1.1" 200 XYZ "-" "-"', # Non-numeric bytes
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertIsNone(parse_line(case))

    def test_top_error_paths(self):
        lines = [
            '1.1.1.1 - - [10/Oct/2026:10:00:00 +0000] "GET /a?q=1 HTTP/1.1" 500 10 "-" "-"',
            '1.1.1.1 - - [10/Oct/2026:10:00:01 +0000] "GET /a?q=2 HTTP/1.1" 503 10 "-" "-"',
            '1.1.1.1 - - [10/Oct/2026:10:00:02 +0000] "POST /b HTTP/1.1" 500 10 "-" "-"',
            '1.1.1.1 - - [10/Oct/2026:10:00:03 +0000] "GET /a HTTP/1.1" 200 10 "-" "-"', # Not an error
            '1.1.1.1 - - [10/Oct/2026:10:00:04 +0000] "GET /c HTTP/1.1" 500 10 "-" "-"',
            'invalid line',                                                              # Malformed
            '1.1.1.1 - - [10/Oct/2026:10:00:05 +0000] "GET /b HTTP/1.1" 500 10 "-" "-"', # Tie breaker test
        ]
        # /a: 2 errors, /b: 2 errors, /c: 1 error
        # Tie breaker: /a vs /b -> /a comes first (alphabetical)
        expected = [("/a", 2), ("/b", 2), ("/c", 1)]
        self.assertEqual(top_error_paths(lines, n=3), expected)

    def test_top_error_paths_n_limit(self):
        lines = [
            '1.1.1.1 - - [10/Oct/2026:10:00:00 +0000] "GET /a HTTP/1.1" 500 10 "-" "-"',
            '1.1.1.1 - - [10/Oct/2026:10:00:00 +0000] "GET /b HTTP/1.1" 500 10 "-" "-"',
            '1.1.1.1 - - [10/Oct/2026:10:00:00 +0000] "GET /c HTTP/1.1" 500 10 "-" "-"',
            '1.1.1.1 - - [10/Oct/2026:10:00:00 +0000] "GET /d HTTP/1.1" 500 10 "-" "-"',
        ]
        result = top_error_paths(lines, n=2)
        self.assertEqual(len(result), 2)

if __name__ == "__main__":
    unittest.main()
