from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    make_response,
    g,
)
from flask_jwt_extended import (
    set_access_cookies,
    jwt_required,
    get_jwt_identity,
    verify_jwt_in_request,
    unset_jwt_cookies,
)

from app.extensions import db
from app.models import User, UserMovie
from app.services.user_service import (
    register_user,
    authenticate_user,
    confirm_user_email,
    reset_user_password,
    get_current_user,
)
from app.utils.tmdb import fetch_movie_details
from app.utils.user_management import (
    get_movies_based_on_filter,
    fetch_user_calendar_events,
    send_password_reset_email,
)

html = Blueprint("html", __name__)


def initialize_user():
    verify_jwt_in_request(optional=True)
    g.current_user = get_current_user()
    return g.current_user


@html.route("/", methods=["GET"])
def home():
    initialize_user()
    return render_template("home.html")


@html.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.form
        try:
            user = register_user(data)
            flash(
                "User registered successfully. Please check your email to confirm.",
                "success",
            )
            return redirect(url_for("html.login"))
        except Exception as e:
            flash(str(e), "danger")
            return redirect(url_for("html.register"))
    return render_template("register.html")


@html.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.form
        try:
            access_token = authenticate_user(data)
            response = make_response(redirect(url_for("html.profile")))
            set_access_cookies(response, access_token)
            flash("Logged in successfully.", "success")
            return response
        except Exception as e:
            flash(str(e), "danger")
            return redirect(url_for("html.login"))
    return render_template("login.html")


@html.route("/logout", methods=["POST"])
def logout():
    flash("Logged out successfully.", "success")
    response = make_response(redirect(url_for("html.home")))
    unset_jwt_cookies(response)
    return response


@html.route("/profile", methods=["GET"])
def profile():
    initialize_user()
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return render_template("profile.html", user=user)


@html.route("/confirm-email/<token>", methods=["GET"])
def confirm_email(token):
    try:
        confirm_user_email(token)
        flash("Email confirmed successfully.", "success")
        return redirect(url_for("html.login"))
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("html.home"))


@html.route("/reset-password-request", methods=["GET", "POST"])
def reset_password_request():
    if request.method == "POST":
        data = request.form
        email = data.get("email")
        try:
            user = User.query.filter_by(email=email).first()
            if not user:
                flash("Email not found.", "danger")
                return redirect(url_for("html.reset_password_request"))
            send_password_reset_email(user)
            flash("Password reset email sent.", "success")
            return redirect(url_for("html.login"))
        except Exception as e:
            flash(str(e), "danger")
            return redirect(url_for("html.reset_password_request"))
    return render_template("reset_password_request.html")


@html.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if request.method == "POST":
        data = request.form
        new_password = data.get("new_password")
        try:
            reset_user_password(token, new_password)
            flash("Password reset successfully.", "success")
            return redirect(url_for("html.login"))
        except Exception as e:
            flash(str(e), "danger")
            return redirect(url_for("html.reset_password", token=token))
    return render_template("reset_password.html", token=token)


@html.route("/movies/review", methods=["POST"])
@jwt_required()
def review_movie():
    user_id = get_jwt_identity()
    data = request.form
    movie_id = data.get("movie_id")
    decision = data.get("decision")

    if decision not in ["approve", "disapprove"]:
        flash("Invalid decision value.", "danger")
        return redirect(url_for("html.profile"))

    user_movie = UserMovie(user_id=user_id, movie_id=movie_id, decision=decision)

    db.session.add(user_movie)
    try:
        db.session.commit()
        flash("Movie reviewed successfully.", "success")
        return redirect(url_for("html.profile"))
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))


@html.route("/movies", methods=["GET"])
def get_movies():
    user = initialize_user()
    filter_mode = request.args.get("filter", "pending")

    try:
        movies = get_movies_based_on_filter(user, filter_mode)
        return render_template("movies.html", movies=movies)
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))


@html.route("/movies/<int:movie_id>", methods=["GET"])
def get_movie_details(movie_id):
    try:
        user = initialize_user()
        movie = fetch_movie_details(movie_id, user.language or "en-US")
        if not movie:
            flash("Movie not found.", "danger")
            return redirect(url_for("html.profile"))
        return render_template("movie_details.html", movie=movie)
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))


@html.route("/movies/reviewed/<int:movie_id>", methods=["POST"])
@jwt_required()
def remove_reviewed_movie(movie_id):
    user_id = get_jwt_identity()
    user_movie = UserMovie.query.filter_by(
        user_id=user_id, movie_id=movie_id
    ).first()
    if not user_movie:
        flash("Movie not found in reviewed list.", "danger")
        return redirect(url_for("html.profile"))

    db.session.delete(user_movie)
    try:
        db.session.commit()
        flash("Movie removed from reviewed list.", "success")
        return redirect(url_for("html.profile"))
    except Exception as e:
        db.session.rollback()
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))


@html.route("/calendar", methods=["GET"])
@jwt_required()
def get_user_calendar():
    user_id = get_jwt_identity()
    try:
        calendar_events = fetch_user_calendar_events(user_id)
        return render_template("calendar.html", events=calendar_events)
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))


@html.errorhandler(400)
def bad_request(error):
    return render_template("400.html"), 400


@html.errorhandler(401)
def unauthorized(error):
    return render_template("401.html"), 401


@html.errorhandler(403)
def forbidden(error):
    return render_template("403.html"), 403


@html.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@html.errorhandler(500)
def internal_server_error(error):
    return render_template("500.html"), 500
