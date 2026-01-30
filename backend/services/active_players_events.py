from collections import defaultdict
from typing import Callable, Dict, List, Tuple

from nicegui.client import Client


Subscriber = Tuple[Client, Callable[[dict], None]]
_subscribers: Dict[int, List[Subscriber]] = defaultdict(list)


def subscribe(match_id: int, client: Client, callback: Callable[[dict], None]) -> None:
    _subscribers[match_id].append((client, callback))


def unsubscribe(match_id: int, client: Client) -> None:
    if match_id not in _subscribers:
        return
    _subscribers[match_id] = [
        (c, cb) for c, cb in _subscribers[match_id] if c != client
    ]
    if not _subscribers[match_id]:
        _subscribers.pop(match_id, None)


def notify(match_id: int, payload: dict) -> None:
    for client, callback in list(_subscribers.get(match_id, [])):
        client.safe_invoke(lambda: callback(payload))
