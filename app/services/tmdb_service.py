import logging

from natsort import natsorted

from app.extensions import db
from app.models import TmdbLanguage, TmdbRegion, User
from app.utils.tmdb import fetch_languages, fetch_regions
import natsort

_logger = logging.getLogger(__name__)


def fetch_new_languages():
    api_languages = {
        language["iso_639_1"]: language for language in fetch_languages()
    }
    db_languages = {
        language.code: language for language in TmdbLanguage.query.all()
    }

    languages_to_delete = [
        code for code in db_languages if code not in api_languages
    ]
    if languages_to_delete:
        db.session.delete(languages_to_delete)

    new_languages = [
        TmdbLanguage.create_from_tmdb(api_languages[code])
        for code in api_languages
        if code not in db_languages
    ]
    db.session.bulk_save_objects(new_languages)

    for language in api_languages.values():
        if language["iso_639_1"] in db_languages:
            existing_language = db_languages[language["iso_639_1"]]
            if existing_language.update_from_tmdb(language):
                db.session.add(existing_language)

    db.session.commit()


def _sort_objects(objects, user_counts):
    for obj in objects:
        if obj.code not in user_counts:
            user_counts[obj.code] = 0

    # calculate the average and median of the user counts

    sorted_counts = sorted(user_counts.values())
    average = sum(sorted_counts) / len(sorted_counts)
    median = sorted_counts[len(sorted_counts) // 2]

    # select all objects that have more users than both the average and the median
    popular_choices = [
        lang
        for lang in objects
        if user_counts[lang.code] > average and user_counts[lang.code] > median
    ]

    # the biggest 5 of those will be showed first (alphabetically),
    # then the rest, also alphabetically
    popular_choices.sort(key=lambda o: user_counts[o.code], reverse=True)
    top_objects = popular_choices[:5]
    top_objects = natsorted(
        top_objects, alg=natsort.ns.LOCALE, key=lambda o: o.get_name()
    )
    objects = natsorted(objects, alg=natsort.ns.LOCALE, key=lambda o: o.get_name())

    # step = 10 to allow for re-ordering some objects later, e.g. browser language
    c = 10

    for obj in top_objects:
        obj.sort_order = c
        db.session.add(obj)
        c += 10

    c += 1000  # useful to detect the difference between top and other choices
    for obj in objects:
        if obj in top_objects:
            continue
        obj.sort_order = c
        db.session.add(obj)
        c += 10


def calculate_language_sort_orders():
    languages = TmdbLanguage.query.all()
    user_counts = (
        db.session.query(User.language, db.func.count(User.id))
        .group_by(User.language)
        .all()
    )
    lang_counts = {lang: count for lang, count in user_counts}
    _sort_objects(languages, lang_counts)


def update_languages():
    fetch_new_languages()
    calculate_language_sort_orders()
    db.session.commit()


def calculate_region_sort_orders():
    regions = TmdbRegion.query.all()
    user_counts = (
        db.session.query(User.region, db.func.count(User.id))
        .group_by(User.region)
        .all()
    )
    region_counts = {reg: count for reg, count in user_counts}
    _sort_objects(regions, region_counts)


def fetch_new_regions():
    api_regions = {region["iso_3166_1"]: region for region in fetch_regions()}
    db_regions = {region.code: region for region in TmdbRegion.query.all()}

    regions_to_delete = [code for code in db_regions if code not in api_regions]
    if regions_to_delete:
        db.session.delete(regions_to_delete)

    new_regions = [
        TmdbRegion(
            code=api_regions[code]["iso_3166_1"],
            english_name=api_regions[code]["english_name"],
            native_name=api_regions[code]["native_name"],
        )
        for code in api_regions
        if code not in db_regions
    ]
    db.session.bulk_save_objects(new_regions)

    for region in api_regions.values():
        if region["iso_3166_1"] in db_regions:
            existing_region = db_regions[region["iso_3166_1"]]
            if existing_region.update_from_tmdb(region):
                db.session.add(existing_region)


def update_regions():
    fetch_new_regions()
    calculate_region_sort_orders()

    db.session.commit()
