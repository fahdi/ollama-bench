import asyncio
async def fetch_all(urls, fetch, limit=5, retries=2):
    if limit < 1: raise ValueError("limit")
    sem = asyncio.Semaphore(limit)
    async def one(u):
        last = None
        for _ in range(retries + 1):
            async with sem:
                try: return await fetch(u)
                except Exception as e: last = e
        return last
    return list(await asyncio.gather(*(one(u) for u in urls)))
