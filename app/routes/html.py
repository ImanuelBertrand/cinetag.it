import logging
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from babel.dates import format_date
from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_jwt_extended import (
    unset_jwt_cookies,
)

from app.errors import UserFeedbackError
from app.extensions import bcrypt, db
from app.models.movie import Movie
from app.models.movie_region_info import MovieRegionInfo
from app.models.notification_channel import NotificationChannel
from app.models.tmdb_language import TmdbLanguage
from app.models.tmdb_region import TmdbRegion
from app.models.user import User
from app.models.user_calendar import UserCalendar
from app.models.user_movie import UserMovie
from app.services.image_service import ensure_image_exists, get_image_url
from app.services.user_service import (
    authenticate_user,
    confirm_user_email,
    fetch_user_events,
    get_current_user,
    hash_password,
    queue_confirmation_mail,
    reset_user_password,
)
from app.utils.auth import generate_new_tokens
from app.utils.email import queue_email
from app.utils.ics import create_ics_file

html = Blueprint("html", __name__)
_logger = logging.getLogger(__name__)

ONE_DAY = 86400
MIN_PASSWORD_LENGTH = 8


@html.route("/sw.js")
def service_worker():
    return send_from_directory("static/js", "sw.js")


@html.route("/", methods=["GET"])
def home():
    return render_template("home.html")


def _validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


def _validate_password(password):
    return len(password) >= MIN_PASSWORD_LENGTH


def validate_register_post(user: User, data: dict) -> bool:
    # --- Time-based check: too fast submission or too old form (using old data?) ---
    try:
        form_ts = int(data.get("form_rendered_at", "0"))
    except ValueError:
        form_ts = 0

    now = int(datetime.now(UTC).timestamp())
    min_seconds = 3  # adjust as desired
    if form_ts and (now - form_ts) < min_seconds:
        flash("Please take a moment to complete the form.", "danger")
        return False

    if form_ts and (now - form_ts) > ONE_DAY:
        flash("Something went wrong. Please try again.", "danger")
        return False

    # --- JavaScript challenge: ensure a minimal JS executed ---
    if (data.get("form_state") or "0") != "initializing":
        flash("Something went wrong. Please try again.", "danger")
        return False

    return True


def validate_register_post_credentials(email: str, password: str) -> bool:
    # password sanity check
    if not password:
        flash("Password is required.", "danger")
        return False
    if not _validate_password(password):
        flash("Password must be at least 8 characters.", "danger")
        return False

    # e-mail sanity check
    if not email:
        flash("Email is required.", "danger")
        return False
    if not _validate_email(email):
        flash("Invalid email.", "danger")
        return False

    existing_user = User.query.filter(
        db.or_(
            User.email == email,
            User.new_email == email,
        )
    ).first()

    if existing_user:
        flash("Email address already in use.", "danger")
        return False

    return True


def register_post(user: User):
    """
    Register a new user or update the temporary user with the provided data.

    In CineTagIt's unique authentication flow, users start with a
    temporary anonymous account.
    This function converts that temporary account into a permanent one
    by adding an email address and password.

    The function:
    1. Validates the email and password
    2. Sets the email and password on the user object
    3. Queues a confirmation email
    4. Saves the updated user to the database

    This approach allows users
    to use the application before explicitly registering
    and ensures no data is lost when they decide to register.

    Args:
        user: The User object to update (typically a temporary anonymous user)

    Returns:
        A redirect response or None if there was an error
    """
    data = request.form

    # --- Honeypot: hidden field bots may fill ---
    hp_value = (data.get("website") or "").strip()
    if hp_value:
        # Quietly pretend success but do nothing.
        _logger.info("Honeypot field filled, request ignored")
        flash("Thanks! Please check your email to confirm.", "success")
        return redirect(url_for("html.profile"))

    if not validate_register_post(user, data):
        return None

    email = data.get("email")
    password = data.get("password")
    if not validate_register_post_credentials(email, password):
        return None

    user.new_email = email
    user.name = data.get("name")
    user.password = hash_password(password)
    queue_confirmation_mail(user)

    db.session.add(user)
    db.session.commit()

    try:
        msg = "User registered successfully. Please check your email to confirm."
        flash(msg, "success")
        return redirect(url_for("html.profile"))
    except UserFeedbackError as e:
        flash(str(e), "danger")
        return None
    except Exception:
        _logger.exception("Error registering user.")
        return None


