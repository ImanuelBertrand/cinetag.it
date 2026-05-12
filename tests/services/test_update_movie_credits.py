from datetime import UTC, datetime

from app.extensions import db
from app.models.movie import Movie
from app.models.movie_credit import MovieCredit, Person
from app.services.tmdb_service import update_movie_credits


def _make_movie(movie_id: int = 9001) -> Movie:
    movie = Movie(
        id=movie_id,
        original_title="Test Movie",
        popularity=1.0,
        original_language="en",
        info_update_at=datetime.now(UTC),
    )
    db.session.add(movie)
    db.session.commit()
    return movie


def test_persists_directors_writers_and_top_cast(app) -> None:
    with app.app_context():
        movie = _make_movie()

        payload = {
            "cast": [
                {"id": 1, "name": "Lead Actor", "character": "Hero", "order": 0},
                {"id": 2, "name": "Side Actor", "character": "Sidekick", "order": 1},
            ]
            + [
                {"id": 100 + i, "name": f"Extra {i}", "character": "", "order": i + 2}
                for i in range(20)
            ],
            "crew": [
                {"id": 50, "name": "A Director", "job": "Director"},
                {"id": 51, "name": "A Writer", "job": "Screenplay"},
                {"id": 52, "name": "Other", "job": "Sound"},
            ],
        }

        update_movie_credits(movie.id, payload)
        db.session.commit()

        credits = MovieCredit.query.filter_by(movie_id=movie.id).all()
        cast_credits = [c for c in credits if c.department == "cast"]
        crew_credits = [c for c in credits if c.department == "crew"]

        # Capped at 10 cast members
        assert len(cast_credits) == 10
        # Top-billed kept by order
        top_two = sorted(cast_credits, key=lambda c: c.sort_order)[:2]
        assert {c.person_id for c in top_two} == {1, 2}

        crew_by_job = {c.role: c.person_id for c in crew_credits}
        assert crew_by_job == {"Director": 50, "Screenplay": 51}

        lead = db.session.get(Person, 1)
        director = db.session.get(Person, 50)
        assert lead is not None
        assert lead.name == "Lead Actor"
        assert director is not None
        assert director.name == "A Director"
        # Sound crew job dropped, so person 52 is never written
        assert db.session.get(Person, 52) is None


def test_reconciles_changes_on_subsequent_call(app) -> None:
    with app.app_context():
        movie = _make_movie(movie_id=9002)

        update_movie_credits(
            movie.id,
            {
                "cast": [{"id": 1, "name": "Old", "character": "X", "order": 0}],
                "crew": [{"id": 2, "name": "Old Director", "job": "Director"}],
            },
        )
        db.session.commit()

        # Replace cast, swap director, rename existing person
        update_movie_credits(
            movie.id,
            {
                "cast": [{"id": 3, "name": "New", "character": "Y", "order": 0}],
                "crew": [{"id": 2, "name": "Renamed Director", "job": "Director"}],
            },
        )
        db.session.commit()

        credits = MovieCredit.query.filter_by(movie_id=movie.id).all()
        assert {(c.person_id, c.department, c.role) for c in credits} == {
            (3, "cast", "Y"),
            (2, "crew", "Director"),
        }
        # Old cast person row still exists (Person table is shared across movies)
        assert db.session.get(Person, 1) is not None
        renamed = db.session.get(Person, 2)
        assert renamed is not None
        assert renamed.name == "Renamed Director"
