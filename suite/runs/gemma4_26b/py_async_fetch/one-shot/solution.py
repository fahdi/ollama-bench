import asyncio

async def fetch_all(urls: list[str], fetch, limit: int = 5, retries: int = 2) -> list:
    """
    Fetches all URLs concurrently with a limit on in-flight requests.
    Retries failed requests up to 'retries' times.
    Returns results in the original order.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")
    
    if not urls:
        return []

    # Semaphore controls the number of concurrent in-flight requests
    semaphore = asyncio.Semaphore(limit)

    async def worker(url: str):
        last_exception = None
        # Total attempts = 1 (initial) + retries
        for attempt in range(retries + 1):
            try:
                async with semaphore:
                    return await fetch(url)
            except Exception as e:
                last_exception = e
                # If we have retries left, the loop continues immediately
                continue
        
        # If all attempts failed, return the last exception instance
        return last_exception

    # Create tasks for all URLs. 
    # Note: We don't use a worker pool pattern here because we need to 
    # preserve order and handle individual retry logic per URL.
    # The semaphore inside the worker ensures the concurrency limit.
    tasks = [asyncio.create_task(worker(url)) for url in urls]
    
    # Wait for all tasks to complete and gather results in order
    return await asyncio.gather(*tasks)

if __name__ == "__main__":
    # Quick test harness
    async def mock_fetch(url: str):
        if "fail" in url:
            raise ValueError(f"Error at {url}")
        return f"Success: {url}"

    async def main():
        urls = ["a", "fail_1", "b", "fail_2", "c"]
        # limit=2, retries=1
        results = await fetch_all(urls, mock_fetch, limit=2, retries=1)
        print(results)
        # Expected: ['Success: a', ValueError('Error at fail_1'), 'Success: b', ValueError('Error at fail_2'), 'Success: c']

    asyncio.run(main())
