from app.extensions import db
from app.models.misc_data import MiscData


def test_save_creates_new_entry(app) -> None:
    """Test MiscData.save creates a new entry."""
    with app.app_context():
        MiscData.save("test_key", "test_value")
        db.session.commit()

        data = MiscData.query.filter_by(key="test_key").first()
        assert data is not None
        assert data.value == "test_value"


def test_save_updates_existing_entry(app) -> None:
    """Test MiscData.save updates an existing entry."""
    with app.app_context():
        MiscData.save("update_key", "initial_value")
        db.session.commit()

        MiscData.save("update_key", "updated_value")
        db.session.commit()

        data = MiscData.query.filter_by(key="update_key").all()
        assert len(data) == 1
        assert data[0].value == "updated_value"


def test_save_with_commit(app) -> None:
    """Test MiscData.save with commit=True commits automatically."""
    with app.app_context():
        MiscData.save("commit_key", "commit_value", commit=True)

        data = MiscData.query.filter_by(key="commit_key").first()
        assert data is not None
        assert data.value == "commit_value"


def test_get_returns_value(app) -> None:
    """Test MiscData.get returns the value for an existing key."""
    with app.app_context():
        MiscData.save("get_key", "get_value")
        db.session.commit()

        value = MiscData.get("get_key")
        assert value == "get_value"


def test_get_returns_default_for_missing_key(app) -> None:
    """Test MiscData.get returns default when key doesn't exist."""
    with app.app_context():
        value = MiscData.get("nonexistent_key", default="default_val")
        assert value == "default_val"


def test_get_returns_none_for_missing_key_without_default(app) -> None:
    """Test MiscData.get returns None when key doesn't exist and no default."""
    with app.app_context():
        value = MiscData.get("nonexistent_key_2")
        assert value is None


def test_repr(app) -> None:
    """Test MiscData __repr__."""
    with app.app_context():
        MiscData.save("repr_key", "repr_value")
        db.session.commit()

        data = MiscData.query.filter_by(key="repr_key").first()
        assert "repr_key" in repr(data)
        assert "repr_value" in repr(data)
