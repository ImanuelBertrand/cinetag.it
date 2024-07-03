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
    jwt_required,
    get_jwt_identity,
    unset_jwt_cookies,
)

from app.extensions import db, bcrypt
from app.models import User, TmdbLanguage, TmdbRegion
from app.services.user_service import (
    reset_user_password,
    initialize_user,
    create_temporary_user,
)
from app.utils.email import send_confirmation_email
from app.utils.tmdb import fetch_movie_details
from app.utils.user_management import (
    get_movies_based_on_filter,
    fetch_user_calendar_events,
    send_password_reset_email,
    confirm_user_email,
    authenticate_user,
)

html = Blueprint("html", __name__)
_logger = logging.getLogger(__name__)


@html.route("/", methods=["GET"])
def home():
    initialize_user()
    return render_template("home.html")


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
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        flash("Invalid email.", "danger")
        return None

    # password sanity check
    password = data.get("password")
    if not password:
        flash("Password is required.", "danger")
        return None
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "danger")
        return None

    if not user:
        user = create_temporary_user()

    user.email = email
    user.email_confirmed = False
    user.name = data.get("name")
    user.password = bcrypt.generate_password_hash(password).decode("utf-8")

    send_confirmation_email(user)

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


@html.route("/login", methods=["GET", "POST"])
def login():
    pre_login_user = initialize_user()
    if request.method == "POST":
        data = request.form
        try:
            user = authenticate_user(data)
            if not pre_login_user.user_movies:
                db.session.delete(pre_login_user)
            else:
                # TODO show option to merge date in /profile
                pass

            g.current_user = user
            return make_response(redirect(url_for("html.profile")))
        except Exception as e:
            _logger.exception("Error authenticating user.")
            flash(str(e), "danger")
            return redirect(url_for("html.login"))
    return render_template("login.html")


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
        data = request.form
        form_data.update(data)
        debug_dict = {}
        debug_dict.update(data)
        _logger.info("Updating user profile: %s", debug_dict)
        user.name = data.get("name")
        user.language = data.get("language")
        user.region = data.get("region")

        if not data.get("email") and user.email:
            user.email = None

        if data.get("email") and data.get("email") != user.email:
            existing_user = User.query.filter_by(email=data.get("email")).first()
            if existing_user:
                flash("Email already in use.", "danger")
            else:
                user.email = data.get("email")
                user.email_confirmed = False
                send_confirmation_email(user)
                flash("Please check your inbox for a confirmation email.", "info")

        db.session.add(user)
        db.session.commit()
        flash("Profile saved successfully.", "success")

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

    return redirect(url_for("html.login"))


@html.route("/request-confirmation-mail", methods=["POST"])
def request_confirmation_email():
    user = initialize_user()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("html.home"))

    if not user.email:
        flash("Email is required to send confirmation email.", "danger")
        return redirect(url_for("html.profile"))

    if user.email_confirmed:
        flash("Email already confirmed.", "info")
        return redirect(url_for("html.profile"))

    try:
        send_confirmation_email(user)
        flash("Confirmation email sent.", "success")
        return redirect(url_for("html.profile"))
    except Exception as e:
        _logger.exception("Error sending confirmation email.")
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))


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


@html.route("/movies/<filter_mode>", methods=["GET"])
def get_movies(filter_mode):
    user = initialize_user()
    if filter_mode not in {"pending", "reviewed", "approved", "disapproved"}:
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
