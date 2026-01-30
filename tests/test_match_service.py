from backend.services.match_service import format_lock_detail


def test_format_lock_detail_with_username():
    assert format_lock_detail("alice") == "Match is locked by alice"


def test_format_lock_detail_without_username():
    assert format_lock_detail(None) == "Match is locked by another user"
