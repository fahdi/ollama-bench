import asyncio

async def fetch_all(urls: list[str], fetch, limit: int = 5, retries: int = 2) -> list:
    """
    Fetches all URLs using the provided async fetch function with concurrency control and retries.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")
    
    if not urls:
        return []

    # Semaphore controls the number of concurrent 'fetch' calls
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
                # If we have more retries left, the loop continues immediately
                continue
        
        # If we exhausted all retries, return the last exception caught
        return last_exception

    # Create tasks for all URLs. 
    # Note: We create all tasks at once, but the semaphore inside 'worker' 
    # ensures only 'limit' number of 'fetch' calls are active.
    tasks = [asyncio.create_task(worker(url)) for url in urls]
    
    # Wait for all tasks to complete and gather results in order
    return await asyncio.gather(*tasks)
