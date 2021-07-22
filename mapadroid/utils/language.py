import json
import os
from typing import Dict

from aiocache import cached
from aiofile import async_open
from cachetools.func import ttl_cache


@cached(ttl=30 * 60)
async def open_json_file(jsonfile):
    try:
        async with async_open('locale/' + os.environ['LANGUAGE'] + '/' + jsonfile + '.json', encoding='utf8',
                              mode="r") as f:
            file_open = json.loads(await f.read())
    except (OSError, json.decoder.JSONDecodeError):
        async with async_open('locale/en/' + jsonfile + '.json', mode="r") as f:
            file_open = json.loads(await f.read())

    return file_open


@ttl_cache(ttl=30 * 60)
def open_json_file_sync(jsonfile):
    try:
        with open('locale/' + os.environ['LANGUAGE'] + '/' + jsonfile + '.json', encoding='utf8',
                  mode="r") as f:
            file_open = json.loads(f.read())
    except (OSError, json.decoder.JSONDecodeError):
        with open('locale/en/' + jsonfile + '.json', mode="r") as f:
            file_open = json.loads(f.read())

    return file_open


async def i8ln(word):
    translations = await _get_translations()
    return translations.get(word, word)


def i8ln_sync(word):
    translations = _get_translations_sync()
    return translations.get(word, word)


@cached(ttl=30 * 60)
async def _get_translations() -> Dict:
    lang_file = 'locale/' + os.environ['LANGUAGE'] + '/mad.json'
    translations: Dict = {}
    if os.path.isfile(lang_file):
        async with async_open(lang_file, "r", encoding='utf8') as f:
            translations = json.loads(await f.read())
    return translations


@ttl_cache(ttl=30 * 60)
def _get_translations_sync() -> Dict:
    lang_file = 'locale/' + os.environ['LANGUAGE'] + '/mad.json'
    translations: Dict = {}
    if os.path.isfile(lang_file):
        with open(lang_file, "r", encoding='utf8') as f:
            translations = json.loads(f.read())
    return translations


def get_mon_name_sync(mon_id: int):
    mons_file = open_json_file_sync('pokemon')
    str_id = str(mon_id)
    if str_id in mons_file:
        if os.environ['LANGUAGE'] != "en":
            return i8ln_sync(mons_file[str_id]["name"])
        else:
            return mons_file[str_id]["name"]
    else:
        return "No-name-in-pokemon-json"


async def get_mon_name(mon_id: int):
    mons_file = await open_json_file('pokemon')
    str_id = str(mon_id)
    if str_id in mons_file:
        if os.environ['LANGUAGE'] != "en":
            return await i8ln(mons_file[str_id]["name"])
        else:
            return mons_file[str_id]["name"]
    else:
        return "No-name-in-pokemon-json"


async def get_mon_ids():
    mons_file = await open_json_file('pokemon')
    return list(mons_file.keys())
