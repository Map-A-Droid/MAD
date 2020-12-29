import enum
from typing import Tuple


class SearchType(enum.Enum):
    eq = 0
    like = 1


def get_search(search_key) -> Tuple[str, SearchType]:
    """ Determines the searching parameters for the search field. Returns SearchType.eq if not present or invalid """
    try:
        search_key, search_type = search_key.split(".", 1)
        if not hasattr(SearchType, search_type):
            raise ValueError
        search_type = getattr(SearchType, search_type)
    except ValueError:
        search_type = SearchType.eq
    return search_key, search_type
