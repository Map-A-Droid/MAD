import json
import os


def open_json_file(jsonfile):
    try:
        with open('locale/' + os.environ['LANGUAGE'] + '/' + jsonfile + '.json', encoding='utf8') as f:
            file_open = json.load(f)
    except (OSError, json.jsonDecodeError):
        with open('locale/en/' + jsonfile + '.json') as f:
            file_open = json.load(f)

    return file_open


def i8ln(word):
    lang_file = 'locale/' + os.environ['LANGUAGE'] + '/mad.json'
    if os.path.isfile(lang_file):
        with open(lang_file, encoding='utf8') as f:
            language_file = json.load(f)
        if word in language_file:
            return language_file[word]

    return word


def get_mon_name(mon_id):
    mons_file = open_json_file('pokemon')
    str_id = str(mon_id)
    if str_id in mons_file:
        if os.environ['LANGUAGE'] != "en":
            return i8ln(mons_file[str_id]["name"])
        else:
            return mons_file[str_id]["name"]
    else:
        return "No-name-in-pokemon-json"