@html.route("/register", methods=["GET", "POST"])
def register():
    user = get_current_user()
    form_data = defaultdict(str)

    if request.method == "POST":
        form_data.update(request.form)
        register_result = register_post(user)
        if register_result:
            return register_result
    else:
        # Provide a render timestamp for the template (UTC seconds)
        form_data["form_rendered_at"] = str(int(datetime.now(UTC).timestamp()))

    return render_template("register.html", form_data=form_data)


@html.route("/merge-temporary-user", methods=["POST"])
def merge_temporary_user():
    user = get_current_user()
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

    if temp_user.email:
        # temporary users should not be able to have email associated
        _logger.error(":%s has email: %s", user.email, temp_user.email)
        flash("Temporary user has email associated.", "danger")
        return redirect(url_for("html.profile"))

    if merge:
        user_movies = {movie.movie_id: movie for movie in user.user_movies}
        for temp_movie in temp_user.user_movies:
            user_movie = user_movies.get(temp_movie.movie_id)
            if not user_movie:
                _logger.info("Adding movie %s", temp_movie.movie.original_title)
                temp_movie.user_id = user.id
                db.session.add(temp_movie)
            elif temp_movie.updated_at > user_movie.updated_at:
                _logger.info("Replacing movie %s", user_movie.movie.original_title)
                db.session.delete(temp_movie)
                temp_movie.user_id = user.id
            else:
                _logger.info(
                    "Deleting movie %s because there is a newer decision: %s",
                    temp_movie.movie.original_title,
                    user_movie.decision,
                )
                db.session.delete(temp_movie)
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
    pre_login_user = get_current_user()

    if request.method == "GET":
        return render_template("login.html")

    data = request.form
    try:
        user = authenticate_user(data)
        if not pre_login_user.user_movies:
            db.session.delete(pre_login_user)
        else:
            user.temporary_user_id = pre_login_user.id
            db.session.add(user)
            db.session.commit()

        (
            g.new_access_token,
            g.new_refresh_token,
        ) = generate_new_tokens(user.id)
        g.current_user = user
        return make_response(redirect(url_for("html.profile")))
    except UserFeedbackError as e:
        _logger.exception("Error authenticating user.")
        flash(str(e), "danger")
        return redirect(url_for("html.login"))
    except Exception:
        _logger.exception("Error authenticating user.")
        flash("Error logging in.", "danger")
        return redirect(url_for("html.login"))


@html.route("/logout", methods=["POST"])
def logout():
    flash("Logged out successfully.", "success")
    response = make_response(redirect(url_for("html.home")))
    g.clear_auth_cookies = True
    return response


@html.route("/delete_data", methods=["POST"])
def delete_data():
    """
    Similar as logout(), but with a different message, and it will delete the
    temporary user.
    :return:
    """
    user = get_current_user()
    if user:
        db.session.delete(user)
        db.session.commit()
    flash("All your data is gone with the wind.", "success")
    response = make_response(redirect(url_for("html.profile")))
    unset_jwt_cookies(response)
    return response


def _validate_profile_input(
    data, has_new_mail, has_new_pw, has_old_email, has_old_pw
) -> bool:
    if (not has_old_email or not has_old_pw) and (has_new_pw or has_new_mail):
        raise UserFeedbackError(
            "Registration is only possible on the registration page."
        )

    if has_new_mail and not _validate_email(data.get("email")):
        flash("Invalid email.", "danger")
        return False

    if has_new_pw and not _validate_password(data.get("new_password")):
        flash("Password must be at least 8 characters.", "danger")
        return False
    return True


