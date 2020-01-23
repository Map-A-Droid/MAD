import json
import os


def open_json_file(jsonfile):
    try:
        with open('locale/' + os.environ['LANGUAGE'] + '/' + jsonfile + '.json', encoding='utf8') as f:
            file_open = json.load(f)
    except:
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
