import pytest

from common.import_ import get_db_and_activity_name


def test_get_db_and_activity_name():
    # Test that an error is raised if no db is provided
    with pytest.raises(ValueError):
        get_db_and_activity_name("test")

    assert get_db_and_activity_name("test_activity", "test_db") == (
        "test_db",
        "test_activity",
    )
    assert get_db_and_activity_name("test_db::test_activity") == (
        "test_db",
        "test_activity",
    )
    assert get_db_and_activity_name("test_db::test_activity", "default_db") == (
        "test_db",
        "test_activity",
    )
