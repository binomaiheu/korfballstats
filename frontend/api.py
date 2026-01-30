import aiohttp
from nicegui import app

BASE_URL = "http://localhost:8855/api/v1"


def _auth_headers() -> dict:
    token = app.storage.user.get("token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


async def _request(method: str, path: str, payload: dict | None = None, auth: bool = True):
    headers = _auth_headers() if auth else {}
    async with aiohttp.ClientSession() as s:
        async with s.request(method, f"{BASE_URL}{path}", json=payload, headers=headers) as r:
            data = None
            try:
                data = await r.json()
            except Exception:
                data = await r.text()
            if r.status >= 400:
                if isinstance(data, dict) and "detail" in data:
                    raise Exception(data["detail"])
                raise Exception(data)
            return data


async def api_get(path: str):
    return await _request("GET", path)


async def api_post(path: str, payload: dict):
    return await _request("POST", path, payload)
        
async def api_delete(path: str):
    await _request("DELETE", path)
            
async def api_put(path: str, payload: dict):
    return await _request("PUT", path, payload)


async def api_login(username: str, password: str):
    return await _request(
        "POST",
        "/auth/login",
        {"username": username, "password": password},
        auth=False,
    )


async def api_change_password(current_password: str, new_password: str):
    return await api_post(
        "/auth/change-password",
        {"current_password": current_password, "new_password": new_password},
    )