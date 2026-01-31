from collections import defaultdict
from dataclasses import dataclass
import time
from typing import Dict, Set, List


@dataclass
class JoinRequest:
    match_id: int
    requester_user_id: int
    requester_username: str
    created_at: float


_match_collaborators: Dict[int, Set[int]] = defaultdict(set)
_pending_requests: Dict[int, List[JoinRequest]] = defaultdict(list)


def add_collaborator(match_id: int, user_id: int) -> None:
    _match_collaborators[match_id].add(user_id)


def remove_collaborator(match_id: int, user_id: int) -> None:
    _match_collaborators[match_id].discard(user_id)


def is_collaborator(match_id: int, user_id: int) -> bool:
    return user_id in _match_collaborators.get(match_id, set())


def list_collaborators(match_id: int) -> Set[int]:
    return set(_match_collaborators.get(match_id, set()))


def add_request(match_id: int, user_id: int, username: str) -> JoinRequest:
    req = JoinRequest(
        match_id=match_id,
        requester_user_id=user_id,
        requester_username=username,
        created_at=time.time(),
    )
    _pending_requests[match_id].append(req)
    return req


def get_requests(match_id: int) -> List[JoinRequest]:
    return list(_pending_requests.get(match_id, []))


def pop_request(match_id: int, requester_user_id: int) -> JoinRequest | None:
    requests = _pending_requests.get(match_id, [])
    for idx, req in enumerate(requests):
        if req.requester_user_id == requester_user_id:
            return requests.pop(idx)
    return None
