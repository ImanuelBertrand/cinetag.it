import logging
import re
from collections import defaultdict

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    make_response,
    current_app,
    g,
)
from flask_jwt_extended import (
    unset_jwt_cookies,
)

from app.extensions import db, bcrypt
from app.models import User, TmdbLanguage, TmdbRegion
from app.services.user_service import (
    get_movies_based_on_filter,
    fetch_user_events,
    confirm_user_email,
    authenticate_user,
    reset_user_password,
    hash_password,
    queue_confirmation_mail,
)
from app.services.user_service import initialize_user
from app.utils.email import queue_email
from app.utils.tmdb import fetch_movie_details

html = Blueprint("html", __name__)
_logger = logging.getLogger(__name__)


@html.route("/", methods=["GET"])
def home():
    initialize_user()
    return render_template("home.html")


def _validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


def _validate_password(password):
    return len(password) >= 8


def register_post(user: User):
    """
    Register a new user or update the temporary user with the provided data.
    :param user: User
    :return:
    """
    data = request.form
    email = data.get("email")

    # e-mail sanity check
    if not email:
        flash("Email is required.", "danger")
        return None
    if not _validate_email(email):
        flash("Invalid email.", "danger")
        return None

    # password sanity check
    password = data.get("password")
    if not password:
        flash("Password is required.", "danger")
        return None
    if not _validate_password(password):
        flash("Password must be at least 8 characters.", "danger")
        return None

    user.new_email = email
    user.name = data.get("name")
    user.password = hash_password(password)
    queue_confirmation_mail(user)

    db.session.add(user)
    db.session.commit()

    try:
        msg = (
            "User registered successfully. Please check your email to confirm."
            "You won't be able to login until you confirm your email."
            "If you don't see the email, you can resend it in your profile."
        )
        flash(msg, "success")
        return redirect(url_for("html.profile"))
    except Exception as e:
        flash(str(e), "danger")
        return None


@html.route("/register", methods=["GET", "POST"])
def register():
    user = initialize_user()
    form_data = defaultdict(str)

    if request.method == "POST":
        form_data.update(request.form)
        register_result = register_post(user)
        if register_result:
            return register_result

    return render_template("register.html", form_data=form_data)


@html.route("/merge-temporary-user", methods=["POST"])
def merge_temporary_user():
    user = initialize_user()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("html.profile"))

    data = request.form
    merge = data.get("merge")
    delete = data.get("delete")

    if bool(merge) == bool(delete):
        flash("Invalid request.", "danger")
        return redirect(url_for("html.profile"))

    temp_user = user.temporary_user_id
    if not temp_user:
        flash("No temporary data found.", "danger")
        return redirect(url_for("html.profile"))

    temp_user = User.query.get(temp_user)

    if merge:
        user_movies = {movie.id: movie for movie in user.user_movies}
        for temp_movie in temp_user.user_movies:
            if temp_movie.id not in user_movies:
                temp_movie.user_id = user.id
                db.session.add(temp_movie)
            elif temp_movie.updated_at > user_movies[temp_movie.id].updated_at:
                user_movies[temp_movie.id].delete()
                temp_movie.user_id = user.id
            else:
                temp_movie.delete()
            db.session.commit()
        flash("Movie tags were successfully imported.", "success")

    db.session.delete(temp_user)
    user.temporary_user_id = None
    db.session.commit()

    if delete:
        flash("Temporary data deleted.", "success")

    return redirect(url_for("html.profile"))


@html.route("/login", methods=["GET", "POST"])
def login():
    pre_login_user = initialize_user()
    _logger.info("pre_login_user: %s", pre_login_user)

    if request.method == "GET":
        return render_template("login.html")

    data = request.form
    try:
        user = authenticate_user(data)
        _logger.info("user: %s", user)
        _logger.info("pre_login_user movies: %s", pre_login_user.user_movies)
        if not pre_login_user.user_movies:
            db.session.delete(pre_login_user)
        else:
            user.temporary_user_id = pre_login_user.id
            db.session.add(user)
            db.session.commit()

        g.current_user = user
        return make_response(redirect(url_for("html.profile")))
    except Exception as e:
        _logger.exception("Error authenticating user.")
        flash(str(e), "danger")
        return redirect(url_for("html.login"))


@html.route("/logout", methods=["POST"])
def logout():
    flash("Logged out successfully.", "success")
    response = make_response(redirect(url_for("html.home")))
    unset_jwt_cookies(response)
    return response


@html.route("/delete_data", methods=["POST"])
def delete_data():
    """
    Similar as logout(), but with a different message, and it will delete the
    temporary user.
    :return:
    """
    user = initialize_user()
    if user:
        db.session.delete(user)
        db.session.commit()
    flash("All your data is gone with the wind.", "success")
    response = make_response(redirect(url_for("html.profile")))
    unset_jwt_cookies(response)
    return response


