import asyncio

async def fetch_all(urls: list[str], fetch, limit: int = 5, retries: int = 2) -> list:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    
    if not urls:
        return []

    # Semaphore controls the number of concurrent 'fetch' calls
    semaphore = asyncio.Semaphore(limit)

    async def worker(url: str):
        last_exception = None
        # Total attempts = initial attempt (1) + retries
        for _ in range(retries + 1):
            try:
                async with semaphore:
                    return await fetch(url)
            except Exception as e:
                last_exception = e
                # Continue to next iteration for retry
                continue
        
        # If we exhausted all retries, return the last exception caught
        return last_exception

    # Create tasks for all URLs. 
    # Note: We use asyncio.gather to preserve order and wait for all to complete.
    tasks = [worker(url) for url in urls]
    return await asyncio.gather(*tasks)
