import pytest

from app.db import SessionLocal
from app.services.auth_states import AuthStateError, consume_auth_state, issue_auth_state


def test_auth_state_is_one_time_and_return_path_is_safe() -> None:
    with SessionLocal() as db:
        state = issue_auth_state(db, "qr", "https://evil.example/")
        assert consume_auth_state(db, state, "qr") == "/"
        with pytest.raises(AuthStateError, match="已使用"):
            consume_auth_state(db, state, "qr")
