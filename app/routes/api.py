from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import UserMovie
from app.services.user_service import (
    initialize_user,
)
from app.utils.user_management import fetch_user_events

api = Blueprint("api", __name__)


@api.route("/user/movies/review", methods=["POST"])
def review_movie():
    user = initialize_user()
    data = request.get_json()
    movie_id = data.get("movie_id")
    decision = data.get("decision")

    if decision not in ["approve", "disapprove", "maybe", "remove"]:
        return jsonify({"error": "Invalid decision value."}), 400

    user_movie = UserMovie.query.filter_by(
        user_id=user.id, movie_id=movie_id
    ).first()

    if decision == "remove":
        if user_movie:
            db.session.delete(user_movie)
            db.session.commit()
        result_decision = None
    else:
        if not user_movie:
            user_movie = UserMovie(
                user_id=user.id, movie_id=movie_id, decision=decision
            )
        else:
            user_movie.decision = decision
        db.session.add(user_movie)
        result_decision = user_movie.decision

    try:
        db.session.commit()
        return (
            jsonify(
                {
                    "success": True,
                    "decision_status": result_decision,
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 409


@api.route("/user/events", methods=["GET"])
def get_user_events():
    user = initialize_user()
    if not user:
        return jsonify({"error": "User not found."}), 404
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify({"error": "Invalid date range."}), 400
    start = datetime.fromisoformat(start)
    end = datetime.fromisoformat(end)
    events = fetch_user_events(user, start, end)
    return jsonify(events)


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
