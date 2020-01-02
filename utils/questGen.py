import gettext
import json
import re

from utils.language import i8ln, open_json_file

gettext.find('quest', 'locales', all=True)
lang = gettext.translation('quest', localedir='locale', fallback=True)
lang.install()


def generate_quest(quest):
    gettext.find('quest', 'locales', all=True)
    lang = gettext.translation('quest', localedir='locale', fallback=True)
    lang.install()

    quest_reward_type = questreward(quest['quest_reward_type'])
    quest_type = questtype(quest['quest_type'])
    if '{0}' in quest_type:
        quest_type = quest_type.replace('{0}', str(quest['quest_target']))

    item_id = 0
    item_amount = 1
    pokemon_id = '000'
    pokemon_name = ''
    item_type = ''
    pokemon_form = extractForm(quest["quest_reward"])

    if quest_reward_type == _('Item'):
        item_amount = quest['quest_item_amount']
        item_type = rewarditem(quest['quest_item_id'])
        item_id = quest['quest_item_id']
    elif quest_reward_type == _('Stardust'):
        item_amount = quest['quest_stardust']
        item_type = _('Stardust')
    elif quest_reward_type == _('Pokemon'):
        item_type = 'Pokemon'
        pokemon_name = i8ln(pokemonname(str(quest['quest_pokemon_id'])))
        pokemon_id = quest['quest_pokemon_id']

    if not quest['task']:
        quest_task = questtask(
            quest['quest_type'], quest['quest_condition'], quest['quest_target'])
    else:
        quest_task = quest['task']

    quest_raw = ({
        'pokestop_id': quest['pokestop_id'],
        'name': quest['name'],
        'url': quest['image'],
        'latitude': quest['latitude'],
        'longitude': quest['longitude'],
        'timestamp': quest['quest_timestamp'],
        'item_id': item_id,
        'item_amount': item_amount,
        'item_type': item_type,
        'pokemon_id': pokemon_id,
        'pokemon_name': pokemon_name,
        'pokemon_form': pokemon_form,
        'quest_type': quest_type,
        'quest_type_raw': quest['quest_type'],
        'quest_reward_type': quest_reward_type,
        'quest_reward_type_raw': quest['quest_reward_type'],
        'quest_task': quest_task,
        'quest_target': quest['quest_target'],
        'quest_condition': quest['quest_condition'],
        'quest_template': quest['quest_template']
    })
    return quest_raw


def extractForm(quest_reward_json):
    quest_reward = json.loads(quest_reward_json)

    if len(quest_reward) == 0:
        return 0

    if "pokemon_encounter" in quest_reward[0]:
        encounter = quest_reward[0]["pokemon_encounter"]
        return encounter["pokemon_display"]["form_value"]


def questreward(quest_reward_type):
    type = {
        2: _("Item"),
        3: _("Stardust"),
        7: _("Pokemon")
    }
    return type.get(quest_reward_type, "nothing")


def questtype(quest_type):
    file = open_json_file('types')
    return (file[str(quest_type)]['text'])


def rewarditem(itemid):
    file = open_json_file('items')
    return (file[str(itemid)]['name'])


def pokemonname(id):
    file = open_json_file('pokemon')
    return file[str(int(id))]["name"]


