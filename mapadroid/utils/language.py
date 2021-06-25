import json
import os

from aiofile import async_open


async def open_json_file(jsonfile):
    try:
        async with async_open('locale/' + os.environ['LANGUAGE'] + '/' + jsonfile + '.json', encoding='utf8', mode="r") as f:
            derp = await f.read()
            file_open = json.loads(derp)
    except (OSError, json.decoder.JSONDecodeError):
        async with async_open('locale/en/' + jsonfile + '.json', mode="r") as f:
            file_open = json.load(await f.read())

    return file_open


async def i8ln(word):
    # TODO: Async...
    lang_file = 'locale/' + os.environ['LANGUAGE'] + '/mad.json'
    if os.path.isfile(lang_file):
        async with async_open(lang_file, "r", encoding='utf8') as f:
            language_file = json.loads(await f.read())
        if word in language_file:
            return language_file[word]

    return word


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
