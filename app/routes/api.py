from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import UserMovie
from app.services.user_service import (
    initialize_user,
)

api = Blueprint("api", __name__)


@api.route("/user/movies/review", methods=["POST"])
def review_movie():
    user = initialize_user()
    data = request.get_json()
    movie_id = data.get("movie_id")
    decision = data.get("decision")

    if decision not in ["approve", "disapprove"]:
        return jsonify({"error": "Invalid decision value."}), 400

    UserMovie.query.filter_by(user_id=user.id, movie_id=movie_id).delete()
    user_movie = UserMovie(user_id=user.id, movie_id=movie_id, decision=decision)

    db.session.add(user_movie)
    try:
        db.session.commit()
        return jsonify({"message": "Movie reviewed successfully."}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 409


@api.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad Request"}), 400


@api.errorhandler(401)
def unauthorized(error):
    return jsonify({"error": "Unauthorized"}), 401


@api.errorhandler(403)
def forbidden(error):
    return jsonify({"error": "Forbidden"}), 403


@api.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not Found"}), 404


@api.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Internal Server Error"}), 500