def profile_post(user, form_data):
    def confirm_current_pw():
        current_pw = form_data.get("current_password")
        if not current_pw:
            raise ValueError("Current password is required.")
        pw_is_valid = bcrypt.check_password_hash(user.password, current_pw)
        if not pw_is_valid:
            raise ValueError("Invalid current password.")

    data = request.form

    form_data.update(data)
    form_data["new_password"] = ""
    form_data["new_password_confirmation"] = ""
    form_data["current_password"] = ""

    # Make initial registration available only on the registration page
    # to avoid edge cases here
    has_new_mail = bool(data.get("email"))
    has_new_pw = bool(data.get("new_password"))
    has_old_pw = bool(user.password)
    has_old_email = bool(user.email)
    if (not has_old_email or not has_old_pw) and (has_new_pw or has_new_mail):
        raise ValueError("Registration is only possible on the registration page.")

    # e-mail sanity check
    if has_new_mail and not _validate_email(data.get("email")):
        flash("Invalid email.", "danger")
        return None

    # password sanity check
    if has_new_pw and not _validate_password(data.get("new_password")):
        flash("Password must be at least 8 characters.", "danger")
        return None

    # Set new credentials
    if has_new_pw and has_new_mail:
        # No old password, so no confirmation possible
        user.password = hash_password(data.get("new_password"))
        user.new_email = data.get("email")
        queue_confirmation_mail(user)
        flash("Please check your inbox for a confirmation email.", "info")

    # Removing the credentials (triggered by empty email field)
    if not has_new_mail and has_old_email:
        confirm_current_pw()
        user.password = None
        user.email = None

    # Changing the password
    if has_new_pw and has_old_pw:
        confirm_current_pw()
        user.password = hash_password(data.get("new_password"))
        flash("Password changed successfully.", "success")

    # Changing the email address
    if has_new_mail and has_old_email and data.get("email") != user.email:
        confirm_current_pw()

        existing_user = User.query.filter_by(email=data.get("email")).first()
        if existing_user:
            flash("Email address already in use.", "danger")
        else:
            user.new_email = data.get("email")
            queue_confirmation_mail(user)
            flash("Please check your inbox for a confirmation email.", "info")
            form_data["email"] = user.email  # reset email field in the UI

    user.name = data.get("name")
    user.language = data.get("language")
    user.region = data.get("region")

    db.session.add(user)
    db.session.commit()
    flash("Profile saved successfully.", "success")


@html.route("/profile", methods=["GET", "POST"])
def profile():
    user = initialize_user()

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("html.home"))

    form_data = defaultdict(str)
    form_data["name"] = user.name or ""
    form_data["language"] = user.language or ""
    form_data["region"] = user.region or ""
    form_data["email"] = user.email or ""

    if request.method == "POST":
        try:
            profile_post(user, form_data)
        except Exception as e:
            _logger.exception("Error updating profile.")
            flash(str(e), "danger")

    def create_select_options(objects):
        result = {}
        for obj in objects:
            if obj.sort_order < 1000:
                result[obj.code] = obj.get_name()
            else:
                break
        result[""] = "──────────"
        for obj in objects:
            if obj.code in result:
                continue
            result[obj.code] = obj.get_name()
        return result

    regions = TmdbRegion.query.order_by(TmdbRegion.sort_order).all()
    languages = TmdbLanguage.query.order_by(TmdbLanguage.sort_order).all()

    # double make sure we never send the password back through the air
    form_data["new_password"] = ""
    form_data["new_password_confirmation"] = ""
    form_data["current_password"] = ""
    return render_template(
        "profile.html",
        user=user,
        form_data=form_data,
        regions=create_select_options(regions),
        languages=create_select_options(languages),
    )


@html.route("/confirm-email/<token>", methods=["GET"])
def confirm_email(token):
    try:
        confirm_user_email(token)
        flash("Email confirmed successfully.", "success")
    except Exception as e:
        _logger.exception("Error confirming email.")
        flash(str(e), "danger")

    return redirect(url_for("html.profile"))


@html.route("/request-confirmation-mail", methods=["POST"])
def request_confirmation_email():
    user = initialize_user()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("html.home"))

    if not user.new_email:
        flash("No email confirmation is pending", "danger")
        return redirect(url_for("html.profile"))

    try:
        queue_confirmation_mail(user)
        flash("Confirmation email sent.", "success")
        return redirect(url_for("html.profile"))
    except Exception as e:
        _logger.exception("Error sending confirmation email.")
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))


@html.route("/forgot-password", methods=["GET", "POST"])
def reset_password_request():
    if request.method == "POST":
        data = request.form
        email = data.get("email")

        if not email:
            flash("Email is required.", "danger")
            return redirect(url_for("html.reset_password_request"))

        try:
            user = User.query.filter_by(email=email).first()
            if user:
                queue_email(user, "reset")
            flash(
                "If the email is registered, a password reset email will be sent.",
                "info",
            )
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
            _logger.exception("Error resetting password.")
            flash(str(e), "danger")
            return redirect(url_for("html.reset_password", token=token))
    return render_template("reset_password.html", token=token)


@html.route("/movies/<filter_mode>", methods=["GET"])
def get_movies(filter_mode):
    user = initialize_user()
    if filter_mode not in {
        "all",
        "maybe",
        "pending",
        "reviewed",
        "approved",
        "disapproved",
    }:
        flash("Invalid filter mode.", "danger")
        return redirect(url_for("html.profile"))

    try:
        movies = get_movies_based_on_filter(user, filter_mode)
        return render_template(
            "movie_list.html", movies=movies, filter_mode=filter_mode
        )
    except Exception as e:
        _logger.exception("Error fetching movies.")
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))


@html.route("/movie/<int:movie_id>", methods=["GET"])
def get_movie_details(movie_id):
    try:
        user = initialize_user()
        language = user.language or current_app.config.DEFAULT_LANGUAGE
        movie = fetch_movie_details(movie_id, language)
        if not movie:
            flash("Movie not found.", "danger")
            return redirect(url_for("html.profile"))
        return render_template("movie_details.html", movie=movie)
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))


@html.route("/release-dates", methods=["GET"])
def get_user_release_dates():
    user = initialize_user()
    try:
        releases = fetch_user_events(user)
        return render_template("release_dates.html", releases=releases)
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))


@html.route("/calendar", methods=["GET"])
def get_user_calendar():
    user = initialize_user()
    try:
        releases = fetch_user_events(user)
        return render_template("calendar.html", releases=releases)
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