def questtask(typeid, condition, target):
    gettext.find('quest', 'locales', all=True)
    lang = gettext.translation('quest', localedir='locale', fallback=True)
    lang.install()

    pokemonTypes = open_json_file('pokemonTypes')
    items = open_json_file('items')
    throwTypes = {"10": _("Nice"), "11": _("Great"),
                  "12": _("Excellent"), "13": _("Curveball")}
    arr = {}
    arr['0'] = target
    text = questtype(typeid)

    if typeid == 4:
        arr['wb'] = ""
        arr['type'] = ""
        arr['poke'] = ""
        arr['different'] = ""

        text = _("Catch {0}{different} {type}Pokemon{wb}")
        match_object = re.search(r'"pokemon_type": \[([0-9, ]+)\]', condition)
        if match_object is not None:
            pt = match_object.group(1).split(', ')
            last = len(pt)
            cur = 1
            if last == 1:
                arr['type'] = pokemonTypes[pt[0]].title() + _('-type ')
            else:
                for ty in pt:
                    arr['type'] += (_('or ') if last == cur else '') + \
                        pokemonTypes[ty].title() + (_('-type ')
                                                    if last == cur else '-, ')
                    cur += 1
        if re.search(r'"type": 3', condition) is not None:
            arr['wb'] = _(" with weather boost")
        elif re.search(r'"type": 21', condition) is not None:
            arr['different'] = _(" different species of")
        match_object = re.search(r'"pokemon_ids": \[([0-9, ]+)\]', condition)
        if match_object is not None:
            pt = match_object.group(1).split(', ')
            last = len(pt)
            cur = 1
            if last == 1:
                arr['poke'] = i8ln(pokemonname(pt[0]))
            else:
                for ty in pt:
                    arr['poke'] += (_('or ') if last == cur else '') + \
                        i8ln(pokemonname(ty)) + ('' if last == cur else ', ')
                    cur += 1
            text = _('Catch {0} {poke}')
    elif typeid == 5:
        text = _("Spin {0} Pokestops or Gyms")
        if re.search(r'"type": 12', condition) is not None:
            text = _("Spin {0} Pokestops you haven't visited before")
    elif typeid == 6:
        text = _("Hatch {0} Eggs")
    elif typeid == 7:
        if re.search(r'"type": 9', condition) is not None:
            text = _("Win {0} Gym Battles")
        elif re.search(r'"type": 10', condition) is not None:
            text = _("Use a supereffective Charged Attack in {0} Gym battles")
        else:
            text = _("Battle in a Gym {0} times")
    elif typeid == 8:
        if re.search(r'"type": 6', condition) is not None:
            text = _("Win {0} Raids")
            if re.search(r'"raid_level": \[3, 4, 5\]', condition) is not None:
                text = _('Win a level 3 or higher raid')
            if re.search(r'"raid_level": \[2, 3, 4, 5\]', condition) is not None:
                text = _('Win a level 2 or higher raid')
        else:
            text = _("Battle in {0} Raids")
    elif typeid == 10:
        text = _("Transfer {0} Pokemon")
    elif typeid == 11:
        text = _("Favourite {0} Pokemon")
    elif typeid == 13:
        text = _('Use {0} {type}Berries to help catch Pokemon')
        arr['type'] = ""
        match_object = re.search(r'"item": ([0-9]+)', condition)
        if match_object is not None:
            arr['type'] = items[match_object.group(
                1)]['name'].replace(_(' Berry'), '')+" "
    elif typeid == 14:
        text = _('Power up Pokemon {0} times')
    elif typeid == 15:
        text = _("Evolve {0} Pokemon")
        if re.search(r'"type": 11', condition) is not None:
            text = _("Use an item to evolve a Pokemon")
        elif re.search(r'"type": 1', condition) is not None:
            text = _("Evolve {0} {type}Pokemon")
            arr['wb'] = ""
            arr['type'] = ""
            arr['poke'] = ""
            match_object = re.search(
                r'"pokemon_type": \[([0-9, ]+)\]', condition)
            if match_object is not None:
                pt = match_object.group(1).split(', ')
                last = len(pt)
                cur = 1
                if last == 1:
                    arr['type'] = pokemonTypes[pt[0]].title() + _('-type ')
                else:
                    for ty in pt:
                        arr['type'] += (_('or ') if last == cur else '') + pokemonTypes[ty].title() + (
                            _('-type ') if last == cur else '-, ')
                        cur += 1
        elif re.search(r'"type": 2', condition) is not None:
            arr['wb'] = ""
            arr['type'] = ""
            arr['poke'] = ""

            match_object = re.search(
                r'"pokemon_ids": \[([0-9, ]+)\]', condition)
            if match_object is not None:
                pt = match_object.group(1).split(', ')
                last = len(pt)
                cur = 1
                if last == 1:
                    arr['poke'] = i8ln(pokemonname(pt[0]))
                else:
                    for ty in pt:
                        arr['poke'] += (_('or ') if last == cur else '') + i8ln(pokemonname(ty)) + (
                            '' if last == cur else ', ')
                        cur += 1
                text = _('Evolve {0} {poke}')
    elif typeid == 16:
        arr['inrow'] = ""
        arr['curve'] = ""
        arr['type'] = ""
        if re.search(r'"type": 14', condition) is not None:
            arr['inrow'] = _(" in a row")
        if re.search(r'"type": 15', condition) is not None:
            arr['curve'] = _("Curveball ")
        match_object = re.search(r'"throw_type": ([0-9]{2})', condition)
        if match_object is not None:
            arr['type'] = throwTypes[match_object.group(1)]+" "
        text = _("Make {0} {type}{curve}Throws{inrow}")
    elif typeid == 17:
        text = _('Earn {0} Candies walking with your buddy')
    elif typeid == 22:
        if int(target) == int(1):
            text = _('Make a new friend')
        else:
            text = _('Make {0} new friends')
    elif typeid == 23:
        text = _('Trade {0} Pokemon')
        arr['distance'] = ""
        if re.search(r'"type": 25', condition) is not None:
            arr['distance'] = re.search(r'"distance_km": ([0-9, ]+)', condition).group(1)
            if int(target) == int(1):
                text = _('Trade Pokemon caught {distance} km apart')
            else:
                text = _('Trade {0} Pokemon caught {distance} km apart')
    elif typeid == 24:
        text = _('Send {0} gifts to friends')
    elif typeid == 27:
        # PVP against trainer or team leader.
        if re.search(r'"type": 22', condition) is not None:
            text = _('Battle a Team Leader {0} times')
        elif re.search(r'"type": 23', condition) is not None:
            text = _('Battle another Trainer {0} times')
    elif typeid == 28:
        # Take snapshots quest
        if re.search(r'"type": 2', condition) is not None:
            arr['poke'] = ""

            match_object = re.search(
                r'"pokemon_ids": \[([0-9, ]+)\]', condition)
            if match_object is not None:
                pt = match_object.group(1).split(', ')
                last = len(pt)
                cur = 1
                if last == 1:
                    arr['poke'] = i8ln(pokemonname(pt[0]))
                else:
                    for ty in pt:
                        arr['poke'] += (_('or ') if last == cur else '') + i8ln(pokemonname(ty)) + (
                            '' if last == cur else ', ')
                        cur += 1
                text = _("Take {0} snapshots of {poke}")
        elif re.search(r'"type": 1', condition) is not None:
            text = _("Take {0} snapshots of {type} Pokemon")
            arr['wb'] = ""
            arr['type'] = ""
            arr['poke'] = ""
            match_object = re.search(
                r'"pokemon_type": \[([0-9, ]+)\]', condition)
            if match_object is not None:
                pt = match_object.group(1).split(', ')
                last = len(pt)
                cur = 1
                if last == 1:
                    arr['type'] = pokemonTypes[pt[0]].title() + _('-type ')
                else:
                    for ty in pt:
                        arr['type'] += (_('or ') if last == cur else '') + pokemonTypes[ty].title() + (
                            _('-type ') if last == cur else '-, ')
                        cur += 1
    elif typeid == 29:
        # QUEST_BATTLE_TEAM_ROCKET Team Go rucket grunt batles.
        # Condition type 27 means against a grunt leader WITH_INVASION_CHARACTER
        if re.search(r'"type": 27', condition) is not None:
            text = _('Battle {0} times against the Team GO Rocket Leaders')

        # Condition type 18 means win a battle
        if re.search(r'"type": 18', condition) is not None:
            text = text.replace(_('Battle'), _('Win'))

    if int(target) == int(1):
        text = text.replace(_(' Eggs'), _('n Egg'))
        text = text.replace(_(' Raids'), _(' Raid'))
        text = text.replace(_(' Battles'), _(' Battle'))
        text = text.replace(_(' candies'), _(' candy'))
        text = text.replace(_(' gifts'), _(' gift'))
        text = text.replace(_(' Pokestops'), _(' Pokestop'))
        text = text.replace(_(' {0} snapshots'), _(' a snapshot'))
        text = text.replace(_('Make {0} {type}{curve}Throws'), _('Make a {type}{curve}Throw'))
        text = text.replace(_(' {0} times'), '')
        arr['0'] = _("a")

    for key, val in arr.items():
        text = text.replace('{'+key+'}', str(val))

    text = text.replace('  ', ' ').strip()
    return text
