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
        
async def api_delete(path: str):
    async with aiohttp.ClientSession() as s:
        async with s.delete(f"{BASE_URL}{path}") as r:
            if r.status != 204:
                raise Exception(f"Failed to delete resource at {path}, status code: {r.status}")
            
async def api_put(path: str, payload: dict):
    async with aiohttp.ClientSession() as s:
        async with s.put(f"{BASE_URL}{path}", json=payload) as r:
            return await r.json()