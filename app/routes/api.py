from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_jwt_extended import create_access_token
from werkzeug.exceptions import Unauthorized, BadRequest

from app.extensions import db
from app.models import User, UserMovie
from app.services.user_service import (
    register_user,
    authenticate_user,
    confirm_user_email,
    reset_user_password,
)
from app.utils.user_management import (
    get_movies_based_on_filter,
    fetch_user_calendar_events,
)

api = Blueprint("api", __name__)


@api.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    try:
        register_user(data)
        return jsonify({"message": "User registered successfully."}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 409


@api.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    try:
        access_token = authenticate_user(data)
        return jsonify({"token": access_token}), 200
    except Unauthorized as e:
        return jsonify({"error": str(e)}), 401


@api.route("/auth/confirm-email/<token>", methods=["GET"])
def confirm_email(token):
    try:
        confirm_user_email(token)
        return jsonify({"message": "Email confirmed successfully."}), 200
    except BadRequest as e:
        return jsonify({"error": str(e)}), 400
    except KeyError:
        return jsonify({"error": "User not found."}), 404


@api.route("/auth/reset-password-request", methods=["POST"])
def reset_password_request():
    data = request.get_json()
    email = data.get("email")
    try:
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({"error": "Email not found."}), 404
        send_password_reset_email(user)
        return jsonify({"message": "Password reset email sent."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    token = data.get("token")
    new_password = data.get("new_password")
    try:
        reset_user_password(token, new_password)
        return jsonify({"message": "Password reset successfully."}), 200
    except BadRequest as e:
        return jsonify({"error": str(e)}), 400
    except KeyError:
        return jsonify({"error": "User not found."}), 404


@api.route("/user/movies/review", methods=["POST"])
@jwt_required()
def review_movie():
    user_id = get_jwt_identity()
    data = request.get_json()
    movie_id = data.get("movie_id")
    decision = data.get("decision")

    if decision not in ["approve", "disapprove"]:
        return jsonify({"error": "Invalid decision value."}), 400

    user_movie = UserMovie(user_id=user_id, movie_id=movie_id, decision=decision)

    db.session.add(user_movie)
    try:
        db.session.commit()
        return jsonify({"message": "Movie reviewed successfully."}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 409


@api.route("/user/movies", methods=["GET"])
@jwt_required()
def get_movies():
    user_id = get_jwt_identity()
    filter_mode = request.args.get("filter")

    try:
        movies = get_movies_based_on_filter(user_id, filter_mode)
        return jsonify({"movies": movies}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/movies/<int:movie_id>", methods=["GET"])
def get_movie_details(movie_id):
    try:
        movie = fetch_movie_details(movie_id)
        if not movie:
            return jsonify({"error": "Movie not found."}), 404
        return jsonify({"movie": movie}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/user/movies/reviewed/<int:movie_id>", methods=["DELETE"])
@jwt_required()
def remove_reviewed_movie(movie_id):
    user_id = get_jwt_identity()
    user_movie = UserMovie.query.filter_by(
        user_id=user_id, movie_id=movie_id
    ).first()
    if not user_movie:
        return jsonify({"error": "Movie not found in reviewed list."}), 404

    db.session.delete(user_movie)
    try:
        db.session.commit()
        return jsonify({"message": "Movie removed from reviewed list."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@api.route("/user/calendar", methods=["GET"])
@jwt_required()
def get_user_calendar():
    user_id = get_jwt_identity()
    try:
        calendar_events = fetch_user_calendar_events(user_id)
        return jsonify({"events": calendar_events}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
