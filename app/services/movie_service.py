from typing import List, Dict

from app.models import MovieRegionInfo, MovieLanguageInfo


def get_region_infos(
    movie_ids: List[int], region: str
) -> Dict[int, MovieRegionInfo]:
    return {
        info.movie_id: info
        for info in MovieRegionInfo.query.filter(
            MovieRegionInfo.movie_id.in_(movie_ids),
            MovieRegionInfo.region == region,
        ).all()
    }


def get_lang_infos(
    movie_ids: List[int], language: str
) -> Dict[int, MovieLanguageInfo]:
    return {
        info.movie_id: info
        for info in MovieLanguageInfo.query.filter(
            MovieLanguageInfo.movie_id.in_(movie_ids),
            MovieLanguageInfo.language == language,
        ).all()
    }
