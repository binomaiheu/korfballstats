from backend.auth import validate_new_password


def test_password_validation_success():
    assert validate_new_password("Validpass1!") == []


def test_password_validation_missing_requirements():
    assert "New password must be at least 8 characters" in validate_new_password("Ab1!")
    assert "New password must include at least one letter" in validate_new_password("12345678!")
    assert "New password must include at least one number" in validate_new_password("Password!")
    assert "New password must include at least one special character" in validate_new_password("Password1")