def _update_user_credentials(
    user, data, form_data, has_new_mail, has_new_pw, has_old_email, has_old_pw
) -> None:
    def confirm_current_pw() -> None:
        current_pw = data.get("current_password")
        if not current_pw:
            raise UserFeedbackError("Current password is required.")
        pw_is_valid = bcrypt.check_password_hash(user.password, current_pw)
        if not pw_is_valid:
            raise UserFeedbackError("Invalid current password.")

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


def profile_post(user: User, form_data: dict[str, str]) -> None:
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
    if not _validate_profile_input(
        data, has_new_mail, has_new_pw, has_old_email, has_old_pw
    ):
        return

    _update_user_credentials(
        user, data, form_data, has_new_mail, has_new_pw, has_old_email, has_old_pw
    )

    user.name = data.get("name")
    user.language = data.get("language")
    user.region = data.get("region")

    db.session.add(user)
    db.session.commit()
    flash("Profile saved successfully.", "success")


def _create_select_options(objects):
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


@html.route("/profile", methods=["GET", "POST"])
def profile():
    user = get_current_user()

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("html.home"))

    if len(user.calendars) == 0:
        user.reset_calendar_hashes()
        db.session.add(user)
        db.session.commit()

    form_data = defaultdict(str)
    form_data["name"] = user.name or ""
    form_data["language"] = user.language or ""
    form_data["region"] = user.region or ""
    form_data["email"] = user.email or ""

    if request.method == "POST":
        try:
            profile_post(user, form_data)
        except UserFeedbackError as e:
            flash(str(e), "danger")
        except Exception:
            _logger.exception("Error updating profile.")
            flash("Error updating profile.", "danger")

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
        regions=_create_select_options(regions),
        languages=_create_select_options(languages),
    )


def profile_notifications_post(user) -> bool:
    """A POST request to the notification page (form submit)
    only handles the email notifications.
    An API endpoint handles push notifications."""
    data = dict(request.form)
    _logger.info("data: %s", data)
    if not re.match(r"^\s*\d+(s*,\s*\d+)*\s*$", data.get("email_days")):
        raise UserFeedbackError(
            "Please enter a comma-separated list of numbers in the 'days' field."
        )

    email_channels = NotificationChannel.query.filter_by(user_id=user.id, mode="email")
    if email_channels.count() > 0:
        email_channel = email_channels[0]
    else:
        email_channel = NotificationChannel(
            user_id=user.id, mode="email", enabled=False
        )

    _logger.info(str(data))

    days = re.split(r"\s*,\s*", data.get("email_days").strip())

    email_channel.enabled = bool(data.get("email_enabled", False))
    email_channel.days_in_advance = list(map(int, days))
    email_channel.include_maybe_movies = bool(data.get("email_with_maybe", False))
    db.session.add(email_channel)
    db.session.commit()

    return True


@html.route("/profile/notifications", methods=["GET", "POST"])
def profile_notifications():
    user = get_current_user()

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("html.profile"))

    template_data = None
    if request.method == "POST":
        try:
            success = profile_notifications_post(user)
        except UserFeedbackError as e:
            flash(str(e), "danger")
            success = False
        except Exception:
            _logger.exception("Unexpected error while updating profile.")
            success = False

        if not success:
            data = request.form
            template_data = {
                "email_enabled": data.get("email_enabled"),
                "email_days": data.get("email_days"),
                "email_with_maybe": data.get("email_with_maybe"),
            }
        else:
            flash("Settings saved successfully.", "success")

    if not template_data:
        email_channels = NotificationChannel.query.filter_by(
            user_id=user.id, mode="email"
        )
        if email_channels.count() > 0:
            email_channel = email_channels[0]
        else:
            email_channel = NotificationChannel(
                user_id=user.id, mode="email", enabled=False
            )

        days = sorted(email_channel.days_in_advance or [])
        template_data = {
            "email_enabled": email_channel.enabled,
            "email_days": ", ".join(map(str, days)),
            "email_with_maybe": email_channel.include_maybe_movies,
        }

    return render_template(
        "profile_notifications.html",
        user=user,
        email_enabled=template_data["email_enabled"],
        email_days=template_data["email_days"],
        email_with_maybe=template_data["email_with_maybe"],
    )


