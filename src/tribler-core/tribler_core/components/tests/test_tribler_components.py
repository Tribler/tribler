import pytest

from tribler_core.components.base import Session, SessionError


def test_session_context_manager(tribler_config):
    session1 = Session(tribler_config, [])
    session2 = Session(tribler_config, [])
    session3 = Session(tribler_config, [])

    with pytest.raises(SessionError, match="Default session was not set"):
        Session.current()

    session1.set_as_default()
    assert Session.current() is session1

    with session2:
        assert Session.current() is session2
        with session3:
            assert Session.current() is session3
        assert Session.current() is session2
    assert Session.current() is session1

    Session.unset_default_session()

    with pytest.raises(SessionError, match="Default session was not set"):
        Session.current()
