import unittest
import asyncio
from solution import fetch_all

class TestFetchAll(unittest.IsolatedAsyncioTestCase):
    async def test_empty_list(self):
        """An empty list returns []."""
        result = await fetch_all([], lambda x: asyncio.sleep(0))
        self.assertEqual(result, [])

    async def test_invalid_limit(self):
        """limit < 1 raises ValueError."""
        with self.assertRaises(ValueError):
            await fetch_all(["url1"], lambda x: asyncio.sleep(0), limit=0)
        with self.assertRaises(ValueError):
            await fetch_all(["url1"], lambda x: asyncio.sleep(0), limit=-1)

    async def test_successful_fetches(self):
        """Normal case: returns results in the same order as urls."""
        urls = ["url1", "url2", "url3"]
        async def mock_fetch(url):
            return f"res_{url}"
        
        result = await fetch_all(urls, mock_fetch)
        self.assertEqual(result, ["res_url1", "res_url2", "res_url3"])

    async def test_concurrency_limit(self):
        """Verify that at most 'limit' calls are in flight."""
        urls = [f"url{i}" for i in range(10)]
        limit = 3
        in_flight = 0
        max_in_flight = 0
        lock = asyncio.Lock()

        async def mock_fetch(url):
            nonlocal in_flight, max_in_flight
            async with lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
            
            await asyncio.sleep(0.01)
            
            async with lock:
                in_flight -= 1
            return url

        await fetch_all(urls, mock_fetch, limit=limit)
        self.assertLessEqual(max_in_flight, limit)
        self.assertGreater(max_in_flight, 1)

    async def test_retries_on_failure(self):
        """If a call raises Exception, retry up to 'retries' times."""
        urls = ["fail_once", "fail_twice", "success"]
        attempts = {"fail_once": 0, "fail_twice": 0, "success": 0}

        async def mock_fetch(url):
            attempts[url] += 1
            if url == "fail_once":
                if attempts[url] == 1:
                    raise ValueError("First fail")
                return "ok_once"
            if url == "fail_twice":
                if attempts[url] <= 2:
                    raise ValueError("Persistent fail")
                return "ok_twice"
            if url == "success":
                return "ok_success"

        # retries=2 means max 3 attempts total
        result = await fetch_all(urls, mock_fetch, limit=2, retries=2)
        
        self.assertEqual(result, ["ok_once", "ok_twice", "ok_success"])
        self.assertEqual(attempts["fail_once"], 2)
        self.assertEqual(attempts["fail_twice"], 3)
        self.assertEqual(attempts["success"], 1)

    async def test_exhausted_retries_returns_exception(self):
        """If all attempts fail, return the exception instance from the LAST attempt."""
        urls = ["always_fail"]
        last_exception = None

        async def mock_fetch(url):
            nonlocal last_exception
            exc = ValueError("Final error")
            last_exception = exc
            raise exc

        # retries=1 means 2 attempts total
        result = await fetch_all(urls, mock_fetch, limit=1, retries=1)
        
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], ValueError)
        self.assertEqual(str(result[0]), "Final error")

    async def test_duplicate_urls_independent(self):
        """Duplicate urls are fetched independently."""
        urls = ["dup", "dup"]
        call_count = 0

        async def mock_fetch(url):
            nonlocal call_count
            call_count += 1
            return "val"

        await fetch_all(urls, mock_fetch)
        self.assertEqual(call_count, 2)

    async def test_mixed_success_and_failure(self):
        """Handles a mix of successful and permanently failing URLs."""
        urls = ["good", "bad"]
        
        async def mock_fetch(url):
            if url == "good":
                return "ok"
            raise RuntimeError("boom")

        result = await fetch_all(urls, mock_fetch, limit=2, retries=0)
        self.assertEqual(result[0], "ok")
        self.assertIsInstance(result[1], RuntimeError)

if __name__ == "__main__":
    unittest.main()
