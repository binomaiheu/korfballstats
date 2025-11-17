import aiohttp

BASE_URL = "http://localhost:8855/api/v1"


async def api_get(path: str):
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{BASE_URL}{path}") as r:
            return await r.json()


async def api_post(path: str, payload: dict):
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{BASE_URL}{path}", json=payload) as r:
            return await r.json()
        