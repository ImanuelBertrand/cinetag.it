from app.extensions import db
from app.models.tmdb_language import TmdbLanguage
from app.models.tmdb_region import TmdbRegion

# TmdbLanguage tests


def test_tmdb_language_create_from_tmdb(app) -> None:
    """Test TmdbLanguage.create_from_tmdb creates the correct instance."""
    with app.app_context():
        data = {"iso_639_1": "fr", "english_name": "French", "name": "Français"}
        lang = TmdbLanguage.create_from_tmdb(data)

        assert lang.code == "fr"
        assert lang.english_name == "French"
        assert lang.name == "Français"


def test_tmdb_language_create_from_tmdb_empty_name(app) -> None:
    """Test TmdbLanguage.create_from_tmdb with empty name uses empty string."""
    with app.app_context():
        data = {"iso_639_1": "xx", "english_name": "Unknown", "name": ""}
        lang = TmdbLanguage.create_from_tmdb(data)

        assert lang.name == ""


def test_tmdb_language_create_from_tmdb_question_mark_name(app) -> None:
    """Test TmdbLanguage.create_from_tmdb with '???' name uses empty string."""
    with app.app_context():
        data = {"iso_639_1": "xx", "english_name": "Unknown", "name": "???"}
        lang = TmdbLanguage.create_from_tmdb(data)

        assert lang.name == ""


def test_tmdb_language_update_from_tmdb_no_changes(app) -> None:
    """Test TmdbLanguage.update_from_tmdb returns False when nothing changes."""
    with app.app_context():
        lang = TmdbLanguage(code="de", english_name="German", name="Deutsch")
        db.session.add(lang)
        db.session.commit()

        data = {"english_name": "German", "name": "Deutsch"}
        updated = lang.update_from_tmdb(data)
        assert updated is False


def test_tmdb_language_update_from_tmdb_with_changes(app) -> None:
    """Test TmdbLanguage.update_from_tmdb returns True when data changes."""
    with app.app_context():
        lang = TmdbLanguage(code="es", english_name="Spanish", name="Español")
        db.session.add(lang)
        db.session.commit()

        data = {"english_name": "Spanish Updated", "name": "Español Updated"}
        updated = lang.update_from_tmdb(data)
        assert updated is True
        assert lang.english_name == "Spanish Updated"
        assert lang.name == "Español Updated"


def test_tmdb_language_get_name_with_name(app) -> None:
    """Test TmdbLanguage.get_name returns name when set."""
    with app.app_context():
        lang = TmdbLanguage(code="it", english_name="Italian", name="Italiano")
        assert lang.get_name() == "Italiano"


def test_tmdb_language_get_name_fallback(app) -> None:
    """Test TmdbLanguage.get_name falls back to english_name when name is empty."""
    with app.app_context():
        lang = TmdbLanguage(code="xx", english_name="Unknown", name="")
        assert lang.get_name() == "Unknown"


# TmdbRegion tests


def test_tmdb_region_create_from_tmdb(app) -> None:
    """Test TmdbRegion.create_from_tmdb creates the correct instance."""
    with app.app_context():
        data = {
            "iso_3166_1": "FR",
            "english_name": "France",
            "native_name": "France",
        }
        region = TmdbRegion.create_from_tmdb(data)

        assert region.code == "FR"
        assert region.english_name == "France"
        assert region.native_name == "France"


def test_tmdb_region_update_from_tmdb_no_changes(app) -> None:
    """Test TmdbRegion.update_from_tmdb returns False when nothing changes."""
    with app.app_context():
        region = TmdbRegion(
            code="DE", english_name="Germany", native_name="Deutschland"
        )
        db.session.add(region)
        db.session.commit()

        data = {"english_name": "Germany", "native_name": "Deutschland"}
        updated = region.update_from_tmdb(data)
        assert updated is False


def test_tmdb_region_update_from_tmdb_with_changes(app) -> None:
    """Test TmdbRegion.update_from_tmdb returns True when data changes."""
    with app.app_context():
        region = TmdbRegion(code="IT", english_name="Italy", native_name="Italia")
        db.session.add(region)
        db.session.commit()

        data = {"english_name": "Italy Updated", "native_name": "Italia Updated"}
        updated = region.update_from_tmdb(data)
        assert updated is True
        assert region.english_name == "Italy Updated"
        assert region.native_name == "Italia Updated"


def test_tmdb_region_get_name(app) -> None:
    """Test TmdbRegion.get_name returns native_name when set."""
    with app.app_context():
        region = TmdbRegion(code="JP", english_name="Japan", native_name="日本")
        assert region.get_name() == "日本"


def test_tmdb_region_get_name_fallback(app) -> None:
    """Test TmdbRegion.get_name falls back to english_name."""
    with app.app_context():
        region = TmdbRegion(code="XX", english_name="Unknown", native_name="")
        assert region.get_name() == "Unknown"


def test_tmdb_region_to_dict(app) -> None:
    """Test TmdbRegion.to_dict returns correct dictionary."""
    with app.app_context():
        region = TmdbRegion(
            code="US", english_name="United States", native_name="United States"
        )
        db.session.add(region)
        db.session.commit()

        result = region.to_dict()
        assert result["code"] == "US"
        assert result["english_name"] == "United States"
        assert result["native_name"] == "United States"
        assert "id" in result
        assert "sort_order" in result
