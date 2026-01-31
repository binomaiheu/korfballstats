from collections import defaultdict
from typing import Callable, Dict, List, Tuple

from nicegui.client import Client


Subscriber = Tuple[Client, Callable[[dict], None]]
_subscribers: Dict[int, List[Subscriber]] = defaultdict(list)


def subscribe(user_id: int, client: Client, callback: Callable[[dict], None]) -> None:
    _subscribers[user_id].append((client, callback))


def unsubscribe(user_id: int, client: Client) -> None:
    if user_id not in _subscribers:
        return
    _subscribers[user_id] = [
        (c, cb) for c, cb in _subscribers[user_id] if c != client
    ]
    if not _subscribers[user_id]:
        _subscribers.pop(user_id, None)


def notify(user_id: int, payload: dict) -> None:
    for client, callback in list(_subscribers.get(user_id, [])):
        client.safe_invoke(lambda: callback(payload))
