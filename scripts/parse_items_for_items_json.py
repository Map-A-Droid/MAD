#!/usr/bin/env python3

import requests
import json

PROTO_URL = "https://raw.githubusercontent.com/Furtif/POGOProtos/master/src/POGOProtos/Inventory/Item/ItemId.proto"

LANGS = {
       "en": "https://raw.githubusercontent.com/PokeMiners/pogo_assets/master/Texts/Latest%20APK/i18n_english.json",
       "de": "https://raw.githubusercontent.com/PokeMiners/pogo_assets/master/Texts/Latest%20APK/i18n_german.json",
       "fr": "https://raw.githubusercontent.com/PokeMiners/pogo_assets/master/Texts/Latest%20APK/i18n_french.json"
}

ITEMS_DICT = {}

# Get all items + numbers
PROTO_TEXT = requests.get(PROTO_URL).text
for line in PROTO_TEXT.split("\n"):
    line = line.strip()
    if not line.startswith("ITEM_"):
        continue
    #split power!
    entry = line.split("=");
    ITEMS_DICT[entry[1].strip().replace(";", "")] = { "protoname": entry[0].strip() }

for LANG in LANGS:
    ITEMS_LANG = ITEMS_DICT.copy();
    LANG_DATA = requests.get(LANGS[LANG]).json()["data"]
    # That is not really a json, this is array, convert to proper json
    it = iter(LANG_DATA)
    LANG_DICT = dict(zip(it, it))
    for item_id in ITEMS_LANG:
        item_key = ITEMS_LANG[item_id]["protoname"].lower() + "_name"
        if item_key in LANG_DICT:
           ITEMS_LANG[item_id]["name"] = LANG_DICT[item_key]
        else:
           ITEMS_LANG[item_id]["name"] = ITEMS_LANG[item_id]["protoname"]
    filename = LANG + "_items.json"
    with open(filename, "w") as outfile:
        json.dump(ITEMS_LANG, outfile, indent=2, sort_keys=False, ensure_ascii=False)

    # print everything
    # print(json.dumps(ITEMS_LANG, indent=2, sort_keys=False, ensure_ascii=False))