@html.route("/confirm-email/<token>", methods=["GET"])
def confirm_email(token):
    try:
        confirm_user_email(token)
        flash("Email confirmed successfully.", "success")
    except UserFeedbackError as e:
        _logger.exception("Error confirming email.")
        flash(str(e), "danger")
    except Exception:
        _logger.exception("Error confirming email.")
        flash("Error confirming email.", "danger")

    return redirect(url_for("html.profile"))


@html.route("/request-confirmation-mail", methods=["POST"])
def request_confirmation_email():
    user = get_current_user()
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
    except UserFeedbackError as e:
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))
    except Exception:
        _logger.exception("Error sending confirmation email.")
        flash("Error sending confirmation email.", "danger")
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
        except UserFeedbackError as e:
            flash(str(e), "danger")
            return redirect(url_for("html.reset_password_request"))
        except Exception:
            _logger.exception("Error sending reset email.")
            flash("Error sending reset email.", "danger")
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
        except UserFeedbackError as e:
            flash(str(e), "danger")
            return redirect(url_for("html.reset_password", token=token))
        except Exception:
            _logger.exception("Error resetting password.")
            flash("Error resetting password.", "danger")
            return redirect(url_for("html.reset_password", token=token))
    return render_template("reset_password.html", token=token)


@html.route("/movies", methods=["GET"])
def get_all_movies():
    return get_movies("all")


@html.route("/movies/<filter_mode>", methods=["GET"])
def get_movies(filter_mode):
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

    return render_template("movie_list.html", filter_mode=filter_mode)


@html.route("/movie/<int:movie_id>", methods=["GET"])
def get_movie_details(movie_id):
    try:
        user = get_current_user()
        language = user.language or current_app.config.DEFAULT_LANGUAGE
        movie = Movie.query.get(movie_id)
        lang_info = movie.get_localized_data(language)
        region_info = MovieRegionInfo.query.filter_by(
            movie_id=movie_id, region=user.region
        ).first()

        # Get all region infos for the movie to display different release dates
        all_region_infos = MovieRegionInfo.query.filter_by(movie_id=movie_id).all()
        region_release_dates = {}
        region_names = {reg.code: reg.english_name for reg in TmdbRegion.query.all()}
        for ri in all_region_infos:
            ri: MovieRegionInfo
            if ri.is_fake:
                continue
            region_display = region_names.get(ri.region, ri.region)
            region_release_dates[region_display] = format_date(
                ri.release_date, locale=language
            )

        # Get original language name
        original_language_obj = TmdbLanguage.query.filter_by(
            code=movie.original_language
        ).first()
        original_language_name = (
            original_language_obj.english_name
            if original_language_obj
            else movie.original_language
        )

        # Parse origin countries
        if movie.origin_country:
            country_codes = movie.origin_country.split(",")
            countries = TmdbRegion.query.filter(TmdbRegion.code.in_(country_codes))
            country_names = {
                country.code: country.english_name for country in countries
            }
            origin_countries = [country_names.get(code, code) for code in country_codes]

        # Get current user's decision for this movie (if any)
        user_movie = UserMovie.query.filter_by(
            user_id=user.id, movie_id=movie_id
        ).first()
        user_decision = user_movie.decision if user_movie else None

        movie_data = {
            "id": movie.id,
            "title": lang_info["title"],
            "overview": lang_info["overview"],
            "poster_url": get_image_url(lang_info["poster_path"], 500),
            "release_date": (
                format_date(region_info.release_date, locale=language)
                if region_info and region_info.release_date
                else None
            ),
            "imdb_id": movie.imdb_id,
            "tagline": lang_info["tagline"],
            "runtime": lang_info["runtime"],
            "original_language": original_language_name,
            "origin_countries": origin_countries,
            "region_release_dates": region_release_dates,
            "decision": user_decision,
        }
        if not movie:
            flash("Movie not found.", "danger")
            return redirect(url_for("html.profile"))
        return render_template("movie_details.html", movie=movie_data)
    except UserFeedbackError as e:
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))
    except Exception:
        _logger.exception("Error fetching movie details.")
        flash("Error fetching movie details.", "danger")
        return redirect(url_for("html.profile"))


