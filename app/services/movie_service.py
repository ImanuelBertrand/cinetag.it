from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo


def get_region_infos(movie_ids: list[int], region: str) -> dict[int, MovieRegionInfo]:
    return {
        info.movie_id: info
        for info in MovieRegionInfo.query.filter(
            MovieRegionInfo.movie_id.in_(movie_ids),
            MovieRegionInfo.region == region,
        ).all()
    }


def get_lang_infos(movie_ids: list[int], language: str) -> dict[int, MovieLanguageInfo]:
    return {
        info.movie_id: info
        for info in MovieLanguageInfo.query.filter(
            MovieLanguageInfo.movie_id.in_(movie_ids),
            MovieLanguageInfo.language == language,
        ).all()
    }
