import aiohttp
from nicegui import app

BASE_URL = "http://localhost:8855/api/v1"


def _auth_headers() -> dict:
    token = app.storage.user.get("token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


async def api_get(path: str):
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{BASE_URL}{path}", headers=_auth_headers()) as r:
            data = await r.json()
            if r.status >= 400:
                raise Exception(data)
            return data


async def api_post(path: str, payload: dict):
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{BASE_URL}{path}", json=payload, headers=_auth_headers()) as r:
            data = await r.json()
            if r.status >= 400:
                raise Exception(data)
            return data
        
async def api_delete(path: str):
    async with aiohttp.ClientSession() as s:
        async with s.delete(f"{BASE_URL}{path}", headers=_auth_headers()) as r:
            if r.status != 204:
                raise Exception(f"Failed to delete resource at {path}, status code: {r.status}")
            
async def api_put(path: str, payload: dict):
    async with aiohttp.ClientSession() as s:
        async with s.put(f"{BASE_URL}{path}", json=payload, headers=_auth_headers()) as r:
            data = await r.json()
            if r.status >= 400:
                raise Exception(data)
            return data


async def api_login(username: str, password: str):
    async with aiohttp.ClientSession() as s:
        async with s.post(
            f"{BASE_URL}/auth/login",
            json={"username": username, "password": password},
        ) as r:
            data = await r.json()
            if r.status >= 400:
                raise Exception(data)
            return data