@html.route("/release-dates", methods=["GET"])
def get_user_release_dates():
    user = get_current_user()
    try:
        # four weeks ago
        start = datetime.now(UTC) - timedelta(weeks=4)
        releases = fetch_user_events(user, start)
        return render_template("release_dates.html", releases=releases)
    except UserFeedbackError as e:
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))
    except Exception:
        _logger.exception("Error fetching release dates.")
        flash("Error fetching release dates.", "danger")
        return redirect(url_for("html.profile"))


@html.route("/calendar", methods=["GET"])
def get_user_calendar():
    user = get_current_user()
    if not user:
        flash("There was an error with your session. Please try again.", "danger")
        return redirect(url_for("html.profile"))

    try:
        releases = fetch_user_events(user)
        return render_template("calendar.html", releases=releases)
    except UserFeedbackError as e:
        flash(str(e), "danger")
        return redirect(url_for("html.profile"))
    except Exception:
        _logger.exception("Error fetching calendar.")
        flash("Error fetching calendar.", "danger")
        return redirect(url_for("html.profile"))


@html.route("/calendar/ics/<calendar_hash>", methods=["GET"])
def get_ics_calendar(calendar_hash):
    """
    Generate an ICS calendar file for a user based on the calendar hash.

    Args:
        calendar_hash: The hash identifying the user and calendar type

    Returns:
        ICS calendar file as a response
    """

    # First try to find the calendar in the new UserCalendar model
    calendar = UserCalendar.query.filter_by(calendar_hash=calendar_hash).first()

    if not calendar:
        return "Calendar not found", 404

    calendar_type = calendar.calendar_type

    try:
        # Set calendar name and decisions based on calendar type
        calendar_name = "Movie Calendar"

        decisions = []
        if calendar_type == "wanted":
            calendar_name = "Wanted Movies"
            decisions = ["approve"]
        elif calendar_type == "maybe":
            calendar_name = "Maybe Movies"
            decisions = ["maybe"]
        elif calendar_type == "all":
            calendar_name = "All Movies"
            decisions = ["approve", "maybe"]

        # Fetch events for the requested calendar type
        events = fetch_user_events(calendar.user)

        # Filter events based on the calendar type
        if calendar_type != "all":
            events = [event for event in events if event["decision"] in decisions]

        # Generate the ICS file
        ics_data = create_ics_file(events, calendar_name)

        # Create the response
        response = make_response(ics_data)
        response.headers["Content-Type"] = "text/calendar"
        response.headers["Content-Disposition"] = (
            f"attachment; filename={calendar_type}_movies.ics"
        )

    except Exception:
        _logger.exception("Error generating ICS calendar")
        return "Error generating calendar", 500
    else:
        return response


@html.route("/poster/<int:width>/<filename>")
def get_poster(width, filename):
    def get_mime_type(f_name: str) -> str:
        if f_name.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        if f_name.endswith(".png"):
            return "image/png"
        if f_name.endswith(".gif"):
            return "image/gif"
        if f_name.endswith(".webp"):
            return "image/webp"
        raise ValueError(f"Unsupported file type: {f_name}")

    valid_widths = {500}
    if width not in valid_widths:
        return "Invalid width", 400

    ensure_image_exists(filename, int(width))

    response = make_response("", 200)
    response.headers["X-Accel-Redirect"] = f"/internal-static/w{width}/{filename}"
    response.headers["Content-Type"] = get_mime_type(filename)
    return response


@html.route("/why", methods=["GET"])
def why():
    return render_template("why.html")


@html.route("/how", methods=["GET"])
def how():
    return render_template("how.html")


@html.route("/who", methods=["GET"])
def who():
    return render_template("who.html")


@html.route("/imprint", methods=["GET"])
def imprint():
    return render_template("imprint.html")


@html.route("/privacy", methods=["GET"])
def privacy():
    return render_template("privacy.html")


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
