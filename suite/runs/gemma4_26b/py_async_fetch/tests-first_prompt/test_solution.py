import unittest
import asyncio
from solution import fetch_all

class TestFetchAll(unittest.IsolatedAsyncioTestCase):
    async def test_empty_list(self):
        self.assertEqual(await fetch_all([], lambda x: x), [])

    async def test_basic_success(self):
        urls = ["a", "b", "c"]
        async def fetch(url):
            return f"res_{url}"
        results = await fetch_all(urls, fetch)
        self.assertEqual(results, ["res_a", "res_b", "res_c"])

    async def test_concurrency_limit(self):
        # We track how many are in flight. 
        # If limit is 2, we should never have more than 2 active tasks.
        urls = [str(i) for i in range(10)]
        in_flight = 0
        max_in_flight = 0
        lock = asyncio.Lock()

        async def fetch(url):
            nonlocal in_flight, max_in_flight
            async with lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
            
            await asyncio.sleep(0.01)
            
            async with lock:
                in_flight -= 1
            return url

        limit = 3
        await fetch_all(urls, fetch, limit=limit)
        self.assertLessEqual(max_in_flight, limit)

    async def test_retries_and_failure(self):
        # url_fail will fail 3 times. With retries=2, it should fail total 3 times (1 original + 2 retries)
        # and return the last exception.
        attempts = {"fail": 0, "success": 0}

        async def fetch(url):
            if url == "fail":
                attempts["fail"] += 1
                raise ValueError("Permanent Failure")
            if url == "success":
                attempts["success"] += 1
                return "ok"
            return "other"

        urls = ["fail", "success", "other"]
        # retries=2 means max 3 attempts total
        results = await fetch_all(urls, fetch, limit=2, retries=2)
        
        self.assertIsInstance(results[0], ValueError)
        self.assertEqual(results[0].args[0], "Permanent Failure")
        self.assertEqual(results[1], "ok")
        self.assertEqual(results[2], "other")
        self.assertEqual(attempts["fail"], 3)

    async def test_partial_retry_success(self):
        # url_retry fails once, then succeeds.
        attempts = {"retry": 0}

        async def fetch(url):
            if url == "retry":
                attempts["retry"] += 1
                if attempts["retry"] == 1:
                    raise RuntimeError("First try failed")
                return "recovered"
            return "normal"

        urls = ["retry", "normal"]
        results = await fetch_all(urls, fetch, retries=1)
        self.assertEqual(results, ["recovered", "normal"])
        self.assertEqual(attempts["retry"], 2)

    async def test_invalid_limit(self):
        with self.assertRaises(ValueError):
            await fetch_all(["a"], lambda x: x, limit=0)
        with self.assertRaises(ValueError):
            await fetch_all(["a"], lambda x: x, limit=-1)

    async def test_order_preservation(self):
        # Use sleep to ensure they finish out of order
        async def fetch(url):
            if url == "slow":
                await asyncio.sleep(0.05)
            return url

        urls = ["fast", "slow", "medium"]
        results = await fetch_all(urls, fetch)
        self.assertEqual(results, ["fast", "slow", "medium"])

if __name__ == "__main__":
    unittest.main()
