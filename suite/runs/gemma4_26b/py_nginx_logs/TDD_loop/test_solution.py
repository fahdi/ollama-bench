import unittest
from datetime import datetime, timezone, timedelta
from solution import parse_line, top_error_paths

class TestNginxTriage(unittest.TestCase):

    def test_parse_line_success(self):
        line = '127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET /api/users?id=5 HTTP/1.1" 502 1234 "-" "curl/8.0"'
        result = parse_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "127.0.0.1")
        # Check datetime and timezone awareness
        expected_dt = datetime(2026, 10, 10, 13, 55, 36, tzinfo=timezone.utc)
        self.assertEqual(result["time"], expected_dt)
        self.assertEqual(result["method"], "GET")
        self.assertEqual(result["path"], "/api/users")
        self.assertEqual(result["status"], 502)
        self.assertEqual(result["bytes"], 1234)

    def test_parse_line_different_timezone(self):
        line = '1.1.1.1 - admin [10/Oct/2026:13:55:36 +0500] "POST /login HTTP/1.1" 200 0 "-" "Mozilla"'
        result = parse_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "1.1.1.1")
        # +0500 offset
        expected_dt = datetime(2026, 10, 10, 13, 55, 36, tzinfo=timezone(timedelta(hours=5)))
        self.assertEqual(result["time"], expected_dt)
        self.assertEqual(result["method"], "POST")
        self.assertEqual(result["path"], "/login")
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["bytes"], 0)

    def test_parse_line_bytes_dash(self):
        line = '127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET / HTTP/1.1" 200 - "-" "-"'
        result = parse_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["bytes"], 0)

    def test_parse_line_malformed_garbage(self):
        self.assertIsNone(parse_line(""))
        self.assertIsNone(parse_line("not a log line"))
        self.assertIsNone(parse_line('127.0.0.1 - - [bad_date] "GET / HTTP/1.1" 200 123 "-" "-"'))

    def test_parse_line_malformed_request(self):
        # Nginx writes "-" for bad requests
        self.assertIsNone(parse_line('127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "-" 400 123 "-" "-"'))
        # Request field not exactly 3 parts
        self.assertIsNone(parse_line('127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET / HTTP/1.1 extra" 200 123 "-" "-"'))

    def test_parse_line_non_numeric_status(self):
        self.assertIsNone(parse_line('127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET / HTTP/1.1" OK 123 "-" "-"'))

    def test_top_error_paths(self):
        logs = [
            '127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET /api/v1/users?id=1 HTTP/1.1" 500 100 "-" "-"',
            '127.0.0.1 - - [10/Oct/2026:13:55:37 +0000] "GET /api/v1/users?id=2 HTTP/1.1" 500 100 "-" "-"',
            '127.0.0.1 - - [10/Oct/2026:13:55:38 +0000] "POST /api/v1/login HTTP/1.1" 503 100 "-" "-"',
            '127.0.0.1 - - [10/Oct/2026:13:55:39 +0000] "GET /api/v1/users?id=3 HTTP/1.1" 500 100 "-" "-"',
            '127.0.0.1 - - [10/Oct/2026:13:55:40 +0000] "GET /api/v1/data HTTP/1.1" 200 100 "-" "-"', # Not an error
            '127.0.0.1 - - [10/Oct/2026:13:55:41 +0000] "GET /api/v1/data HTTP/1.1" 500 100 "-" "-"',
            'garbage line', # Should be ignored
            '127.0.0.1 - - [10/Oct/2026:13:55:42 +0000] "GET /api/v1/auth HTTP/1.1" 500 100 "-" "-"',
        ]
        # Counts:
        # /api/v1/users: 3
        # /api/v1/data: 1
        # /api/v1/login: 1
        # /api/v1/auth: 1
        
        # Top 3:
        # 1. /api/v1/users (3)
        # 2. /api/v1/auth (1) - alphabetical tie-break
        # 3. /api/v1/data (1) - alphabetical tie-break
        
        expected = [
            ("/api/v1/users", 3),
            ("/api/v1/auth", 1),
            ("/api/v1/data", 1)
        ]
        result = top_error_paths(logs, n=3)
        self.assertEqual(result, expected)

    def test_top_error_paths_empty_or_no_errors(self):
        self.assertEqual(top_error_paths([], n=3), [])
        logs = ['127.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET / HTTP/1.1" 200 123 "-" "-"']
        self.assertEqual(top_error_paths(logs, n=3), [])

if __name__ == "__main__":
    unittest.main()
